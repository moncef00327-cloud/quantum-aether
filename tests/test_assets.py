"""Asset inventory for monitoring accounts: verified seed domains, discovery of live subdomains, new-asset and
over-limit alerts, and automatic retirement (with a stated reason) of discovered assets that are gone."""
import os
import shutil
import tempfile
import unittest
from contextlib import closing
from unittest import mock

import assets
import monitor
import monitor_db
import monitor_job
import quantum_saas_app
import sales_db
from tests.test_monitor import PLAN_IDS, FakeMailer, FakePayPal, FakeScanner


def found(*hosts, status="not_pq"):
    hs = [{"host": h, "status": status, "group": "x25519", "version": "TLSv1.3"} for h in hosts]
    return {"source": "crt.sh", "names": len(hs) + 3, "responding": len(hs), "pq": 0, "not_pq": len(hs), "unknown": 0, "hosts": hs}


class AssetsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.scanner, self.paypal, self.mailer = FakeScanner(), FakePayPal(), FakeMailer()
        self.discovered = found("acme.org", "api.acme.org", "mail.acme.org")
        self.discover = mock.Mock(side_effect=lambda base, *a, **k: self.discovered)
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://example.test",
             "PAYPAL_CLIENT_ID": "cid", "OWNER_EMAIL": "owner@example.com", **PLAN_IDS},
            scanner=self.scanner, paypal=self.paypal, mailer=self.mailer)
        self.app.extensions["asset_discover"] = self.discover
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db")))

    def trial(self, email="ops@acme.org", domain="acme.org"):
        self.client.post("/monitoring/trial?lang=en", data={"email": email, "domain": domain, "consent": "1"})
        mail = next(m for m in self.mailer.sent if m[0] == email)
        token = mail[2].split("/monitor/")[1].split("?")[0].split()[0]
        with self.conn() as c:
            acc = c.execute("SELECT id FROM monitor_accounts WHERE email = ?", (email,)).fetchone()[0]
        return token, acc

    def domains(self, acc):
        with self.conn() as c:
            return {d["domain"]: d for d in monitor_db.list_domains(c, acc)}

    def alerts(self, acc):
        with self.conn() as c:
            return [(a["kind"], a["domain"]) for a in monitor_db.recent_alerts(c, acc)]

    # ------------------------------------------------------------ seeds and ownership

    def test_seed_verified_by_account_email_domain(self):
        token, acc = self.trial()
        self.client.post(f"/monitor/{token}/seeds", data={"base": "acme.org"})
        with self.conn() as c:
            seed = assets.seeds(c, acc)[0]
        self.assertEqual((seed["base"], seed["verified_by"]), ("acme.org", "email"))

    def test_foreign_seed_needs_dns_txt(self):
        token, acc = self.trial(email="ops@gmail-like.example")
        self.client.post(f"/monitor/{token}/seeds", data={"base": "acme.org"})
        with self.conn() as c:
            seed = assets.seeds(c, acc)[0]
        self.assertIsNone(seed["verified_at"])
        page = self.client.get(f"/monitor/{token}?lang=en").get_data(as_text=True)
        self.assertIn(f"_quantum-aether.acme.org", page)
        self.assertIn(seed["verify_code"], page)
        # discovery refused until verified
        r = self.client.post(f"/monitor/{token}/seeds/{seed['id']}/discover")
        self.assertIn("n=seed_unverified", r.headers["Location"])
        self.discover.assert_not_called()
        with mock.patch.object(assets, "txt_records", return_value=[f"qa-verify={seed['verify_code']}"]):
            r = self.client.post(f"/monitor/{token}/seeds/{seed['id']}/verify")
        self.assertIn("n=seed_verified", r.headers["Location"])
        with self.conn() as c:
            self.assertEqual(assets.seeds(c, acc)[0]["verified_by"], "dns")

    def test_wrong_txt_does_not_verify(self):
        token, acc = self.trial(email="ops@other.example")
        self.client.post(f"/monitor/{token}/seeds", data={"base": "acme.org"})
        with self.conn() as c:
            sid = assets.seeds(c, acc)[0]["id"]
        with mock.patch.object(assets, "txt_records", return_value=["qa-verify=nope"]):
            r = self.client.post(f"/monitor/{token}/seeds/{sid}/verify")
        self.assertIn("n=seed_dns_missing", r.headers["Location"])

    def test_seed_limit_per_plan(self):
        token, acc = self.trial()
        for b in ("acme.org", "a.acme.org", "b.acme.org"):
            self.client.post(f"/monitor/{token}/seeds", data={"base": b})
        with self.conn() as c:
            self.assertEqual(len(assets.seeds(c, acc)), assets.SEED_LIMITS["TRIAL"])

    # ------------------------------------------------------------ discovery and inventory

    def test_discovery_adds_assets_and_alerts_new_ones_once(self):
        token, acc = self.trial()
        self.client.post(f"/monitor/{token}/seeds", data={"base": "acme.org"})
        with self.conn() as c:
            seed = assets.seeds(c, acc)[0]
            out = assets.run_seed(c, acc, seed, self.discover, now_iso="2026-11-14T05:00:00Z")
        self.assertEqual(out["added"], 2)  # acme.org was already monitored
        d = self.domains(acc)
        self.assertEqual(set(d), {"acme.org", "api.acme.org", "mail.acme.org"})
        self.assertEqual(d["api.acme.org"]["source"], "discovered")
        self.assertEqual(d["acme.org"]["source"], "manual")
        self.assertEqual(sorted(a for a in self.alerts(acc) if a[0] == "NEW_ASSET"),
                         [("NEW_ASSET", "api.acme.org"), ("NEW_ASSET", "mail.acme.org")])
        with self.conn() as c:  # same discovery again: nothing new
            out = assets.run_seed(c, acc, assets.seeds(c, acc)[0], self.discover, now_iso="2026-11-21T05:00:00Z")
        self.assertEqual(out["added"], 0)
        self.assertEqual(len([a for a in self.alerts(acc) if a[0] == "NEW_ASSET"]), 2)

    def test_over_limit_alert_instead_of_silent_drop(self):
        token, acc = self.trial()
        self.discovered = found(*[f"h{i}.acme.org" for i in range(15)])
        self.client.post(f"/monitor/{token}/seeds", data={"base": "acme.org"})
        with self.conn() as c:
            out = assets.run_seed(c, acc, assets.seeds(c, acc)[0], self.discover)
        self.assertEqual(len(self.domains(acc)), monitor.TRIAL_DOMAINS)
        self.assertEqual(out["skipped"], 15 - (monitor.TRIAL_DOMAINS - 1))
        over = [a for a in self.alerts(acc) if a[0] == "ASSETS_OVER_LIMIT"]
        self.assertEqual(len(over), 1)

    def test_retire_discovered_asset_gone_with_reason_never_manual(self):
        token, acc = self.trial()
        self.client.post(f"/monitor/{token}/seeds", data={"base": "acme.org"})
        with self.conn() as c:
            assets.run_seed(c, acc, assets.seeds(c, acc)[0], self.discover)
        self.scanner.results["mail.acme.org"] = OSError("refused")
        self.scanner.results["acme.org"] = OSError("refused")  # manual: must never be retired
        for _ in range(assets.RETIRE_AFTER_FAILURES):
            monitor_job.run(self.app)
        self.discovered = found("acme.org", "api.acme.org")  # mail.* no longer live in CT/probe
        with self.conn() as c:
            c.execute("UPDATE monitor_seeds SET last_run_at = '2020-01-01T00:00:00Z'")
            c.commit()
        monitor_job.run(self.app)
        d = self.domains(acc)
        self.assertNotIn("mail.acme.org", d)
        self.assertIn("acme.org", d)
        retired = [a for a in self.alerts(acc) if a[0] == "ASSET_RETIRED"]
        self.assertEqual(retired, [("ASSET_RETIRED", "mail.acme.org")])
        for lang in ("en", "ar", "de"):
            with self.conn() as c:
                a = next(a for a in monitor_db.recent_alerts(c, acc) if a["kind"] == "ASSET_RETIRED")
            self.assertIn(str(assets.RETIRE_AFTER_FAILURES), monitor.alert_text(a, lang))

    def test_empty_discovery_never_retires(self):
        token, acc = self.trial()
        self.client.post(f"/monitor/{token}/seeds", data={"base": "acme.org"})
        with self.conn() as c:
            assets.run_seed(c, acc, assets.seeds(c, acc)[0], self.discover)
            c.execute("UPDATE monitor_domains SET fail_streak = 99")
            c.commit()
        self.discovered = found()  # source answered with nothing at all
        with self.conn() as c:
            out = assets.run_seed(c, acc, assets.seeds(c, acc)[0], self.discover)
        self.assertEqual(out["retired"], 0)
        self.assertIn("api.acme.org", self.domains(acc))

    def test_ct_names_does_not_trust_an_empty_answer_when_another_source_has_names(self):
        import discovery
        with mock.patch.object(discovery, "ct_names_crtsh", return_value=set()), \
                mock.patch.object(discovery, "ct_names_certspotter", return_value={"a.acme.org"}):
            self.assertEqual(discovery.ct_names("acme.org", None), ({"a.acme.org"}, "certspotter"))
        with mock.patch.object(discovery, "ct_names_crtsh", return_value=set()), \
                mock.patch.object(discovery, "ct_names_certspotter", return_value=set()):
            self.assertEqual(discovery.ct_names("acme.org", None), (set(), "certspotter"))

    def test_daily_job_runs_due_seeds_weekly(self):
        token, acc = self.trial()
        self.client.post(f"/monitor/{token}/seeds", data={"base": "acme.org"})
        monitor_job.run(self.app)
        monitor_job.run(self.app)  # second run same week: not due
        self.assertEqual(self.discover.call_count, 1)
        self.assertIn("api.acme.org", self.domains(acc))

    def test_manual_discover_is_rate_limited(self):
        token, acc = self.trial()
        self.client.post(f"/monitor/{token}/seeds", data={"base": "acme.org"})
        with self.conn() as c:
            sid = assets.seeds(c, acc)[0]["id"]
        r1 = self.client.post(f"/monitor/{token}/seeds/{sid}/discover")
        self.assertIn("n=seed_started", r1.headers["Location"])
        assets.wait_background()
        r2 = self.client.post(f"/monitor/{token}/seeds/{sid}/discover")
        self.assertIn("n=seed_wait", r2.headers["Location"])
        self.assertIn("api.acme.org", self.domains(acc))

    def test_ended_trial_cannot_discover_and_purge_removes_seeds(self):
        token, acc = self.trial()
        self.client.post(f"/monitor/{token}/seeds", data={"base": "acme.org"})
        with self.conn() as c:
            c.execute("UPDATE monitor_accounts SET status='TRIAL_ENDED', updated_at='2020-01-01T00:00:00Z'")
            c.commit()
            sid = assets.seeds(c, acc)[0]["id"]
        r = self.client.post(f"/monitor/{token}/seeds/{sid}/discover")
        self.assertIn("n=inactive", r.headers["Location"])
        with self.conn() as c:
            monitor_db.purge_ended_trials(c, "2025-01-01T00:00:00Z")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM monitor_seeds").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
