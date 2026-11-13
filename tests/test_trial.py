"""14-day free monitoring trial for companies: email-verified signup, daily checks, reminder, end, upgrade to paid."""
import datetime as dt
import os
import shutil
import tempfile
import unittest
from contextlib import closing

import monitor_db
import monitor_job
import quantum_saas_app
import sales_db
from tests.test_monitor import PLAN_IDS, FakeMailer, FakePayPal, FakeScanner


def shift_trial(conn, account_id, days_left):
    end = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days_left)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with conn:
        conn.execute("UPDATE monitor_accounts SET trial_ends_at = ? WHERE id = ?", (end, account_id))


class TrialTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.scanner, self.paypal, self.mailer = FakeScanner(), FakePayPal(), FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://example.test",
             "PAYPAL_CLIENT_ID": "cid", "OWNER_EMAIL": "owner@example.com", **PLAN_IDS},
            scanner=self.scanner, paypal=self.paypal, mailer=self.mailer)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db")))

    def start_trial(self, email="ops@acme.org", domain="acme.org", lang="en", consent="1"):
        data = {"email": email, "domain": domain}
        if consent:
            data["consent"] = consent
        return self.client.post(f"/monitoring/trial?lang={lang}", data=data)

    def trial_token(self):
        """The dashboard link is only ever sent by email: that is the proof the address is real."""
        mail = next(m for m in self.mailer.sent if m[0] != "owner@example.com")
        return mail[2].split("/monitor/")[1].split("?")[0].split()[0]

    def account(self, email="ops@acme.org"):
        with self.conn() as c:
            row = c.execute("SELECT * FROM monitor_accounts WHERE email = ?", (email,)).fetchone()
            return dict(row) if row else None

    # ------------------------------------------------------------ signup

    def test_monitoring_page_offers_trial_first(self):
        body = self.client.get("/monitoring?domain=acme.org&lang=en").get_data(as_text=True)
        self.assertIn('action="/monitoring/trial', body)
        self.assertIn("14 days free", body)
        self.assertLess(body.index('action="/monitoring/trial'), body.index('class="paypal-sub"'))
        for lang in ("ar", "de"):
            self.assertIn('action="/monitoring/trial', self.client.get(f"/monitoring?lang={lang}").get_data(as_text=True))

    def test_trial_signup_emails_dashboard_and_notifies_owner(self):
        r = self.start_trial()
        self.assertEqual(r.status_code, 200)
        self.assertIn("ops@acme.org", r.get_data(as_text=True))
        acc = self.account()
        self.assertEqual(acc["status"], "TRIAL")
        self.assertTrue(acc["trial_ends_at"] > dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        self.assertIsNotNone(acc["consent_at"])
        recipients = [m[0] for m in self.mailer.sent]
        self.assertEqual(sorted(recipients), ["ops@acme.org", "owner@example.com"])
        owner = next(m for m in self.mailer.sent if m[0] == "owner@example.com")
        self.assertIn("trial", owner[1].lower())
        self.assertIn("acme.org", owner[2])
        token = self.trial_token()
        self.assertNotIn(token, owner[2])
        self.assertNotIn(token, r.get_data(as_text=True))  # never shown in the browser
        dash = self.client.get(f"/monitor/{token}?lang=en").get_data(as_text=True)
        self.assertIn("acme.org", dash)
        self.assertIn("days left", dash)

    def test_trial_requires_consent_valid_email_and_domain(self):
        self.assertEqual(self.start_trial(consent=None).status_code, 400)
        self.assertEqual(self.start_trial(email="bad").status_code, 400)
        self.assertEqual(self.start_trial(domain="not a domain").status_code, 400)
        self.assertIsNone(self.account())
        self.assertEqual(self.mailer.sent, [])

    def test_one_trial_per_email(self):
        self.start_trial()
        self.mailer.sent.clear()
        r = self.start_trial(domain="other.org")
        self.assertEqual(r.status_code, 200)
        with self.conn() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM monitor_accounts").fetchone()[0], 1)
        # same neutral page; the existing user gets their link again instead of a second trial
        self.assertEqual([m[0] for m in self.mailer.sent], ["ops@acme.org"])

    def test_trial_signups_are_rate_limited_per_client(self):
        for i in range(3):
            self.assertEqual(self.start_trial(email=f"u{i}@acme{i}.org", domain=f"acme{i}.org").status_code, 200)
        self.assertEqual(self.start_trial(email="u9@acme9.org", domain="acme9.org").status_code, 429)
        self.assertIsNone(self.account("u9@acme9.org"))

    def test_trial_unavailable_without_mail(self):
        self.mailer.enabled = False
        self.assertEqual(self.start_trial().status_code, 503)
        self.assertIsNone(self.account())

    # ------------------------------------------------------------ during the trial

    def test_trial_dashboard_can_add_domains_up_to_trial_limit_and_scan(self):
        self.start_trial()
        token = self.trial_token()
        many = " ".join(f"h{i}.acme.org" for i in range(20))
        self.client.post(f"/monitor/{token}/domains", data={"domains": many})
        with self.conn() as c:
            self.assertEqual(monitor_db.count_domains(c, self.account()["id"]), 10)
        r = self.client.post(f"/monitor/{token}/scan")
        self.assertIn("n=scanned", r.headers["Location"])
        dash = self.client.get(f"/monitor/{token}?lang=en").get_data(as_text=True)
        self.assertNotIn('id="cancel-form"', dash)  # nothing to cancel: no payment

    def test_daily_job_checks_trial_accounts(self):
        self.start_trial()
        monitor_job.run(self.app)
        with self.conn() as c:
            d = monitor_db.list_domains(c, self.account()["id"])
        self.assertEqual(d[0]["grade"], "A")

    def test_login_resends_link_to_trial_users(self):
        self.start_trial()
        self.mailer.sent.clear()
        self.client.post("/monitoring/login", data={"email": "ops@acme.org"})
        self.assertEqual([m[0] for m in self.mailer.sent], ["ops@acme.org"])

    # ------------------------------------------------------------ reminder and end

    def test_reminder_once_then_trial_ends_and_monitoring_pauses(self):
        self.start_trial()
        acc_id = self.account()["id"]
        with self.conn() as c:
            shift_trial(c, acc_id, 2)
        self.mailer.sent.clear()
        monitor_job.run(self.app)
        monitor_job.run(self.app)
        reminders = [m for m in self.mailer.sent if m[0] == "ops@acme.org"]
        self.assertEqual(len(reminders), 1)
        self.assertIn("/monitoring", reminders[0][2])

        with self.conn() as c:
            shift_trial(c, acc_id, -1)
        self.mailer.sent.clear()
        self.scanner.results["acme.org"] = OSError("must not be scanned after the trial")
        monitor_job.run(self.app)
        monitor_job.run(self.app)
        acc = self.account()
        self.assertEqual(acc["status"], "TRIAL_ENDED")
        to_customer = [m for m in self.mailer.sent if m[0] == "ops@acme.org"]
        self.assertEqual(len(to_customer), 1)
        self.assertTrue(any("trial ended" in m[1].lower() for m in self.mailer.sent if m[0] == "owner@example.com"))
        with self.conn() as c:
            self.assertIsNone(monitor_db.list_domains(c, acc_id)[0]["error"])  # not scanned

    def test_ended_trial_dashboard_is_read_only_with_subscribe_buttons(self):
        self.start_trial()
        token = self.trial_token()
        with self.conn() as c:
            shift_trial(c, self.account()["id"], -1)
        monitor_job.run(self.app)
        dash = self.client.get(f"/monitor/{token}?lang=en").get_data(as_text=True)
        self.assertIn("trial has ended", dash)
        self.assertIn('class="paypal-sub"', dash)
        r = self.client.post(f"/monitor/{token}/domains", data={"domains": "x.acme.org"})
        self.assertIn("n=inactive", r.headers["Location"])

    # ------------------------------------------------------------ upgrade to paid

    def test_upgrade_keeps_account_and_domains(self):
        self.start_trial()
        token = self.trial_token()
        acc_id = self.account()["id"]
        r = self.client.post("/api/monitor/upgrade", json={"token": token, "plan": "business", "consent": True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {"account_id": acc_id, "plan_id": PLAN_IDS["PAYPAL_PLAN_BUSINESS"]})
        self.assertEqual(self.client.post("/api/monitor/upgrade", json={"token": token, "plan": "gold", "consent": True}).status_code, 400)
        self.assertEqual(self.client.post("/api/monitor/upgrade", json={"token": token, "plan": "starter"}).status_code, 400)
        self.assertEqual(self.client.post("/api/monitor/upgrade", json={"token": "nope", "plan": "starter", "consent": True}).status_code, 404)

        sub_id = "I-UP"
        self.paypal.subscriptions[sub_id] = {"id": sub_id, "status": "ACTIVE", "custom_id": acc_id,
                                             "plan_id": PLAN_IDS["PAYPAL_PLAN_BUSINESS"]}
        act = self.client.post("/api/monitor/activate", json={"account_id": acc_id, "subscription_id": sub_id, "token": token})
        self.assertEqual(act.status_code, 200)
        self.assertTrue(any("from free trial" in m[1] for m in self.mailer.sent if m[0] == "owner@example.com"))
        acc = self.account()
        self.assertEqual((acc["status"], acc["plan"], acc["subscription_id"]), ("ACTIVE", "business", sub_id))
        with self.conn() as c:
            self.assertEqual([d["domain"] for d in monitor_db.list_domains(c, acc_id)], ["acme.org"])

    def test_activate_without_upgrade_cannot_hijack_a_trial(self):
        """A trial account id alone (no dashboard token) must not be turned into someone else's subscription."""
        self.start_trial()
        acc_id = self.account()["id"]
        self.paypal.subscriptions["I-X"] = {"id": "I-X", "status": "ACTIVE", "custom_id": acc_id,
                                            "plan_id": PLAN_IDS["PAYPAL_PLAN_STARTER"]}
        r = self.client.post("/api/monitor/activate", json={"account_id": acc_id, "subscription_id": "I-X"})
        self.assertEqual(r.status_code, 409)

    def test_ended_trials_are_deleted_after_retention(self):
        self.start_trial()
        acc_id = self.account()["id"]
        with self.conn() as c:
            shift_trial(c, acc_id, -1)
        monitor_job.run(self.app)
        with self.conn() as c:
            c.execute("UPDATE monitor_accounts SET updated_at = '2020-01-01T00:00:00Z' WHERE id = ?", (acc_id,))
            c.commit()
        monitor_job.run(self.app)
        self.assertIsNone(self.account())
        with self.conn() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM monitor_domains").fetchone()[0], 0)

    def test_terms_and_privacy_mention_trial(self):
        self.assertIn("Free trial", self.client.get("/agb?lang=en").get_data(as_text=True))
        self.assertIn("90 days after the trial ends", self.client.get("/datenschutz?lang=en").get_data(as_text=True))

    def test_trial_button_click_is_tracked(self):
        body = self.client.get("/monitoring?lang=en").get_data(as_text=True)
        self.assertIn('data-ev="trial_start"', body)
        self.client.post("/api/ev", data='{"name": "trial_start", "page": "/monitoring", "lang": "en"}',
                         headers={"User-Agent": "Mozilla/5.0"}, content_type="text/plain")
        with self.conn() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM events WHERE name = 'trial_start'").fetchone()[0], 1)

    def test_admin_counts_trials(self):
        self.start_trial()
        with self.conn() as c:
            self.assertEqual(monitor_db.stats(c, {"starter": {"price": "29.00"}})["trials"], 1)

    # ------------------------------------------------------------ entry points

    def test_result_and_site_pages_offer_free_trial(self):
        scan = self.client.post("/api/scan", json={"domain": "acme.org"}).get_json()
        page = self.client.get(f"/scan/{scan['scan_id']}?lang=en").get_data(as_text=True)
        self.assertIn("free for 14 days", page)
        self.assertIn("/monitoring?domain=acme.org", page)
        site = self.client.get("/site/acme.org?lang=en").get_data(as_text=True)
        self.assertIn("free for 14 days", site)


if __name__ == "__main__":
    unittest.main()
