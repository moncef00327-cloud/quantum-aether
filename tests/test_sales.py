"""دفعة البيع: الملاحظات على صفحة النتيجة، «مرة واحدة»، «نبّهني مجاناً» بتأكيد مزدوج، مصدر الفحص."""
import datetime as dt
import re
import shutil
import tempfile
import unittest

import free_alerts
import quantum_saas_app
import sales_db
from test_app import fake_scanner
from test_monitor import FakeMailer, FakeScanner, result_for


class SalesBatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mailer, self.scanner = FakeMailer(), FakeScanner()
        self.scanner.results["example.com"] = fake_scanner("example.com")   # B، كلاسيكي
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quatum.cloud", "HASH_SALT": "s"},
            scanner=self.scanner, paypal=None, mailer=self.mailer)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return sales_db.connect(f"{self.tmp}/quantum_saas.db")

    def scan(self, domain="example.com", src="home"):
        res = self.client.post("/scan?lang=en", data={"domain": domain, "src": src})
        self.assertEqual(res.status_code, 303)
        return res.headers["Location"]

    def subscribe(self, email="u@example.org", domain="example.com", consent="1"):
        data = {"email": email, "domain": domain}
        if consent:
            data["consent"] = consent
        return self.client.post("/alerts?lang=en", data=data)

    def token_from_mail(self):
        return re.search(r"/alerts/confirm/([A-Za-z0-9_-]+)", self.mailer.sent[-1][2]).group(1)

    # صفحة النتيجة
    def test_result_page_shows_findings_free_fix_one_time_and_alert_form(self):
        body = self.client.get(self.scan()).get_data(as_text=True)
        self.assertIn("What we found", body)
        self.assertIn("Classical key exchange only (x25519)", body)
        self.assertIn('class="st-warning"', body)
        self.assertIn("/guides/enable-x25519mlkem768-nginx?lang=en", body)
        self.assertIn("One-time payment. No subscription.", body)
        self.assertIn('action="/alerts?lang=en"', body)
        self.assertNotIn("ssl_ecdh_curve", body)   # لا خطوات إصلاح من التقرير المدفوع

    def test_grade_a_has_no_fix_hint(self):
        self.scanner.results["good.test"] = result_for("good.test")
        body = self.client.get(self.scan("good.test")).get_data(as_text=True)
        self.assertNotIn("enable-x25519mlkem768-nginx", body)

    # المصدر
    def test_scan_source_recorded_and_whitelisted(self):
        self.scan(src="example")
        self.scan("good.test", src="evil<>")
        rows = dict(self.conn().execute("SELECT domain, source FROM scans").fetchall())
        self.assertEqual(rows["example.com"], "example")
        self.assertIsNone(rows["good.test"])
        self.client.get("/api/v1/scan?domain=x.test")
        self.assertEqual(self.conn().execute("SELECT source FROM scans WHERE domain='x.test'").fetchone()[0], "api")
        funnel = {r["source"]: r["scans"] for r in sales_db.funnel_by_source(self.conn(), "2000-01-01")}
        self.assertEqual(funnel["example"], 1)

    # نبّهني مجاناً
    def test_double_opt_in_flow(self):
        self.scan()
        res = self.subscribe()
        self.assertEqual(res.status_code, 200)
        self.assertIn("confirmation link", res.get_data(as_text=True))
        self.assertEqual(self.mailer.sent[-1][0], "u@example.org")
        token = self.token_from_mail()
        self.assertEqual(self.conn().execute("SELECT status FROM free_alerts").fetchone()[0], "PENDING")
        # GET (ماسح روابط البريد) لا يؤكد
        page = self.client.get(f"/alerts/confirm/{token}?lang=en")
        self.assertIn("Confirm my alert", page.get_data(as_text=True))
        self.assertEqual(page.headers["Cache-Control"], "no-store")
        self.assertEqual(self.conn().execute("SELECT status FROM free_alerts").fetchone()[0], "PENDING")
        done = self.client.post(f"/alerts/confirm/{token}?lang=en").get_data(as_text=True)
        self.assertIn("Confirmed", done)
        row = self.conn().execute("SELECT status, last_grade, last_pq FROM free_alerts").fetchone()
        self.assertEqual(tuple(row), ("ACTIVE", "B", 0))   # أساس المقارنة من آخر فحص

    def test_rejections(self):
        self.assertEqual(self.subscribe(consent=None).status_code, 400)
        self.assertEqual(self.subscribe(email="not-an-email").status_code, 400)
        self.assertEqual(len(self.mailer.sent), 0)
        for _ in range(free_alerts.CONFIRMATIONS_PER_EMAIL_PER_DAY):
            self.assertEqual(self.subscribe(domain="example.com").status_code, 200)
        self.assertEqual(self.subscribe(domain="example.com").status_code, 400)   # حدّ رسائل التأكيد لنفس البريد
        self.assertEqual(len(self.mailer.sent), free_alerts.CONFIRMATIONS_PER_EMAIL_PER_DAY)
        for i in range(2):
            self.subscribe(email=f"x{i}@example.org")
        self.assertEqual(self.subscribe(email="y@example.org").status_code, 400)  # حدّ الاتصال (5 يومياً)

    def test_one_free_domain_replaced_on_confirm_and_stop_deletes(self):
        conn = self.conn()
        t1, _ = free_alerts.subscribe(conn, "a@b.org", "one.test", "en", "c1")
        free_alerts.confirm(conn, t1)
        t2, _ = free_alerts.subscribe(conn, "a@b.org", "two.test", "en", "c1")
        free_alerts.confirm(conn, t2)
        self.assertEqual([r[0] for r in conn.execute("SELECT domain FROM free_alerts")], ["two.test"])
        self.assertEqual(free_alerts.subscribe(conn, "A@B.org", "two.test", "en", "c1"), (None, "already_active"))
        self.assertIn("Stop emails", self.client.get(f"/alerts/stop/{t2}").get_data(as_text=True))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM free_alerts").fetchone()[0], 1)  # GET لا يحذف
        self.client.post(f"/alerts/stop/{t2}")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM free_alerts").fetchone()[0], 0)

    def test_weekly_run_emails_changes_with_stop_link(self):
        conn = self.conn()
        token, _ = free_alerts.subscribe(conn, "a@b.org", "site.test", "ar", "c1")
        free_alerts.confirm(conn, token, result_for("site.test", grade="A", pq=True))
        # لم يحن الموعد بعد (فُحص الآن)
        self.assertEqual(free_alerts.run(conn, self.scanner, self.mailer, "https://x"), (0, 0))
        with conn:
            conn.execute("UPDATE free_alerts SET last_checked = '2026-01-01T00:00:00Z'")
        self.scanner.results["site.test"] = result_for("site.test", grade="B", pq=False, group="x25519")
        self.assertEqual(free_alerts.run(conn, self.scanner, self.mailer, "https://x"), (1, 1))
        to, subject, text = self.mailer.sent[-1]
        self.assertEqual(to, "a@b.org")
        self.assertIn("site.test", subject)
        self.assertIn("https://x/alerts/stop/", text)
        self.assertIn("https://x/monitoring?lang=ar", text)
        new_token = re.search(r"/alerts/stop/([A-Za-z0-9_-]+)", text).group(1)
        self.assertIsNotNone(free_alerts.get(conn, new_token))
        # لا تغيير في الأسبوع التالي ← لا رسالة
        with conn:
            conn.execute("UPDATE free_alerts SET last_checked = '2026-01-01T00:00:00Z'")
        self.assertEqual(free_alerts.run(conn, self.scanner, self.mailer, "https://x"), (1, 0))
        # فشل الفحص لا يرسل شيئاً
        with conn:
            conn.execute("UPDATE free_alerts SET last_checked = '2026-01-01T00:00:00Z'")
        self.scanner.results["site.test"] = RuntimeError("down")
        self.assertEqual(free_alerts.run(conn, self.scanner, self.mailer, "https://x"), (1, 0))

    def test_unconfirmed_requests_pruned_after_7_days(self):
        conn = self.conn()
        free_alerts.subscribe(conn, "a@b.org", "p.test", "en", "c1")
        later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=8)
        self.assertEqual(free_alerts.prune_pending(conn, now=later), 1)

    def test_privacy_page_mentions_free_alert(self):
        self.assertIn("Double-Opt-in", self.client.get("/datenschutz?lang=de").get_data(as_text=True))
        self.assertIn("double opt-in", self.client.get("/datenschutz?lang=en").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
