"""Crawler counter: counts declared crawlers per day/section, verified or not, and never stores IPs or URLs."""
import datetime as dt
import sqlite3
import tempfile
import unittest
from unittest import mock

import crawler_log
import quantum_saas_app

GOOGLE = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
BROWSER = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/147.0 Safari/537.36"


class CrawlerLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def rows(self):
        conn = sqlite3.connect(crawler_log.db_path(self.tmp.name))
        try:
            return conn.execute("SELECT family, verified, section, status, hits FROM crawler_hits ORDER BY section").fetchall()
        finally:
            conn.close()

    def test_counts_declared_crawlers_only_without_ip_or_url(self):
        with mock.patch("data_access.verify_bot", return_value=True):
            self.client.get("/guides/enable-x25519mlkem768-nginx?lang=en", headers={"User-Agent": GOOGLE})
            self.client.get("/guides/harvest-now-decrypt-later", headers={"User-Agent": GOOGLE})
            self.client.get("/llms.txt", headers={"User-Agent": GOOGLE})
            self.client.get("/", headers={"User-Agent": BROWSER})
        rows = self.rows()
        self.assertIn(("google", 1, "/guides/", 200, 2), rows)
        self.assertIn(("google", 1, "/llms.txt", 200, 1), rows)
        self.assertEqual(sum(r[4] for r in rows), 3)               # the browser visit is not counted
        cols = [c[1] for c in sqlite3.connect(crawler_log.db_path(self.tmp.name)).execute("PRAGMA table_info(crawler_hits)")]
        self.assertEqual(cols, ["day", "family", "verified", "section", "status", "hits"])

    def test_spoofed_crawler_is_kept_apart_from_verified_ones(self):
        with mock.patch("data_access.verify_bot", return_value=False):
            self.client.get("/", headers={"User-Agent": GOOGLE})
        s = crawler_log.summary(self.tmp.name)
        self.assertEqual(s["families"], [])
        self.assertEqual(s["unverified"], 1)

    def test_counter_failure_never_breaks_the_page(self):
        with mock.patch("data_access.verify_bot", side_effect=RuntimeError("dns down")):
            self.assertEqual(self.client.get("/", headers={"User-Agent": GOOGLE}).status_code, 200)

    def test_weekly_summary_compares_with_previous_week(self):
        today = dt.date(2026, 11, 23)
        for day, n in ((today, 5), (today - dt.timedelta(days=9), 2)):
            for _ in range(n):
                crawler_log.record(self.tmp.name, "bing", True, "/site/example.org", 200, day=day.isoformat())
        crawler_log.record(self.tmp.name, "bing", True, "/missing", 404, day=today.isoformat())
        s = crawler_log.summary(self.tmp.name, today=today)
        self.assertEqual(s["families"], [{"family": "bing", "hits": 6, "previous": 2}])
        self.assertEqual(s["errors"], 1)
        text = crawler_log.as_text(s)
        self.assertIn("bing", text)
        self.assertIn("+4", text)
        self.assertNotIn("example.org", text)                      # sections only, never the visited domain

    def test_sections_are_coarse(self):
        self.assertEqual(crawler_log.section_of("/site/example.org"), "/site/")
        self.assertEqual(crawler_log.section_of("/sitemap-sites-1.xml"), "sitemap*")
        self.assertEqual(crawler_log.section_of("/"), "/")
        self.assertEqual(crawler_log.section_of("/gravity"), "/gravity")
        self.assertEqual(crawler_log.section_of("/report/secret-token"), "/report/")


if __name__ == "__main__":
    unittest.main()
