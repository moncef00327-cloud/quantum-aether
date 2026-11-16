"""Daily run: watch-list domains are scanned the day they are added, new or changed URLs reach IndexNow once."""
import datetime as dt
import json
import os
import tempfile
import unittest
from unittest import mock

import adoption
import adoption_job
import quantum_saas_app
import sales_db
from tests.test_adoption import result

TODAY = dt.date(2026, 11, 18)          # Wednesday of 2026-W47
WEEK = adoption.week_of(TODAY)


class DailyIndexingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name,
                                                "PUBLIC_URL": "https://ather-quantum.com"})
        self.conn = sales_db.connect(os.path.join(self.tmp.name, "quantum_saas.db"))
        self.posts = []

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def post(self, payload):
        self.posts.append(json.loads(payload)["urlList"])

    def add_row(self, domain, sector=None, rank=None, week=WEEK):
        target = {"domain": domain, "rank": rank, "sector": sector}
        adoption.record(self.conn, week, target, result(domain), f"{TODAY.isoformat()}T03:40:00+00:00", None)
        self.conn.commit()

    def sent(self):
        return [u for batch in self.posts for u in batch]

    def test_new_and_changed_urls_are_sent_once(self):
        self.add_row("example.org", rank=5)
        first = adoption_job.notify_new_urls(self.app, self.conn, post=self.post)
        urls = self.sent()
        self.assertEqual(first, len(urls))
        self.assertIn("https://ather-quantum.com/gravity?lang=ar", urls)
        self.assertIn("https://ather-quantum.com/site/example.org?lang=en", urls)
        self.assertIn("https://ather-quantum.com/", urls)

        self.posts.clear()
        self.assertEqual(adoption_job.notify_new_urls(self.app, self.conn, post=self.post), 0)
        self.assertEqual(self.posts, [])

        with self.app.test_request_context("/"):
            pages = quantum_saas_app._sitemap_pages()
        edited = [(p, "2099-01-01" if p == "/gravity" else d, langs) for p, d, langs in pages]
        with mock.patch.object(quantum_saas_app, "_sitemap_pages", return_value=edited):
            adoption_job.notify_new_urls(self.app, self.conn, post=self.post)
        self.assertEqual(sorted(self.sent()), ["https://ather-quantum.com/gravity?lang=ar",
                                               "https://ather-quantum.com/gravity?lang=en"])

    def test_llms_txt_lists_every_sitemap_page_automatically(self):
        client = self.app.test_client()
        llms = client.get("/llms.txt").get_data(as_text=True)
        with self.app.test_request_context("/"):
            paths = [p for p, _d, _l in quantum_saas_app._sitemap_pages()]
        listing = llms[llms.index("## Every public page"):]
        for path in paths:
            self.assertIn(f"https://ather-quantum.com{path}", listing, path)

    def test_weekly_notification_is_not_repeated_by_the_daily_run(self):
        self.add_row("example.org", rank=5)
        adoption_job.notify_indexnow(self.app, self.conn, WEEK, post=self.post)
        self.assertIn("https://ather-quantum.com/site/example.org?lang=ar", self.sent())
        self.posts.clear()
        adoption_job.notify_new_urls(self.app, self.conn, post=self.post)
        self.assertFalse([u for u in self.sent() if "/site/" in u])

    def test_failed_send_is_retried_next_day(self):
        def broken(payload):
            raise OSError("network down")
        self.assertEqual(adoption_job.notify_new_urls(self.app, self.conn, post=broken), 0)
        self.assertGreater(adoption_job.notify_new_urls(self.app, self.conn, post=self.post), 0)

    def test_catch_up_scans_only_new_or_resectored_watch_list_domains(self):
        self.add_row("example.org", rank=5)                       # Tranco site, now also in a sector
        self.add_row("old.example", sector="banks-dach")          # already scanned this week
        targets = [{"domain": "example.org", "rank": 5, "sector": "telecom"},
                   {"domain": "old.example", "rank": None, "sector": "banks-dach"},
                   {"domain": "new.example", "rank": None, "sector": "telecom"},
                   {"domain": "plain.example", "rank": 9, "sector": None}]
        scanned = []

        def scanner(domain):
            scanned.append(domain)
            return result(domain)
        with mock.patch.object(adoption, "load_targets", return_value=targets):
            n = adoption_job.catch_up_watchlists(self.app, self.conn, scanner=scanner, day=TODAY, asn_lookup=None)
        self.assertEqual(n, 2)
        self.assertEqual(sorted(scanned), ["example.org", "new.example"])
        rows = dict(self.conn.execute("SELECT domain, sector FROM adoption_results WHERE week = ?", (WEEK,)))
        self.assertEqual(rows["new.example"], "telecom")
        self.assertEqual(rows["example.org"], "telecom")
        rank = self.conn.execute("SELECT rank FROM adoption_results WHERE week = ? AND domain = 'example.org'",
                                 (WEEK,)).fetchone()[0]
        self.assertEqual(rank, 5)

    def test_catch_up_waits_for_the_weekly_scan(self):
        self.add_row("old.example", sector="banks-dach", week=adoption.week_of(TODAY - dt.timedelta(days=7)))
        with mock.patch.object(adoption, "load_targets",
                               return_value=[{"domain": "new.example", "rank": None, "sector": "telecom"}]):
            n = adoption_job.catch_up_watchlists(self.app, self.conn, scanner=lambda d: self.fail(d), day=TODAY,
                                                 asn_lookup=None)
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
