import datetime as dt
import sqlite3
import unittest

import radar

SINCE = dt.datetime(2026, 11, 1, tzinfo=dt.timezone.utc)


class FakeMailer:
    enabled = True

    def __init__(self):
        self.sent = []

    def send(self, to, subject, text, html=None):
        self.sent.append((to, subject, text))
        return True


def fake_get(url):
    if "hn.algolia.com" in url:
        return {"hits": [
            {"objectID": "101", "title": "How do I enable X25519MLKEM768 on nginx?", "created_at": "2026-11-02T10:00:00Z"},
            {"objectID": "102", "title": "Quantum computing stocks rally", "created_at": "2026-11-02T11:00:00Z"},
        ]}
    if "api.stackexchange.com" in url and "serverfault" in url:
        return {"items": [{"link": "https://serverfault.com/q/1", "title": "Apache httpd ML-KEM groups not working",
                           "tags": ["apache", "tls"], "creation_date": 1793000000}]}
    if "api.stackexchange.com" in url:
        return {"items": []}
    if "api.github.com" in url:
        return {"items": [
            {"html_url": "https://github.com/x/y/issues/1", "title": "Bump openssl to 3.5 (adds MLKEM)", "body": "", "created_at": ""},
            {"html_url": "https://github.com/x/y/issues/2", "title": "Support X25519MLKEM768 in TLS config?",
             "body": "How can we enable the hybrid group on our nginx reverse proxy?", "created_at": ""},
        ]}
    raise AssertionError(url)


class RadarTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        radar.init(self.conn)
        self.mailer = FakeMailer()

    def test_finds_relevant_discussions_and_drafts_replies(self):
        out = radar.run(self.conn, self.mailer, "owner@example.com", SINCE, get=fake_get)
        self.assertEqual(out["errors"], [])
        urls = [r[0] for r in self.conn.execute("SELECT url FROM radar_seen ORDER BY url")]
        self.assertIn("https://news.ycombinator.com/item?id=101", urls)
        self.assertIn("https://serverfault.com/q/1", urls)
        self.assertIn("https://github.com/x/y/issues/2", urls)
        self.assertNotIn("https://news.ycombinator.com/item?id=102", urls)   # لا علاقة له بـ TLS
        self.assertNotIn("https://github.com/x/y/issues/1", urls)            # تحديث مكتبة آلي
        to, subject, text = self.mailer.sent[0]
        self.assertEqual(to, "owner@example.com")
        self.assertIn("ssl_ecdh_curve", text)            # مسودة nginx تبدأ بالإجابة
        self.assertIn("SSLOpenSSLConfCmd", text)         # مسودة apache
        self.assertIn("Disclosure", text)

    def test_never_repeats_and_stores_no_people(self):
        radar.run(self.conn, self.mailer, "owner@example.com", SINCE, get=fake_get)
        second = radar.run(self.conn, self.mailer, "owner@example.com", SINCE, get=fake_get)
        self.assertEqual(second["new"], 0)
        self.assertEqual(len(self.mailer.sent), 1)       # لا بريد إن لم يوجد جديد
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(radar_seen)")]
        self.assertEqual(cols, ["url", "source", "title", "topic", "found_at"])

    def test_one_failing_source_does_not_stop_the_rest(self):
        def flaky(url):
            if "api.github.com" in url:
                raise OSError("rate limited")
            return fake_get(url)
        out = radar.run(self.conn, self.mailer, "owner@example.com", SINCE, get=flaky)
        self.assertGreater(out["new"], 0)
        self.assertTrue(any("github" in e for e in out["errors"]))


if __name__ == "__main__":
    unittest.main()
