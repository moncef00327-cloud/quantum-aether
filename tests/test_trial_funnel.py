"""Trial funnel (2026-11-14): every server rejection is logged with its reason (domain only) and counted,
fixable errors re-show the filled form, personal addresses work with a domain, CTAs carry the trial form."""
import shutil
import tempfile
import unittest

import analytics_db
import quantum_saas_app
import sales_db
from tests.test_crawlers import seed


class FakeMailer:
    enabled = True

    def __init__(self, ok=True):
        self.ok, self.sent = ok, []

    def send(self, to, subject, text, html=None, attachments=None):
        self.sent.append((to, subject))
        return self.ok


class TrialFunnelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quantum.com", "HASH_SALT": "s"},
            scanner=lambda raw: None, paypal=None)
        self.mailer = FakeMailer()
        self.app.extensions["mailer"] = self.mailer
        self.client = self.app.test_client()
        conn = sales_db.connect(f"{self.tmp}/quantum_saas.db")
        seed(conn)
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return sales_db.connect(f"{self.tmp}/quantum_saas.db")

    def post(self, lang="en", **form):
        return self.client.post(f"/monitoring/trial?lang={lang}", data=form, headers={"User-Agent": "Mozilla/5.0 (X11)"})

    def accounts(self):
        return self.conn().execute("SELECT COUNT(*) FROM monitor_accounts").fetchone()[0]

    def test_missing_consent_logs_reason_and_reshows_filled_form(self):
        with self.assertLogs("quantum_saas", "WARNING") as logs:
            r = self.post(email="it@firma-test.example", domain="firma-test.example")
        self.assertEqual(r.status_code, 400)
        body = r.get_data(as_text=True)
        self.assertIn('value="it@firma-test.example"', body)
        self.assertIn('value="firma-test.example"', body)
        self.assertIn("trial-error", body)
        self.assertIn('name="consent"', body)
        self.assertTrue(any("reason=consent_missing domain=firma-test.example" in m for m in logs.output))
        self.assertFalse(any("it@" in m for m in logs.output))
        self.assertEqual(analytics_db.event_funnel(self.conn(), "2000-01-01")["trial_failed"], 1)
        self.assertEqual(self.accounts(), 0)

    def test_personal_mail_without_domain_asks_for_domain_in_each_language(self):
        for lang, word in (("en", "personal mailbox"), ("de", "private Adresse"), ("ar", "بريد شخصي")):
            r = self.post(lang=lang, email="someone@gmail.com", consent="1")
            self.assertEqual(r.status_code, 400)
            self.assertIn(word, r.get_data(as_text=True))

    def test_personal_mail_with_domain_creates_trial(self):
        r = self.post(email="someone@gmail.com", domain="firma-test.example", consent="1")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.accounts(), 1)
        self.assertEqual(self.mailer.sent[0][0], "someone@gmail.com")

    def test_mail_failure_is_logged_and_leaves_no_account(self):
        self.mailer.ok = False
        with self.assertLogs("quantum_saas", "WARNING") as logs:
            r = self.post(email="it@firma-test.example", consent="1")
        self.assertEqual(r.status_code, 503)
        self.assertEqual(self.accounts(), 0)
        self.assertTrue(any("reason=unavailable" in m for m in logs.output))

    def test_trial_cta_and_script_on_pages(self):
        for path in ("/monitoring?lang=de&domain=firma-test.example", "/?lang=de", "/?lang=en"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertIn("/static/trial-form.js", body, path)
        body = self.client.get("/monitoring?lang=de&domain=firma-test.example").get_data(as_text=True)
        self.assertIn('value="firma-test.example"', body)

    def test_new_event_names_are_accepted(self):
        for name in ("trial_submit", "trial_invalid", "trial_failed"):
            self.assertIn(name, analytics_db.EVENT_NAMES)


if __name__ == "__main__":
    unittest.main()


class ScanErrorTrackingTests(unittest.TestCase):
    """Scan rejections (2026-11-14): code + domain (no IP, no email) in the log, the 'error' event and the admin page."""
    setUp, tearDown, conn = TrialFunnelTests.setUp, TrialFunnelTests.tearDown, TrialFunnelTests.conn

    def failing_scanner(self, raw):
        import quantum_vuln_scanner
        raise quantum_vuln_scanner.ScanError("dns_failure", "could not resolve")

    def test_form_scan_error_is_logged_and_counted_with_code_and_domain(self):
        self.app.extensions["scanner"] = self.failing_scanner
        with self.assertLogs("quantum_saas", "WARNING") as logs:
            r = self.client.post("/scan?lang=en", data={"domain": " https://Missing-Host.example/path "},
                                 headers={"User-Agent": "Mozilla/5.0 (X11)"})
        self.assertGreaterEqual(r.status_code, 400)
        self.assertTrue(any("scan rejected: code=dns_failure domain=missing-host.example" in m for m in logs.output),
                        logs.output)
        rows = analytics_db.error_details(self.conn(), "2000-01-01")
        self.assertEqual([(row["detail"], row["n"]) for row in rows], [("dns_failure:missing-host.example", 1)])

    def test_api_invalid_domain_is_counted_with_its_code(self):
        with self.assertLogs("quantum_saas", "WARNING") as logs:
            r = self.client.post("/api/scan", json={"domain": "localhost"}, headers={"User-Agent": "Mozilla/5.0 (X11)"})
        self.assertEqual(r.status_code, 400)
        self.assertTrue(any("code=invalid_domain domain=localhost" in m for m in logs.output), logs.output)
        details = [row["detail"] for row in analytics_db.error_details(self.conn(), "2000-01-01")]
        self.assertEqual(details, ["invalid_domain:localhost"])

    def test_scan_page_is_a_tracked_path(self):
        self.assertEqual(analytics_db.normalize_path("/scan"), "/scan")
        for p in ("/prooflab", "/banks/arab-banks-2026-11", "/reports/2026-11", "/analytics", "/exposure",
                  "/gravity", "/tools/pq-tls-config", "/agents", "/press", "/transparency"):
            self.assertEqual(analytics_db.normalize_path(p), p)
        self.assertIsNone(analytics_db.normalize_path("/exposure/claim/secret-token"))

    def test_homepage_scan_box_comes_before_trial_form(self):
        for lang in ("ar", "en"):
            body = self.client.get(f"/?lang={lang}").get_data(as_text=True)
            self.assertIn(f'action="/scan?lang={lang}"', body)
            self.assertIn('id="domain-hero" name="domain"', body)
            self.assertLess(body.index('id="domain-hero"'), body.index('id="trial"'))

    def test_invisible_characters_from_copy_paste_do_not_reject_a_valid_domain(self):
        import quantum_vuln_scanner as qs
        for raw in ("\u200bexample.com", "example.com\u200e", "\"example.com\"", "<example.com>", "example.com,", "\u00a0example.com"):
            with self.subTest(raw=raw):
                self.assertEqual(qs.normalize_domain(raw), "example.com")


class ConsentPlacementTests(unittest.TestCase):
    """The required consent box sits directly above the submit button in every server-rendered trial form, so on a
    phone the browser's "please tick this box" bubble is visible where the visitor taps (2026-11-14)."""
    setUp, tearDown = TrialFunnelTests.setUp, TrialFunnelTests.tearDown

    def trial_forms(self, path):
        import re
        body = self.client.get(path, headers={"User-Agent": "Mozilla/5.0 (X11)"}).get_data(as_text=True)
        return re.findall(r'<form[^>]*action="[^"]*/monitoring/trial[^"]*"[^>]*>.*?</form>', body, re.S)

    def test_consent_comes_after_the_email_field_and_right_before_the_button(self):
        checked = 0
        for path in ("/monitoring?lang=de", "/monitoring?lang=ar", "/?lang=de", "/pricing?lang=en"):
            for form in self.trial_forms(path):
                with self.subTest(path=path):
                    consent, button = form.find('name="consent"'), form.find('type="submit"')
                    self.assertGreater(consent, form.find('name="email"'))
                    self.assertGreater(button, consent)
                    self.assertNotIn('name="', form[form.find("</label>", consent):button].replace('name="consent"', ""))
                    checked += 1
        self.assertGreaterEqual(checked, 1)
