"""دفعة التحويل: أحداث الصفحة، الأمثلة بنتائجها، الشارة من المتتبّع، صور المعاينة، صفحة المواعيد."""
import json
import shutil
import tempfile
import unittest
import xml.dom.minidom

import analytics_db
import og_image
import quantum_saas_app
import sales_db
from tests.test_crawlers import seed


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quatum.cloud", "HASH_SALT": "s"},
            scanner=self.scanner, paypal=None)
        self.client = self.app.test_client()
        conn = sales_db.connect(f"{self.tmp}/quantum_saas.db")
        seed(conn)
        conn.close()

    @staticmethod
    def scanner(raw):
        import quantum_vuln_scanner
        quantum_vuln_scanner.normalize_domain(raw)  # يرفع ScanError لنطاق غير صالح
        raise quantum_vuln_scanner.ScanError("unreachable", "unreachable")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return sales_db.connect(f"{self.tmp}/quantum_saas.db")

    def ev(self, name, ua="Mozilla/5.0 (iPhone)", **headers):
        return self.client.post("/api/ev", data=json.dumps({"name": name, "page": "/", "lang": "ar"}),
                                headers={"User-Agent": ua, **headers})

    def test_events_recorded_once_and_filtered(self):
        for _ in range(3):
            self.assertEqual(self.ev("focus").status_code, 204)
        self.ev("submit")
        self.ev("evil<script>")                                   # اسم غير مسموح
        self.ev("focus", ua="Googlebot/2.1")                       # روبوت
        self.ev("type", **{"Sec-Fetch-Site": "cross-site"})        # من موقع آخر
        funnel = analytics_db.event_funnel(self.conn(), "2000-01-01")
        self.assertEqual(funnel["focus"], 1)
        self.assertEqual(funnel["submit"], 1)
        self.assertEqual(funnel["type"], 0)
        rows = self.conn().execute("SELECT COUNT(*) FROM events").fetchone()[0]
        self.assertEqual(rows, 3)                                  # focus + submit + focus(bot)

    def test_admin_visitor_events_ignored(self):
        with self.app.test_request_context():
            cookie = quantum_saas_app.admin_cookie_value()
        self.client.set_cookie(quantum_saas_app.ADMIN_COOKIE, cookie)
        self.ev("focus")
        self.assertEqual(self.conn().execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)

    def test_homepage_examples_hooks_and_no_site_line(self):
        body = self.client.get("/?lang=en").get_data(as_text=True)
        self.assertIn('class="example-link example-chip', body)
        self.assertIn("No website of your own?", body)
        self.assertIn('data-ev="monitoring_cta"', body)
        self.assertIn("/deadlines?lang=en", body)
        ar = self.client.get("/?lang=ar").get_data(as_text=True)
        self.assertIn("لا تملك موقعاً؟", ar)

    def test_scan_error_page_keeps_examples(self):
        res = self.client.post("/scan", data={"domain": "not a domain!"})
        self.assertEqual(res.status_code, 400)
        body = res.get_data(as_text=True)
        self.assertIn('data-ev-load="error"', body)
        self.assertIn("example-chip", body)

    def test_badge_uses_weekly_tracker(self):
        import datetime as dt
        now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn = self.conn()
        with conn:
            conn.execute("UPDATE adoption_results SET scanned_at = ? WHERE domain = 'alpha.test' AND week = '2026-W45'", (now,))
        svg = self.client.get("/badge/alpha.test.svg").get_data(as_text=True)
        self.assertNotIn("not scanned", svg)
        self.assertIn("A ·", svg)
        old = self.client.get("/badge/beta.test.svg").get_data(as_text=True)   # فحص قديم (>30 يوماً في الاختبار؟)
        self.assertTrue("not scanned" in old or "B ·" in old)
        self.assertIn("undetermined", self.client.get("/badge/gamma.test.svg").get_data(as_text=True))  # observed but inconclusive, not absent

    def test_og_tags_point_to_images(self):
        body = self.client.get("/site/alpha.test?lang=en").get_data(as_text=True)
        self.assertIn('property="og:image" content="https://ather-quatum.cloud/og/site/alpha.test.png"', body)
        self.assertIn('content="summary_large_image"', body)
        home = self.client.get("/?lang=en").get_data(as_text=True)
        self.assertIn('content="https://ather-quatum.cloud/og/default.png"', home)

    @unittest.skipUnless(og_image.available(), "Pillow not installed")
    def test_og_images_render_and_cache(self):
        res = self.client.get("/og/site/alpha.test.png")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "image/png")
        self.assertTrue(res.data.startswith(b"\x89PNG"))
        self.assertEqual(self.client.get("/og/default.png").status_code, 200)
        self.assertEqual(self.client.get("/og/site/unknown-xyz.test.png").status_code, 404)

    def test_deadlines_page_all_languages(self):
        for lang, needle in (("en", "No law today forces"), ("ar", "لا يوجد اليوم قانون"), ("de", "Kein Gesetz")):
            body = self.client.get(f"/deadlines?lang={lang}").get_data(as_text=True)
            self.assertIn(needle, body)
            self.assertIn("https://csrc.nist.gov/pubs/fips/203/final", body)
            self.assertIn('"@type": "Article"', body)
        self.assertIn("/deadlines?lang=de", self.client.get("/sitemap-pages.xml").get_data(as_text=True))
        feed = self.client.get("/feed.xml").get_data(as_text=True)
        xml.dom.minidom.parseString(feed)
        self.assertIn("/deadlines", feed)
        self.assertIn("/deadlines", self.client.get("/llms.txt").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
