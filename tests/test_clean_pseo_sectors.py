"""Clean programmatic SEO: curated commercial sectors (2.5x+ indexable B2B brands, zero adult/gambling) + /adoption/sector/<key> hubs."""
import json
import re
import tempfile
import unittest

import quantum_saas_app
import sales_db
import search_indexing


JSONLD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


class CleanProgrammaticSeoTests(unittest.TestCase):
    def setUp(self):
        search_indexing.reset_runtime_state()
        self.tmp = tempfile.TemporaryDirectory()
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://ather-quantum.com"})
        self.client = self.app.test_client()
        self.conn = sales_db.connect(self.tmp.name + "/quantum_saas.db")
        with self.conn:
            for dom, sec, pq, g, grp in (
                ("www.paypal.com", "payments-fintech", 0, "B", "x25519"),
                ("stripe.com", "payments-fintech", 1, "A", "X25519MLKEM768"),
                ("www.coinbase.com", "crypto-exchanges", 1, "A", "X25519MLKEM768"),
                ("www.cloudflare.com", "cloud-security", 1, "A", "X25519MLKEM768"),
                ("www.alrajhibank.com.sa", "banks-mena", 0, "B", "x25519"),
            ):
                self.conn.execute(
                    "INSERT INTO adoption_results (week,domain,rank,ok,grade,grp,tls,pq,unsure,sector,scanned_at) "
                    "VALUES ('2026-W48',?,NULL,1,?,?,'TLSv1.3',?,0,?,'2026-11-23T04:00:00Z')",
                    (dom, g, grp, pq, sec),
                )

    def tearDown(self):
        search_indexing.reset_runtime_state()
        self.conn.close()
        self.tmp.cleanup()

    def test_expanded_notable_hosts_exceed_1000_and_have_zero_adult_or_excluded(self):
        hosts = search_indexing.notable_institution_hosts()
        self.assertGreaterEqual(len(hosts), 1000)
        for h in hosts:
            self.assertFalse(search_indexing.is_excluded(h), f"excluded host leaked: {h}")
            self.assertFalse(search_indexing.keyword_suspect(h), f"sensitive keyword leaked: {h}")
        for brand in ("paypal.com", "stripe.com", "coinbase.com", "cloudflare.com",
                      "salesforce.com", "alrajhibank.com.sa", "signal.org", "pqshield.com"):
            self.assertTrue(search_indexing.is_notable_institution(brand), brand)
            self.assertTrue(search_indexing.is_indexable(brand, rank=9999), brand)
        # Random Tranco high-rank hosts and adult hosts remain blocked
        self.assertFalse(search_indexing.is_indexable("random-unknown-site.example", rank=9999))
        self.assertFalse(search_indexing.is_indexable("besthindiporn.com", rank=1))

    def test_sector_hub_clean_route_jsonld_cta_and_sitemap(self):
        for lang in ("en", "ar", "de"):
            r = self.client.get(f"/adoption/sector/payments-fintech?lang={lang}")
            self.assertEqual(r.status_code, 200, lang)
            body = r.get_data(as_text=True)
            self.assertIn("stripe.com", body)
            self.assertIn("/site/stripe.com", body)
            self.assertIn("/monitoring/trial", body)
            types = {json.loads(b).get("@type") for b in JSONLD_RE.findall(body)}
            self.assertTrue({"Dataset", "FAQPage", "BreadcrumbList"}.issubset(types), (lang, types))
        sm = self.client.get("/sitemap-pages.xml").get_data(as_text=True)
        for lang in ("en", "ar", "de"):
            self.assertIn(f"https://ather-quantum.com/adoption/sector/payments-fintech?lang={lang}", sm)
        # Unknown sector returns 404
        self.assertEqual(self.client.get("/adoption/sector/does-not-exist?lang=en").status_code, 404)


if __name__ == "__main__":
    unittest.main()
