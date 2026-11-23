"""Unit tests for the 5 autonomous ethical marketing employees (marketing_desk.py) and pqc_news DATA_DIR refresh."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import adoption
import marketing_desk
import outreach_suppress
import pqc_news
import radar


class MarketingDeskTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "quantum_saas.db")
        conn = sqlite3.connect(self.db_path)
        adoption.init(conn)
        radar.init(conn)
        outreach_suppress.init(conn)
        conn.execute("CREATE TABLE pageviews (day TEXT, path TEXT, referrer TEXT, visitor TEXT, is_bot INTEGER, is_test INTEGER DEFAULT 0)")
        with conn:
            # 12 banks-mena (5 PQ, 7 non-PQ including C/F) + 12 health-insurance-dach
            for i in range(12):
                pq = 1 if i < 5 else 0
                grade = "A" if pq else ("F" if i == 5 else ("C" if i < 9 else "B"))
                grp = "X25519MLKEM768" if pq else "X25519"
                conn.execute(
                    "INSERT INTO adoption_results (week, domain, rank, sector, ok, grade, grp, tls, pq, scanned_at, unsure) "
                    "VALUES ('2026-W47', ?, NULL, 'banks-mena', 1, ?, ?, 'TLSv1.3', ?, '2026-11-22T04:00:00Z', 0)",
                    (f"bank{i}.example.sa", grade, grp, pq),
                )
                conn.execute(
                    "INSERT INTO adoption_results (week, domain, rank, sector, ok, grade, grp, tls, pq, scanned_at, unsure) "
                    "VALUES ('2026-W47', ?, NULL, 'health-insurance-dach', 1, ?, ?, 'TLSv1.3', ?, '2026-11-22T04:00:00Z', 0)",
                    (f"ins{i}.example.de", grade, grp, pq),
                )
            # Previous week regression on bank6.example.sa (was A/pq=1 in W46, dropped to C/pq=0 in W47)
            conn.execute(
                "INSERT INTO adoption_results (week, domain, rank, sector, ok, grade, grp, tls, pq, scanned_at, unsure) "
                "VALUES ('2026-W46', 'bank6.example.sa', NULL, 'banks-mena', 1, 'A', 'X25519MLKEM768', 'TLSv1.3', 1, '2026-11-15T04:00:00Z', 0)"
            )
            # Mark bank5.example.sa as already contacted -> must be skipped by Employee 4
            conn.execute(
                "INSERT INTO outreach_sent (email, domain, org, lang, kex_group, kex_class, subject, sent_at) "
                "VALUES ('sec@bank5.example.sa', 'bank5.example.sa', 'Bank 5', 'ar', 'X25519', 'classical', 's', '2026-11-22T00:00:00Z')"
            )
            # Radar hot discussion
            conn.execute(
                "INSERT INTO radar_seen (url, source, title, topic, found_at, intent, stack, snippet, score, status) "
                "VALUES ('https://github.com/org/repo/issues/1', 'GitHub', 'pip hangs on PQ ClientHello', 'clienthello', "
                "'2026-11-22T18:00:00+00:00', 'breakage', 'clienthello', 'snippet', 95, 'new')"
            )
            # Inbound interest yesterday
            conn.execute(
                "INSERT INTO pageviews (day, path, referrer, visitor, is_bot, is_test) "
                "VALUES ('2026-11-22', '/site/bank7.example.sa', 'google.com', 'vis1', 0, 0)"
            )
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_all_five_employees_generate_brief_without_sending_external_mail(self):
        res = marketing_desk.run(data_dir=self.tmp.name, refresh_news=False, send_email=False,
                                 today=marketing_desk.dt.date(2026, 11, 23))
        self.assertFalse(res["emailed"])
        self.assertTrue(Path(res["path"]).exists())
        self.assertTrue(Path(res["latest"]).exists())
        brief = res["brief"]
        # Employee 1: radar reply draft
        self.assertIn("pip hangs on PQ ClientHello", brief)
        self.assertIn("tls-clienthello-middlebox-fragmentation", brief)
        # Employee 2: multilingual data journalist drafts + regression
        self.assertIn("LinkedIn (عربي", brief)
        self.assertIn("LinkedIn (English", brief)
        self.assertIn("LinkedIn (Deutsch", brief)
        self.assertIn("bank6.example.sa", brief)
        # Employee 3: Grade A badge shoutouts
        self.assertIn("#badge", brief)
        # Employee 4: inbound hot lead bank7 included, already-contacted bank5 excluded
        self.assertIn("bank7.example.sa", brief)
        self.assertNotIn("bank5.example.sa", brief)

    def test_pqc_news_prefers_newer_data_dir_snapshot(self):
        feed = {
            "schema_version": 1,
            "updated_at": "2099-01-01T00:00:00+00:00",
            "sources": ["NIST"],
            "items": [{
                "title": "Fresh NIST ML-KEM Guidance",
                "url": "https://www.nist.gov/news-events/pqc",
                "source": "NIST",
                "category": "standards",
                "importance": "high",
                "takeaway": {"en": "en", "ar": "ar", "de": "de"},
            }],
        }
        Path(self.tmp.name, "news_feed.json").write_text(json.dumps(feed), encoding="utf-8")
        old_env = os.environ.get("QS_DATA_DIR")
        pqc_news._CACHE["data"] = None
        pqc_news._CACHE["checked_at"] = 0.0
        os.environ["QS_DATA_DIR"] = self.tmp.name
        try:
            loaded = pqc_news.load_feed()
            self.assertEqual(loaded["updated_at"], "2099-01-01T00:00:00+00:00")
            self.assertEqual(loaded["items"][0]["title"], "Fresh NIST ML-KEM Guidance")
        finally:
            if old_env is None:
                os.environ.pop("QS_DATA_DIR", None)
            else:
                os.environ["QS_DATA_DIR"] = old_env
            pqc_news._CACHE["data"] = None
            pqc_news._CACHE["checked_at"] = 0.0


if __name__ == "__main__":
    unittest.main()
