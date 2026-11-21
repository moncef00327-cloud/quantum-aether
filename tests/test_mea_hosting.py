"""Arab world + Africa hosting study page (2026-11-21): aggregates only, ar/en, correction form, listings."""
import json
import os
import tempfile
import unittest
from unittest.mock import Mock

import quantum_saas_app
from tests.test_app import RESULT

DATA = {
    "generated_utc": "2026-11-21T03:00:00+00:00", "source": "Tranco top 100k (list GQ38K)", "min_sites": 5, "max_sites": 10,
    "buckets": {"arab": {"global_cdn_cloud": 142, "local_host": 175}, "africa": {"global_cdn_cloud": 416, "local_host": 251}},
    "rounds": [{"round": n, "started_utc": f"2026-11-21T0{n}:00:00+00:00", "finished_utc": f"2026-11-21T0{n}:05:00+00:00",
                "sites": 12} for n in (1, 2, 3)],
    "providers": [
        {"asn": 36947, "provider": "Telecom Algeria", "sites_found": 10, "countries": ["DZ"], "region": "arab", "measured": 6,
         "counts": {"pq": 0, "classical": 6, "mixed": 0, "undetermined": 0, "unreachable": 0, "variable": 0}, "graded": True,
         "pq_share": 0.0, "sites": [{"domain": "secret-customer.dz", "result": "classical"}]},
        {"asn": 37153, "provider": "Xneelo (Pty) Ltd", "sites_found": 8, "countries": ["ZA"], "region": "africa", "measured": 6,
         "counts": {"pq": 3, "classical": 1, "mixed": 0, "undetermined": 0, "unreachable": 2, "variable": 0}, "graded": False,
         "pq_share": None, "sites": []},
    ],
}


class MeaHostingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self.tmp.name, "mea.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DATA, f)
        os.environ["MEA_RESULTS"] = path
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://ather-quantum.com"},
                                               scanner=Mock(return_value=dict(RESULT)))
        self.client = self.app.test_client()

    def tearDown(self):
        os.environ.pop("MEA_RESULTS", None)
        self.tmp.cleanup()

    def test_page_ar_en_aggregates_only(self):
        en = self.client.get("/adoption/arab-africa-hosting?lang=en").get_data(as_text=True)
        self.assertIn("0 of 6 sites negotiate X25519MLKEM768 (0.0%)", en)
        self.assertIn("Insufficient data", en)
        self.assertIn("Telecom Algeria", en)
        self.assertNotIn("secret-customer.dz", en)
        ar = self.client.get("/adoption/arab-africa-hosting?lang=ar").get_data(as_text=True)
        self.assertIn("العالم العربي", ar)
        self.assertIn("الجزائر", ar)
        self.assertNotIn("secret-customer.dz", ar)

    def test_listed_in_sitemap_llms_and_feed(self):
        self.assertIn("/adoption/arab-africa-hosting", self.client.get("/llms.txt").get_data(as_text=True))
        self.assertIn("/adoption/arab-africa-hosting", self.client.get("/feed.xml").get_data(as_text=True))

    def test_correction_validates_provider(self):
        bad = self.client.post("/adoption/arab-africa-hosting/correction",
                               data={"provider": "Nope", "name": "A", "email": "a@example.com", "message": "hello there"})
        self.assertIn("error=invalid", bad.headers["Location"])
        ok = self.client.post("/adoption/arab-africa-hosting/correction",
                              data={"provider": "Telecom Algeria", "name": "A", "email": "a@example.com",
                                    "message": "we enabled it", "lang": "ar"})
        self.assertIn("sent=1", ok.headers["Location"])

    def test_404_without_results(self):
        os.environ["MEA_RESULTS"] = os.path.join(self.tmp.name, "missing.json")
        self.assertEqual(self.client.get("/adoption/arab-africa-hosting").status_code, 404)


if __name__ == "__main__":
    unittest.main()
