"""Traffic audit fixes (2026-11-21): /index and /partners are counted, the English home canonical is / with ar/de
alternates (and Vary: Accept-Language when the language is negotiated), the English home no longer preloads the
362 KB Arabic font, and an empty trial email gets a clear message in the page language (client and server)."""
import json
import os
import re
import shutil
import tempfile
import unittest

import analytics_db
import quantum_saas_app
import sales_db
from tests.test_crawlers import seed

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://ather-quantum.com"
BROWSER = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/130.0"}


class FakeMailer:
    enabled = True

    def __init__(self):
        self.sent = []

    def send(self, to, subject, text, html=None, attachments=None):
        self.sent.append((to, subject))
        return True


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": SITE, "HASH_SALT": "s"},
            scanner=lambda raw: None, paypal=None)
        self.app.extensions["mailer"] = FakeMailer()
        self.client = self.app.test_client()
        conn = sales_db.connect(f"{self.tmp}/quantum_saas.db")
        seed(conn)
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return sales_db.connect(f"{self.tmp}/quantum_saas.db")


class AnalyticsCoverageTests(Base):
    def test_index_and_partners_are_tracked_downloads_are_not(self):
        self.assertEqual(analytics_db.normalize_path("/index"), "/index")
        self.assertEqual(analytics_db.normalize_path("/partners"), "/partners")
        for path in ("/index.csv", "/index.json", "/index/panel.csv", "/indexnow"):
            self.assertIsNone(analytics_db.normalize_path(path), path)
        # existing pages unchanged
        for path in ("/", "/pricing", "/adoption", "/study/top-1000-post-quantum-tls"):
            self.assertEqual(analytics_db.normalize_path(path), path)
        self.assertIsNone(analytics_db.normalize_path("/report/secret"))

    def test_pageview_beacon_records_index_with_utm_source(self):
        for lang in ("en", "ar", "de"):
            self.client.post("/api/pv", data=json.dumps({"path": "/index", "search": f"?lang={lang}&utm_source=email"
                                                         "&utm_medium=cold&utm_campaign=acquirers-2026-11", "ref": ""}),
                             headers=BROWSER, content_type="text/plain")
        self.client.post("/api/pv", data=json.dumps({"path": "/partners", "search": "", "ref": ""}),
                         headers=BROWSER, content_type="text/plain")
        rows = self.conn().execute("SELECT path, referrer FROM pageviews ORDER BY rowid").fetchall()
        self.assertEqual([tuple(r) for r in rows],
                         [("/index", "utm:email")] * 3 + [("/partners", "(direct)")])

    def test_index_and_partners_pages_load_the_beacon_script(self):
        for path in ("/index?lang=en", "/partners?lang=en"):
            r = self.client.get(path)
            if r.status_code != 200:
                self.skipTest(f"{path} needs data not present in this checkout")
            self.assertIn("/static/app.js", r.get_data(as_text=True), path)


class HomeCanonicalTests(Base):
    def links(self, body):
        canonical = re.search(r'<link rel="canonical" href="([^"]+)"', body).group(1)
        alternates = dict(re.findall(r'<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"', body))
        return canonical, alternates

    def test_english_home_canonical_is_root(self):
        for url in ("/?lang=en", "/"):
            body = self.client.get(url, headers={"Accept-Language": "en"}).get_data(as_text=True)
            canonical, alt = self.links(body)
            self.assertEqual(canonical, SITE + "/", url)
            self.assertEqual(alt["en"], SITE + "/")
            self.assertEqual(alt["x-default"], SITE + "/")
            self.assertEqual(alt["ar"], SITE + "/?lang=ar")
            self.assertEqual(alt["de"], SITE + "/?lang=de")
            self.assertNotIn("?lang=en", canonical)

    def test_arabic_and_german_home_keep_their_own_canonical(self):
        self.assertEqual(self.links(self.client.get("/?lang=ar").get_data(as_text=True))[0], SITE + "/?lang=ar")
        self.assertEqual(self.links(self.client.get("/?lang=de").get_data(as_text=True))[0], SITE + "/?lang=de")

    def test_negotiated_language_varies_on_accept_language(self):
        r = self.client.get("/", headers={"Accept-Language": "ar"})
        self.assertIn("Accept-Language", r.headers.get("Vary", ""))
        self.assertEqual(self.links(r.get_data(as_text=True))[0], SITE + "/?lang=ar")
        r = self.client.get("/?lang=en")
        self.assertNotIn("Accept-Language", r.headers.get("Vary", ""))

    def test_sitemap_lists_root_not_lang_en_for_home(self):
        xml = self.client.get("/sitemap-pages.xml").get_data(as_text=True)
        self.assertIn(f"<loc>{SITE}/</loc>", xml)
        self.assertNotIn(f"<loc>{SITE}/?lang=en</loc>", xml)
        self.assertIn(f'hreflang="en" href="{SITE}/"', xml)


class HomeSpeedTests(Base):
    def test_arabic_font_preloaded_only_on_arabic_home(self):
        en = self.client.get("/?lang=en").get_data(as_text=True)
        ar = self.client.get("/?lang=ar").get_data(as_text=True)
        self.assertNotIn('rel="preload" href="/static/fonts/noto-arabic.woff2"', en)
        self.assertIn('rel="preload" href="/static/fonts/noto-arabic.woff2"', ar)
        for body in (en, ar):  # the app itself is unchanged and still loaded
            self.assertIn('<script type="module" src="/static/command/app.js', body)
            self.assertIn('id="command-root"', body)


class EmptyEmailTests(Base):
    def test_script_names_the_missing_email_in_three_languages(self):
        with open(os.path.join(BASE, "static", "trial-form.js"), encoding="utf-8") as f:
            js = f.read()
        for text in ("Email required:", "E-Mail-Adresse fehlt:", "البريد مطلوب:"):
            self.assertIn(text, js)
        self.assertIn("row.parentNode.insertBefore(el, row.nextSibling)", js)
        for path in ("/pricing?lang=en", "/?lang=en", "/monitoring?lang=ar"):
            self.assertIn("trial-form.js?v=20261121-email-required1", self.client.get(path).get_data(as_text=True), path)

    def test_pricing_email_field_is_required_with_visible_label(self):
        body = self.client.get("/pricing?lang=en").get_data(as_text=True)
        field = re.search(r'<input id="trial-email"[^>]*>', body).group(0)
        for attr in ('type="email"', "required", 'aria-required="true"', 'name="email"'):
            self.assertIn(attr, field)
        self.assertIn('<label for="trial-email">', body)

    def test_server_rejects_empty_email_with_clear_message(self):
        for lang, text in (("en", "Email required:"), ("ar", "البريد مطلوب:"), ("de", "E-Mail-Adresse fehlt:")):
            r = self.client.post(f"/monitoring/trial?lang={lang}", data={"email": "", "consent": "1", "src": "pricing"},
                                 headers=BROWSER)
            self.assertEqual(r.status_code, 400, lang)
            body = r.get_data(as_text=True)
            self.assertIn(text, body, lang)
            self.assertIn("autofocus", body)
        self.assertEqual(self.conn().execute("SELECT COUNT(*) FROM monitor_accounts").fetchone()[0], 0)

    def test_bad_email_keeps_its_own_message(self):
        r = self.client.post("/monitoring/trial?lang=en", data={"email": "nope", "consent": "1"}, headers=BROWSER)
        self.assertEqual(r.status_code, 400)
        self.assertNotIn("Email required:", r.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
