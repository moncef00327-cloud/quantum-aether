"""Partner programme (2026-11-21): consent before cookie, attribution, application, commissions."""
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock

import partners
import quantum_saas_app
import sales_db
from tests.test_app import RESULT, FakePayPal


class PartnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.paypal = FakePayPal()
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://ather-quantum.com",
                                                "PAYPAL_CLIENT_ID": "c", "SCANS_PER_HOUR": 5},
                                               scanner=Mock(return_value=dict(RESULT)), paypal=self.paypal)
        self.client = self.app.test_client()
        self.db = f"{self.tmp.name}/quantum_saas.db"
        c = sqlite3.connect(self.db)
        partners.init(c)
        with c:
            c.execute("INSERT INTO partners (code, name, email, channel, payout, status, consent_at) "
                      "VALUES ('AHMED10', 'Ahmed', 'a@example.com', 'security newsletter', 'paypal', 'ACTIVE', 'now')")
        c.close()

    def tearDown(self):
        self.tmp.cleanup()

    def cookie(self):
        return self.client.get_cookie(partners.COOKIE)

    def test_ref_link_asks_consent_and_sets_no_cookie_by_itself(self):
        html = self.client.get("/?ref=ahmed10&lang=en").get_data(as_text=True)
        self.assertIn('id="ref-bar"', html)
        self.assertIn("AHMED10", html)
        self.assertIsNone(self.cookie())
        self.assertNotIn('id="ref-bar"', self.client.get("/?lang=en").get_data(as_text=True))
        self.assertNotIn('id="ref-bar"', self.client.get("/?ref=UNKNOWN1&lang=en").get_data(as_text=True))
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("SELECT n FROM partner_clicks WHERE code='AHMED10'").fetchone()[0], 1)

    def test_consent_sets_cookie_and_purchase_is_attributed(self):
        self.assertEqual(self.client.post("/partners/consent", json={"code": "NOPE"}).status_code, 400)
        r = self.client.post("/partners/consent", json={"code": "ahmed10"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.cookie().value, "AHMED10")
        self.assertIn("Max-Age=5184000", r.headers["Set-Cookie"])
        self.assertIn("HttpOnly", r.headers["Set-Cookie"])
        sid = self.client.post("/api/scan", json={"domain": "example.com"}).get_json()["scan_id"]
        order = self.client.post("/api/paypal/orders", json={"scan_id": sid, "consent": True}).get_json()["id"]
        self.client.post(f"/api/paypal/orders/{order}/capture")
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("SELECT code FROM referrals WHERE kind='report'").fetchone()[0], "AHMED10")
        com = partners.commissions(c)["AHMED10"]
        self.assertAlmostEqual(com["pending"], 49 * 0.20, places=2)  # inside the 30-day hold
        self.assertEqual(com["due"], 0)

    def test_no_cookie_no_attribution(self):
        sid = self.client.post("/api/scan", json={"domain": "example.com"}).get_json()["scan_id"]
        self.client.post("/api/paypal/orders", json={"scan_id": sid, "consent": True})
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM referrals").fetchone()[0], 0)

    def test_application_page_and_form(self):
        for lang, word in (("en", "Partner programme"), ("de", "Partnerprogramm"), ("ar", "برنامج الشركاء")):
            self.assertIn(word, self.client.get(f"/partners?lang={lang}").get_data(as_text=True))
        bad = self.client.post("/partners/apply", data={"name": "X", "email": "bad", "channel": "short"})
        self.assertIn("error=invalid", bad.headers["Location"])
        ok = self.client.post("/partners/apply", data={"name": "Sara", "email": "s@example.com", "lang": "ar",
                                                       "channel": "LinkedIn audience of 5k security people", "payout": "usdc", "consent": "1"})
        self.assertIn("sent=1", ok.headers["Location"])
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("SELECT status, lang FROM partners WHERE email='s@example.com'").fetchone(), ("PENDING", "ar"))

    def test_privacy_mentions_referral_cookie(self):
        self.assertIn("qa_ref", self.client.get("/datenschutz?lang=en").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
