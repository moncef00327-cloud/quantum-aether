import unittest

import guides
import quantum_saas_app


class ContentPagesTest(unittest.TestCase):
    def setUp(self):
        app = quantum_saas_app.create_app({"TESTING": True, "PUBLIC_URL": "https://example.test"},
                                          scanner=lambda d: {}, paypal=None)
        self.client = app.test_client()

    def test_every_guide_renders_in_both_languages(self):
        for slug, g in guides.GUIDES.items():
            for lang in ("en", "ar"):
                r = self.client.get(f"/guides/{slug}?lang={lang}")
                self.assertEqual(r.status_code, 200, (slug, lang))
                self.assertIn(g[lang]["title"], r.get_data(as_text=True))

    def test_unknown_guide_is_404(self):
        self.assertEqual(self.client.get("/guides/missing").status_code, 404)

    def test_study_page_and_data(self):
        page = self.client.get("/study/top-1000-post-quantum-tls?lang=en").get_data(as_text=True)
        data = self.client.get("/study/top-1000-post-quantum-tls.json").get_json()
        self.assertIn(f"{data['pq']} (", page)
        self.assertEqual(len(data["sites"]), data["reachable"])

    def test_sitemap_lists_content(self):
        body = self.client.get("/sitemap.xml").get_data(as_text=True)
        self.assertIn("https://example.test/study/top-1000-post-quantum-tls?lang=ar", body)
        for slug in guides.GUIDES:
            self.assertIn(f"/guides/{slug}?lang=en", body)


if __name__ == "__main__":
    unittest.main()
