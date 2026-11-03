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
             "PAYPAL_CLIENT_ID": "cid", "OWNER_EMAIL": "owner@example.com", **PLAN_IDS},
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
        self.assertEqual([m[0] for m in self.mailer.sent], ["ops@example.com", "owner@example.com"])
        self.assertIn(token, self.mailer.sent[0][2])
        self.assertIn("New subscription", self.mailer.sent[1][1])
        self.assertNotIn(token, self.mailer.sent[1][2])  # رابط العميل السري لا يصل لصاحب الموقع
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
        self.assertIn("Cancelled by customer", self.mailer.sent[-1][1])
        self.assertEqual(self.mailer.sent[-1][0], "owner@example.com")
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
        self.assertEqual([m[0] for m in self.mailer.sent], ["ops@example.com"])

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
        self.assertIn("suspended", self.mailer.sent[-1][1])
        self.assertEqual(self.mailer.sent[-1][0], "owner@example.com")

    def test_cert_alert_fires_once_per_threshold(self):
        prev = {"grade": "A", "pq": 1, "days_left": 20, "error": None}
        r10 = result_for("x.example.com", days=10)
        self.assertEqual([k for k, _ in monitor.diff(prev, r10)], ["CERT_EXPIRING"])
        self.assertEqual(monitor.diff(dict(prev, days_left=10), result_for("x.example.com", days=9)), [])
        self.assertEqual([k for k, _ in monitor.diff(dict(prev, days_left=9), result_for("x.example.com", days=3))],
                         ["CERT_EXPIRING"])


if __name__ == "__main__":
    unittest.main()


class MailerTest(unittest.TestCase):
    def test_reply_to_is_sent_to_resend(self):
        import mailer as mailer_module

        class Session:
            def post(self, url, json, timeout, headers):
                self.body = json

                class R:
                    status_code = 200
                    text = ""
                return R()

        session = Session()
        m = mailer_module.Mailer("key", "QA <a@example.com>", "owner@example.com", session=session)
        self.assertTrue(m.send("c@example.com", "s", "t"))
        self.assertEqual(session.body["reply_to"], "owner@example.com")
        self.assertFalse(mailer_module.Mailer("", "x").send("c@example.com", "s", "t"))


class BadgeAndAdminTest(unittest.TestCase):
    def setUp(self):
        from werkzeug.security import generate_password_hash
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "ADMIN_PASSWORD_HASH": generate_password_hash("pw"),
             "PAYPAL_CLIENT_ID": "cid", **PLAN_IDS},
            scanner=lambda raw: result_for(quantum_vuln_scanner.normalize_domain(raw)),
            paypal=FakePayPal(), mailer=FakeMailer())
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_badge_unscanned_then_graded(self):
        r = self.client.get("/badge/example.com.svg")
        self.assertEqual(r.mimetype, "image/svg+xml")
        self.assertIn("not scanned", r.get_data(as_text=True))
        self.client.post("/api/scan", json={"domain": "example.com"})
        body = self.client.get("/badge/example.com.svg").get_data(as_text=True)
        self.assertIn("A · ML-KEM", body)
        self.assertEqual(self.client.get("/badge/localhost.svg").status_code, 404)

    def test_scan_page_offers_badge_for_grade_a(self):
        scan_url = self.client.post("/api/scan", json={"domain": "example.com"}).get_json()["scan_url"]
        body = self.client.get(scan_url.split("example.test")[-1].replace("http://localhost", "")).get_data(as_text=True)
        self.assertIn("/badge/example.com.svg", body)

    def test_index_prefills_domain(self):
        self.assertIn('value="example.com"', self.client.get("/?domain=example.com").get_data(as_text=True))

    def test_admin_shows_mrr(self):
        import base64
        with closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db"))) as c:
            a, _ = monitor_db.create_account(c, "x@example.com", "business", "en")
            monitor_db.set_status(c, a, "ACTIVE", "I-1")
            b, _ = monitor_db.create_account(c, "y@example.com", "starter", "en")
            monitor_db.set_status(c, b, "ACTIVE", "I-2")
        auth = {"Authorization": "Basic " + base64.b64encode(b"admin:pw").decode()}
        body = self.client.get("/admin?lang=en", headers=auth).get_data(as_text=True)
        self.assertIn("$128.00", body)
        self.assertIn("y@example.com", body)


class AnalyticsTest(unittest.TestCase):
    def setUp(self):
        from werkzeug.security import generate_password_hash
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quatum.cloud",
             "ADMIN_PASSWORD_HASH": generate_password_hash("pw")},
            scanner=lambda raw: result_for(quantum_vuln_scanner.normalize_domain(raw)), paypal=None, mailer=FakeMailer())
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_tracks_humans_sources_and_skips_private_pages(self):
        browser = {"User-Agent": "Mozilla/5.0 Firefox/140"}
        self.client.get("/", headers=dict(browser, Referer="https://news.ycombinator.com/item?id=1"))
        self.client.get("/guides", headers=dict(browser, Referer="https://ather-quatum.cloud/"))
        self.client.get("/", headers={"User-Agent": "Mozilla/5.0 (compatible; bingbot/2.0)"})
        self.client.get("/robots.txt", headers=browser)
        self.client.get("/admin", headers=browser)
        import base64
        auth = {"Authorization": "Basic " + base64.b64encode(b"admin:pw").decode()}
        body = self.client.get("/admin?lang=en", headers=auth).get_data(as_text=True)
        self.assertIn("news.ycombinator.com", body)
        with closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db"))) as c:
            rows = c.execute("SELECT path, referrer, is_bot FROM pageviews ORDER BY rowid").fetchall()
        self.assertEqual([tuple(r) for r in rows],
                         [("/", "news.ycombinator.com", 0), ("/guides", "(internal)", 0), ("/", "(direct)", 1)])


