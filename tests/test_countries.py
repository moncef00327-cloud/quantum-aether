"""ترتيب الدول: التصنيف بامتداد الدولة، الاستبعاد، الحد الأدنى، التغيّر الأسبوعي، الصفحات والصور."""
import json
import shutil
import tempfile
import unittest
import xml.dom.minidom

import countries
import og_image
import quantum_saas_app
import sales_db


def seed(conn):
    rows = []
    # ألمانيا: 25 موقعاً، 15 جاهزة هذا الأسبوع (60%) و10 الأسبوع الماضي (40%)
    for i in range(25):
        rows.append(("2026-W44", f"de{i}.de", 100 + i, 1, "A" if i < 10 else "B", int(i < 10), 0))
        rows.append(("2026-W45", f"de{i}.de", 100 + i, 1, "A" if i < 15 else "B", int(i < 15), 0))
    # فرنسا: 20 موقعاً، 18 جاهزة (90%)
    for i in range(20):
        rows.append(("2026-W45", f"fr{i}.fr", 200 + i, 1, "A" if i < 18 else "B", int(i < 18), 0))
    # النمسا: 5 فقط ← لا تدخل الترتيب؛ ‎.io مستبعد؛ موقع غير محسوم لا يُحسب
    for i in range(5):
        rows.append(("2026-W45", f"at{i}.at", 300 + i, 1, "A", 1, 0))
    for i in range(30):
        rows.append(("2026-W45", f"x{i}.io", 400 + i, 1, "A", 1, 0))
    rows.append(("2026-W45", "blocked.de", 500, 1, "B", 0, 1))
    with conn:
        conn.executemany("INSERT INTO adoption_results (week, domain, rank, ok, grade, pq, unsure, scanned_at) "
                         "VALUES (?,?,?,?,?,?,?, '2026-11-02T01:00:00Z')", rows)


class CountriesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quatum.cloud", "HASH_SALT": "s"},
            scanner=lambda d: None, paypal=None)
        self.client = self.app.test_client()
        conn = sales_db.connect(f"{self.tmp}/quantum_saas.db")
        seed(conn)
        self.conn = conn

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp)

    def test_leaderboard_ranks_and_deltas(self):
        board = countries.leaderboard(self.conn)
        codes = [e["code"] for e in board["entries"]]
        self.assertEqual(codes, ["fr", "de"])          # at (<20) و io (عام) خارج الترتيب
        de = board["entries"][1]
        self.assertEqual((de["measured"], de["pq"], de["pct"]), (25, 15, 60.0))   # blocked.de غير محسوم: لا يُحسب
        self.assertEqual(de["delta_pp"], 20.0)
        self.assertEqual(de["rank_change"], -1)          # كانت الأولى وحدها، وتجاوزتها فرنسا
        self.assertIsNone(board["entries"][0]["delta_pp"])                       # فرنسا بلا أسبوع سابق
        self.assertEqual(countries.flag("de"), "🇩🇪")
        self.assertEqual(countries.code_of("bbc.co.uk"), "uk")
        self.assertIsNone(countries.code_of("github.io"))

    def test_pages_json_and_sitemap(self):
        body = self.client.get("/adoption/countries?lang=ar").get_data(as_text=True)
        self.assertIn("ألمانيا", body)
        self.assertIn("▲ 20.0", body)
        self.assertIn('"@type": "Dataset"', body)
        de = self.client.get("/adoption/countries/de?lang=en").get_data(as_text=True)
        self.assertIn("60.0% of Germany", de)
        self.assertIn('href="/site/de0.de"', de)
        self.assertIn("https://ather-quatum.cloud/og/country/de.png", de)
        self.assertIn("Undetermined", de)
        self.assertEqual(self.client.get("/adoption/countries/at").status_code, 404)
        self.assertIn("Deutschland", self.client.get("/adoption/countries/de?lang=de").get_data(as_text=True))
        data = json.loads(self.client.get("/adoption/countries.json").get_data(as_text=True))
        self.assertEqual(data["entries"][0]["name"], "France")
        self.assertEqual(data["license"], "CC BY 4.0")
        sm = self.client.get("/sitemap-pages.xml").get_data(as_text=True)
        xml.dom.minidom.parseString(sm)
        self.assertIn("/adoption/countries/de?lang=de", sm)
        self.assertIn("/adoption/countries", self.client.get("/llms.txt").get_data(as_text=True))
        self.assertIn("/adoption/countries", self.client.get("/feed.xml").get_data(as_text=True))

    def test_site_page_links_country(self):
        body = self.client.get("/site/de3.de?lang=en").get_data(as_text=True)
        self.assertIn('href="/adoption/countries/de?lang=en"', body)
        self.assertIn("#2/2", body)

    @unittest.skipUnless(og_image.available(), "Pillow not installed")
    def test_country_og_image(self):
        res = self.client.get("/og/country/de.png")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
