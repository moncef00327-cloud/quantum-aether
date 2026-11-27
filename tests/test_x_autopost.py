"""Tests for tools/x_autopost.py (OAuth 1.0a signing, 6 rotating <=280-char templates, slot idempotency, anti-loop replies)."""
import datetime as dt
import os
import sqlite3
import tempfile
import unittest

from tools import x_autopost as xa


class XAutopostTests(unittest.TestCase):
    def test_all_six_daily_variants_fit_280_chars(self):
        summary = {"measured": 152, "pq_hybrid": 120, "pq_pct": 78.9, "classical": 28, "tls12": 4}
        seen = set()
        for day_off in range(2):
            day = dt.date(2026, 11, 27) + dt.timedelta(days=day_off)
            for slot in range(3):
                t = xa.build_daily_tweet(summary, day, slot=slot)
                self.assertLessEqual(len(t), 280, f"day={day} slot={slot} len={len(t)}")
                self.assertIn("https://", t)
                self.assertIn("#AIAgents", t)
                seen.add(t)
        self.assertEqual(len(seen), 6)
        self.assertTrue(any("/.well-known/x402" in t for t in seen), "x402 discovery URL must not be truncated")
        for t in seen:
            self.assertNotIn("ather-quantum.com/mcp ", t, "use browser-friendly /agents instead of POST-only /mcp")
            self.assertNotIn("ather-quantum.com/api/v1/scan ", t, "avoid 400 bare /api/v1/scan link")

    def test_extract_urls(self):
        urls = xa.extract_urls("Check https://ather-quantum.com/mcp-index and https://ather-quantum.com/agents.")
        self.assertEqual(urls, ["https://ather-quantum.com/mcp-index", "https://ather-quantum.com/agents"])

    def test_mention_reply_variants_and_skip(self):
        r1 = xa.build_mention_reply("AxiomBot", "A signed scan receipt with timestamp would help")
        self.assertIsNotNone(r1)
        self.assertLessEqual(len(r1), 280)
        self.assertIn("jwks.json", r1)

        r2 = xa.build_mention_reply("boardyai", "agents paying per call with its own wallet")
        self.assertIsNotNone(r2)
        self.assertLessEqual(len(r2), 280)
        self.assertIn(".well-known/x402", r2)

        r3 = xa.build_mention_reply("ChenY390353", "@Aether_Quantum 点了关注，这成绩很亮眼")
        self.assertIsNotNone(r3)
        self.assertLessEqual(len(r3), 280)
        self.assertIn("感谢关注", r3)
        self.assertFalse(r3.startswith("@"), "X reply_to prepends @username automatically")

        self.assertIsNone(xa.build_mention_reply("spammer", "free airdrop giveaway"))

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

    def test_slot_idempotency_and_anti_loop(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        xa.init_db(conn)
        self.assertFalse(xa.already_posted_slot(conn, "2026-11-27", 0))
        xa.record_post(conn, "daily_post", "2026-11-27", "tweet_id=123")
        self.assertTrue(xa.already_posted_slot(conn, "2026-11-27", 0))
        self.assertFalse(xa.already_posted_slot(conn, "2026-11-27", 1))
        self.assertEqual(xa.posts_today_count(conn, "2026-11-27"), 1)

        self.assertFalse(xa.replied_author_recently(conn, "999", "boardyai", hours=24))
        xa.record_post(conn, "mention_reply", "m1", "replied @boardyai author_id=999 tweet_id=456")
        self.assertTrue(xa.replied_author_recently(conn, "999", "boardyai", hours=24))


if __name__ == "__main__":
    unittest.main()
