"""Fixes from the 2026-11-18 OpenSEO audit: /analytics?lang=de must really be German (it is advertised as de in
hreflang and the sitemap), and /gravity must have a distinct <title> per language."""
import re
import tempfile
import unittest

import quantum_saas_app


class SeoAuditFixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name}).test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_analytics_german_is_german_with_self_canonical(self):
        body = self.client.get("/analytics?lang=de").get_data(as_text=True)
        self.assertIn('<html lang="de"', body)
        self.assertIn("PQC- und TLS-Lagebild", body)
        self.assertIn('<link rel="canonical" href="http://localhost/analytics?lang=de">', body)
        self.assertIn('hreflang="de"', body)

    def test_gravity_titles_differ_by_language(self):
        titles = {lang: re.search(r"<title>([^<]*)", self.client.get(f"/gravity?lang={lang}").get_data(as_text=True)).group(1)
                  for lang in ("en", "ar")}
        self.assertNotEqual(titles["en"], titles["ar"])
        self.assertIn("محرك اكتشاف الطلب التقني", titles["ar"])

    def test_arabic_brand_is_in_title_meta_body_and_jsonld(self):
        body = self.client.get("/?lang=ar").get_data(as_text=True)
        title = re.search(r"<title>([^<]*)</title>", body).group(1)
        desc = re.search(r'<meta name="description" content="([^"]*)"', body).group(1)
        self.assertIn("الأثير الكمومي", title)
        self.assertIn("الأثير الكمومي", desc)
        self.assertIn("كوانتوم أثير", desc)
        self.assertIn("الأثير الكمومي · Quantum Aether", body)
        self.assertIn('"alternateName"', body)
        for path in ("/business?lang=ar", "/pricing?lang=ar", "/agents?lang=ar", "/data-license?lang=ar"):
            page_title = re.search(r"<title>([^<]*)</title>", self.client.get(path).get_data(as_text=True)).group(1)
            self.assertIn("الأثير الكمومي", page_title, path)


if __name__ == "__main__":
    unittest.main()
