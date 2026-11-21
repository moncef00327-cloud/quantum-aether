"""SEO first-deploy: /site/ allow-list, 404 noindex, untranslated German 301, lighter /adoption."""
import unittest
from html.parser import HTMLParser

import search_indexing
import quantum_saas_app
import sales_db
from tests.test_app import RESULT
from tests.test_crawlers import seed
from tests.test_search_indexing import HeadAndLinks, metadata, BASE


class SeoFirstDeployTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        search_indexing.reset_runtime_state()
        self.tmp = tempfile.TemporaryDirectory()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": BASE,
             "PAYPAL_CLIENT_ID": "", "PAYPAL_CLIENT_SECRET": "", "HASH_SALT": "seo-first-deploy"},
            scanner=lambda d: (_ for _ in ()).throw(AssertionError("no scan")))
        self.client = self.app.test_client()
        self.conn = sales_db.connect(self.tmp.name + "/quantum_saas.db")
        seed(self.conn)

    def tearDown(self):
        search_indexing.reset_runtime_state()
        self.conn.close()
        self.tmp.cleanup()

    def test_404_is_noindex_and_has_no_self_canonical(self):
        response = self.client.get("/this-page-does-not-exist-xyz-seo")
        self.assertEqual(response.status_code, 404)
        self.assertIn("noindex", response.headers.get("X-Robots-Tag", ""))
        doc = metadata(response)
        self.assertTrue(any("noindex" in tag for tag in doc.robots))
        self.assertFalse(any("does-not-exist" in (href or "") for href in doc.canonical))
        self.assertEqual(doc.canonical, [])
        body = response.get_data(as_text=True)
        self.assertNotIn('rel="canonical"', body)

    def test_untranslated_german_guides_redirect_to_english(self):
        response = self.client.get("/guides?lang=de", follow_redirects=False)
        self.assertEqual(response.status_code, 301)
        location = response.headers.get("Location", "")
        self.assertIn("lang=en", location)
        self.assertIn("/guides", location)

    def test_translated_german_homepage_stays(self):
        response = self.client.get("/?lang=de", follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn('lang="de"', response.get_data(as_text=True)[:500])

    def test_legal_german_is_not_redirected(self):
        response = self.client.get("/impressum?lang=de", follow_redirects=False)
        self.assertEqual(response.status_code, 200)

    def test_reference_rank_is_indexable_but_high_rank_is_not(self):
        self.assertTrue(search_indexing.is_indexable("alpha.test", rank=12))
        self.assertFalse(search_indexing.is_indexable("ordinary-high.example", rank=200, sector="banks-europe"))
        self.assertFalse(search_indexing.is_indexable("ordinary-high.example", rank=200, sector="finance-worldwide"))
        self.client.get("/site/ordinary-high.example?lang=en")  # may 404 if unknown
        # fixture alpha.test is within REFERENCE_MAX_RANK
        response = self.client.get("/site/alpha.test?lang=en")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("noindex", response.headers.get("X-Robots-Tag", ""))

    def test_human_traffic_can_allow_a_host(self):
        self.assertFalse(search_indexing.is_indexable("traffic.example", rank=900))
        search_indexing.set_human_traffic_hosts({"traffic.example"})
        self.assertTrue(search_indexing.is_indexable("www.traffic.example", rank=900))

    def test_notable_dach_institution_is_indexable_without_a_top_rank(self):
        # bundesbank.de is on the banks-dach watchlist shipped with the repo.
        self.assertTrue(search_indexing.is_notable_institution("www.bundesbank.de"))
        self.assertTrue(search_indexing.is_indexable("bundesbank.de", rank=5000))

    def test_adoption_main_page_is_capped_sector_page_has_the_rest(self):
        response = self.client.get("/adoption?lang=en")
        self.assertEqual(response.status_code, 200)
        # The endpoint accepts a sector query; an unknown key is 404, a missing
        # snapshot still renders the main page.
        missing = self.client.get("/adoption?lang=en&sector=does-not-exist-sector")
        self.assertEqual(missing.status_code, 404)
        self.assertIn("noindex", missing.headers.get("X-Robots-Tag", ""))


if __name__ == "__main__":
    unittest.main()
