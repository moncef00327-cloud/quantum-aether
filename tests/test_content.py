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
        body = self.client.get("/sitemap-pages.xml").get_data(as_text=True)
        self.assertIn("https://example.test/study/top-1000-post-quantum-tls?lang=ar", body)
        for slug in guides.GUIDES:
            self.assertIn(f"/guides/{slug}?lang=en", body)


    def test_sample_report_is_public_full_report(self):
        for lang in ("en", "ar"):
            body = self.client.get(f"/sample-report?lang={lang}").get_data(as_text=True)
            self.assertIn("github.com", body)
            self.assertNotIn("noindex", body)
            self.assertIn("X25519MLKEM768", body)  # خطوات الإصلاح ظاهرة
            self.assertNotIn("DNA", body)
        self.assertIn("/sample-report?lang=en", self.client.get("/sitemap-pages.xml").get_data(as_text=True))

    def test_home_states_scan_limits_and_links_sample(self):
        body = self.client.get("/?lang=en").get_data(as_text=True)
        self.assertIn("What this scan does not cover", body)
        self.assertIn("/sample-report", body)
        self.assertNotIn("DNA", body)


    def test_atom_feed_and_opengraph(self):
        import xml.dom.minidom
        feed = self.client.get("/feed.xml")
        self.assertEqual(feed.status_code, 200)
        xml.dom.minidom.parseString(feed.get_data(as_text=True))
        self.assertIn("<entry>", feed.get_data(as_text=True))
        home = self.client.get("/?lang=en").get_data(as_text=True)
        self.assertIn('property="og:title"', home)
        self.assertIn('name="twitter:card"', home)
        self.assertIn('application/atom+xml', home)
        self.assertIn("/feed.xml", self.client.get("/robots.txt").get_data(as_text=True))



if __name__ == "__main__":
    unittest.main()
