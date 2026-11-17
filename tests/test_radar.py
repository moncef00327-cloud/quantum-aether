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
        # تحليل: نخزّن حقول النيّة/الدرجة، لكن لا أي عمود يخصّ شخصاً (اسم/حساب/بريد/مؤلّف)
        self.assertEqual(cols, ["url", "source", "title", "topic", "found_at",
                                "intent", "stack", "snippet", "score", "status"])
        self.assertFalse(any(bad in c.lower() for c in cols
                             for bad in ("author", "user", "account", "name", "email", "handle")))

    def test_github_breakage_reports_count_and_off_topic_does_not(self):
        def gh(title, body=""):
            return {"source": "GitHub", "url": "https://github.com/a/b/issues/9", "title": title, "text": body}
        keep = ["cli: hangs before sending request on networks that drop fragmented TLS ClientHello (post-quantum)",
                "[Bug] CDN64: Edge schließt Verbindung bei großem TLS-ClientHello (OpenSSL 3.5 / ML-KEM)",
                "[Action required] AKS is adopting post-quantum TLS: validate firewalls and proxies"]
        drop = ["[Bug] Old REALITY configs fail to connect since post-quantum hybrid key share (X25519MLKEM768)",
                "RUSTSEC-2026-0349: Unauthenticated ServerHello can downgrade later connections to classical key exchange",
                "net.tls: optional pure-V TLS 1.3 with hybrid post-quantum support",          # ميزة مكتبة، لا عطل
                "macOS: host traffic loses the DF bit"]
        for title in keep:
            self.assertTrue(radar.relevant(gh(title)), title)
        for title in drop:
            self.assertFalse(radar.relevant(gh(title, "X25519MLKEM768 ClientHello is fragmented by the firewall")), title)
        self.assertEqual(radar.topic_of(gh(keep[0])), "clienthello")
        self.assertIn("ClientHello", radar.draft_reply(gh(keep[0]), "clienthello"))

    def test_https_inside_a_link_is_not_tls_context(self):
        comment = {"source": "Hacker News", "url": "https://news.ycombinator.com/item?id=5",
                   "title": "Ask HN: What cryptography book do you recommend?",
                   "text": "Why not post-quantum? See https://www.schneier.com/books/applied-cryptography/"}
        self.assertFalse(radar.relevant(comment))
        comment["text"] = "How do I enable post-quantum TLS on my web server?"
        self.assertTrue(radar.relevant(comment))

    def test_github_queries_are_spaced_for_the_unauthenticated_limit(self):
        calls, pauses = [], []
        def counting(url):
            calls.append(url)
            return fake_get(url)
        radar.collect(SINCE, get=counting, sleep=pauses.append)
        github = [u for u in calls if "api.github.com" in u]
        self.assertEqual(len(github), len(radar.GITHUB_QUERIES))
        self.assertEqual(pauses, [radar.GITHUB_PAUSE] * (len(radar.GITHUB_QUERIES) - 1))
        self.assertLessEqual(len(radar.GITHUB_QUERIES), 10)

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
