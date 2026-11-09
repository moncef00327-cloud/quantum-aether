"""ما يجذب الزواحف: صفحات نطاقات من المتتبّع الأسبوعي، Last-Modified/304، llms-full.txt، security.txt."""
import shutil
import tempfile
import unittest
import xml.dom.minidom

import adoption
import quantum_saas_app
import sales_db


def seed(conn):
    rows = [
        ("2026-W44", "alpha.test", 501, 1, "B", "X25519", "TLSv1.3", 0, 0, "CLOUDFLARENET", "2026-10-27T01:00:00Z"),
        ("2026-W45", "alpha.test", 501, 1, "A", "X25519MLKEM768", "TLSv1.3", 1, 0, "CLOUDFLARENET", "2026-11-02T01:00:00Z"),
        ("2026-W45", "beta.test", 502, 1, "B", "X25519", "TLSv1.3", 0, 0, "CLOUDFLARENET", "2026-11-02T01:00:00Z"),
        ("2026-W45", "gamma.test", 503, 1, "B", None, "TLSv1.3", 0, 1, "AMAZON-02", "2026-11-02T01:00:00Z"),
        ("2026-W45", "down.test", 504, 0, None, None, None, 0, 0, None, "2026-11-02T01:00:00Z"),
        # outside the top 1000: page stays reachable but is not indexed
        ("2026-W45", "longtail.test", 5005, 1, "B", "X25519", "TLSv1.3", 0, 0, "CLOUDFLARENET", "2026-11-02T01:00:00Z"),
        # direct rank neighbour on another network: no longer linked
        ("2026-W45", "neighbour.test", 500, 1, "B", "X25519", "TLSv1.3", 0, 0, "OTHER-NET", "2026-11-02T01:00:00Z"),
    ]
    with conn:
        conn.executemany("INSERT INTO adoption_results (week, domain, rank, ok, grade, grp, tls, pq, unsure, as_name, scanned_at) "
                         "VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)


class CrawlerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quantum.com", "HASH_SALT": "s"},
            scanner=lambda d: None, paypal=None)
        self.client = self.app.test_client()
        conn = sales_db.connect(f"{self.tmp}/quantum_saas.db")
        seed(conn)
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_weekly_domain_page_has_answer_history_and_links(self):
        res = self.client.get("/site/alpha.test?lang=en")
        self.assertEqual(res.status_code, 200)
        body = res.get_data(as_text=True)
        self.assertIn("Yes. As of 2026-11-02, alpha.test negotiates the hybrid post-quantum key exchange X25519MLKEM768", body)
        self.assertIn("weekly tracker", body)
        self.assertIn("2026-W44", body)            # السجل الأسبوعي
        self.assertIn("CLOUDFLARENET", body)       # الشبكة
        self.assertIn('href="/site/beta.test"', body)  # رابط داخلي لنطاق على الشبكة نفسها
        self.assertNotIn("/site/down.test", body)  # لم يُجب: لا رابط له
        self.assertIn('"FAQPage"', body)
        self.assertIn('"dateModified": "2026-11-02"', body)
        self.assertNotIn("noindex", body)

    def test_classical_and_undetermined_answers(self):
        self.assertIn("No. As of 2026-11-02, beta.test does not negotiate post-quantum key exchange",
                      self.client.get("/site/beta.test?lang=en").get_data(as_text=True))
        self.assertIn("could not determine whether gamma.test",
                      self.client.get("/site/gamma.test?lang=en").get_data(as_text=True))

    def test_unknown_domain_is_404_noindex(self):
        res = self.client.get("/site/wp-login.php")
        self.assertEqual(res.status_code, 404)
        self.assertIn("noindex", res.get_data(as_text=True))

    def test_related_links_skip_rank_neighbours_and_long_tail(self):
        body = self.client.get("/site/alpha.test?lang=en").get_data(as_text=True)
        self.assertIn('href="/site/beta.test"', body)
        self.assertNotIn("neighbour.test", body)
        self.assertNotIn("longtail.test", body)
        self.assertIn("<title>Does alpha.test use post-quantum TLS? (grade A)</title>", body)

    def test_long_tail_page_is_reachable_but_noindex_and_not_in_sitemap(self):
        res = self.client.get("/site/longtail.test?lang=en")
        self.assertEqual(res.status_code, 200)
        self.assertIn("noindex", res.headers["X-Robots-Tag"])
        self.assertIn('<meta name="robots" content="noindex', res.get_data(as_text=True))
        self.assertNotIn("longtail.test", self.client.get("/sitemap-sites-1.xml").get_data(as_text=True))

    def test_live_scan_alone_does_not_make_page_indexable(self):
        with self.app.test_request_context():
            self.assertFalse(quantum_saas_app.site_is_indexable("random-shop.test"))
            self.assertTrue(quantum_saas_app.site_is_indexable("alpha.test"))
            self.assertFalse(quantum_saas_app.site_is_indexable("longtail.test"))

    def test_last_modified_and_304(self):
        res = self.client.get("/site/alpha.test?lang=en")
        stamp = res.headers["Last-Modified"]
        self.assertEqual(stamp, "Mon, 02 Nov 2026 01:00:00 GMT")
        again = self.client.get("/site/alpha.test?lang=en", headers={"If-Modified-Since": stamp})
        self.assertEqual(again.status_code, 304)
        self.assertEqual(again.data, b"")
        older = self.client.get("/site/alpha.test?lang=en", headers={"If-Modified-Since": "Sun, 01 Nov 2026 00:00:00 GMT"})
        self.assertEqual(older.status_code, 200)

    def test_sitemap_includes_weekly_domains_with_scan_dates(self):
        index = self.client.get("/sitemap.xml").get_data(as_text=True)
        xml.dom.minidom.parseString(index)
        body = self.client.get("/sitemap-sites-1.xml").get_data(as_text=True)
        xml.dom.minidom.parseString(body)
        self.assertIn("<loc>https://ather-quantum.com/site/alpha.test?lang=en</loc><lastmod>2026-11-02</lastmod>", body)
        self.assertNotIn("down.test", body)
        self.assertEqual(body.count("/site/alpha.test?lang=en</loc>"), 1)

    def test_llms_full_has_guides_and_live_figures(self):
        body = self.client.get("/llms-full.txt").get_data(as_text=True)
        self.assertIn("Live adoption figures (week 2026-W45", body)
        self.assertIn("## 1. Check your OpenSSL version", body)
        self.assertIn("```", body)
        self.assertIn("https://ather-quantum.com/guides/harvest-now-decrypt-later", body)
        self.assertNotIn("<p>", body)
        self.assertIn("llms-full.txt", self.client.get("/robots.txt").get_data(as_text=True))
        self.assertIn("llms-full.txt", self.client.get("/llms.txt").get_data(as_text=True))

    def test_security_txt_and_touch_icon(self):
        for path in ("/.well-known/security.txt", "/security.txt"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertIn("Contact: mailto:", body)
            self.assertNotIn("<a", body)
            self.assertIn("Expires: ", body)
        icon = self.client.get("/apple-touch-icon.png")
        self.assertEqual(icon.status_code, 200)
        self.assertEqual(icon.mimetype, "image/png")


if __name__ == "__main__":
    unittest.main()
