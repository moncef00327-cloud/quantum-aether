import datetime as dt
import os
import shutil
import tempfile
import unittest

import monitor
import sales_db
import scorecard


class ScorecardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.conn = sales_db.connect(os.path.join(self.tmp, "q.db"))

    def tearDown(self):
        self.conn.close()
        shutil.rmtree(self.tmp)

    def test_expected_matches_simulation_inputs(self):
        e = scorecard.expected_week(scorecard.SCENARIOS["realistic"], 0)
        self.assertAlmostEqual(e["visitors"], 1500 / 4.345, places=3)
        self.assertAlmostEqual(e["scans"], e["visitors"] * 0.15, places=6)

    def test_counts_exclude_bots_tests_and_owner(self):
        c = self.conn
        with c:
            c.executemany("INSERT INTO pageviews (day, path, referrer, visitor, is_bot, is_test) VALUES (?,?,?,?,?,?)", [
                ("2026-11-03", "/", "x", "v1", 0, 0), ("2026-11-03", "/guides", "x", "v1", 0, 0),  # نفس الزائر
                ("2026-11-03", "/", "x", "v2", 0, 0), ("2026-11-03", "/", "x", "b", 1, 0), ("2026-11-03", "/", "x", "a", 0, 1),
                ("2026-11-04", "/", "x", "v1", 0, 0)])
        card = scorecard.build(c, "owner@x.test", monitor.PLANS, today=dt.date(2026, 11, 5))
        week = card["weeks"][0]
        self.assertEqual(week["visitors"], 3)    # v1 (يومان) + v2
        self.assertEqual(week["partial_days"], 3)
        self.assertEqual(card["verdict"], "pessimistic")
        self.assertIn("PESSIMISTIC", scorecard.as_text(card))
        self.assertEqual(card["breakeven_subs"], 5)
        self.assertEqual(card["cost_so_far"], 0)  # ما زلنا ضمن رصيد Vultr

    def test_conversion_warning_when_no_scans(self):
        totals = {"visitors": 70, "scans": 0}
        self.assertIn("not converting", scorecard.conversion_warning(totals, "realistic"))
        self.assertIsNone(scorecard.conversion_warning({"visitors": 70, "scans": 10}, "realistic"))
        self.assertIsNone(scorecard.conversion_warning({"visitors": 5, "scans": 0}, "realistic"))

    def test_closest_scenario_by_ratio(self):
        self.assertEqual(scorecard.closest_scenario(350, 0), "realistic")
        self.assertEqual(scorecard.closest_scenario(1200, 0), "optimistic")
        self.assertEqual(scorecard.closest_scenario(10, 0), "pessimistic")


if __name__ == "__main__":
    unittest.main()
