"""Funnel round 4 (2026-11-14): one-click trial CTA on scan results, source tagging, /scan/<domain>,
and the monitoring form above the fold in en/de/ar."""
import json
import shutil
import tempfile
import unittest

import analytics_db
import quantum_saas_app
from tests.test_app import RESULT
from tests.test_monitor import PLAN_IDS, FakeMailer, FakePayPal


def result(grade, pq, group, domain="www.acme.org"):
    r = dict(RESULT, grade=grade, domain=domain)
    r["key_exchange"] = dict(RESULT["key_exchange"], pq=pq, group=group)
    return r


class FunnelRound4Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.outcome = result("B", False, "x25519")
        self.mailer = FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PAYPAL_CLIENT_ID": "cid",
             "OWNER_EMAIL": "owner@example.com", "PUBLIC_URL": "https://ather-quantum.com",
             "HASH_SALT": "s", **PLAN_IDS},
            scanner=lambda raw: dict(self.outcome, domain=raw), paypal=FakePayPal(), mailer=self.mailer)
        self.client = self.app.test_client()
        self.ua = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) FunnelRound4"}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def scan(self, domain="www.acme.org"):
        sid = self.client.post("/api/scan", json={"domain": domain}, headers=self.ua).get_json()["scan_id"]
        return sid

    def test_scan_id_and_domain_urls_show_prefilled_editable_cta(self):
        sid = self.scan()
        for path in (f"/scan/{sid}?lang=en", "/scan/www.acme.org?lang=en", "/scan/acme.org?lang=en"):
            html = self.client.get(path, headers=self.ua).get_data(as_text=True)
            self.assertIn('id="scan-trial"', html, path)
            self.assertNotIn('trial-cta-urgent', html.split('id="scan-trial"', 1)[1].split('</section>', 1)[0], path)
            self.assertIn('data-trial-source="scan_result"', html, path)
            self.assertIn('name="src" value="scan_result"', html, path)
            section = html.split('id="scan-trial"', 1)[1].split('</section>', 1)[0]
            self.assertIn('id="scan-trial-domain"', section, path)
            self.assertIn('value="acme.org"', section, path)
            self.assertIn("Start 14-day free monitoring, no card", html, path)
            # Prefilled domain is editable; public scan results do not prove ownership.
            self.assertIn('name="consent"', html, path)
            consent, button = html.find('name="consent"'), html.find('data-ev="trial_start"')
            # compare within the scan-trial section
            section = html.split('id="scan-trial"', 1)[1]
            self.assertLess(section.find('name="consent"'), section.find('type="submit"'), path)

    def test_grade_a_cta_is_present_but_not_urgent(self):
        self.outcome = result("A", True, "X25519MLKEM768")
        html = self.client.get(f"/scan/{self.scan()}?lang=en", headers=self.ua).get_data(as_text=True)
        self.assertIn('id="scan-trial"', html)
        self.assertIn('id="scan-trial-domain"', html)
        self.assertNotIn("trial-cta-urgent", html.split('id="scan-trial"', 1)[1].split("</section>", 1)[0])

    def test_scan_domain_page_is_translated(self):
        self.scan()
        ar = self.client.get("/scan/www.acme.org?lang=ar", headers=self.ua).get_data(as_text=True)
        self.assertIn("ابدأ مراقبة 14 يوماً مجاناً، بلا بطاقة", ar)
        de = self.client.get("/scan/www.acme.org?lang=de", headers=self.ua).get_data(as_text=True)
        self.assertIn("14 Tage kostenlos überwachen, ohne Karte", de)
        self.assertIn('lang="de"', de)

    def test_unknown_scan_domain_is_404(self):
        self.assertEqual(self.client.get("/scan/no-such-domain.example", headers=self.ua).status_code, 404)

    def test_site_page_leads_with_prefilled_cta(self):
        self.scan("cewe.example")
        # Public site pages suggest an editable domain but do not assume ownership.
        html = self.client.get("/site/cewe.example?lang=en", headers=self.ua).get_data(as_text=True)
        self.assertIn('id="site-trial"', html)
        self.assertIn('data-trial-source="scan_result"', html)
        section = html.split('id="site-trial"', 1)[1].split('</section>', 1)[0]
        self.assertIn('id="site-trial-domain"', section)
        self.assertIn('value="cewe.example"', section)
        self.assertLess(html.index('id="site-trial"'), html.index('id="alert"'))
        self.assertLess(html.index('id="site-trial"'), html.index('id="badge"') if 'id="badge"' in html else len(html))

    def test_monitoring_form_is_first_and_has_one_line_in_each_language(self):
        cases = {
            "en": "14 days free, no card required.",
            "de": "14 Tage, kostenlos, keine Karte nötig.",
            "ar": "14 يوماً مجاناً، بلا بطاقة.",
        }
        for lang, line in cases.items():
            html = self.client.get(f"/monitoring?lang={lang}&domain=acme.org", headers=self.ua).get_data(as_text=True)
            self.assertIn('class="hero trial-fold"', html, lang)
            self.assertIn(line, html, lang)
            self.assertIn('data-trial-source="monitoring"', html, lang)
            self.assertIn('value="acme.org"', html, lang)
            # form is on the first screen: before features, plan table and subscribe
            self.assertLess(html.index('id="trial"'), html.index('id="subscribe"'), lang)
            self.assertLess(html.index("trial-form"), html.index('id="subscribe"'), lang)
            if lang == "en":
                self.assertLess(html.index("trial-form"), html.index("Plan and data limits"))
            # consent still sits above the button
            form = html.split('class="scan-form trial-form"', 1)[1].split("</form>", 1)[0]
            self.assertLess(form.find('name="consent"'), form.find('type="submit"'), lang)

    def test_prefilled_scan_result_form_starts_a_trial_and_records_source(self):
        r = self.client.post("/monitoring/trial?lang=en", headers=self.ua,
                             data={"email": "it@acme.org", "domain": "acme.org", "consent": "1", "src": "scan_result"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("it@acme.org", [m[0] for m in self.mailer.sent])
        conn = __import__("sales_db").connect(f"{self.tmp}/quantum_saas.db")
        funnel = analytics_db.event_funnel(conn, "2000-01-01")
        self.assertEqual(funnel["trial_created"], 1)
        row = conn.execute("SELECT detail FROM events WHERE name = 'trial_created'").fetchone()
        self.assertEqual(row[0], "scan_result")

    def test_browser_event_keeps_source_detail(self):
        r = self.client.post("/api/ev", headers={**self.ua, "Sec-Fetch-Site": "same-origin",
                                                 "Content-Type": "text/plain"},
                             data=json.dumps({"name": "trial_submit", "page": "/scan/www.acme.org",
                                              "lang": "en", "detail": "scan_result"}))
        self.assertEqual(r.status_code, 204)
        conn = __import__("sales_db").connect(f"{self.tmp}/quantum_saas.db")
        row = conn.execute("SELECT detail, name FROM events WHERE name = 'trial_submit'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "scan_result")


if __name__ == "__main__":
    unittest.main()
