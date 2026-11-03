"""اختبارات لأخطاء وُجدت بفحص الموقع الحيّ (2026-11-03): زر النسخ، رموز الأخطاء، نص الموافقة."""
import shutil
import tempfile
import unittest

import quantum_saas_app
from paypal_client import PayPalError
from tests import test_app, test_monitor


class CopyButtonAndConsentTests(test_app.AppTestCase):
    def test_copy_button_shows_label_not_python_method(self):
        scan = self.scan()
        for lang, label in (("en", "Copy"), ("ar", "نسخ")):
            page = self.client.get(f"/scan/{scan['scan_id']}?lang={lang}").get_data(as_text=True)
            self.assertNotIn("built-in method", page)
            self.assertIn(f">{label}</button>", page)

    def test_site_page_copy_button(self):
        self.scan("example.com")
        page = self.client.get("/site/example.com?lang=en").get_data(as_text=True)
        self.assertNotIn("built-in method", page)

    def test_consent_text_has_no_dangling_dash(self):
        scan = self.scan()
        page = self.client.get(f"/scan/{scan['scan_id']}?lang=en").get_data(as_text=True)
        self.assertNotIn("withdrawal. —", page)
        self.assertIn("withdrawal. (<a", page)


class CaptureErrorCodeTests(test_app.AppTestCase):
    def test_unapproved_order_is_409_not_502(self):
        scan = self.scan()
        self.paypal.capture_error = "ORDER_NOT_APPROVED"
        capture = self.pay(scan["scan_id"])
        self.assertEqual(capture.status_code, 409)
        self.assertEqual(capture.get_json(), {"error": "order_not_approved"})


class MissingSubscriptionPayPal:
    def get_subscription(self, subscription_id):
        raise PayPalError("The specified resource does not exist.", status=404, issue="INVALID_RESOURCE_ID")


class ActivationErrorCodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mailer = test_monitor.FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://example.test",
             "PAYPAL_CLIENT_ID": "cid", **test_monitor.PLAN_IDS},
            scanner=test_monitor.FakeScanner(), paypal=test_monitor.FakePayPal(), mailer=self.mailer)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_unknown_subscription_is_404_not_502(self):
        r = self.client.post("/api/monitor/signup", json={"email": "ops@example.com", "plan": "starter", "consent": True})
        account_id = r.get_json()["account_id"]
        self.app.extensions["paypal"] = MissingSubscriptionPayPal()
        r = self.client.post("/api/monitor/activate", json={"account_id": account_id, "subscription_id": "I-FAKE"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.get_json(), {"error": "subscription_not_found"})
        self.assertEqual(self.mailer.sent, [])
