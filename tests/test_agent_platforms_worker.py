"""Tests for tools/agent_platforms_worker.py (Agentboard.ai & Moltbook.com continuous heartbeat worker)."""
import sqlite3
import unittest

from tools import agent_platforms_worker as apw


class AgentPlatformsWorkerTests(unittest.TestCase):
    def test_extract_requested_domain_skips_own_and_platform_domains(self):
        self.assertIsNone(apw.extract_requested_domain("Check ather-quantum.com or agentboard.ai"))
        self.assertEqual(apw.extract_requested_domain("Can you scan stripe.com please?"), "stripe.com")
        self.assertEqual(apw.extract_requested_domain("Check api.cloudflare.dev"), "api.cloudflare.dev")

    def test_build_daily_digest_includes_key_metrics_and_x402scan(self):
        title, body = apw.build_daily_digest({
            "updated_at": "2026-11-27T05:00:00Z",
            "measured": 150,
            "pq_hybrid": 120,
            "pq_pct": 80.0,
            "classical": 25,
            "tls12": 5,
            "pq_not_preferred": 2,
        })
        self.assertIn("80.0%", title)
        self.assertIn("150", title)
        self.assertIn("x402scan.com/server/", body)
        self.assertIn("$0.10 batch-scan", body)
        self.assertIn("npx skills add moncef00327-cloud/quantum-aether", body)

    def test_activity_idempotency(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        apw.init_db(conn)
        self.assertFalse(apw.already_done(conn, "agentboard", "daily_digest", "2026-11-27"))
        apw.record_done(conn, "agentboard", "daily_digest", "2026-11-27", "ok")
        self.assertTrue(apw.already_done(conn, "agentboard", "daily_digest", "2026-11-27"))

    def test_moltbook_series_templates_format_cleanly(self):
        for submolt, title_tpl, body_tpl in apw.MOLTBOOK_SERIES:
            t = title_tpl.format(measured=118, pq_n=91, pq_pct=77.1, classical=24, tls12=3)
            b = body_tpl.format(measured=118, pq_n=91, pq_pct=77.1, classical=24, tls12=3,
                                site=apw.SITE, x402scan=apw.X402SCAN_URL)
            self.assertTrue(len(t) <= 300, submolt)
            self.assertIn("?", b, f"{submolt} post should end with an engaging question")
            self.assertIn("## Sources", b, f"{submolt} post should include clean Sources block")


if __name__ == "__main__":
    unittest.main()
