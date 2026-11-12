"""/banks/<id>: frozen Arab banks report, counts only, ranking, opt-out, ar/en."""
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import bank_report
import quantum_saas_app

DISC = {"alinma.com": {"names": 50, "responding": 40, "pq": 4, "not_pq": 36, "unknown": 0,
                       "hosts": [{"host": "secret-api.alinma.com", "status": "not_pq"}]},
        "qnb.com": {"names": 30, "responding": 20, "pq": 19, "not_pq": 1, "unknown": 0, "hosts": []},
        "kfh.com": {"names": 3, "responding": 2, "pq": 2, "not_pq": 0, "unknown": 0, "hosts": []},
        "adcb.com": {"error": "crt.sh: RuntimeError"}}
WEEKLY = {"www.alinma.com": {"ok": 1, "grade": "C", "grp": "secp256r1", "tls": "TLSv1.2", "pq": 0},
          "www.qnb.com": {"ok": 1, "grade": "A", "grp": "X25519MLKEM768", "tls": "TLSv1.3", "pq": 1},
          "www.alahli.com": {"ok": 0}}


class BankReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "bank_reports")
        os.makedirs(self.dir)
        report = bank_report.build(WEEKLY, DISC, "2026-11-12", "arab-banks-2026-11")
        with open(os.path.join(self.dir, "arab-banks-2026-11.json"), "w") as f:
            json.dump(report, f)
        self.patch = patch.object(bank_report, "DIR", self.dir)
        self.patch.start()
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://ather-quantum.com",
                                                "PAYPAL_CLIENT_ID": "", "PAYPAL_CLIENT_SECRET": "", "HASH_SALT": "b"},
                                               scanner=Mock(side_effect=AssertionError("no scans")))
        self.client = self.app.test_client()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_build_drops_host_names(self):
        text = open(os.path.join(self.dir, "arab-banks-2026-11.json")).read()
        self.assertNotIn("secret-api", text)
        self.assertEqual(len(json.loads(text)["rows"]), len(bank_report.BANKS))

    def test_ranking_and_totals(self):
        rows = bank_report.ranked(bank_report.load("arab-banks-2026-11"), optout=set())
        self.assertEqual([r["domain"] for r in rows[:2]], ["qnb.com", "alinma.com"])
        self.assertIsNone(next(r for r in rows if r["domain"] == "kfh.com")["share"])  # too few answered
        tot = bank_report.totals(rows)
        self.assertEqual((tot["responding"], tot["pq"], tot["pct"]), (60, 23, 38))

    def test_opt_out_removes_bank(self):
        rows = bank_report.ranked(bank_report.load("arab-banks-2026-11"), optout={"alinma.com"})
        self.assertNotIn("alinma.com", [r["domain"] for r in rows])

    def test_pages(self):
        ar = self.client.get("/banks/arab-banks-2026-11?lang=ar").get_data(as_text=True)
        self.assertIn("البنوك العربية والتشفير ما بعد الكمومي 2026", ar)
        self.assertIn("مصرف الإنماء", ar)
        self.assertIn("12 نوفمبر 2026", ar)
        self.assertIn("/audit", ar)
        self.assertNotIn("secret-api", ar)
        en = self.client.get("/banks/arab-banks-2026-11?lang=en").get_data(as_text=True)
        self.assertIn("Alinma Bank", en)
        self.assertLess(en.index("QNB"), en.index("Alinma Bank"))
        self.assertEqual(self.client.get("/banks/nope").status_code, 404)
        data = self.client.get("/banks/arab-banks-2026-11.json").get_json()
        self.assertEqual(data["license"], "CC BY 4.0")
        self.assertIn("/banks/arab-banks-2026-11", self.client.get("/sitemap-pages.xml").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()


class BankDetailTests(BankReportTests):
    def test_detail_page_award_and_badge(self):
        winner = self.client.get("/banks/arab-banks-2026-11/qnb.com?lang=ar").get_data(as_text=True)
        self.assertIn("بنك قطر الوطني", winner)
        self.assertIn("جائزة", winner)
        self.assertIn("/og/bank/arab-banks-2026-11/qnb.com.png", winner)
        self.assertIn("/audit?domain=qnb.com", winner)
        badge = self.client.get("/banks/arab-banks-2026-11/award/qnb.com.svg")
        self.assertEqual(badge.status_code, 200)
        self.assertIn("Quantum-safe bank 2026", badge.get_data(as_text=True))
        self.assertEqual(self.client.get("/banks/arab-banks-2026-11/award/alinma.com.svg").status_code, 404)
        loser = self.client.get("/banks/arab-banks-2026-11/alinma.com?lang=en").get_data(as_text=True)
        self.assertIn("protect 34 more subdomains and enable protection on the main website", loser)  # ceil(.95*40)=38-4
        self.assertIn("Other banks in Saudi Arabia", loser)
        self.assertEqual(self.client.get("/banks/arab-banks-2026-11/example.com").status_code, 404)

    def test_report_lists_winner(self):
        page = self.client.get("/banks/arab-banks-2026-11?lang=en").get_data(as_text=True)
        self.assertIn("/og/banks/arab-banks-2026-11.png", page)
        img = self.client.get("/og/banks/arab-banks-2026-11.png")
        self.assertEqual((img.status_code, img.mimetype), (200, "image/png"))
        self.assertIn("Quantum-safe bank 2026", page)
        self.assertIn("/banks/arab-banks-2026-11/qnb.com", page)
