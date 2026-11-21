"""/banks/weekly: weekly bank post-quantum tracker built from the adoption tables."""
import os
import sqlite3
import tempfile
import unittest

import adoption
import quantum_saas_app
import weekly_banks

WATCH = {"banks-mena": {"labels": {"en": "Gulf banks", "ar": "بنوك الخليج", "de": "Golfbanken"}, "domains": []},
         "banks-dach": {"labels": {"en": "DACH banks"}, "domains": []},
         "banks-europe": {"labels": {"en": "EU banks"}, "domains": []}}


def _row(conn, week, domain, sector, pq, ok=1, unsure=0):
    conn.execute("INSERT INTO adoption_results (week, domain, rank, sector, ok, grade, grp, tls, pq, scanned_at, unsure) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (week, domain, None, sector, ok, "A" if pq else "C",
                                                    "X25519MLKEM768" if pq else "x25519", "TLSv1.3", pq,
                                                    "2026-11-16T03:40:00+00:00", unsure))


class WeeklyBanksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name})
        self.client = self.app.test_client()
        conn = sqlite3.connect(os.path.join(self.tmp.name, "quantum_saas.db"))
        adoption.init(conn)
        for week, nbk in (("2026-W46", 0), ("2026-W47", 1)):
            _row(conn, week, "www.nbk.com", "banks-mena", nbk)
            _row(conn, week, "www.qnb.com", "banks-mena", 1)
            _row(conn, week, "www.dkb.de", "banks-dach", 0)
            _row(conn, week, "www.ing.nl", "banks-europe", 1)
            _row(conn, week, "github.com", None, 1)
        conn.commit()
        conn.close()
        self.conn = sqlite3.connect(os.path.join(self.tmp.name, "quantum_saas.db"))
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_build_counts_and_changes(self):
        rep = weekly_banks.build(self.conn, watchlists=WATCH)
        self.assertEqual(rep["week"], "2026-W47")
        self.assertEqual((rep["n"], rep["pq"]), (4, 3))
        gulf = rep["regions"][0]
        self.assertEqual((gulf["key"], gulf["n"], gulf["pq"]), ("banks-mena", 2, 2))
        self.assertEqual(rep["adopted"], ["www.nbk.com"])
        self.assertEqual(rep["dropped"], [])
        self.assertIsNone(weekly_banks.build(self.conn, "2026-W40", watchlists=WATCH))

    def test_posts_and_email_text(self):
        rep = weekly_banks.build(self.conn, watchlists=WATCH)
        p = weekly_banks.posts(rep)
        self.assertIn("2 من 2", p["ar"])
        self.assertIn("www.nbk.com", p["en"])
        self.assertIn("/banks/weekly/2026-W47?lang=de", p["de"])
        self.assertIn("WEEKLY BANK TRACKER 2026-W47: 3/4", weekly_banks.as_text(rep))

    def test_pages_render_in_three_languages(self):
        for lang, needle in (("en", "Weekly bank post-quantum tracker"), ("ar", "المتتبع الأسبوعي"),
                             ("de", "Wöchentlicher Post-Quanten-Tracker")):
            body = self.client.get(f"/banks/weekly/2026-W47?lang={lang}").get_data(as_text=True)
            self.assertIn(needle, body)
            self.assertIn("www.nbk.com", body)
            self.assertIn(f'<html lang="{lang}"', body)
        self.assertEqual(self.client.get("/banks/weekly").status_code, 200)
        self.assertEqual(self.client.get("/banks/weekly/2026-W01").status_code, 404)
        data = self.client.get("/banks/weekly/2026-W47.json").get_json()
        self.assertEqual(data["pq"], 3)
        self.assertNotIn("github.com", str(data))

    def test_in_sitemap(self):
        body = self.client.get("/sitemap-pages.xml").get_data(as_text=True)
        # The newest week is served by the hub; only older weeks are listed as dated archive pages.
        self.assertIn("/banks/weekly?lang=ar", body)
        self.assertIn("/banks/weekly/2026-W46", body)
        self.assertNotIn("/banks/weekly/2026-W47", body)

    def test_newest_dated_page_canonicalises_to_hub(self):
        for lang in ("en", "ar", "de"):
            body = self.client.get(f"/banks/weekly/2026-W47?lang={lang}").get_data(as_text=True)
            self.assertIn(f'<link rel="canonical" href="http://localhost/banks/weekly?lang={lang}">', body)
        body = self.client.get("/banks/weekly/2026-W46?lang=en").get_data(as_text=True)
        self.assertIn('<link rel="canonical" href="http://localhost/banks/weekly/2026-W46?lang=en">', body)
        hub = self.client.get("/banks/weekly?lang=en").get_data(as_text=True)
        self.assertIn('<link rel="canonical" href="http://localhost/banks/weekly?lang=en">', hub)


if __name__ == "__main__":
    unittest.main()
