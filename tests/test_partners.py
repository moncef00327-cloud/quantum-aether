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
        self.sent_mail = []
        self.mailer = Mock()
        self.mailer.send.side_effect = lambda to, subj, text, **kw: self.sent_mail.append((to, subj, text)) or True
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://ather-quantum.com",
                                                "PAYPAL_CLIENT_ID": "c", "SCANS_PER_HOUR": 5, "OWNER_EMAIL": "owner@example.com"},
                                               scanner=Mock(return_value=dict(RESULT)), paypal=self.paypal, mailer=self.mailer)
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

    def test_ref_link_sets_cookie_immediately_without_consent_bar(self):
        r = self.client.get("/?ref=ahmed10&lang=en")
        html = r.get_data(as_text=True)
        self.assertNotIn('id="ref-bar"', html)
        self.assertEqual(self.cookie().value, "AHMED10")
        self.assertIn("Max-Age=5184000", r.headers["Set-Cookie"])
        self.assertIn("HttpOnly", r.headers["Set-Cookie"])
        self.assertNotIn('id="ref-bar"', self.client.get("/?lang=en").get_data(as_text=True))
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("SELECT n FROM partner_clicks WHERE code='AHMED10'").fetchone()[0], 1)
        c.close()

        # Unknown ref code does not set a cookie
        c2 = self.app.test_client()
        r_unknown = c2.get("/?ref=UNKNOWN1&lang=en")
        self.assertNotIn('id="ref-bar"', r_unknown.get_data(as_text=True))
        self.assertIsNone(c2.get_cookie(partners.COOKIE))

    def test_click_sets_cookie_and_purchase_is_attributed_immediately(self):
        self.assertEqual(self.client.post("/partners/consent", json={"code": "NOPE"}).status_code, 400)
        r = self.client.get("/?ref=ahmed10&lang=en")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.cookie().value, "AHMED10")
        sid = self.client.post("/api/scan", json={"domain": "example.com"}).get_json()["scan_id"]
        order = self.client.post("/api/paypal/orders", json={"scan_id": sid, "consent": True}).get_json()["id"]
        self.client.post(f"/api/paypal/orders/{order}/capture")
        c = sqlite3.connect(self.db)
        self.assertEqual(c.execute("SELECT code FROM referrals WHERE kind='report'").fetchone()[0], "AHMED10")
        com = partners.commissions(c)["AHMED10"]
        self.assertAlmostEqual(com["pending"], 49 * 0.20, places=2)  # inside the 30-day hold
        self.assertEqual(com["due"], 0)
        c.close()

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

        # 4) End-to-end referral click -> immediate cookie -> purchase attribution -> monthly manual commission
        r_ref = self.client.get(f"/?ref={code}&lang=en")
        self.assertEqual(r_ref.status_code, 200)
        self.assertNotIn('id="ref-bar"', r_ref.get_data(as_text=True))
        self.assertEqual(self.cookie().value, code)
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

    def test_owner_notified_on_partner_pilot_and_agent_registrations(self):
        # 1) Invalid & honeypot submissions send zero email
        self.client.post("/partners/apply", data={"name": "X", "email": "bad", "channel": "short"})
        self.client.post("/partners/apply", data={"name": "Bot", "email": "b@b.com", "channel": "spam channel text",
                                                  "payout": "paypal", "consent": "1", "website2": "trap"})
        self.client.post("/partners/pilot", data={"name": "Bot", "email": "b@b.com", "consent": "1", "website2": "trap"})
        self.assertEqual(len(self.sent_mail), 0)

        # 2) Valid partner application notifies owner only
        self.client.post("/partners/apply", data={"name": "Nadia", "email": "nadia@example.com", "lang": "ar",
                                                  "channel": "Security newsletter with 3k readers", "payout": "paypal", "consent": "1"})
        self.assertEqual(len(self.sent_mail), 1)
        self.assertEqual(self.sent_mail[0][0], "owner@example.com")
        self.assertIn("Nadia", self.sent_mail[0][1])
        self.assertIn("nadia@example.com", self.sent_mail[0][2])

        # 3) Valid MSP pilot lead notifies owner only
        self.client.post("/partners/pilot", data={"lang": "de", "name": "Lukas", "email": "lukas@msp.example",
                                                  "company": "MSP Nord GmbH", "hostnames": "40", "consent": "1"})
        self.assertEqual(len(self.sent_mail), 2)
        self.assertEqual(self.sent_mail[1][0], "owner@example.com")
        self.assertIn("MSP Nord GmbH", self.sent_mail[1][1])
        self.assertIn("lukas@msp.example", self.sent_mail[1][2])

        # 4) New agent affiliate notifies owner once; idempotent repeat does not re-notify
        payload = {"name": "NotifyBot", "contact_email": "bot@example.com", "payout_method": "paypal", "consent_terms": True}
        self.assertEqual(self.client.post("/api/v1/agent/affiliate/register", json=payload).status_code, 201)
        self.assertEqual(len(self.sent_mail), 3)
        self.assertEqual(self.sent_mail[2][0], "owner@example.com")
        self.assertIn("NotifyBot", self.sent_mail[2][1])
        self.assertEqual(self.client.post("/api/v1/agent/affiliate/register", json=payload).status_code, 200)
        self.assertEqual(len(self.sent_mail), 3)


if __name__ == "__main__":
    unittest.main()
