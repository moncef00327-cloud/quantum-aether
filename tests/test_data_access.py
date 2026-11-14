import csv
import io
import os
import shutil
import tempfile
import unittest
from contextlib import closing
from unittest import mock

import adoption
import data_access
import quantum_saas_app
import sales_db


def nx(name, qtype=2, ns="1.1.1.1"):
    return 3


class DataAccessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp, "TRUSTED_PROXIES": 0,
                                                "RATE_LIMIT_ENABLED": True},
                                               scanner=lambda d: (_ for _ in ()).throw(AssertionError("no scans")))
        self.client = self.app.test_client()
        with closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db"))) as c:
            adoption.init(c)
            for week, pq in (("2026-W45", 0), ("2026-W46", 1)):
                for i, dom in enumerate(("bank.example", "shop.example", "news.example")):
                    c.execute("INSERT INTO adoption_results (week, domain, rank, ok, grade, grp, tls, pq, scanned_at, as_name, asn) "
                              "VALUES (?, ?, ?, 1, 'A', 'X25519MLKEM768', 'TLSv1.3', ?, ?, 'NET', 13335)",
                              (week, dom, i + 1, pq, adoption.week_monday(week).isoformat() + "T04:00:00+00:00"))
            c.commit()
        data_access._VERIFY_CACHE.clear()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db")))

    def burst(self, path, n, **kw):
        codes = [self.client.get(path, **kw).status_code for _ in range(n)]
        return codes

    def test_burst_gets_429_with_retry_after(self):
        codes = self.burst("/exposure/bank.example", 61, environ_base={"REMOTE_ADDR": "203.0.113.9"})
        self.assertEqual(codes[:60].count(429), 0)
        self.assertEqual(codes[60], 429)
        r = self.client.get("/exposure/bank.example", environ_base={"REMOTE_ADDR": "203.0.113.9"})
        self.assertTrue(1 <= int(r.headers["Retry-After"]) <= 60)
        # another visitor is unaffected; sitemaps, MCP and pages outside the guard are never limited
        self.assertEqual(self.client.get("/exposure/bank.example", environ_base={"REMOTE_ADDR": "203.0.113.10"}).status_code, 200)
        self.assertEqual(self.client.get("/sitemap.xml", environ_base={"REMOTE_ADDR": "203.0.113.9"}).status_code, 200)
        self.assertNotEqual(self.client.get("/robots.txt", environ_base={"REMOTE_ADDR": "203.0.113.9"}).status_code, 429)

    def test_rotating_addresses_in_one_subnet_are_capped(self):
        codes = [self.client.get("/exposure/bank.example", environ_base={"REMOTE_ADDR": f"203.0.113.{i % 50 + 1}"}).status_code
                 for i in range(245)]
        self.assertEqual(codes[:240].count(429), 0)
        self.assertIn(429, codes[240:])

    def test_api_429_is_json(self):
        for _ in range(60):
            self.client.get("/api/v1/exposure/bank.example", environ_base={"REMOTE_ADDR": "198.51.100.7"})
        r = self.client.get("/api/v1/exposure/bank.example", environ_base={"REMOTE_ADDR": "198.51.100.7"})
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.get_json()["error"], "rate_limited")

    def test_verified_googlebot_not_limited_but_spoofed_ua_is(self):
        ua = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
        with mock.patch.object(data_access, "_rdns_verified", side_effect=lambda ip, suf, timeout=2.0: ip == "66.249.66.1"):
            codes = self.burst("/exposure/bank.example", 200, headers=ua, environ_base={"REMOTE_ADDR": "66.249.66.1"})
            self.assertNotIn(429, codes)
            spoof = self.burst("/exposure/bank.example", 130, headers=ua, environ_base={"REMOTE_ADDR": "192.0.2.50"})
            self.assertIn(429, spoof)  # claimed bot from a non-Google IP: elevated but bounded
            self.assertEqual(spoof[:120].count(429), 0)

    def test_published_ranges_verify_ai_crawler(self):
        os.makedirs(self.tmp, exist_ok=True)
        rep = data_access.refresh_ranges(self.tmp, fetch=lambda url: b'{"prefixes":[{"ipv4Prefix":"20.171.206.0/24"}]}')
        self.assertEqual(rep["openai"], 1)
        self.assertTrue(data_access.verify_bot("20.171.206.5", "openai", self.tmp, rdns=lambda *a: False))
        self.assertFalse(data_access.verify_bot("192.0.2.1", "openai", self.tmp, rdns=lambda *a: False))

    def test_api_key_full_history_export_and_canaries(self):
        with self.conn() as c:
            key = data_access.create_key(c, "test licensee")
            data_access.generate_canaries(c, count=6, rcode=nx)
            pool = set(data_access.active_canaries(c))
        self.assertEqual(len(pool), 6)
        self.assertEqual(self.client.get("/api/v1/registry/export.csv").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/exposure/bank.example?history=full").status_code, 401)
        auth = {"Authorization": f"Bearer {key}"}
        self.assertEqual(self.client.get("/api/v1/exposure/bank.example?history=full", headers=auth).status_code, 200)
        body = self.client.get("/api/v1/registry/export.csv", headers=auth).get_data(as_text=True)
        domains = [r["domain"] for r in csv.DictReader(io.StringIO(body))]
        marked = [d for d in domains if d in pool]
        self.assertEqual(len(marked), 4)  # 2 per week
        with self.conn() as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM data_canary_log WHERE export='registry_export'").fetchone()[0], 2)
        # canaries never get a public page, and key holders get higher limits
        self.assertEqual(self.client.get(f"/exposure/{marked[0]}").status_code, 404)
        codes = self.burst("/api/v1/exposure/bank.example", 80, headers=auth)
        self.assertNotIn(429, codes)

    def test_open_csv_marked_per_client_and_counts_unchanged(self):
        with self.conn() as c:
            data_access.generate_canaries(c, count=8, rcode=nx)
            pool = set(data_access.active_canaries(c))
        a = self.client.get("/adoption.csv", environ_base={"REMOTE_ADDR": "203.0.113.1"}).get_data(as_text=True)
        rows = list(csv.DictReader(io.StringIO(a)))
        self.assertEqual(len([r for r in rows if r["domain"] in pool]), 2)
        js = self.client.get("/adoption.json", environ_base={"REMOTE_ADDR": "203.0.113.1"}).get_json()
        self.assertEqual(js["license"], "CC BY 4.0")
        self.assertEqual(js["reachable"], 3)  # stats ignore canaries
        page = self.client.get("/adoption").get_data(as_text=True)
        self.assertFalse(any(d in page for d in pool))

    def test_terms_page_languages(self):
        for lang, word in (("en", "96/9/EC"), ("de", "96/9/EG"), ("ar", "96/9/EC")):
            r = self.client.get(f"/data-license?lang={lang}")
            self.assertEqual(r.status_code, 200)
            self.assertIn(word, r.get_data(as_text=True))
            self.assertIn("OpenTimestamps", r.get_data(as_text=True))
        self.assertIn("/data-license", self.client.get("/sitemap-pages.xml").get_data(as_text=True))

    def test_canary_generation_skips_registered_names(self):
        with self.conn() as c:
            self.assertEqual(data_access.generate_canaries(c, count=3, rcode=lambda *a: 0), 0)
            data_access.generate_canaries(c, count=3, rcode=nx)
            self.assertEqual(len(data_access.recheck_canaries(c, rcode=lambda *a: 0)), 3)
            self.assertEqual(data_access.active_canaries(c), [])


if __name__ == "__main__":
    unittest.main()
