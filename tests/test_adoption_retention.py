import os, sqlite3, unittest
from unittest import mock
import adoption


def _conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    adoption.init(c)
    for w in ("2026-W40", "2026-W41", "2026-W42"):
        c.execute("INSERT INTO adoption_results (week, domain, ok, pq, scanned_at) VALUES (?, 'example.com', 1, 0, '2026-10-01')", (w,))
    c.commit()
    return c


class PruneRetentionTests(unittest.TestCase):
    def setUp(self):
        self.p = mock.patch.object(adoption, "purge_excluded", return_value=0)
        self.p.start()

    def tearDown(self):
        self.p.stop()

    def test_default_never_deletes_history(self):
        c = _conn()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("QS_ADOPTION_PRUNE", None)
            out = adoption.prune(c, keep_weeks=1)
        self.assertEqual(out["mode"], "off")
        self.assertEqual(c.execute("SELECT COUNT(*) FROM adoption_results").fetchone()[0], 3)

    def test_unknown_mode_falls_back_to_off(self):
        c = _conn()
        with mock.patch.dict(os.environ, {"QS_ADOPTION_PRUNE": "yes-please"}):
            self.assertEqual(adoption.prune(c, keep_weeks=1)["mode"], "off")
        self.assertEqual(c.execute("SELECT COUNT(*) FROM adoption_results").fetchone()[0], 3)

    def test_archive_moves_rows_instead_of_dropping(self):
        c = _conn()
        with mock.patch.dict(os.environ, {"QS_ADOPTION_PRUNE": "archive"}):
            out = adoption.prune(c, keep_weeks=1)
        self.assertEqual(out["weeks"], 2)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM adoption_results").fetchone()[0], 1)
        self.assertEqual(sorted(r[0] for r in c.execute("SELECT week FROM adoption_results_archive")), ["2026-W40", "2026-W41"])


if __name__ == "__main__":
    unittest.main()
