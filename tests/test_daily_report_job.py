"""Unit tests for daily_report_job.py including x402_attestations, partner_clicks, partners, and pilot_leads."""
import sqlite3
import unittest

import daily_report_job


class DailyReportJobTests(unittest.TestCase):
    def _base_db(self):
        c = sqlite3.connect(":memory:")
        c.row_factory = sqlite3.Row
        c.executescript(
            """
            CREATE TABLE pageviews (day TEXT, path TEXT, referrer TEXT, visitor TEXT, is_bot INTEGER, is_test INTEGER DEFAULT 0);
            CREATE TABLE scans (created_at TEXT, domain TEXT, grade TEXT, is_test INTEGER DEFAULT 0);
            CREATE TABLE events (day TEXT, name TEXT, is_bot INTEGER, is_test INTEGER DEFAULT 0);
            CREATE TABLE orders (created_at TEXT, status TEXT, is_test INTEGER DEFAULT 0);
            CREATE TABLE monitor_accounts (created_at TEXT, email TEXT, plan TEXT, status TEXT);
            CREATE TABLE audit_requests (created_at TEXT, org TEXT, domain TEXT, email TEXT, is_test INTEGER DEFAULT 0);
            """
        )
        return c

    def test_handles_missing_optional_tables_gracefully(self):
        c = self._base_db()
        text = daily_report_job.build(c, "2026-11-24")
        self.assertIn("شهادات Attestation (5 USDC): 0 (الإجمالي: 0)", text)
        self.assertIn("لا نقرات", text)

    def test_reports_attestations_partner_clicks_and_pilot_leads(self):
        c = self._base_db()
        c.executescript(
            """
            CREATE TABLE x402_attestations (att_id TEXT, issued_at TEXT);
            CREATE TABLE partner_clicks (code TEXT, day TEXT, n INTEGER);
            CREATE TABLE partners (id INTEGER PRIMARY KEY, code TEXT, status TEXT, created_at TEXT);
            CREATE TABLE pilot_leads (id INTEGER PRIMARY KEY, created_at TEXT);
            INSERT INTO x402_attestations VALUES ('att_1', '2026-11-24T12:00:00Z');
            INSERT INTO x402_attestations VALUES ('att_0', '2026-11-23T12:00:00Z');
            INSERT INTO partner_clicks VALUES ('RAHAFALT21', '2026-11-24', 5);
            INSERT INTO partners VALUES (1, 'RAHAFALT21', 'ACTIVE', '2026-11-24T08:00:00Z');
            INSERT INTO pilot_leads VALUES (1, '2026-11-24T15:00:00Z');
            """
        )
        text = daily_report_job.build(c, "2026-11-24")
        self.assertIn("شهادات Attestation (5 USDC): 1 (الإجمالي: 2)", text)
        self.assertIn("طلبات MSP Pilot (290 €): 1 (الإجمالي: 1)", text)
        self.assertIn("شركاء جدد: 1 (نشطون: 1)", text)
        self.assertIn("RAHAFALT21=5", text)


if __name__ == "__main__":
    unittest.main()
