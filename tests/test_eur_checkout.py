"""EUR monitoring plans next to the legacy USD plans, company billing data for subscriptions, page currency."""
import os
import shutil
import tempfile
import unittest
from contextlib import closing

import company_billing
import quantum_saas_app
import sales_db
from tests.test_monitor import COMPANY, PLAN_IDS, FakeMailer, FakePayPal, FakeScanner

EUR_IDS = {"PAYPAL_PLAN_STARTER_EUR": "P-STARTER-EUR", "PAYPAL_PLAN_BUSINESS_EUR": "P-BUSINESS-EUR"}


class EurSubscriptionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.paypal, self.mailer = FakePayPal(), FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://example.test", "PAYPAL_CLIENT_ID": "cid",
             "OWNER_EMAIL": "owner@example.com", **PLAN_IDS, **EUR_IDS},
            scanner=FakeScanner(), paypal=self.paypal, mailer=self.mailer)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db")))

    def signup(self, plan="starter", **kw):
        return self.client.post("/api/monitor/signup", json=dict(COMPANY, email="ops@example.com", plan=plan, **kw))

    def activate(self, account_id, plan_id, status="ACTIVE"):
        sub_id = f"I-{account_id}"
        self.paypal.subscriptions[sub_id] = {"id": sub_id, "status": status, "custom_id": account_id, "plan_id": plan_id}
        return self.client.post("/api/monitor/activate", json={"account_id": account_id, "subscription_id": sub_id})

    def test_page_offers_eur_plans_with_company_form(self):
        for lang in ("en", "ar", "de"):
            body = self.client.get(f"/monitoring?lang={lang}").get_data(as_text=True)
            self.assertIn("currency=EUR", body)
            self.assertIn("intent=subscription", body)
            self.assertNotIn("enable-funding=eps", body)  # PayPal: eps does not support billing agreements
            self.assertIn("29.00 EUR", body)
            self.assertIn("99.00 EUR", body)
            self.assertNotIn("≈ €", body)
            self.assertIn('"priceCurrency": "EUR"', body)
            self.assertIn('class="paypal-sub" data-plan="starter" hidden', body)
            for box in ('name="company_buyer"', 'name="agb_consent"', 'name="contact_consent"', 'name="postal_code"'):
                self.assertIn(box, body)
        self.assertIn("eps", self.client.get("/monitoring?lang=en").get_data(as_text=True))

    def test_signup_returns_eur_plan_and_stores_billing(self):
        r = self.signup("business")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["plan_id"], "P-BUSINESS-EUR")
        account_id = r.get_json()["account_id"]
        with self.conn() as c:
            rec = company_billing.get(c, "subscription", account_id)
        self.assertEqual((rec["org"], rec["plan"], rec["plan_id"], rec["amount"], rec["currency"]),
                         ("Example GmbH", "business", "P-BUSINESS-EUR", "99.00", "EUR"))
        self.assertEqual(rec["billing_address"], "Ringstrasse 1\n1010 Wien\nAustria")
        res = self.activate(account_id, "P-BUSINESS-EUR")
        self.assertEqual(res.status_code, 200)
        owner = [m for m in self.mailer.sent if m[0] == "owner@example.com"][-1]
        self.assertIn("99.00 EUR", owner[1])
        self.assertIn("Example GmbH", owner[2])

    def test_eur_signup_rejects_usd_or_other_plan(self):
        account_id = self.signup("business").get_json()["account_id"]
        self.assertEqual(self.activate(account_id, "P-BUSINESS").status_code, 402)
        account_id = self.signup("business", domain="other.example").get_json()["account_id"]
        self.assertEqual(self.activate(account_id, "P-STARTER-EUR").status_code, 402)

    def test_legacy_pending_account_without_billing_accepts_both_plans(self):
        import monitor_db
        with self.conn() as c:
            legacy_usd, _ = monitor_db.create_account(c, "old@example.com", "starter", "en", consent_at="2026-01-01T00:00:00Z")
            legacy_eur, _ = monitor_db.create_account(c, "old2@example.com", "starter", "en", consent_at="2026-01-01T00:00:00Z")
        self.assertEqual(self.activate(legacy_usd, "P-STARTER").status_code, 200)
        self.assertEqual(self.activate(legacy_eur, "P-STARTER-EUR").status_code, 200)

    def test_signup_requires_company_form(self):
        for bad, code in (({"org": ""}, "required_fields"), ({"company_buyer": False}, "consent_required"),
                          ({"name": "Иван"}, "latin_required"), ({"email": "x"}, "invalid_email")):
            r = self.signup(**bad) if "email" not in bad else self.client.post(
                "/api/monitor/signup", json=dict(COMPANY, plan="starter", **bad))
            self.assertEqual((r.status_code, r.get_json()["error"]), (400, code))

    def test_without_eur_plans_falls_back_to_usd(self):
        app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PAYPAL_CLIENT_ID": "cid", **PLAN_IDS},
            scanner=FakeScanner(), paypal=FakePayPal(), mailer=FakeMailer())
        body = app.test_client().get("/monitoring?lang=en").get_data(as_text=True)
        self.assertIn("currency=USD", body)
        r = app.test_client().post("/api/monitor/signup", json=dict(COMPANY, email="a@example.com", plan="starter"))
        self.assertEqual(r.get_json()["plan_id"], "P-STARTER")

    def test_pricing_page_shows_eur(self):
        body = self.client.get("/pricing?lang=en").get_data(as_text=True)
        self.assertIn("29.00 EUR", body)
        self.assertIn("199.00 EUR", body)


if __name__ == "__main__":
    unittest.main()
