"""/insurers/weekly: DACH insurer post-quantum tracker built from the adoption tables."""
import os
import sqlite3
import tempfile
import unittest

import adoption
import quantum_saas_app
import weekly_insurers
from tests.test_weekly_banks import _row


class WeeklyInsurersTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name})
        self.client = self.app.test_client()
        conn = sqlite3.connect(os.path.join(self.tmp.name, "quantum_saas.db"))
        adoption.init(conn)
        s = weekly_insurers.SECTOR
        for week, axa in (("2026-W46", 0), ("2026-W47", 1)):
            _row(conn, week, "www.axa.de", s, axa)
            _row(conn, week, "www.aok.de", s, 0)
            _row(conn, week, "www.sbk.org", s, 0)
            _row(conn, week, "www.merkur.at", s, 0)
            _row(conn, week, "www.css.ch", s, 1)
            _row(conn, week, "www.dkb.de", "banks-dach", 1)
        conn.commit()
        conn.close()
        self.conn = sqlite3.connect(os.path.join(self.tmp.name, "quantum_saas.db"))
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_build_groups_by_country_and_type(self):
        rep = weekly_insurers.build(self.conn)
        self.assertEqual(rep["week"], "2026-W47")
        self.assertEqual((rep["n"], rep["pq"]), (5, 2))
        by = {g["key"]: (g["n"], g["pq"]) for g in rep["groups"]}
        self.assertEqual(by, {"DE": (3, 1), "AT": (1, 0), "CH": (1, 1)})  # sbk.org counted as DE
        self.assertEqual((rep["statutory"]["n"], rep["statutory"]["pq"]), (2, 0))
        self.assertEqual((rep["private"]["n"], rep["private"]["pq"]), (3, 2))
        self.assertEqual(rep["adopted"], ["www.axa.de"])
        self.assertIsNone(weekly_insurers.build(self.conn, "2026-W40"))

    def test_posts(self):
        p = weekly_insurers.posts(weekly_insurers.build(self.conn))
        self.assertIn("2 von 5", p["de"])
        self.assertIn("• Deutschland: 1 von 3", p["de"])
        self.assertIn("/insurers/weekly/2026-W47?lang=en", p["en"])

    def test_email_section(self):
        text = weekly_insurers.as_text(weekly_insurers.build(self.conn))
        self.assertIn("WEEKLY DACH INSURER TRACKER 2026-W47: 2/5", text)
        self.assertIn("still classical (1; for LinkedIn mentions, NOT email): www.merkur.at", text)  # aok/sbk statutory
        self.assertIn("--- LinkedIn post (de) ---", text)
        self.assertIn("no data yet", weekly_insurers.as_text(None))

    def test_pages_render_and_sitemap(self):
        for lang, needle in (("de", "Versicherer und Krankenkassen in DACH"), ("en", "DACH insurers"),
                             ("ar", "شركات التأمين")):
            body = self.client.get(f"/insurers/weekly/2026-W47?lang={lang}").get_data(as_text=True)
            self.assertIn(needle, body)
            self.assertIn("www.merkur.at", body)
            self.assertIn(f'<html lang="{lang}"', body)
        self.assertEqual(self.client.get("/insurers/weekly").status_code, 200)
        self.assertEqual(self.client.get("/insurers/weekly/2026-W01").status_code, 404)
        data = self.client.get("/insurers/weekly/2026-W47.json").get_json()
        self.assertEqual(data["pq"], 2)
        self.assertNotIn("dkb.de", str(data))
        sitemap = self.client.get("/sitemap-pages.xml").get_data(as_text=True)
        self.assertIn("/insurers/weekly?lang=de", sitemap)
        self.assertNotIn("/insurers/weekly/2026-W47", sitemap)  # newest week = the hub, canonicalised there
        body = self.client.get("/insurers/weekly/2026-W47?lang=ar").get_data(as_text=True)
        self.assertIn('<link rel="canonical" href="http://localhost/insurers/weekly?lang=ar">', body)


if __name__ == "__main__":
    unittest.main()
