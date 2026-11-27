"""Tests for tools/x_autopost.py (RFC 5849 OAuth 1.0a signing, 280-char templates, daily idempotency)."""
import datetime as dt
import os
import sqlite3
import tempfile
import unittest

from tools import x_autopost as xa


class XAutopostTests(unittest.TestCase):
    def test_all_four_daily_variants_fit_280_chars(self):
        summary = {"measured": 150, "pq_hybrid": 115, "pq_pct": 76.7, "classical": 30, "tls12": 5}
        seen = set()
        for offset in range(4):
            day = dt.date(2026, 11, 27) + dt.timedelta(days=offset)
            t = xa.build_daily_tweet(summary, day)
            self.assertLessEqual(len(t), 280, f"day {day} len={len(t)}")
            self.assertIn("https://", t)
            seen.add(t)
        self.assertEqual(len(seen), 4)

    def test_oauth1_header_structure(self):
        creds = {
            "api_key": "k_test",
            "api_secret": "s_test",
            "access_token": "t_test",
            "access_token_secret": "ts_test",
        }
        h = xa.oauth1_header("POST", xa.TWEETS_URL, creds, nonce="abc123", timestamp="1700000000")
        self.assertTrue(h.startswith("OAuth "))
        for part in ('oauth_consumer_key="k_test"', 'oauth_token="t_test"', 'oauth_signature_method="HMAC-SHA1"', 'oauth_signature="'):
            self.assertIn(part, h)

    def test_missing_creds_exits_cleanly_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = xa.main(["--post", "--creds", os.path.join(tmp, "missing.json"), "--db", os.path.join(tmp, "t.db")])
            self.assertEqual(rc, 0)

    def test_daily_idempotency(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        xa.init_db(conn)
        self.assertFalse(xa.already_posted_today(conn, "2026-11-27"))
        xa.record_post(conn, "daily_post", "2026-11-27", "tweet_id=123")
        self.assertTrue(xa.already_posted_today(conn, "2026-11-27"))


if __name__ == "__main__":
    unittest.main()
