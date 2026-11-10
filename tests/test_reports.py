import json
import shutil
import tempfile
import unittest

import quantum_saas_app
import reports


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.client = quantum_saas_app.create_app({"DATA_DIR": self.dir, "TESTING": True}).test_client()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_published_report_pages(self):
        rid = reports.ids()[0]
        for lang in ("en", "ar", "de"):
            r = self.client.get(f"/reports/{rid}?lang={lang}")
            self.assertEqual(r.status_code, 200, lang)
            body = r.get_data(as_text=True)
            self.assertIn(f'<html lang="{lang}"', body)
            self.assertIn("X25519MLKEM768", body)
            self.assertEqual(self.client.get(f"/press?lang={lang}").status_code, 200)
        self.assertIn(f"/reports/{rid}", self.client.get("/reports").headers["Location"])

    def test_json_and_charts(self):
        rid = reports.ids()[0]
        data = self.client.get(f"/reports/{rid}.json").get_json()
        self.assertEqual(data["license"], "CC BY 4.0")
        for name in reports.CHARTS:
            r = self.client.get(f"/reports/{rid}/{name}.svg")
            self.assertEqual(r.status_code, 200, name)
            self.assertTrue(r.get_data(as_text=True).startswith("<svg"))
        self.assertEqual(self.client.get(f"/reports/{rid}/evil.svg").status_code, 404)
        self.assertEqual(self.client.get("/reports/../etc").status_code, 404)
        self.assertEqual(self.client.get("/reports/2099-01").status_code, 404)

    def test_findings_use_report_numbers_only(self):
        r = reports.load(reports.ids()[0])
        facts = reports.findings(r, "en")
        self.assertIn(str(r["top1000"]["pct"]), facts[0])
        for lang in ("ar", "de"):
            self.assertEqual(len(reports.findings(r, lang)), len(facts))

    def test_svg_escapes_labels(self):
        svg = reports.bar_svg("<x>", [("a&b<script>", 50.0)], "s")
        self.assertNotIn("<script>", svg)
        self.assertIn("&lt;x&gt;", svg)


if __name__ == "__main__":
    unittest.main()
