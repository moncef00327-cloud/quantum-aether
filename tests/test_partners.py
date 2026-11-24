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

    def test_msp_pilot_lead_capture(self):
        # Pilot CTAs are instrumented and the on-page capture form is present in every language.
        for lang in ("en", "de", "ar"):
            html = self.client.get(f"/partners?lang={lang}").get_data(as_text=True)
            self.assertIn('data-ev="msp_pilot_cta"', html)
            self.assertIn('id="pilot-apply"', html)
            self.assertIn('action="/partners/pilot"', html)
        # Invalid (missing email) is rejected and stores nothing.
        bad = self.client.post("/partners/pilot", data={"lang": "en", "name": "X", "email": "bad", "consent": "1"})
        self.assertIn("perror=invalid", bad.headers["Location"])
        # Honeypot is silently accepted but stores nothing.
        self.client.post("/partners/pilot", data={"lang": "en", "name": "Bot", "email": "b@b.com",
                                                  "consent": "1", "website2": "spam"})
        # Valid lead is stored with clamped hostnames and surfaces to the owner's review.
        ok = self.client.post("/partners/pilot", data={"lang": "de", "name": "Max MSP", "email": "max@msp.example",
                              "company": "MSP GmbH", "client_domain": "client.example", "hostnames": "400",
                              "white_label": "yes", "note": "NIS2", "consent": "1"})
        self.assertIn("psent=1", ok.headers["Location"])
        c = sqlite3.connect(self.db)
        rows = c.execute("SELECT name, email, hostnames, white_label, status FROM pilot_leads").fetchall()
        c.close()
        self.assertEqual(rows, [("Max MSP", "max@msp.example", 50, "yes", "NEW")])  # 400 clamped to 50

    def test_privacy_mentions_referral_cookie(self):
        self.assertIn("qa_ref", self.client.get("/datenschutz?lang=en").get_data(as_text=True))

    def test_agent_affiliate_mcp_and_http_with_monthly_manual_payout(self):
        wallet = "0x" + "1a" * 20
        # 1) Register via MCP tool register_agent_affiliate
        r_mcp = self.client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 10, "method": "tools/call",
            "params": {
                "name": "register_agent_affiliate",
                "arguments": {
                    "name": "SecAuditBot",
                    "contact_email": "ops@secauditbot.example",
                    "payout_method": "usdc",
                    "payout_destination": wallet,
                    "channel": "Automated NIS2 & TLS posture assistant",
                    "consent_terms": True,
                },
            },
        })
        self.assertEqual(r_mcp.status_code, 200)
        res = r_mcp.get_json()["result"]
        self.assertFalse(res["isError"])
        sc = res["structuredContent"]
        self.assertEqual(sc["status"], "ACTIVE")
        self.assertEqual(sc["terms"]["payout_schedule"], "monthly_manual_by_owner")
        self.assertEqual(sc["terms"]["monitoring_commission_pct"], 30)
        self.assertEqual(sc["terms"]["one_time_commission_pct"], 20)
        self.assertEqual(sc["terms"]["hold_days"], 30)
        self.assertEqual(sc["terms"]["min_payout_usd"], 50)
        code = sc["code"]
        self.assertIn(f"?ref={code}", sc["referral_links"]["home"])

        # 2) Idempotent re-registration returns same code
        r_http_dup = self.client.post("/api/v1/agent/affiliate/register", json={
            "name": "SecAuditBot",
            "contact_email": "ops@secauditbot.example",
            "payout_method": "usdc",
            "payout_destination": wallet,
            "consent_terms": True,
        })
        self.assertEqual(r_http_dup.status_code, 200)
        self.assertTrue(r_http_dup.get_json()["already_registered"])
        self.assertEqual(r_http_dup.get_json()["code"], code)

        # 3) Missing consent or bad wallet rejected
        self.assertEqual(
            self.client.post("/api/v1/agent/affiliate/register", json={
                "name": "BadBot", "contact_email": "b@example.com", "payout_method": "usdc",
                "payout_destination": wallet, "consent_terms": False,
            }).status_code,
            400,
        )
        self.assertEqual(
            self.client.post("/api/v1/agent/affiliate/register", json={
                "name": "BadWallet", "contact_email": "w@example.com", "payout_method": "usdc",
                "payout_destination": "not-an-evm-address", "consent_terms": True,
            }).status_code,
            400,
        )

        # 4) End-to-end referral click -> consent -> purchase attribution -> monthly manual commission
        html = self.client.get(f"/?ref={code}&lang=en").get_data(as_text=True)
        self.assertIn(code, html)
        self.assertEqual(self.client.post("/partners/consent", json={"code": code}).status_code, 200)
        sid = self.client.post("/api/scan", json={"domain": "example.com"}).get_json()["scan_id"]
        order = self.client.post("/api/paypal/orders", json={"scan_id": sid, "consent": True}).get_json()["id"]
        self.client.post(f"/api/paypal/orders/{order}/capture")
        c = sqlite3.connect(self.db)
        com = partners.commissions(c)[code]
        self.assertAlmostEqual(com["pending"], 49 * 0.20, places=2)
        self.assertEqual(com["due"], 0)
        c.close()

        # 5) Discovery advertises agent affiliate endpoint & monthly manual payout
        manifest = self.client.get("/.well-known/agent-service.json").get_json()
        self.assertTrue(manifest["pricing"]["partner_affiliate"]["enabled"])
        self.assertEqual(manifest["pricing"]["partner_affiliate"]["payout_schedule"], "monthly_manual_by_owner")
        self.assertIn("register_agent_affiliate", manifest["mcp"]["tools"])


if __name__ == "__main__":
    unittest.main()