class AdminExclusionAndSeoTest(unittest.TestCase):
    def setUp(self):
        import base64
        from werkzeug.security import generate_password_hash
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quatum.cloud",
             "ADMIN_PASSWORD_HASH": generate_password_hash("pw"), "HASH_SALT": "salt"},
            scanner=lambda raw: result_for(quantum_vuln_scanner.normalize_domain(raw)), paypal=None, mailer=FakeMailer())
        self.auth = {"Authorization": "Basic " + base64.b64encode(b"admin:pw").decode()}
        self.browser = {"User-Agent": "Mozilla/5.0 Firefox/140"}

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def db(self):
        return closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db")))

    def test_admin_cookie_excludes_visits_and_scans(self):
        admin = self.app.test_client()
        r = admin.get("/admin", headers=self.auth)
        cookie = r.headers["Set-Cookie"]
        self.assertIn("qa_admin=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Max-Age=31536000", cookie)
        admin.get("/", headers=self.browser)
        admin.get("/monitoring", headers=self.browser)
        admin.post("/api/scan", json={"domain": "example.com"})
        visitor = self.app.test_client()
        visitor.get("/", headers=self.browser)
        visitor.post("/api/scan", json={"domain": "example.org"})
        with self.db() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM pageviews").fetchone()[0], 1)
            self.assertEqual(sales_db.stats(c)["scans"], 1)
            self.assertEqual(c.execute("SELECT is_test FROM scans WHERE domain = 'example.com'").fetchone()[0], 1)
        body = admin.get("/admin?lang=en", headers=self.auth).get_data(as_text=True)
        self.assertIn("excluded from all statistics", body)

    def test_forged_cookie_is_ignored(self):
        client = self.app.test_client()
        client.set_cookie("qa_admin", "forged")
        client.get("/", headers=self.browser)
        with self.db() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM pageviews").fetchone()[0], 1)

    def test_migration_marks_existing_rows_as_tests(self):
        import sqlite3
        path = os.path.join(self.tmp, "old.db")
        old = sqlite3.connect(path)
        old.executescript(sales_db.SCHEMA)
        old.execute("INSERT INTO scans (id, report_token, domain, grade, result_json, client_hash) VALUES ('s','t','a.com','A','{}','h')")
        old.commit(); old.close()
        with closing(sales_db.connect(path)) as c:
            self.assertEqual(c.execute("SELECT is_test FROM scans").fetchone()[0], 1)
            self.assertEqual(sales_db.stats(c)["scans"], 0)

    def test_hreflang_on_pages(self):
        body = self.app.test_client().get("/guides?lang=ar").get_data(as_text=True)
        for lang in ("en", "ar", "x-default"):
            self.assertIn(f'hreflang="{lang}"', body)
        self.assertIn('hreflang="x-default" href="http://localhost/guides?lang=en"', body)

    def test_legal_pages_in_both_languages_with_placeholders(self):
        client = self.app.test_client()
        for slug in ("impressum", "datenschutz", "agb"):
            for lang in ("de", "en"):
                r = client.get(f"/{slug}?lang={lang}")
                self.assertEqual(r.status_code, 200, (slug, lang))
                body = r.get_data(as_text=True)
                self.assertIn('class="placeholder"', body)
                self.assertIn(f'<html lang="{lang}" dir="ltr">', body)
                self.assertIn('hreflang="de"', body)
        home = client.get("/?lang=ar").get_data(as_text=True)
        for slug in ("impressum", "datenschutz", "agb"):
            self.assertIn(f"/{slug}?lang=en", home)

    def test_sitemap_has_xhtml_alternates(self):
        import xml.dom.minidom
        body = self.app.test_client().get("/sitemap.xml").get_data(as_text=True)
        xml.dom.minidom.parseString(body)
        self.assertIn('xmlns:xhtml="http://www.w3.org/1999/xhtml"', body)
        self.assertIn('<xhtml:link rel="alternate" hreflang="x-default" href="https://ather-quatum.cloud/guides?lang=en"/>', body)
        self.assertIn("https://ather-quatum.cloud/impressum?lang=de", body)
        self.assertEqual(body.count("<url>"), 2 * (5 + 3) + 2 * 3)

    def test_robots_points_to_sitemap(self):
        self.assertIn("Sitemap: https://ather-quatum.cloud/sitemap.xml",
                      self.app.test_client().get("/robots.txt").get_data(as_text=True))
