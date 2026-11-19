import os
import sqlite3
import tempfile
import unittest
from unittest import mock

import adoption
import exposure


def conn_with(rows):
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    adoption.init(c)
    for week, domain, ok, pq, rank in rows:
        c.execute("INSERT INTO adoption_results (week, domain, rank, ok, grade, grp, tls, pq, scanned_at, as_name) "
                  "VALUES (?, ?, ?, ?, ?, ?, 'TLSv1.3', ?, ?, 'NET')",
                  (week, domain, rank, ok, "A" if pq else "C", "X25519MLKEM768" if pq else "x25519", pq,
                   adoption.week_monday(week).isoformat() + "T04:00:00+00:00"))
    c.commit()
    return c


class ExposureTests(unittest.TestCase):
    def test_went_pq_window(self):
        c = conn_with([("2026-W45", "bank.example", 1, 0, None), ("2026-W46", "bank.example", 1, 0, None),
                       ("2026-W47", "bank.example", 1, 1, None)])
        w = exposure.window(c, "bank.example")
        self.assertEqual(w["status"], "went_pq")
        self.assertEqual(w["first_pq_week"], "2026-W47")
        self.assertEqual(w["exposure_window"]["start"], "2026-11-02")
        self.assertEqual(w["exposure_window"]["end"], "2026-11-16")
        self.assertEqual(w["exposure_window"]["days"], 14)
        self.assertFalse(w["indexable"])  # 3 weeks, unranked

    def test_classical_open_window_and_regression(self):
        c = conn_with([("2026-W45", "a.example", 1, 1, 5), ("2026-W46", "a.example", 1, 0, 5)])
        w = exposure.window(c, "a.example")
        self.assertEqual(w["status"], "pq_since_first_observation")
        self.assertEqual(w["regression_weeks"], ["2026-W46"])
        self.assertTrue(w["indexable"])  # top 1000
        c2 = conn_with([("2026-W45", "b.example", 1, 0, None)])
        self.assertTrue(exposure.window(c2, "b.example")["exposure_window"]["open"])
        self.assertIsNone(exposure.window(c2, "nothing.example"))

    def test_indexing_rule(self):
        self.assertTrue(exposure.is_indexable("x.example", 1000, 1))
        self.assertFalse(exposure.is_indexable("x.example", 1001, 3))
        self.assertTrue(exposure.is_indexable("x.example", None, 4))
        self.assertFalse(exposure.is_indexable("w4nkr.com", 10, 10))
        self.assertFalse(exposure.is_indexable("googleapis.com", 5, 10))
        rows = [(f"2026-W{w}", "long.example", 1, 0, 5000) for w in (44, 45, 46, 47)] + [("2026-W47", "short.example", 1, 0, 5000)]
        self.assertEqual([d for d, _ in exposure.sitemap_domains(conn_with(rows))], ["long.example"])

    def test_manifest_is_deterministic_and_hides_names(self):
        c = conn_with([("2026-W45", "a.example", 1, 1, 1), ("2026-W45", "b.example", 0, 0, 2)])
        body, rows = exposure.manifest_bytes(c, "2026-W45")
        self.assertEqual(rows, 2)
        self.assertEqual(body, exposure.manifest_bytes(c, "2026-W45")[0])
        self.assertNotIn(b"a.example", body)
        self.assertIn(exposure.domain_key("a.example").encode(), body)

    def test_anchor_written_once(self):
        c = conn_with([("2026-W45", "a.example", 1, 1, 1)])
        with tempfile.TemporaryDirectory() as d:
            calls = []

            def fake_stamp(path):
                calls.append(path)
                open(path + ".ots", "wb").write(b"proof")
                return 0, "Submitting to remote calendar"
            rec = exposure.anchor_week(c, d, "2026-W45", stamp=fake_stamp)
            self.assertEqual(rec["status"], "pending")
            again = exposure.anchor_week(c, d, "2026-W45", stamp=fake_stamp)
            self.assertEqual(len(calls), 1)
            self.assertEqual(again["manifest_sha256"], rec["manifest_sha256"])
            run = mock.Mock(side_effect=[(0, ""), (0, "BitcoinBlockHeaderAttestation(912345)")])
            self.assertEqual(exposure.upgrade_anchors(d, run=run), ["2026-W45"])
            self.assertEqual(exposure.load_anchor(d, "2026-W45")["bitcoin_block"], 912345)
            self.assertIsNone(exposure.load_anchor(d, "../etc"))

    def test_claim_token(self):
        tok = exposure.claim_token("a.example", "salt")
        res = exposure.verify_claim("a.example", "salt", query=lambda fqdn: [tok] if fqdn == "_ather-claim.a.example" else [])
        self.assertTrue(res["verified"])
        self.assertFalse(exposure.verify_claim("a.example", "other", query=lambda fqdn: [tok])["verified"])


class McpPackageTests(unittest.TestCase):
    def test_core_exposure_window_calls_public_api(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))
        from quantum_aether_mcp import core
        with mock.patch.object(core, "_get", return_value={"domain": "a.example"}) as get:
            self.assertEqual(core.exposure_window("A.example"), {"domain": "a.example"})
        get.assert_called_once_with("/api/v1/exposure/a.example")


if __name__ == "__main__":
    unittest.main()
