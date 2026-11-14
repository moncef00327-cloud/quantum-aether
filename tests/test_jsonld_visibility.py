"""Batch 4 (2026-11-14): JSON-LD on /press, /guides, guide pages, country pages; Organization sameAs on home."""
import json
import tempfile
import unittest

import quantum_saas_app
import sales_db
from tests.test_countries import seed as seed_countries
from tests.test_dataset_jsonld import JsonLdScripts, objects

SAME = {"https://github.com/moncef00327-cloud/quantum-aether", "https://pypi.org/project/quantum-aether-mcp/",
        "https://github.com/marketplace/actions/post-quantum-tls-check-quantum-aether"}


class VisibilityJsonLdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name,
                                                "PUBLIC_URL": "https://ather-quantum.com"})
        self.client = self.app.test_client()
        self.conn = sales_db.connect(self.tmp.name + "/quantum_saas.db")
        seed_countries(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def docs(self, path):
        r = self.client.get(path)
        self.assertEqual(r.status_code, 200, path)
        p = JsonLdScripts()
        p.feed(r.get_data(as_text=True))
        self.assertTrue(p.documents, path)
        for d in p.documents:
            json.dumps(d)
            self.assertEqual(d["@context"], "https://schema.org")
        return [o for d in p.documents for o in objects(d)]

    def test_home_organization_has_same_as(self):
        for lang in ("en", "ar", "de"):
            objs = self.docs(f"/?lang={lang}")
            org = next(o for o in objs if o.get("@type") == "Organization" and o.get("sameAs"))
            self.assertTrue(SAME <= set(org["sameAs"]))
            self.assertNotIn("quatum", json.dumps(objs))
            site = next(o for o in objs if o.get("@type") == "WebSite")
            self.assertTrue(SAME <= set(site["sameAs"]))

    def test_press_guides_guide(self):
        press = self.docs("/press?lang=en")
        self.assertIn("WebPage", [o.get("@type") for o in press])
        idx = self.docs("/guides?lang=ar")
        coll = next(o for o in idx if o.get("@type") == "CollectionPage")
        items = coll["mainEntity"]["itemListElement"]
        self.assertGreater(len(items), 3)
        self.assertTrue(all(i["item"]["@type"] == "TechArticle" and i["item"]["url"].startswith("https://ather-quantum.com/guides/")
                            for i in items))
        slug = items[0]["item"]["url"].split("/guides/")[1].split("?")[0]
        art = next(o for o in self.docs(f"/guides/{slug}?lang=en") if o.get("@type") == "TechArticle")
        self.assertTrue(SAME <= set(art["publisher"]["sameAs"]))

    def test_country_dataset(self):
        code = self.client.get("/adoption/countries.json").get_json()["entries"][0]["code"]
        objs = self.docs(f"/adoption/countries/{code}?lang=en")
        ds = next(o for o in objs if o.get("@type") == "Dataset" and "spatialCoverage" in o)
        self.assertGreaterEqual(len(ds["description"]), 50)
        self.assertEqual(ds["license"], "https://creativecommons.org/licenses/by/4.0/")
        self.assertEqual(ds["creator"]["@type"], "Organization")
        self.assertEqual(ds["isPartOf"]["license"], "https://creativecommons.org/licenses/by/4.0/")


if __name__ == "__main__":
    unittest.main()
