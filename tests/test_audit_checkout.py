"""Small-company audit checkout: server-verified PayPal capture, serial invoices (real and TEST series),
Latin-only billing data, owner notification, automatic PDF report and the refund gate."""
import json
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
    "street": "Hauptstraße 12", "postal_code": "4020", "city": "Linz", "country": "Österreich",
    "domain": "https://www.example.org/login", "company_buyer": True,
    "agb_consent": True, "contact_consent": True,
}

HOSTS = [{"host": "api.example.org", "status": "not_pq", "group": "x25519", "version": "TLSv1.3"},
         {"host": "example.org", "status": "pq", "group": "X25519MLKEM768", "version": "TLSv1.3"},
         {"host": "www.example.org", "status": "pq", "group": "X25519MLKEM768", "version": "TLSv1.3"}]


class FakePayPal:
    def __init__(self):
        self.orders, self.refunds, self.created = {}, [], []
        self.amount_override = None
        self.refund_status = "COMPLETED"

    def create_order(self, reference_id, amount, currency, description, return_url=None, cancel_url=None, **kw):
        order_id = f"AUDIT-{len(self.orders) + 1}"
        self.orders[order_id] = {"reference": reference_id, "amount": amount, "currency": currency}
        self.created.append(kw)
        return {"id": order_id}

    def capture_order(self, order_id):
        row = self.orders[order_id]
        amount = self.amount_override or row["amount"]
        return {"status": "COMPLETED", "payer": {"email_address": "payer@example.org"},
                "purchase_units": [{"reference_id": row["reference"], "payments": {"captures": [{
                    "id": "CAPTURE-" + order_id, "status": "COMPLETED",
                    "amount": {"currency_code": row["currency"], "value": amount}}]}}]}

    def refund_capture(self, capture_id, request_id, note=""):
        self.refunds.append((capture_id, request_id))
        return {"id": "REFUND-1", "status": self.refund_status}


class FakeMailer:
    enabled = True

    def __init__(self):
        self.sent = []

    def send(self, to, subject, text, html=None, attachments=None):
        self.sent.append({"to": to, "subject": subject, "text": text, "attachments": attachments or []})
        return True


