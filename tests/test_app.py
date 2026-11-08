import base64
import shutil
import tempfile
import unittest
from contextlib import closing

from werkzeug.security import generate_password_hash

import bio_archive_report
import quantum_saas_app
import quantum_vuln_scanner
import sales_db
from paypal_client import PayPalError

class FakeMailer:
    enabled = True

    def __init__(self):
        self.sent = []

    def send(self, to, subject, text, html=None):
        self.sent.append((to, subject, text))
        return True


RESULT = {
    "domain": "example.com",
    "ip": "93.184.215.14",
    "port": 443,
    "scanned_at": "2026-11-02T10:00:00+00:00",
    "scanner_version": "2.0",
    "key_exchange": {"version": "TLSv1.3", "group": "x25519", "pq": False, "pq_hello_ok": True, "hrr": False,
                     "cipher": "TLS_AES_128_GCM_SHA256", "kx": "TLS1.3"},
    "certificate": {"verified": True, "verify_error": None, "key_algorithm": "ECDSA", "key_bits": 256, "curve": "secp256r1",
                    "signature_algorithm": "ecdsa-with-SHA256", "subject": "example.com", "issuer": "Test CA",
                    "not_after": "2027-01-01T00:00:00+00:00", "days_left": 60, "san_count": 1, "sans": ["example.com"],
                    "negotiated_version": "TLSv1.3", "negotiated_cipher": "TLS_AES_128_GCM_SHA256"},
    "grade": "B",
    "findings": [
        {"code": "KX_CLASSICAL", "status": "warning", "params": {"group": "x25519"}},
        {"code": "CERT_SHOR_VULNERABLE", "status": "info", "params": {"algorithm": "ECDSA-256"}},
    ],
}


def fake_scanner(raw):
    domain = quantum_vuln_scanner.normalize_domain(raw)
    return dict(RESULT, domain=domain)


class FakePayPal:
    def __init__(self):
        self.orders = {}
        self.capture_amount = "49.00"
        self.capture_error = None

    def create_order(self, reference_id, amount, currency, description, return_url=None, cancel_url=None):
        order_id = f"ORDER{len(self.orders) + 1}"
        self.orders[order_id] = reference_id
        self.last_return_url = return_url
        links = [{"rel": "payer-action", "href": f"https://www.paypal.com/checkoutnow?token={order_id}"}] if return_url else []
        return {"id": order_id, "status": "PAYER_ACTION_REQUIRED" if return_url else "CREATED", "links": links}

    def capture_order(self, order_id):
        if self.capture_error:
            raise PayPalError("declined", status=422, issue=self.capture_error)
        return {
            "id": order_id,
            "status": "COMPLETED",
            "payer": {"email_address": "buyer@example.com"},
            "purchase_units": [{
                "reference_id": self.orders[order_id],
                "payments": {"captures": [{"id": "CAP-" + order_id, "status": "COMPLETED",
                                           "amount": {"currency_code": "USD", "value": self.capture_amount}}]},
            }],
        }

    get_order = capture_order


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.mkdtemp()
        self.paypal = FakePayPal()
        self.app = quantum_saas_app.create_app(
            {"DATA_DIR": self.data_dir, "TESTING": True, "TRUSTED_PROXIES": 0, "SCANS_PER_HOUR": 3,
             "PAYPAL_CLIENT_ID": "test-client", "ADMIN_PASSWORD_HASH": generate_password_hash("s3cret")},
            scanner=fake_scanner, paypal=self.paypal)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.data_dir, ignore_errors=True)

    def scan(self, domain="example.com"):
        response = self.client.post("/api/scan", json={"domain": domain})
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()

    def pay(self, scan_id):
        order = self.client.post("/api/paypal/orders", json={"scan_id": scan_id, "consent": True})
        self.assertEqual(order.status_code, 201)
        return self.client.post(f"/api/paypal/orders/{order.get_json()['id']}/capture")


