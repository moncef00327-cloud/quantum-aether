import tempfile
import unittest

import quantum_saas_app
import search_indexing

SLUG = "nis2-dora-post-quantum-cryptography"


class Nis2GuideTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name}).test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_three_languages_with_hreflang(self):
        for lang, needle in (("en", "Article 21(2)(h)"), ("ar", "المادة 21(2)(h)"), ("de", "§ 30 BSIG")):
            body = self.client.get(f"/guides/{SLUG}?lang={lang}").get_data(as_text=True)
            self.assertIn(needle, body)
            self.assertIn(f'<html lang="{lang}"', body)
        body = self.client.get(f"/guides/{SLUG}?lang=en").get_data(as_text=True)
        self.assertIn(f'hreflang="de" href="http://localhost/guides/{SLUG}?lang=de"'.split(' href')[0], body)

    def test_german_only_where_translated(self):
        body = self.client.get("/guides/harvest-now-decrypt-later?lang=de").get_data(as_text=True)
        self.assertIn('<html lang="en"', body)
        self.assertNotIn('hreflang="de"', body)

    def test_sitemap_lists_german_version(self):
        body = self.client.get("/sitemap-pages.xml").get_data(as_text=True)
        self.assertIn(f"/guides/{SLUG}?lang=de", body)
        self.assertNotIn("/guides/harvest-now-decrypt-later?lang=de", body)

    def test_onlyfans_not_indexable(self):
        self.assertTrue(search_indexing.is_excluded("onlyfans.com"))
        self.assertFalse(search_indexing.is_indexable("onlyfans.com", rank=830))


if __name__ == "__main__":
    unittest.main()
