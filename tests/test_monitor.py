import os
import shutil
import tempfile
import unittest
from contextlib import closing

import monitor
import monitor_db
import monitor_job
import quantum_saas_app
import quantum_vuln_scanner
import sales_db
from tests.test_app import RESULT

PLAN_IDS = {"PAYPAL_PLAN_STARTER": "P-STARTER", "PAYPAL_PLAN_BUSINESS": "P-BUSINESS"}


def result_for(domain, grade="A", pq=True, days=60, group="X25519MLKEM768"):
    r = dict(RESULT, domain=domain, grade=grade)
    r["key_exchange"] = dict(RESULT["key_exchange"], pq=pq, group=group)
    r["certificate"] = dict(RESULT["certificate"], days_left=days)
    return r


class FakeScanner:
    def __init__(self):
        self.results = {}

    def __call__(self, raw):
        domain = quantum_vuln_scanner.normalize_domain(raw)
        outcome = self.results.get(domain, result_for(domain))
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakePayPal:
    def __init__(self):
        self.subscriptions = {}
        self.cancelled = []

    def get_subscription(self, subscription_id):
        return self.subscriptions[subscription_id]

    def cancel_subscription(self, subscription_id, reason):
        self.cancelled.append(subscription_id)
        self.subscriptions[subscription_id]["status"] = "CANCELLED"
        return {}


class FakeMailer:
    enabled = True

    def __init__(self):
        self.sent = []

    def send(self, to, subject, text, html=None):
        self.sent.append((to, subject, text))
        return True


class MonitoringTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.scanner, self.paypal, self.mailer = FakeScanner(), FakePayPal(), FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://example.test",
             "PAYPAL_CLIENT_ID": "cid", **PLAN_IDS},
            scanner=self.scanner, paypal=self.paypal, mailer=self.mailer)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db")))

    def subscribe(self, plan="starter", email="ops@example.com", status="ACTIVE", plan_id=None):
        r = self.client.post("/api/monitor/signup", json={"email": email, "plan": plan})
        self.assertEqual(r.status_code, 201)
        account_id = r.get_json()["account_id"]
        self.assertEqual(r.get_json()["plan_id"], PLAN_IDS[f"PAYPAL_PLAN_{plan.upper()}"])
        sub_id = f"I-{account_id}"
        self.paypal.subscriptions[sub_id] = {"id": sub_id, "status": status, "custom_id": account_id,
                                             "plan_id": plan_id or PLAN_IDS[f"PAYPAL_PLAN_{plan.upper()}"]}
        return account_id, self.client.post("/api/monitor/activate", json={"account_id": account_id, "subscription_id": sub_id})

    def token_from(self, response):
        url = response.get_json()["dashboard_url"]
        return url.split("/monitor/")[1].split("?")[0]

    # ------------------------------------------------------------ الاشتراك

    def test_pricing_page_shows_both_plans(self):
        body = self.client.get("/monitoring?lang=en").get_data(as_text=True)
        self.assertIn("Starter", body)
        self.assertIn("Business", body)
        self.assertIn("intent=subscription", body)

    def test_pricing_page_without_plans_disables_checkout(self):
        app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp}, scanner=self.scanner, paypal=None)
        body = app.test_client().get("/monitoring?lang=en").get_data(as_text=True)
        self.assertNotIn("intent=subscription", body)
        self.assertEqual(app.test_client().post("/api/monitor/signup", json={}).status_code, 503)

    def test_signup_validates_email_and_plan(self):
        self.assertEqual(self.client.post("/api/monitor/signup", json={"email": "bad", "plan": "starter"}).status_code, 400)
        self.assertEqual(self.client.post("/api/monitor/signup", json={"email": "a@b.co", "plan": "gold"}).status_code, 400)

    def test_activation_verifies_with_paypal_and_sends_welcome(self):
        account_id, r = self.subscribe()
        self.assertEqual(r.status_code, 200)
        token = self.token_from(r)
        with self.conn() as c:
            self.assertEqual(monitor_db.get_account(c, account_id)["status"], "ACTIVE")
        self.assertEqual(len(self.mailer.sent), 1)
        self.assertIn(token, self.mailer.sent[0][2])
        self.assertEqual(self.client.get(f"/monitor/{token}").status_code, 200)

    def test_activation_rejects_wrong_plan_or_inactive(self):
        _, r = self.subscribe(plan="business", plan_id="P-STARTER")  # دفع خطة أرخص لحساب أغلى
        self.assertEqual(r.status_code, 402)
        _, r = self.subscribe(status="APPROVAL_PENDING")
        self.assertEqual(r.status_code, 402)
        self.assertEqual(self.mailer.sent, [])

    def test_activation_cannot_be_replayed(self):
        account_id, _ = self.subscribe()
        r = self.client.post("/api/monitor/activate", json={"account_id": account_id, "subscription_id": f"I-{account_id}"})
        self.assertEqual(r.status_code, 409)

    def test_pending_account_has_no_dashboard(self):
        r = self.client.post("/api/monitor/signup", json={"email": "x@example.com", "plan": "starter"})
        with self.conn() as c:
            token = monitor_db.rotate_token(c, r.get_json()["account_id"])
        self.assertEqual(self.client.get(f"/monitor/{token}").status_code, 404)
        self.assertEqual(self.client.get("/monitor/not-a-token").status_code, 404)

    # ------------------------------------------------------------ لوحة التحكم

    def test_add_domains_respects_plan_limit_and_dedupes(self):
        _, r = self.subscribe()
        token = self.token_from(r)
        domains = "\n".join(f"site{i}.example.com" for i in range(12)) + "\nsite0.example.com"
        r = self.client.post(f"/monitor/{token}/domains", data={"domains": domains})
        self.assertIn("n=limit", r.headers["Location"])
        body = self.client.get(f"/monitor/{token}?lang=en").get_data(as_text=True)
        self.assertIn("10 / 10", body)

    def test_invalid_domain_is_skipped(self):
        _, r = self.subscribe()
        token = self.token_from(r)
        r = self.client.post(f"/monitor/{token}/domains", data={"domains": "localhost, ok.example.com"})
        self.assertIn("n=invalid", r.headers["Location"])
        self.assertIn("ok.example.com", self.client.get(f"/monitor/{token}").get_data(as_text=True))

    def test_manual_scan_is_rate_limited(self):
        _, r = self.subscribe()
        token = self.token_from(r)
        self.client.post(f"/monitor/{token}/domains", data={"domains": "a.example.com"})
        self.assertIn("n=scanned", self.client.post(f"/monitor/{token}/scan").headers["Location"])
        self.assertIn("n=wait", self.client.post(f"/monitor/{token}/scan").headers["Location"])

    def test_cancel_calls_paypal_and_stops_service(self):
        account_id, r = self.subscribe()
        token = self.token_from(r)
        self.client.post(f"/monitor/{token}/cancel")
        self.assertEqual(self.paypal.cancelled, [f"I-{account_id}"])
        r = self.client.post(f"/monitor/{token}/domains", data={"domains": "a.example.com"})
        self.assertIn("n=inactive", r.headers["Location"])

    def test_dashboard_is_private(self):
        _, r = self.subscribe()
        r = self.client.get(f"/monitor/{self.token_from(r)}")
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        self.assertEqual(r.headers["Referrer-Policy"], "no-referrer")
        self.assertIn("noindex", r.headers["X-Robots-Tag"])

    def test_login_link_is_emailed_only_to_active_subscribers(self):
        self.subscribe(email="ops@example.com")
        self.mailer.sent.clear()
        self.client.post("/monitoring/login", data={"email": "nobody@example.com"})
        self.assertEqual(self.mailer.sent, [])
        r = self.client.post("/monitoring/login", data={"email": "OPS@example.com"})
        self.assertEqual(r.status_code, 303)
        self.assertEqual(len(self.mailer.sent), 1)

    # ------------------------------------------------------------ المهمة اليومية والتنبيهات

    def test_daily_job_detects_regressions_and_emails_once(self):
        account_id, r = self.subscribe()
        token = self.token_from(r)
        self.client.post(f"/monitor/{token}/domains", data={"domains": "a.example.com b.example.com c.example.com"})
        monitor_job.run(self.app)  # أول فحص: خط الأساس، بلا تنبيهات
        self.mailer.sent.clear()

        self.scanner.results["a.example.com"] = result_for("a.example.com", grade="B", pq=False, group="x25519")
        self.scanner.results["b.example.com"] = result_for("b.example.com", days=10)
        self.scanner.results["c.example.com"] = OSError("connection refused")
        monitor_job.run(self.app)

        with self.conn() as c:
            kinds = sorted(a["kind"] for a in monitor_db.recent_alerts(c, account_id))
        self.assertEqual(kinds, ["CERT_EXPIRING", "GRADE_CHANGED", "PQ_LOST", "UNREACHABLE"])
        self.assertEqual(len(self.mailer.sent), 1)
        self.assertIn("a.example.com", self.mailer.sent[0][2])

        monitor_job.run(self.app)  # لا تغيير جديد: لا رسالة ثانية
        self.assertEqual(len(self.mailer.sent), 1)

    def test_daily_job_deactivates_cancelled_subscriptions(self):
        account_id, _ = self.subscribe()
        self.paypal.subscriptions[f"I-{account_id}"]["status"] = "SUSPENDED"
        monitor_job.run(self.app)
        with self.conn() as c:
            self.assertEqual(monitor_db.get_account(c, account_id)["status"], "SUSPENDED")

    def test_cert_alert_fires_once_per_threshold(self):
        prev = {"grade": "A", "pq": 1, "days_left": 20, "error": None}
        r10 = result_for("x.example.com", days=10)
        self.assertEqual([k for k, _ in monitor.diff(prev, r10)], ["CERT_EXPIRING"])
        self.assertEqual(monitor.diff(dict(prev, days_left=10), result_for("x.example.com", days=9)), [])
        self.assertEqual([k for k, _ in monitor.diff(dict(prev, days_left=9), result_for("x.example.com", days=3))],
                         ["CERT_EXPIRING"])


if __name__ == "__main__":
    unittest.main()
