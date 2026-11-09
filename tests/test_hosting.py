"""Readiness by hosting network: page, JSON, FAQ answer, sitemap, languages."""
import json
import shutil
import tempfile
import unittest

import quantum_saas_app
import sales_db


def seed(conn):
    rows = []
    for i in range(25):  # CDN: 24/25 ready
        rows.append(("2026-W45", f"cdn{i}.test", 100 + i, 1, "A" if i else "B", "X25519MLKEM768", "TLSv1.3", int(i > 0), 0, 13335, "Cloudflare, Inc."))
    for i in range(20):  # VPS host: 4/20 ready
        rows.append(("2026-W45", f"vps{i}.test", 200 + i, 1, "A" if i < 4 else "B", "X25519", "TLSv1.3", int(i < 4), 0, 24940, "Hetzner Online GmbH"))
    for i in range(5):   # too small to list
        rows.append(("2026-W45", f"tiny{i}.test", 300 + i, 1, "A", "X25519MLKEM768", "TLSv1.3", 1, 0, 64512, "Tiny Net"))
    with conn:
        conn.executemany("INSERT INTO adoption_results (week, domain, rank, ok, grade, grp, tls, pq, unsure, asn, as_name, scanned_at) "
                         "VALUES (?,?,?,?,?,?,?,?,?,?,?, '2026-11-02T01:00:00Z')", rows)


class HostingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quantum.com", "HASH_SALT": "s"},
            scanner=lambda d: None, paypal=None)
        self.client = self.app.test_client()
        conn = sales_db.connect(f"{self.tmp}/quantum_saas.db")
        seed(conn)
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_page_lists_networks_with_shares_and_faq(self):
        body = self.client.get("/adoption/hosting?lang=en").get_data(as_text=True)
        self.assertIn("<title>Which hosting providers and CDNs support post-quantum TLS?", body)
        self.assertIn("Cloudflare, Inc.", body)
        self.assertIn("96.0%", body)
        self.assertIn("20.0%", body)
        self.assertNotIn("Tiny Net", body)
        self.assertIn('"FAQPage"', body)
        self.assertIn("Cloudflare, Inc. (AS13335, 96.0%)", body)
        self.assertNotIn("noindex", body)

    def test_languages_and_json(self):
        for lang in ("ar", "de"):
            self.assertEqual(self.client.get(f"/adoption/hosting?lang={lang}").status_code, 200)
        data = self.client.get("/adoption/hosting.json").get_json()
        self.assertEqual(data["license"], "CC BY 4.0")
        self.assertEqual({r["asn"] for r in data["rows"]}, {13335, 24940})

    def test_sitemap_and_adoption_link(self):
        self.assertIn("/adoption/hosting?lang=de", self.client.get("/sitemap-pages.xml").get_data(as_text=True))
        self.assertIn("/adoption/hosting?lang=en", self.client.get("/adoption?lang=en").get_data(as_text=True))

    def test_404_without_data(self):
        empty = tempfile.mkdtemp()
        try:
            app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": empty, "PUBLIC_URL": "https://ather-quantum.com",
                                               "HASH_SALT": "s"}, scanner=lambda d: None, paypal=None)
            self.assertEqual(app.test_client().get("/adoption/hosting").status_code, 404)
        finally:
            shutil.rmtree(empty)


if __name__ == "__main__":
    unittest.main()