class PageTests(AppTestCase):
    def test_index_in_both_languages(self):
        ar = self.client.get("/?lang=ar").get_data(as_text=True)
        en = self.client.get("/?lang=en").get_data(as_text=True)
        self.assertIn('dir="rtl"', ar)
        self.assertIn("X25519MLKEM768", ar)
        self.assertIn('dir="ltr"', en)

    def test_form_scan_redirects_to_result(self):
        response = self.client.post("/scan?lang=en", data={"domain": "https://Example.com/x"})
        self.assertEqual(response.status_code, 303)
        page = self.client.get(response.headers["Location"]).get_data(as_text=True)
        self.assertIn("example.com", page)
        self.assertIn("paypal-button-container", page)

    def test_invalid_domain_shows_error(self):
        response = self.client.post("/scan?lang=en", data={"domain": "localhost"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("not a valid domain", response.get_data(as_text=True))

    def test_research_page(self):
        page = self.client.get("/research?lang=en").get_data(as_text=True)
        self.assertIn("dbjcpopkdqps7390bqv0", page)
        self.assertIn("96.29%", page)

    def test_discovery_files(self):
        self.assertIn("Sitemap: http://localhost/sitemap.xml", self.client.get("/robots.txt").get_data(as_text=True))
        self.assertIn("/api/scan", self.client.get("/openapi.yaml").get_data(as_text=True))
        self.assertIn("X25519MLKEM768", self.client.get("/llms.txt").get_data(as_text=True))
        self.assertEqual(self.client.get("/healthz").get_json(), {"status": "ok", "payments": True})


class ApiTests(AppTestCase):
    def test_scan_summary(self):
        summary = self.scan()
        self.assertEqual(summary["grade"], "B")
        self.assertFalse(summary["post_quantum_key_exchange"])
        self.assertEqual(self.client.get(f"/api/scan/{summary['scan_id']}").get_json()["domain"], "example.com")

    def test_agent_endpoint_scans_a_domain(self):
        response = self.client.post("/api/v1/quantum-scan", json={"domain": "example.com"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["grade"], "B")

    def test_agent_endpoint_key_size_is_honest(self):
        body = self.client.post("/api/v1/quantum-scan", json={"key_size": 4096}).get_json()
        self.assertTrue(body["quantum_vulnerable"])
        self.assertEqual(body["classical_security"], "acceptable")
        self.assertNotIn("quantum_break_time_seconds", body)
        weak = self.client.post("/api/v1/quantum-scan", json={"key_size": 1024}).get_json()
        self.assertEqual(weak["classical_security"], "weak")
        self.assertEqual(self.client.post("/api/v1/quantum-scan", json={"key_size": "big"}).status_code, 400)

    def test_robots_names_ai_crawlers_and_keeps_private_paths_blocked(self):
        robots = self.client.get("/robots.txt").get_data(as_text=True)
        group, _, _ = robots.partition("\n\n")
        for agent in ("GPTBot", "ClaudeBot", "PerplexityBot", "*"):
            self.assertIn(f"User-agent: {agent}\n", group)
        self.assertIn("Disallow: /admin", group)

    def test_rate_limit_counts_failed_attempts(self):
        self.client.post("/api/scan", json={"domain": "localhost"})
        self.scan()
        self.scan()
        response = self.client.post("/api/scan", json={"domain": "example.com"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json(), {"error": "rate_limited"})


class PaymentTests(AppTestCase):
    def test_report_locked_until_paid_then_unlocked(self):
        scan = self.scan()
        with closing(sales_db.connect(f"{self.data_dir}/quantum_saas.db")) as conn:
            stored = sales_db.get_scan(conn, scan["scan_id"])
        self.assertEqual(self.client.get(f"/report/{stored['report_token']}").status_code, 404)

        capture = self.pay(scan["scan_id"])
        self.assertEqual(capture.status_code, 200)
        report_url = capture.get_json()["report_url"]
        page = self.client.get(report_url)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers["Referrer-Policy"], "no-referrer")
        self.assertIn("ssl_ecdh_curve X25519MLKEM768", page.get_data(as_text=True))

        fasta = self.client.get(report_url.split("?")[0] + "/dna.txt").get_data(as_text=True)
        restored = bio_archive_report.from_fasta(fasta).decode("utf-8")
        self.assertIn('"grade": "B"', restored)

    def test_capture_is_idempotent(self):
        scan = self.scan()
        order = self.client.post("/api/paypal/orders", json={"scan_id": scan["scan_id"], "consent": True}).get_json()
        first = self.client.post(f"/api/paypal/orders/{order['id']}/capture").get_json()
        second = self.client.post(f"/api/paypal/orders/{order['id']}/capture").get_json()
        self.assertEqual(first, second)
        self.assertEqual(self.client.post("/api/paypal/orders", json={"scan_id": scan["scan_id"], "consent": True}).status_code, 409)

    def test_wrong_amount_does_not_unlock(self):
        scan = self.scan()
        self.paypal.capture_amount = "0.01"
        capture = self.pay(scan["scan_id"])
        self.assertEqual(capture.status_code, 402)
        self.assertNotIn("report_url", capture.get_json())

    def test_unknown_order_is_rejected(self):
        response = self.client.post("/api/paypal/orders/FOREIGN-ORDER/capture")
        self.assertEqual(response.status_code, 404)

    def test_declined_card_asks_for_restart(self):
        scan = self.scan()
        self.paypal.capture_error = "INSTRUMENT_DECLINED"
        capture = self.pay(scan["scan_id"])
        self.assertEqual(capture.get_json(), {"error": "INSTRUMENT_DECLINED"})

    def test_payments_disabled_without_credentials(self):
        app = quantum_saas_app.create_app({"DATA_DIR": self.data_dir, "TESTING": True, "TRUSTED_PROXIES": 0,
                                           "PAYPAL_CLIENT_ID": "", "PAYPAL_CLIENT_SECRET": ""}, scanner=fake_scanner)
        client = app.test_client()
        scan_id = client.post("/api/scan", json={"domain": "example.com"}).get_json()["scan_id"]
        self.assertEqual(client.post("/api/paypal/orders", json={"scan_id": scan_id, "consent": True}).status_code, 503)
        page = client.get(f"/scan/{scan_id}?lang=en").get_data(as_text=True)
        self.assertIn("Payments are currently unavailable", page)
        self.assertNotIn("paypal.com/sdk", page)


class AgentPaymentTests(AppTestCase):
    def test_agent_gets_approval_link_then_return_unlocks_report(self):
        scan = self.scan()
        created = self.client.post("/api/v1/orders", json={"scan_id": scan["scan_id"], "consent_immediate_delivery": True})
        self.assertEqual(created.status_code, 201)
        order = created.get_json()
        self.assertIn("checkoutnow?token=", order["approve_url"])
        self.assertEqual(self.paypal.last_return_url, "http://localhost/paypal/return")
        self.assertNotIn("report_url", self.client.get(f"/api/v1/orders/{order['order_id']}").get_json())

        back = self.client.get(f"/paypal/return?token={order['order_id']}&PayerID=TESTPAYER")
        self.assertEqual(back.status_code, 303)
        self.assertIn("/report/", back.headers["Location"])

        status = self.client.get(f"/api/v1/orders/{order['order_id']}").get_json()
        self.assertEqual(status["status"], "COMPLETED")
        self.assertEqual(self.client.get(status["report_url"]).status_code, 200)

    def test_return_with_unknown_or_bad_payment(self):
        self.assertEqual(self.client.get("/paypal/return?token=FOREIGN").status_code, 404)
        scan = self.scan()
        order = self.client.post("/api/v1/orders", json={"scan_id": scan["scan_id"], "consent_immediate_delivery": True}).get_json()
        self.paypal.capture_amount = "1.00"
        self.assertEqual(self.client.get(f"/paypal/return?token={order['order_id']}").status_code, 400)
        self.assertEqual(self.client.get(f"/api/v1/orders/{order['order_id']}").get_json()["status"], "FAILED")


class AdminTests(AppTestCase):
    def test_requires_password(self):
        self.assertEqual(self.client.get("/admin").status_code, 401)
        bad = base64.b64encode(b"admin:wrong").decode()
        self.assertEqual(self.client.get("/admin", headers={"Authorization": f"Basic {bad}"}).status_code, 401)

    def test_shows_only_confirmed_revenue(self):
        paid = self.scan()
        self.pay(paid["scan_id"])
        unpaid = self.scan()
        self.client.post("/api/paypal/orders", json={"scan_id": unpaid["scan_id"], "consent": True})
        good = base64.b64encode(b"admin:s3cret").decode()
        page = self.client.get("/admin?lang=en", headers={"Authorization": f"Basic {good}"}).get_data(as_text=True)
        self.assertIn("49.00 USD", page)
        self.assertIn("Awaiting payment", page)



class ReceiptEmailTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mailer = FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"DATA_DIR": self.tmp, "TESTING": True, "TRUSTED_PROXIES": 0, "PUBLIC_URL": "https://ather-quantum.com",
             "PAYPAL_CLIENT_ID": "c"}, scanner=fake_scanner, paypal=FakePayPal(), mailer=self.mailer)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_paypal_purchase_emails_receipt_to_payer(self):
        sid = self.client.post("/api/scan", json={"domain": "example.com"}).get_json()["scan_id"]
        oid = self.client.post("/api/paypal/orders", json={"scan_id": sid, "consent": True}).get_json()["id"]
        r = self.client.post(f"/api/paypal/orders/{oid}/capture")
        self.assertEqual(r.get_json()["status"], "COMPLETED")
        receipt = [m for m in self.mailer.sent if m[0] == "buyer@example.com"]
        self.assertEqual(len(receipt), 1)
        self.assertIn("example.com", receipt[0][1])
        self.assertIn("/report/", receipt[0][2])  # رابط التقرير في الإيصال


if __name__ == "__main__":
    unittest.main()