class AuditCheckoutTests(unittest.TestCase):
    paypal_env = "live"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.paypal, self.mailer = FakePayPal(), FakeMailer()
        self.discoveries = []

        def discover(domain):
            self.discoveries.append(domain)
            return {"source": "fixture", "names": 3, "responding": 3, "pq": 2, "not_pq": 1, "unknown": 0,
                    "hosts": [dict(h) for h in HOSTS]}

        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quantum.com",
             "HASH_SALT": "test-salt", "OWNER_EMAIL": "owner@example.org", "AUDIT_PAYPAL_ENV": self.paypal_env,
             "AUDIT_PAYPAL_CLIENT_ID": "sandbox-client", "ADMIN_PASSWORD_HASH": generate_password_hash("pw")},
            scanner=FakeScanner(), paypal=self.paypal, mailer=self.mailer, audit_discovery=discover,
            discovery_probe=lambda host: None)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def conn(self):
        return sales_db.connect(self.tmp + "/quantum_saas.db")

    def create(self, payload=None):
        return self.client.post("/api/paypal/audit?lang=de", json=payload or FORM)

    def admin_login(self):
        self.assertEqual(self.client.get("/admin", auth=("admin", "pw")).status_code, 200)

    def pay(self):
        order_id = self.create().get_json()["id"]
        r = self.client.post(f"/api/paypal/audit/{order_id}/capture")
        self.assertEqual(r.status_code, 200, r.get_json())
        return order_id, r.get_json()

    # ---------------------------------------------------------------- page

    def test_page_shows_checkout_enterprise_quote_and_hidden_buttons(self):
        for lang in ("en", "ar", "de"):
            html = self.client.get(f"/audit?lang={lang}").get_data(as_text=True)
            self.assertIn('id="audit-checkout-form"', html)
            self.assertIn('id="enterprise-quote"', html)
            self.assertIn("1,500" if lang != "de" else "1.500", html)
            self.assertIn("490 EUR", html)
            self.assertIn('id="audit-paypal-buttons" hidden', html)
            self.assertIn("currency=EUR", html)
            self.assertIn("enable-funding=card", html)
            for box in ("company_buyer", "agb_consent", "contact_consent"):
                self.assertIn(f'name="{box}"', html)
        self.assertNotIn("PayPal sandbox", self.client.get("/audit?lang=en").get_data(as_text=True))

    def test_usd_fallback_is_stated_on_the_page(self):
        self.app.config["AUDIT_CURRENCY"] = "USD"
        html = self.client.get("/audit?lang=en").get_data(as_text=True)
        self.assertIn("Charged in USD", html)
        self.assertIn("currency=USD", html)

    # ---------------------------------------------------------------- validation

    def test_creation_requires_all_fields_boxes_and_latin_billing_data(self):
        cases = {"required_fields": [dict(FORM, street=""), dict(FORM, city="  ")],
                 "consent_required": [dict(FORM, agb_consent=False), dict(FORM, company_buyer=False),
                                      dict(FORM, contact_consent=False), dict(FORM, agb_consent="true")],
                 "latin_required": [dict(FORM, org="شركة المثال"), dict(FORM, name="Иван"),
                                    dict(FORM, city="東京"), dict(FORM, street="Main St\u200b 1")],
                 "invalid_domain": [dict(FORM, domain="localhost")],
                 "invalid_email": [dict(FORM, email="not-an-email")]}
        for error, payloads in cases.items():
            for payload in payloads:
                r = self.create(payload)
                self.assertEqual(r.status_code, 400, payload)
                self.assertEqual(r.get_json()["error"], error, payload)
        self.assertEqual(self.paypal.orders, {})
        # Accents, ß and the euro sign are fine (cp1252).
        self.assertEqual(self.create(dict(FORM, org="Café Müller & Søn GmbH", street="Straße 1 – Top 2")).status_code, 201)

    def test_order_is_created_in_eur_without_shipping(self):
        r = self.create()
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertEqual((r.get_json()["amount"], r.get_json()["currency"]), ("490.00", "EUR"))
        self.assertEqual(self.paypal.created[0], {"no_shipping": True})
        row = audit_checkout.by_order(self.conn(), r.get_json()["id"])
        self.assertEqual(row["domain"], "example.org")
        self.assertEqual(row["billing_address"], "Hauptstraße 12\n4020 Linz\nÖsterreich")
        self.assertEqual(row["company_buyer"], 1)

    # ---------------------------------------------------------------- happy path

    def test_paid_order_invoice_emails_report_and_scan(self):
        order_id, data = self.pay()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertEqual(data["invoice_number"], "QA-" + data["invoice_number"][3:7] + "-0001")
        self.assertEqual(data["audit_status"], "DONE")
        row = audit_checkout.by_order(self.conn(), order_id)
        self.assertEqual(row["status"], "COMPLETED")
        self.assertEqual(row["is_test"], 0)
        pdf = open(row["invoice_path"], "rb").read()
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        for text in ("Kleinunternehmer gemäß § 6 Abs. 1 Z 27 UStG – keine USt.", "Example GmbH", "Hauptstraße 12",
                     "4020 Linz", "490.00 EUR", "Omer Alsaloum", "Sparkaßen 11/12, 5280 Braunau am Inn",
                     data["invoice_number"]):
            self.assertIn(text.encode("cp1252"), pdf, text)
        self.assertNotIn(b"TESTRECHNUNG", pdf)
        # Summary keeps the full host list (classical first) and the primary-domain check.
        summary = json.loads(row["audit_summary"])
        self.assertEqual([h["host"] for h in summary["hosts"]][0], "api.example.org")
        self.assertEqual(len(summary["hosts"]), 3)
        self.assertIn("grade", summary["main"])
        report = open(row["report_path"], "rb").read()
        for host in ("api.example.org", "www.example.org", "CLASSICAL", "X25519MLKEM768", "Report date"):
            self.assertIn(host.encode(), report)
        to_customer = [m for m in self.mailer.sent if m["to"] == "ada@example.org"]
        self.assertEqual(len(to_customer), 2)  # invoice mail, then report mail
        self.assertEqual(to_customer[0]["attachments"][0]["content"], pdf)
        self.assertTrue(to_customer[1]["attachments"][0]["filename"].endswith("-report.pdf"))
        to_owner = [m for m in self.mailer.sent if m["to"] == "owner@example.org"]
        self.assertTrue(any("Audit paid" in m["subject"] for m in to_owner))
        self.assertFalse(any(m["subject"].startswith("[TEST]") for m in self.mailer.sent))
        self.assertEqual(self.discoveries, ["example.org"])
        sent = len(self.mailer.sent)
        # Retrying the capture is idempotent: no second mail, number or scan.
        again = self.client.post(f"/api/paypal/audit/{order_id}/capture")
        self.assertEqual(again.get_json()["invoice_number"], data["invoice_number"])
        self.assertEqual(len(self.mailer.sent), sent)
        self.assertEqual(self.discoveries, ["example.org"])

    def test_real_invoice_numbers_are_sequential(self):
        numbers = [self.pay()[1]["invoice_number"] for _ in range(2)]
        self.assertEqual([n[-4:] for n in numbers], ["0001", "0002"])

    def test_wrong_amount_never_invoices_or_starts_scan(self):
        created = self.create().get_json()
        self.paypal.amount_override = "1.00"
        r = self.client.post(f"/api/paypal/audit/{created['id']}/capture")
        self.assertEqual(r.status_code, 402)
        row = audit_checkout.by_order(self.conn(), created["id"])
        self.assertEqual(row["status"], "FAILED")
        self.assertIsNone(row["invoice_number"])
        self.assertEqual(self.mailer.sent, [])
        self.assertEqual(self.discoveries, [])

    # ---------------------------------------------------------------- unreachable + refund

    def test_reachable_domain_is_not_refundable(self):
        _, data = self.pay()
        row = audit_checkout.recent(self.conn())[0]
        self.admin_login()
        r = self.client.post(f"/admin/audit/{row['id']}/refund", data={"confirm": "yes"})
        self.assertIn("refund-not-eligible", r.headers["Location"])
        self.assertEqual(self.paypal.refunds, [])
        self.assertNotIn("via PayPal</button>", self.client.get("/admin", auth=("admin", "pw")).get_data(as_text=True))

    def test_unreachable_domain_gets_no_report_and_a_confirmed_full_refund(self):
        self.app.extensions["audit_discover"] = lambda d: {"source": "fixture", "names": 2, "hosts": []}
        self.app.extensions["scanner"].results["example.org"] = RuntimeError("no answer")
        order_id, data = self.pay()
        row = audit_checkout.by_order(self.conn(), order_id)
        self.assertEqual(row["audit_status"], "ACCESS_ISSUE")
        self.assertIsNone(row["report_path"])
        self.assertTrue(any("unreachable" in m["subject"] and m["to"] == "owner@example.org" for m in self.mailer.sent))
        self.admin_login()
        page = self.client.get("/admin", auth=("admin", "pw")).get_data(as_text=True)
        self.assertIn("Refund 490.00 EUR via PayPal", page)
        self.assertIn("refund-not-confirmed", self.client.post(f"/admin/audit/{row['id']}/refund").headers["Location"])
        r = self.client.post(f"/admin/audit/{row['id']}/refund", data={"confirm": "yes"})
        self.assertIn("refund-ok", r.headers["Location"])
        self.assertEqual(self.paypal.refunds, [("CAPTURE-" + order_id, f"audit-refund-{row['id']}")])
        self.assertEqual(audit_checkout.by_order(self.conn(), order_id)["status"], "REFUNDED")
        self.assertTrue(any("Refund" in m["subject"] and m["to"] == "ada@example.org" for m in self.mailer.sent))
        again = self.client.post(f"/admin/audit/{row['id']}/refund", data={"confirm": "yes"})
        self.assertIn("refund-not-eligible", again.headers["Location"])
        self.assertEqual(len(self.paypal.refunds), 1)

    def test_admin_actions_require_admin(self):
        order_id, _ = self.pay()
        row = audit_checkout.by_order(self.conn(), order_id)
        for path in ("refund", "retry-delivery"):
            self.assertEqual(self.client.post(f"/admin/audit/{row['id']}/{path}", data={"confirm": "yes"}).status_code, 401)
        for path in ("invoice", "report"):
            self.assertEqual(self.client.get(f"/admin/audit/{row['id']}/{path}").status_code, 401)
        self.admin_login()
        r = self.client.get(f"/admin/audit/{row['id']}/report")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data.startswith(b"%PDF"))

    def test_failed_customer_mail_can_be_retried_from_admin(self):
        real_send = self.mailer.send
        self.mailer.send = lambda to, *a, **k: False if to == "ada@example.org" else real_send(to, *a, **k)
        order_id, data = self.pay()
        self.assertFalse(data["invoice_email_sent"])
        self.mailer.send = real_send
        row = audit_checkout.by_order(self.conn(), order_id)
        self.admin_login()
        r = self.client.post(f"/admin/audit/{row['id']}/retry-delivery")
        self.assertIn("delivery-ok", r.headers["Location"])
        row = audit_checkout.by_order(self.conn(), order_id)
        self.assertEqual((row["customer_email_sent"], row["report_email_sent"]), (1, 1))


