"""Discovery coverage (2026-11-14): every published section reaches the Atom feed and llms.txt, not only the sitemap."""
import re
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET

import guides
import quantum_saas_app
from tests.test_monitor import PLAN_IDS, FakeMailer, FakePayPal

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
ATOM = "{http://www.w3.org/2005/Atom}"


class IndexListingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PAYPAL_CLIENT_ID": "cid",
             "OWNER_EMAIL": "owner@example.com", "PUBLIC_URL": "https://ather-quantum.com",
             "HASH_SALT": "s", **PLAN_IDS},
            scanner=lambda raw: None, paypal=FakePayPal(), mailer=FakeMailer())
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_feed_lists_new_sections_with_valid_dates(self):
        r = self.client.get("/feed.xml", headers=UA)
        self.assertEqual(r.status_code, 200)
        root = ET.fromstring(r.data)
        links = [e.find(ATOM + "link").get("href") for e in root.findall(ATOM + "entry")]
        for path in ("/banks/arab-banks-2026-11", "/adoption/dach-hosting", "/exposure", "/tools/pq-tls-config",
                     "/audit", "/prooflab"):
            self.assertIn("https://ather-quantum.com" + path, links)
        self.assertEqual(len(links), len(set(links)))
        for e in root.findall(ATOM + "entry"):
            self.assertRegex(e.find(ATOM + "updated").text, r"^\d{4}-\d{2}-\d{2}T00:00:00Z$")
            self.assertTrue(e.find(ATOM + "summary").text)

    def test_llms_txt_lists_every_guide_and_new_section(self):
        r = self.client.get("/llms.txt", headers=UA)
        self.assertEqual(r.status_code, 200)
        text = r.get_data(as_text=True)
        for slug in guides.GUIDES:
            self.assertIn(f"https://ather-quantum.com/guides/{slug}?", text)
        for path in ("/banks/arab-banks-2026-11?", "/banks/arab-banks-2026-11.json", "/adoption/dach-hosting?",
                     "/tools/pq-tls-config?", "/audit?", "/prooflab?", "/press?", "/exposure?"):
            self.assertIn("https://ather-quantum.com" + path, text)
        self.assertNotIn("{{", text)
        self.assertIsNone(re.search(r"\n- [^\n]*— \s*\(", text))  # no entry with an empty title


if __name__ == "__main__":
    unittest.main()
