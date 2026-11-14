import sqlite3
import unittest

import scan_followups


class ScanFollowupTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        scan_followups.init(self.conn)
        self.scan = {"id": "scan123", "result": {"domain": "example.test", "grade": "B",
            "findings": [{"code": "KX_CLASSICAL", "status": "warning"}]}}

    def tearDown(self):
        self.conn.close()

    def test_opt_in_persists_timestamp_source_grade_and_findings(self):
        row = scan_followups.record(self.conn, self.scan, "User@Example.com", "US", "registered_company")
        self.assertEqual(row["email"], "user@example.com")
        self.assertEqual(row["grade"], "B")
        self.assertEqual(row["consent_source"], "scan-result")
        self.assertEqual(row["consent_version"], scan_followups.CONSENT_VERSION)
        self.assertTrue(row["consent_at"])
        self.assertIn("KX_CLASSICAL", row["findings_json"])
        self.assertEqual(row["status"], "OPTED_IN")
        self.assertEqual(row["country_code"], "US")
        self.assertEqual(row["recipient_type"], "registered_company")

    def test_grade_a_cannot_be_recorded(self):
        self.scan["result"]["grade"] = "A"
        with self.assertRaisesRegex(ValueError, "grade_not_eligible"):
            scan_followups.record(self.conn, self.scan, "user@example.com", "US", "registered_company")
        self.assertEqual(self.conn.execute("SELECT count(*) FROM scan_followups").fetchone()[0], 0)

    def test_unsubscribe_token_is_bound_to_record_and_address(self):
        row = scan_followups.record(self.conn, self.scan, "user@example.com", "US", "registered_company")
        token = scan_followups.unsubscribe_token(row, "secret")
        self.assertTrue(scan_followups.token_valid(row, "secret", token))
        self.assertFalse(scan_followups.token_valid(row, "wrong", token))
        self.conn.execute("UPDATE scan_followups SET status='UNSUBSCRIBED' WHERE id=?", (row["id"],))
        self.assertEqual(scan_followups.eligible(self.conn), [])

    def test_opt_in_does_not_send_mail_and_is_only_eligible_after_explicit_record(self):
        self.assertEqual(scan_followups.eligible(self.conn), [])
        scan_followups.record(self.conn, self.scan, "user@example.com", "US", "registered_company")
        self.assertEqual(len(scan_followups.eligible(self.conn)), 1)
        self.assertIsNone(scan_followups.eligible(self.conn)[0]["sent_at"])

    def test_eu_is_excluded_and_unsubscribe_suppresses_all_rows_until_new_opt_in(self):
        eu = scan_followups.record(self.conn, self.scan, "eu@example.com", "PL", "registered_company")
        self.assertEqual(scan_followups.eligible(self.conn), [])
        us_scan = dict(self.scan, id="scan456")
        row = scan_followups.record(self.conn, us_scan, "user@example.com", "US", "registered_company")
        self.assertEqual(len(scan_followups.eligible(self.conn)), 1)
        scan_followups.suppress_email(self.conn, row["email"], "2026-11-14T00:00:00+00:00")
        self.assertEqual(scan_followups.eligible(self.conn), [])
        scan_followups.record(self.conn, us_scan, "user@example.com", "US", "registered_company")
        self.assertEqual(len(scan_followups.eligible(self.conn)), 1)



if __name__ == "__main__":
    unittest.main()