class SandboxAuditCheckoutTests(AuditCheckoutTests):
    """With the audit PayPal client in sandbox every order is a test order with its own TEST series."""
    paypal_env = "sandbox"

    def test_paid_order_invoice_emails_report_and_scan(self):
        order_id, data = self.pay()
        self.assertRegex(data["invoice_number"], r"^TEST-\d{4}-0001$")
        row = audit_checkout.by_order(self.conn(), order_id)
        self.assertEqual((row["is_test"], row["paypal_env"]), (1, "sandbox"))
        pdf = open(row["invoice_path"], "rb").read()
        self.assertIn(b"TESTRECHNUNG", pdf)
        self.assertIn("Kleinunternehmer gemäß § 6 Abs. 1 Z 27 UStG – keine USt.".encode("cp1252"), pdf)
        owner = [m for m in self.mailer.sent if m["to"] == "owner@example.org"]
        self.assertTrue(owner and all(m["subject"].startswith("[TEST]") for m in owner))
        self.assertTrue(any("Audit paid" in m["subject"] for m in owner))
        customer = [m for m in self.mailer.sent if m["to"] == "ada@example.org"]
        self.assertTrue(customer and all(m["subject"].startswith("[TEST]") for m in customer))

    def test_real_invoice_numbers_are_sequential(self):
        self.pay()
        self.pay()
        with self.conn() as conn:
            rows = dict(((r["series"], r["year"]), r["next_number"]) for r in
                        conn.execute("SELECT * FROM audit_invoice_sequence"))
        self.assertEqual([k[0] for k in rows], ["TEST"])  # the real QA series was never touched
        self.assertEqual(list(rows.values()), [3])

    def test_page_shows_checkout_enterprise_quote_and_hidden_buttons(self):
        self.assertIn("PayPal sandbox", self.client.get("/audit?lang=en").get_data(as_text=True))


