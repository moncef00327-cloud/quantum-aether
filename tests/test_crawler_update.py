"""Crawlers and AI agents see the free trial, every-address checks and the check history."""
import json
import re
import shutil
import tempfile
import unittest

import quantum_saas_app
from tests.test_app import fake_scanner


class CrawlerUpdateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.client = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quantum.com"},
                                                  scanner=fake_scanner).test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_monitoring_title_description_and_offers(self):
        for lang, word in (("en", "free trial"), ("ar", "تجربة مجانية"), ("de", "kostenlos")):
            html = self.client.get(f"/monitoring?lang={lang}").get_data(as_text=True)
            title = re.search(r"<title>([^<]*)</title>", html).group(1)
            self.assertIn(word.lower(), title.lower())
            desc = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
            self.assertIn("14", desc)
            ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
            self.assertEqual(ld["@type"], "Service")
            self.assertEqual([o["price"] for o in ld["offers"]], ["0", "29.00", "99.00"])

    def test_llms_feed_and_manifest(self):
        llms = self.client.get("/llms.txt").get_data(as_text=True)
        for phrase in ("Free trial: 14 days", "IPv4/IPv6 address", "CSV export"):
            self.assertIn(phrase, llms)
        self.assertIn("Free trial: 14 days", self.client.get("/llms-full.txt").get_data(as_text=True))
        self.assertIn("free 14-day monitoring trial", self.client.get("/feed.xml").get_data(as_text=True))
        m = self.client.get("/.well-known/agent-service.json").get_json()
        self.assertIn("all_address_observation", m["capabilities"])
        self.assertEqual(m["pricing"]["monitoring"]["free_trial_days"], 14)


if __name__ == "__main__":
    unittest.main()
