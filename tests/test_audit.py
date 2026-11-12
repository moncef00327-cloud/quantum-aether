"""/audit: organization offer + invoice request that reaches the owner by email (no online payment)."""
import shutil
import tempfile
import unittest

import quantum_saas_app
import sales_db
from tests.test_discovery import FakeHTTP, FakeMailer, _result, fake_probe

FORM = {"org": "Example Bank AG", "domain": "https://www.example.com/login", "email": "ciso@example.com",
        "name": "A. Person", "message": "Need it before our DORA review", "consent": "1"}


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.mailer = FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"DATA_DIR": self.dir, "TESTING": True, "TRUSTED_PROXIES": 0, "OWNER_EMAIL": "owner@example.org"},
            scanner=lambda raw: dict(_result(), domain=raw), mailer=self.mailer,
            discovery_http=FakeHTTP(), discovery_probe=fake_probe)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_page_in_three_languages_with_price(self):
        for lang, word in (("en", "Request audit"), ("ar", "اطلب التدقيق"), ("de", "Audit anfordern")):
            r = self.client.get(f"/audit?lang={lang}&domain=example.com")
            self.assertEqual(r.status_code, 200)
            html = r.get_data(as_text=True)
            self.assertIn(word, html)
            self.assertIn("490 EUR", html)
            self.assertIn('value="example.com"', html)
            self.assertNotIn("noindex", html)

    def test_request_mails_owner_with_discovery_numbers(self):
        scan_id = self.client.post("/api/scan", json={"domain": "www.example.com"}).get_json()["scan_id"]
        self.client.post(f"/api/discovery/{scan_id}")
        r = self.client.post("/audit?lang=en", data=FORM)
        self.assertEqual(r.status_code, 200)
        self.assertIn("ciso@example.com", r.get_data(as_text=True))
        to, subject, text = self.mailer.sent[-1]
        self.assertEqual(to, "owner@example.org")
        self.assertIn("Example Bank AG (example.com)", subject)
        self.assertIn("1 not PQ", text)
        self.assertIn("DORA review", text)
        conn = sales_db.connect(self.dir + "/quantum_saas.db")
        self.assertEqual(conn.execute("SELECT domain FROM audit_requests").fetchone()[0], "example.com")

    def test_validation_and_rate_limit(self):
        for change, code in (({"consent": ""}, 400), ({"email": "nope"}, 400), ({"org": ""}, 400),
                             ({"domain": "localhost"}, 400)):
            r = self.client.post("/audit?lang=en", data=dict(FORM, **change))
            self.assertEqual(r.status_code, code, change)
            self.assertIn('value="', r.get_data(as_text=True))  # form keeps what was typed
        self.assertEqual(self.mailer.sent, [])
        for _ in range(3):
            self.assertEqual(self.client.post("/audit", data=FORM).status_code, 200)
        self.assertEqual(self.client.post("/audit", data=FORM).status_code, 429)

    def test_no_owner_address_means_unavailable_not_lost(self):
        self.app.config["OWNER_EMAIL"] = ""
        self.assertEqual(self.client.post("/audit", data=FORM).status_code, 503)

    def test_linked_from_pricing_and_in_sitemap(self):
        self.assertIn("/audit", self.client.get("/pricing?lang=en").get_data(as_text=True))
        self.assertIn("/audit", self.client.get("/sitemap-pages.xml").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
