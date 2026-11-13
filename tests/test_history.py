"""Every monitoring check is kept as dated evidence: dashboard log + CSV export for auditors."""
import csv
import io
import os
import shutil
import tempfile
import unittest
from contextlib import closing

import monitor_db
import monitor_job
import quantum_saas_app
import sales_db
from tests.test_monitor import PLAN_IDS, FakeMailer, FakePayPal, FakeScanner, result_for


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.scanner, self.paypal, self.mailer = FakeScanner(), FakePayPal(), FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://example.test",
             "PAYPAL_CLIENT_ID": "cid", "OWNER_EMAIL": "owner@example.com", **PLAN_IDS},
            scanner=self.scanner, paypal=self.paypal, mailer=self.mailer)
        self.client = self.app.test_client()
        self.client.post("/monitoring/trial?lang=en", data={"email": "ops@acme.org", "domain": "acme.org", "consent": "1"})
        mail = next(m for m in self.mailer.sent if m[0] == "ops@acme.org")
        self.token = mail[2].split("/monitor/")[1].split("?")[0].split()[0]

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db")))

    def account_id(self):
        with self.conn() as c:
            return c.execute("SELECT id FROM monitor_accounts").fetchone()[0]

    def test_each_check_is_recorded_including_failures(self):
        monitor_job.run(self.app)
        self.scanner.results["acme.org"] = result_for("acme.org", grade="B", pq=False, group="x25519")
        monitor_job.run(self.app)
        self.scanner.results["acme.org"] = OSError("connection refused")
        monitor_job.run(self.app)
        with self.conn() as c:
            rows = monitor_db.check_history(c, self.account_id())
        self.assertEqual(len(rows), 3)
        newest, middle, oldest = rows
        self.assertEqual((oldest["grade"], oldest["pq"]), ("A", 1))
        self.assertEqual((middle["grade"], middle["pq"], middle["grp"]), ("B", 0, "x25519"))
        self.assertIn("connection refused", newest["error"])

    def test_dashboard_shows_log_and_csv_link(self):
        monitor_job.run(self.app)
        page = self.client.get(f"/monitor/{self.token}?lang=en").get_data(as_text=True)
        self.assertIn("Check history", page)
        self.assertIn(f"/monitor/{self.token}/history.csv", page)

    def test_csv_export(self):
        monitor_job.run(self.app)
        self.scanner.results["acme.org"] = OSError("=HYPERLINK(\"http://evil\")")
        monitor_job.run(self.app)
        r = self.client.get(f"/monitor/{self.token}/history.csv")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.headers["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        rows = list(csv.DictReader(io.StringIO(r.get_data(as_text=True))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["domain"], "acme.org")
        self.assertEqual(rows[1]["post_quantum"], "yes")
        self.assertEqual(rows[1]["grade"], "A")
        self.assertTrue(rows[0]["error"].startswith("'="))  # spreadsheet formula injection neutralised
        self.assertIn("one location", rows[1]["measurement"])

    def test_csv_requires_valid_token(self):
        self.assertEqual(self.client.get("/monitor/not-a-token/history.csv").status_code, 404)

    def test_history_survives_domain_removal_and_is_pruned_by_age(self):
        monitor_job.run(self.app)
        with self.conn() as c:
            d = monitor_db.list_domains(c, self.account_id())[0]
            monitor_db.remove_domain(c, self.account_id(), d["id"])
            self.assertEqual(len(monitor_db.check_history(c, self.account_id())), 1)
            c.execute("UPDATE monitor_checks SET checked_at = '2020-01-01T00:00:00Z'")
            c.commit()
            self.assertEqual(monitor_db.prune_checks(c, "2025-01-01T00:00:00Z"), 1)
            self.assertEqual(monitor_db.check_history(c, self.account_id()), [])

    def test_ended_trial_purge_deletes_history(self):
        monitor_job.run(self.app)
        with self.conn() as c:
            c.execute("UPDATE monitor_accounts SET status = 'TRIAL_ENDED', updated_at = '2020-01-01T00:00:00Z'")
            c.commit()
            monitor_db.purge_ended_trials(c, "2025-01-01T00:00:00Z")
            self.assertEqual(c.execute("SELECT COUNT(*) FROM monitor_checks").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