class LatinTests(unittest.TestCase):
    def test_latin_ok(self):
        for ok in ("Müller GmbH", "Café – Straße 1", "O'Brien & Sons, S.à r.l.", "€ Co"):
            self.assertTrue(audit_checkout.latin_ok(ok), ok)
        for bad in ("شركة", "Иван", "東京", "a\u200bb", "a\x00b", "Łódź"):
            self.assertFalse(audit_checkout.latin_ok(bad), bad)

    def test_pdf_never_prints_question_marks_for_unsupported_text(self):
        with self.assertRaises(UnicodeEncodeError):
            audit_checkout.render_pdf([("شركة", "body")])

    def test_long_report_paginates(self):
        hosts = [{"host": f"h{i}.example.org", "status": "not_pq", "group": "x25519", "version": "TLSv1.3"}
                 for i in range(200)]
        order = {"domain": "example.org", "org": "Example GmbH", "invoice_number": "QA-2026-0001"}
        pdf = audit_checkout.report_pdf(order, {"hosts": hosts, "responding": 200}, {"name": "A", "address": "B",
                                        "email": "c@d.e"}, "2026-11-14 07:00")
        self.assertRegex(pdf, rb"/Count [4-9]")
        self.assertIn(b"h199.example.org", pdf)


if __name__ == "__main__":
    unittest.main()
