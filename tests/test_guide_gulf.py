import re
import tempfile
import unittest

import quantum_saas_app

SLUG = "gulf-banks-post-quantum-cryptography-requirements"


class GulfGuideTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name}).test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_arabic_and_english_with_hreflang(self):
        for lang, needle in (("ar", "التعميم رقم 482021280"), ("en", "circular No. 482021280")):
            res = self.client.get(f"/guides/{SLUG}?lang={lang}")
            self.assertEqual(res.status_code, 200)
            body = res.get_data(as_text=True)
            self.assertIn(needle, body)
            self.assertIn("2-5-5-1", body)
            self.assertIn(f'<html lang="{lang}"', body)
            self.assertIn('hreflang="ar"', body)
            self.assertIn('hreflang="en"', body)

    def test_internal_links_resolve(self):
        body = self.client.get(f"/guides/{SLUG}?lang=ar").get_data(as_text=True)
        article = body[body.find("<h1"):]
        links = set(re.findall(r'href="(/[^"#]*)"', article))
        self.assertGreater(len(links), 5)
        for link in links:
            self.assertEqual(self.client.get(link).status_code, 200, link)

    def test_listed_in_sitemap(self):
        body = self.client.get("/sitemap-pages.xml").get_data(as_text=True)
        self.assertIn(f"/guides/{SLUG}?lang=ar", body)
        self.assertIn(f"/guides/{SLUG}?lang=en", body)


if __name__ == "__main__":
    unittest.main()
