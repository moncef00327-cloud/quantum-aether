"""Server-verified PayPal checkout, invoice delivery and audit refund gates."""
import shutil
import tempfile
import unittest

import audit_checkout
import quantum_saas_app
import sales_db
from tests.test_monitor import FakeScanner
from werkzeug.security import generate_password_hash


FORM = {
    "name": "Ada Example", "email": "ada@example.org", "org": "Example GmbH",
    "street": "Hauptstraße 12", "postal_code": "4020", "city": "Linz", "country": "Austria",
    "domain": "https://www.example.org/login", "company_buyer": True,
    "agb_consent": True, "contact_consent": True,
}


class FakePayPal:
    def __init__(self):
        self.orders = {}
        self.amount_override = None
        self.refunds = []

    def create_order(self, reference_id, amount, currency, description, return_url=None, cancel_url=None):
        order_id = f"AUDIT-{len(self.orders) + 1}"
        self.orders[order_id] = {"reference": reference_id, "amount": amount, "currency": currency}
        return {"id": order_id}

    def capture_order(self, order_id):
        row = self.orders[order_id]
        amount = self.amount_override or row["amount"]
        return {"status": "COMPLETED", "payer": {"email_address": "payer@example.org"},
                "purchase_units": [{"reference_id": row["reference"], "payments": {"captures": [{
                    "id": "CAPTURE-" + order_id, "status": "COMPLETED",
                    "amount": {"currency_code": row["currency"], "value": amount}}]}}]}

    def refund_capture(self, capture_id, request_id, note=""):
        self.refunds.append((capture_id, request_id, note))
        return {"id": "REFUND-1", "status": "COMPLETED"}


class FakeMailer:
    enabled = True

    def __init__(self):
        self.sent = []

    def send(self, to, subject, text, html=None, attachments=None):
        self.sent.append({"to": to, "subject": subject, "text": text, "attachments": attachments or []})
        return True


class AuditCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.paypal, self.mailer = FakePayPal(), FakeMailer()
        self.discoveries = []

        def discover(domain):
            self.discoveries.append(domain)
            return {"status": "DONE", "source": "fixture", "names": 3, "responding": 2,
                    "pq": 1, "not_pq": 1, "unknown": 0}

        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quantum.com",
             "HASH_SALT": "test-salt", "OWNER_EMAIL": "owner@example.org",
             "AUDIT_PAYPAL_CLIENT_ID": "sandbox-client", "ADMIN_PASSWORD_HASH": generate_password_hash("pw")},
            scanner=FakeScanner(), paypal=self.paypal, mailer=self.mailer, audit_discovery=discover)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def conn(self):
        return sales_db.connect(self.tmp + "/quantum_saas.db")

    def create(self, payload=None):
        return self.client.post("/api/paypal/audit?lang=de", json=payload or FORM)

    def test_paypal_creation_requires_all_fields_and_consents(self):
        for payload in (dict(FORM, street=""), dict(FORM, agb_consent=False), dict(FORM, company_buyer=False),
                        dict(FORM, contact_consent=False), dict(FORM, domain="localhost")):
            response = self.create(payload)
            self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(self.paypal.orders, {})

    def test_payment_is_server_verified_invoice_emailed_and_discovery_started_once(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["amount"], "490.00")
        self.assertEqual(response.get_json()["currency"], "EUR")
        order_id = response.get_json()["id"]
        row = audit_checkout.by_order(self.conn(), order_id)
        self.assertEqual(row["domain"], "example.org")
        self.assertEqual(row["billing_address"], "Hauptstraße 12\n4020 Linz\nAustria")
        self.assertEqual(row["company_confirmed_at"], row["agb_consent_at"])
        self.assertEqual(row["consent_source"], "audit-checkout")

        captured = self.client.post(f"/api/paypal/audit/{order_id}/capture")
        self.assertEqual(captured.status_code, 200, captured.get_json())
        data = captured.get_json()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertEqual(data["audit_status"], "DONE")
        self.assertTrue(data["invoice_number"].startswith("QA-"))

        paid = audit_checkout.by_order(self.conn(), order_id)
        self.assertEqual(paid["status"], "COMPLETED")
        self.assertEqual(paid["audit_status"], "DONE")
        self.assertTrue(paid["invoice_path"].endswith(".pdf"))
        with open(paid["invoice_path"], "rb") as invoice_file:
            pdf = invoice_file.read()
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn("Kleinunternehmer gemäß § 6 Abs. 1 Z 27 UStG – keine USt".encode("cp1252"), pdf)
        self.assertIn("Example GmbH".encode("cp1252"), pdf)

        customer = next(m for m in self.mailer.sent if m["to"] == "ada@example.org")
        self.assertIn(data["invoice_number"], customer["subject"])
        self.assertEqual(customer["attachments"][0]["filename"], data["invoice_number"] + ".pdf")
        self.assertEqual(customer["attachments"][0]["content"], pdf)
        self.assertTrue(any(m["to"] == "owner@example.org" for m in self.mailer.sent))
        self.assertEqual(self.discoveries, ["example.org"])

        again = self.client.post(f"/api/paypal/audit/{order_id}/capture")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(len(self.mailer.sent), 2)
        self.assertEqual(self.discoveries, ["example.org"])

    def test_wrong_amount_never_invoices_or_starts_scan(self):
        created = self.create().get_json()
        self.paypal.amount_override = "1.00"
        response = self.client.post(f"/api/paypal/audit/{created['id']}/capture")
        self.assertEqual(response.status_code, 402)
        row = audit_checkout.by_order(self.conn(), created["id"])
        self.assertEqual(row["status"], "FAILED")
        self.assertIsNone(row["invoice_number"])
        self.assertEqual(self.mailer.sent, [])
        self.assertEqual(self.discoveries, [])

    def test_full_refund_button_is_exposed_only_for_unreachable_paid_audit(self):
        def unreachable(_domain):
            self.discoveries.append("unreachable")
            return {"status": "DONE", "names": 2, "responding": 0, "pq": 0, "not_pq": 0, "unknown": 0}
        self.app.extensions["audit_discover"] = unreachable
        order_id = self.create().get_json()["id"]
        self.assertEqual(self.client.post(f"/api/paypal/audit/{order_id}/capture").status_code, 200)
        row = audit_checkout.by_order(self.conn(), order_id)
        self.assertEqual(row["audit_status"], "ACCESS_ISSUE")
        order_page = self.client.get("/admin", auth=("admin", "pw"))
        self.assertEqual(order_page.status_code, 200)
        self.assertIn("Refund 490.00 EUR", order_page.get_data(as_text=True))
        refund = self.client.post(f"/admin/audit/{row['id']}/refund")
        self.assertEqual(refund.status_code, 200, refund.get_json())
        self.assertEqual(refund.get_json()["status"], "REFUNDED")
        self.assertEqual(self.paypal.refunds[0][0], row["capture_id"])
        self.assertEqual(audit_checkout.by_order(self.conn(), order_id)["status"], "REFUNDED")
        self.assertEqual(self.client.post(f"/admin/audit/{row['id']}/refund").status_code, 409)


if __name__ == "__main__":
    unittest.main()
