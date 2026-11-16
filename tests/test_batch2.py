"""Batch 2 (2026-11-14): PQ failure reason + stack fix, common subdomains, evidence PDF, removed research surfaces."""
import copy
import datetime as dt
import os
import tempfile
import unittest
from unittest.mock import Mock

import evidence
import monitor_db
import quantum_saas_app
import sales_db
import scan_insights
from tests.test_app import RESULT

CFG = {"TESTING": True, "PUBLIC_URL": "https://ather-quantum.com", "HASH_SALT": "s",
       "PAYPAL_CLIENT_ID": "", "PAYPAL_CLIENT_SECRET": ""}


def probe(host):
    return {"mail.example.com": {"host": host, "status": "not_pq", "group": "x25519", "version": "TLSv1.3"},
            "www.example.com": {"host": host, "status": "pq", "group": "X25519MLKEM768", "version": "TLSv1.3"}}.get(host)


class Base(unittest.TestCase):
    def make(self, result=RESULT, probe_fn=probe):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.probe = Mock(side_effect=probe_fn)
        self.app = quantum_saas_app.create_app(dict(CFG, DATA_DIR=self.tmp.name),
                                               scanner=Mock(return_value=copy.deepcopy(result)), discovery_probe=self.probe)
        self.app.extensions["server_header"] = Mock(return_value="nginx/1.24.0 (Ubuntu)")
        self.client = self.app.test_client()

    def scan(self, lang="en"):
        r = self.client.post(f"/scan?lang={lang}", data={"domain": "example.com"})
        return r.headers["Location"].split("/scan/")[1].split("?")[0]


class ReasonTests(unittest.TestCase):
    def test_reason_codes(self):
        kx = lambda **k: {"key_exchange": dict({"version": "TLSv1.3", "group": "x25519", "pq": False,
                                                "pq_hello_ok": True, "hrr": False}, **k), "certificate": {}}
        self.assertEqual(scan_insights.reason(kx()), "classical_group")
        self.assertEqual(scan_insights.reason(kx(version="TLSv1.2")), "tls12")
        self.assertEqual(scan_insights.reason(kx(pq_hello_ok=False)), "pq_hello_rejected")
        self.assertEqual(scan_insights.reason(kx(hrr=True)), "hrr_classical")
        self.assertEqual(scan_insights.reason(kx(pq=True, group="X25519MLKEM768")), "pq_ok")

    def test_stack_detection_and_fix_line(self):
        self.assertEqual(scan_insights.detect_stack("nginx/1.24.0"), "nginx")
        self.assertEqual(scan_insights.detect_stack("cloudflare"), "cloudflare")
        self.assertEqual(scan_insights.detect_stack("Apache/2.4.58 (Ubuntu)"), "apache")
        self.assertIsNone(scan_insights.detect_stack("Microsoft-IIS/10.0"))
        self.assertIn("X25519MLKEM768", scan_insights.fix_line("nginx", "en")["line"])
        self.assertEqual({t["stack"] for t in scan_insights.fix_tabs("ar")} >= {"nginx", "apache", "caddy", "haproxy", "cloudflare"}, True)


class ResultPageTests(Base):
    def test_classical_result_shows_reason_and_tabs_top(self):
        self.make()
        sid = self.scan()
        page = self.client.get(f"/scan/{sid}?lang=en").get_data(as_text=True)
        self.assertIn('id="why"', page)
        self.assertIn("chose the classical group x25519", page)
        self.assertIn("ssl_ecdh_curve X25519MLKEM768", page)
        for name in ("nginx", "Apache httpd", "Caddy", "HAProxy", "Cloudflare"):
            self.assertIn(f"<summary>{name}</summary>", page)
        self.assertLess(page.index('id="why"'), page.index('id="common-hosts"'))
        self.assertLess(page.index('id="common-hosts"'), page.index('id="discovery"'))
        # paid report collapsed at the bottom, without the brief/sample links; dev tools after share
        self.assertNotIn("executive-brief", page)
        self.assertNotIn("/sample-report", page)
        self.assertIn('<details class="card buy buy-more" id="buy"', page)
        self.assertLess(page.index('data-copy="#badge-html"'), page.index('id="buy"'))
        self.assertLess(page.index('linkedin.com/sharing'), page.index('data-copy="#badge-html"'))

    def test_grade_a_has_no_reason_block(self):
        a = copy.deepcopy(RESULT)
        a["grade"] = "A"
        a["key_exchange"].update(group="X25519MLKEM768", pq=True)
        self.make(result=a)
        page = self.client.get(f"/scan/{self.scan('ar')}?lang=ar").get_data(as_text=True)
        self.assertNotIn('id="why"', page)
        self.assertIn('id="common-hosts"', page)
        self.assertIn('data-grade-a="1"', page)
        self.assertLess(page.index('id="scan-trial"'), page.index('id="common-hosts"'))

    def test_insights_api_probes_once_and_caches(self):
        self.make()
        sid = self.scan()
        d = self.client.post(f"/api/scan/{sid}/insights?lang=en").get_json()
        self.assertEqual(d["state"], "done")
        self.assertEqual(d["stack"], "nginx")
        self.assertIn("X25519MLKEM768", d["fix"]["line"])
        hosts = {h["host"]: h["status"] for h in d["hosts"]}
        self.assertEqual(hosts["mail.example.com"], "not_pq")
        self.assertEqual(hosts["www.example.com"], "pq")
        self.assertEqual(hosts["api.example.com"], "none")
        self.assertEqual(d["classical"], ["mail.example.com"])
        self.assertEqual(self.probe.call_count, 5)
        self.client.post(f"/api/scan/{sid}/insights?lang=en")
        self.assertEqual(self.probe.call_count, 5)  # cached
        self.assertEqual(self.client.post("/api/scan/nope/insights").status_code, 404)
        self.assertEqual(self.client.get(f"/api/scan/{sid}/insights").status_code, 405)


