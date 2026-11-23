"""GSC fixes (2026-11-23): Product JSON-LD image/brand, bare /index and /pricing
canonicals, English-only country-detail sitemap entries, noindex on utility endpoints."""
import json
import tempfile
import unittest

import quantum_saas_app
from tests.test_dataset_jsonld import JsonLdScripts, objects


def _docs(client, path, status=200):
    r = client.get(path)
    assert r.status_code == status, (path, r.status_code)
    parser = JsonLdScripts()
    parser.feed(r.get_data(as_text=True))
    for doc in parser.documents:
        json.dumps(doc)
        assert doc["@context"] == "https://schema.org"
    return r, [obj for doc in parser.documents for obj in objects(doc)]


class GscFixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://ather-quantum.com"}
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def _product(self, path):
        response, objs = _docs(self.client, path)
        product = next(obj for obj in objs if obj.get("@type") == "Product")
        return response, product

    def test_audit_and_agency_product_jsonld(self):
        for path in ("/audit?lang=en", "/agency?lang=en"):
            _response, product = self._product(path)
            self.assertEqual(product["image"], "https://ather-quantum.com/og/default.png", path)
            self.assertTrue(product["image"].startswith("https://"), path)
            self.assertEqual(product["brand"], {"@type": "Brand", "name": "Quantum Aether"}, path)
            self.assertNotEqual(product["brand"].get("@type"), "Organization", path)
            self.assertNotIn("aggregateRating", product, path)
            self.assertNotIn("review", product, path)
            offer = product["offers"]
            if isinstance(offer, list):
                offer = offer[0]
            self.assertEqual(offer["@type"], "Offer", path)
            self.assertNotIn("hasMerchantReturnPolicy", offer, path)
            self.assertNotIn("shippingDetails", offer, path)

    def test_index_and_pricing_are_indexable_self_canonical(self):
        for path, canonical in (
            ("/index", "https://ather-quantum.com/index"),
            ("/index?lang=en", "https://ather-quantum.com/index"),
            ("/pricing", "https://ather-quantum.com/pricing"),
            ("/pricing?lang=en", "https://ather-quantum.com/pricing"),
        ):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertNotIn("noindex", r.headers.get("X-Robots-Tag", ""), path)
            body = r.get_data(as_text=True)
            self.assertNotIn('name="robots" content="noindex', body, path)
            self.assertIn(f'rel="canonical" href="{canonical}"', body, path)
            self.assertIn(f'hreflang="en" href="{canonical}"', body, path)
            self.assertIn('hreflang="x-default" href="' + canonical + '"', body, path)

        de = self.client.get("/index?lang=de")
        self.assertEqual(de.status_code, 200)
        self.assertIn('rel="canonical" href="https://ather-quantum.com/index?lang=de"', de.get_data(as_text=True))

        sitemap = self.client.get("/sitemap-pages.xml").get_data(as_text=True)
        self.assertIn("<loc>https://ather-quantum.com/index</loc>", sitemap)
        self.assertIn("<loc>https://ather-quantum.com/pricing</loc>", sitemap)
        self.assertNotIn("<loc>https://ather-quantum.com/index?lang=en</loc>", sitemap)
        self.assertNotIn("<loc>https://ather-quantum.com/pricing?lang=en</loc>", sitemap)
        self.assertIn("<loc>https://ather-quantum.com/index?lang=de</loc>", sitemap)
        self.assertIn("<loc>https://ather-quantum.com/pricing?lang=de</loc>", sitemap)

        home = self.client.get("/?lang=en").get_data(as_text=True)
        footer = self.client.get("/audit?lang=en").get_data(as_text=True)
        self.assertIn("/index", home)
        self.assertIn("/pricing", home)
        self.assertIn("/pricing", footer)
        self.assertIn("/index", footer)

    def test_utility_endpoints_send_noindex_and_stay_out_of_sitemap(self):
        for path in (
            "/verify/otter.ai/qa_report.json",
            "/install-agent.sh",
            "/install-agent.sh?domain=unm.edu",
        ):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            self.assertIn("noindex", r.headers.get("X-Robots-Tag", ""), path)

        sitemap = self.client.get("/sitemap-pages.xml").get_data(as_text=True)
        index = self.client.get("/sitemap.xml").get_data(as_text=True)
        for text in (sitemap, index):
            self.assertNotIn("/verify/", text)
            self.assertNotIn("install-agent.sh", text)
            self.assertNotIn("qa_report.json", text)


if __name__ == "__main__":
    unittest.main()
