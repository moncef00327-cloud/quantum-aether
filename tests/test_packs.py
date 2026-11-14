"""باقة الوكالات: 10 تقارير مقابل 199 EUR، نموذج الشركة، الفاتورة، التحقق من الدفع، الخصم، عدم الخصم مرتين، الإيراد."""
import re
import shutil
import tempfile
import unittest

import packs
import quantum_saas_app
import sales_db
from tests.test_monitor import COMPANY, FakeMailer, FakeScanner, result_for


class FakePayPal:
    def __init__(self):
        self.orders = {}
        self.amount_override = None

    def create_order(self, reference_id, amount, currency, description, return_url=None, cancel_url=None, **kw):
        oid = f"ORDER{len(self.orders) + 1}"
        self.orders[oid] = (reference_id, amount, currency)
        return {"id": oid}

    def capture_order(self, order_id):
        ref, amount, currency = self.orders[order_id]
        value = self.amount_override or amount
        return {"status": "COMPLETED", "payer": {"email_address": "agency@example.org"},
                "purchase_units": [{"reference_id": ref, "payments": {"captures": [
                    {"id": "CAP" + order_id, "status": "COMPLETED", "amount": {"value": value, "currency_code": currency}}]}}]}


class PackTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.paypal, self.mailer, self.scanner = FakePayPal(), FakeMailer(), FakeScanner()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quantum.com", "HASH_SALT": "s",
             "OWNER_EMAIL": "owner@example.org", "SCANS_PER_HOUR": 100},
            scanner=self.scanner, paypal=self.paypal, mailer=self.mailer)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return sales_db.connect(f"{self.tmp}/quantum_saas.db")

    def buy(self):
        res = self.client.post("/api/paypal/packs?lang=en", json=dict(COMPANY, email="buyer@agency.example"))
        self.assertEqual(res.status_code, 201)
        oid = res.get_json()["id"]
        cap = self.client.post(f"/api/paypal/packs/{oid}/capture")
        self.assertEqual(cap.status_code, 200)
        return oid, cap.get_json()["pack_url"]

    def test_agency_page_all_languages(self):
        for lang, needle in (("en", "10 full reports for 199.00 EUR"), ("ar", "10 تقارير كاملة مقابل 199.00 EUR"),
                             ("de", "199.00 EUR")):
            body = self.client.get(f"/agency?lang={lang}").get_data(as_text=True)
            self.assertIn(needle, body)
            self.assertIn("pack-checkout.js", body)
            self.assertIn("company-form.js", body)
            self.assertIn("currency=EUR", body)
            self.assertIn("enable-funding=card,eps", body)
            for box in ('name="company_buyer"', 'name="agb_consent"', 'name="contact_consent"', 'name="street"'):
                self.assertIn(box, body)
            self.assertIn('id="paypal-button-container" hidden', body)
            self.assertNotIn("≈", body.split('id="buy"')[1].split("</section>")[0])
        self.assertIn("19.90 EUR each", self.client.get("/agency?lang=en").get_data(as_text=True))
        self.assertIn("/agency?lang=de", self.client.get("/sitemap-pages.xml").get_data(as_text=True))
        # 2026-11-14: agency pack left the homepage; it stays linked lower on /pricing
        self.assertIn("/agency", self.client.get("/pricing?lang=en").get_data(as_text=True))

    def test_consent_required(self):
        self.assertEqual(self.client.post("/api/paypal/packs", json={}).status_code, 400)
        for key in ("company_buyer", "agb_consent", "contact_consent"):
            r = self.client.post("/api/paypal/packs", json=dict(COMPANY, email="a@b.example", **{key: False}))
            self.assertEqual((r.status_code, r.get_json()["error"]), (400, "consent_required"))
        r = self.client.post("/api/paypal/packs", json=dict(COMPANY, email="a@b.example", street=""))
        self.assertEqual((r.status_code, r.get_json()["error"]), (400, "required_fields"))
        r = self.client.post("/api/paypal/packs", json=dict(COMPANY, email="a@b.example", org="شركة"))
        self.assertEqual((r.status_code, r.get_json()["error"]), (400, "latin_required"))
        self.assertEqual(self.paypal.orders, {})

    def test_purchase_emails_link_and_redeems(self):
        oid, url = self.buy()
        self.assertTrue(url.startswith("https://ather-quantum.com/pack/"))
        to_buyer = [m for m in self.mailer.sent if m[0] == "buyer@agency.example"][0]
        self.assertIn(url, to_buyer[2])
        self.assertTrue(any(m[0] == "owner@example.org" for m in self.mailer.sent))
        path = url.replace("https://ather-quantum.com", "")
        page = self.client.get(path)
        self.assertIn("10 of 10 reports left", page.get_data(as_text=True))
        self.assertEqual(page.headers["Cache-Control"], "no-store")
        token = path.split("/")[2].split("?")[0]
        res = self.client.post(f"/pack/{token}/redeem?lang=en", data={"domain": "client.test"})
        self.assertEqual(res.status_code, 303)
        report = self.client.get(res.headers["Location"])
        self.assertEqual(report.status_code, 200)      # التقرير الكامل مفتوح
        self.assertIn("9 of 10 reports left", self.client.get(path).get_data(as_text=True))
        # الإيراد: 199 مرة واحدة، لا 199 + قيمة التقارير
        self.assertEqual(sales_db.stats(self.conn())["revenue"], {"EUR": "199.00"})
        self.assertEqual(sales_db.stats(self.conn())["packs_sold"], 1)
        # التقاط ثانٍ لا يكشف الرابط مرة أخرى
        again = self.client.post(f"/api/paypal/packs/{oid}/capture").get_json()
        self.assertNotIn("pack_url", again)

    def test_credits_run_out_and_same_scan_not_charged_twice(self):
        _, url = self.buy()
        token = url.split("/pack/")[1].split("?")[0]
        conn = self.conn()
        pack = packs.by_token(conn, token)
        for i in range(10):
            self.assertEqual(self.client.post(f"/pack/{token}/redeem", data={"domain": f"c{i}.test"}).status_code, 303)
        res = self.client.post(f"/pack/{token}/redeem?lang=en", data={"domain": "extra.test"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("All reports in this pack have been used", res.get_data(as_text=True))
        sid = conn.execute("SELECT scan_id FROM orders WHERE order_id LIKE 'pack:%' LIMIT 1").fetchone()[0]
        self.assertTrue(packs.redeem(conn, packs.by_token(conn, token), sid))  # مفتوح مسبقاً: لا خصم
        self.assertEqual(packs.by_token(conn, token)["used"], 10)
        self.assertEqual(pack["credits"], 10)

    def test_wrong_amount_rejected(self):
        res = self.client.post("/api/paypal/packs", json=dict(COMPANY, email="buyer@agency.example"))
        oid = res.get_json()["id"]
        self.paypal.amount_override = "1.00"
        self.assertEqual(self.client.post(f"/api/paypal/packs/{oid}/capture").status_code, 402)
        self.assertEqual(self.conn().execute("SELECT status, token_hash FROM packs").fetchone()[:], ("FAILED", None))

    def test_order_is_eur_and_invoice_follows_audit_rules(self):
        oid, _url = self.buy()
        self.assertEqual(self.paypal.orders[oid][1:], ("199.00", "EUR"))
        conn = self.conn()
        record = conn.execute("SELECT * FROM billing_records WHERE kind='pack'").fetchone()
        self.assertEqual((record["org"], record["currency"], record["amount"]), ("Example GmbH", "EUR", "199.00"))
        self.assertEqual(record["billing_address"], "Ringstrasse 1\n1010 Wien\nAustria")
        self.assertTrue(record["company_confirmed_at"] and record["agb_consent_at"] and record["contact_consent_at"])
        self.assertRegex(record["invoice_number"], r"^QA-\d{4}-0001$")
        pdf = open(record["invoice_path"], "rb").read()
        self.assertTrue(pdf.startswith(b"%PDF"))
        text = pdf.decode("cp1252")
        self.assertIn(__import__("audit_checkout").TAX_LINE, text)
        self.assertIn("Agenturpaket: 10 vollst\u00e4ndige", text)
        self.assertIn("199.00 EUR", text)
        self.assertIn("Example GmbH", text)
        attached = [a for to, a in self.mailer.attachments if to == "buyer@agency.example"][0]
        self.assertEqual(attached[0]["filename"], record["invoice_number"] + ".pdf")
        # Capturing again never allocates a second number.
        self.client.post(f"/api/paypal/packs/{oid}/capture")
        self.assertEqual(conn.execute("SELECT next_number FROM audit_invoice_sequence WHERE series='QA'").fetchone()[0], 2)

    def test_bad_token_404(self):
        self.assertEqual(self.client.get("/pack/nope").status_code, 404)
        self.assertEqual(self.client.post("/pack/nope/redeem", data={"domain": "x.test"}).status_code, 404)

    def test_terms_mention_pack(self):
        self.assertIn("Agenturpaket", self.client.get("/agb?lang=de").get_data(as_text=True))
        self.assertIn("19.90 per unused report", self.client.get("/agb?lang=en").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