class RemovedSurfaceTests(Base):
    def test_dna_export_disabled_and_research_unlisted(self):
        self.make()
        self.assertEqual(self.client.get("/report/anything/dna.txt").status_code, 404)
        r = self.client.get("/research?lang=en")
        self.assertIn("noindex", r.headers.get("X-Robots-Tag", ""))
        llms = self.client.get("/llms.txt").get_data(as_text=True)
        for word in ("/research", "GHZ", "IBM Quantum", "DNA"):
            self.assertNotIn(word, llms)
        sitemap = self.client.get("/sitemap-pages.xml").get_data(as_text=True)
        self.assertNotIn("/research", sitemap)
        self.assertIn("/gravity?lang=en", sitemap)
        self.assertIn("/gravity?lang=ar", sitemap)

    def test_home_and_pricing_top_without_pack_and_audit(self):
        self.make()
        for lang in ("en", "ar", "de"):
            home = self.client.get(f"/?lang={lang}").get_data(as_text=True)
            self.assertNotIn('data-ev="agency_cta"', home)
            for word in ("OBSERVATORY", "مرصد الويب", "POST-QUANTUM INTELLIGENCE", "INTELLIGENCE FOR THE POST-QUANTUM WEB"):
                self.assertNotIn(word, home)
            pricing = self.client.get(f"/pricing?lang={lang}").get_data(as_text=True)
            self.assertLess(pricing.index("plan-grid"), pricing.index('id="one-time"'))
            self.assertNotIn("purchase-grid", pricing)
            self.assertIn("/agency?lang=" + lang + "#buy", pricing[pricing.index('id="one-time"'):])


class EvidencePdfTests(Base):
    def setUp(self):
        self.make()
        conn = sales_db.connect(os.path.join(self.tmp.name, "quantum_saas.db"))
        ends = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.account_id, self.token = monitor_db.create_trial(conn, "it@acme-gmbh.example", "de", "2026-11-14T08:00:00Z",
                                                              "h", ends)
        monitor_db.add_domain(conn, self.account_id, "acme-gmbh.example")
        did = conn.execute("SELECT id FROM monitor_domains").fetchone()[0]
        a = copy.deepcopy(RESULT)
        a.update(domain="acme-gmbh.example", grade="A")
        a["key_exchange"].update(group="X25519MLKEM768", pq=True)
        a["certificate"]["days_left"] = 21
        monitor_db.save_check(conn, did, a)
        b = copy.deepcopy(RESULT)
        b.update(domain="acme-gmbh.example")
        b["certificate"]["days_left"] = 20
        conn.execute("UPDATE monitor_checks SET checked_at = '2026-11-13T06:00:00Z'")
        conn.commit()
        monitor_db.save_check(conn, did, b)
        monitor_db.add_alert(conn, self.account_id, "acme-gmbh.example", "PQ_LOST", {"group": "x25519"})
        conn.close()

    def test_dashboard_has_button_and_pdf_has_contents(self):
        page = self.client.get(f"/monitor/{self.token}?lang=ar").get_data(as_text=True)
        self.assertIn(f"/monitor/{self.token}/evidence.pdf", page)
        r = self.client.get(f"/monitor/{self.token}/evidence.pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["Content-Type"], "application/pdf")
        self.assertIn("no-store", r.headers.get("Cache-Control", ""))
        body = r.data
        self.assertTrue(body.startswith(b"%PDF"))
        for text in (b"acme-gmbh.example", b"Not legal advice", b"Keine Rechtsberatung", b"post-quantum key exchange lost",
                     b"ATTENTION: under 30 days", b"Generated", b"PQ_LOST", b"free trial"):
            self.assertIn(text, body, text)
        self.assertEqual(self.client.get("/monitor/wrong-token/evidence.pdf").status_code, 404)

    def test_non_latin_text_does_not_break_pdf(self):
        lines = evidence.evidence_lines({"email": "عمر@example.com", "plan": "starter", "status": "TRIAL",
                                         "trial_ends_at": None, "created_at": None},
                                        [{"domain": "xn--mgbh0fb.example", "grade": None, "pq": None, "error": None,
                                          "checked_at": None, "days_left": None}], [], [])
        self.assertTrue(evidence.audit_checkout.render_pdf(lines).startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
