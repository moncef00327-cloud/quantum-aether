"""PQ-TLS Index (/index, 2026-11-21): page in en/ar/de, CDN caveat, no certificate details, canary-marked downloads
with blank institution names, correction form into dach_corrections, sitemap, /site/ allow-list via pq_index_orgs.csv."""
import csv
import io
import json
import os
import tempfile
import unittest
from unittest.mock import Mock

import pq_index
import quantum_saas_app
import search_indexing
from tests.test_app import RESULT

def _row(i, cc, region, sector, host, status, network="Cloudflare, Inc."):
    return {"org_id": f"{cc}-x-{i:03d}", "country_code": cc, "region": region, "sector": sector, "role": "bank",
            "name": f"Institution {i}", "host": host, "status": status,
            "group": "X25519MLKEM768" if status == "pq_hybrid" else ("x25519" if status == "classical" else ""),
            "tls_version": "TLSv1.3" if status != "not_measured" else "", "network": network if status != "not_measured" else "",
            "asn": 13335 if status != "not_measured" else None, "scanned_at_utc": "2026-11-21T13:40:00+00:00"}

DATA = {"meta": {"edition": "2026-11", "scanner_version": "2.0", "vantage": "London, UK (Vultr, AS20473)",
                 "scan_started_utc": "2026-11-21T13:37:15+00:00", "scan_finished_utc": "2026-11-21T13:49:00+00:00", "license": "CC BY 4.0"},
        "results": [_row(1, "SA", "GCC", "banking", "www.bank-one.sa", "pq_hybrid"),
                    _row(2, "SA", "GCC", "banking", "www.bank-two.sa", "classical", "Local Telecom"),
                    _row(3, "DE", "DACH", "government", "www.amt.de", "pq_hybrid", "ITZBund"),
                    _row(4, "DZ", "Maghreb", "telecom", "www.telco.dz", "not_measured"),
                    _row(5, "EG", "Egypt", "central-bank", "www.cb.eg", "classical", "Local"),
                    _row(6, "EU", "EU institutions", "regulator", "www.eu-body.europa.eu", "pq_hybrid")]}


class PqIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        with open(os.path.join(self.tmp.name, "pq_index_2026-11.json"), "w", encoding="utf-8") as f:
            json.dump(DATA, f)
        with open(os.path.join(self.tmp.name, "pq_index_orgs.csv"), "w", encoding="utf-8") as f:
            f.write("org_id,name,host\nSA-x-001,Institution 1,www.bank-one.sa\n")
        os.environ["PQ_INDEX_DIR"] = self.tmp.name
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://ather-quantum.com"},
                                               scanner=Mock(return_value=dict(RESULT)))
        self.client = self.app.test_client()

    def tearDown(self):
        os.environ.pop("PQ_INDEX_DIR", None)
        self.tmp.cleanup()

    def test_view_counts_exclude_not_measured_and_reference(self):
        v = pq_index.view(pq_index.load(self.tmp.name))
        self.assertEqual(v["overall"], {"pq": 2, "classical": 2, "n": 4, "not_measured": 1, "total": 5, "pct": 50.0})
        self.assertEqual(v["reference"]["pq"], 1)
        self.assertEqual(v["cdn"], 2)  # Cloudflare rows (incl. EU reference); ITZBund is not a CDN
        self.assertEqual(v["pq_all"], 3)

    def test_page_in_three_languages(self):
        for lang, word in (("en", "CDN effect"), ("ar", "أثر شبكات توصيل المحتوى"), ("de", "CDN-Effekt")):
            r = self.client.get(f"/index?lang={lang}")
            self.assertEqual(r.status_code, 200, lang)
            body = r.get_data(as_text=True)
            self.assertIn(word, body)
            self.assertIn("www.bank-one.sa", body)
            self.assertIn("2.0", body)
            self.assertIn('action="/index/correction"', body)
        self.assertIn("not measured", self.client.get("/index?lang=en").get_data(as_text=True))

    def test_no_certificate_details_published(self):
        page = self.client.get("/index?lang=en").get_data(as_text=True)
        csv_body = self.client.get("/index.csv").get_data(as_text=True)
        for text in (page, csv_body, self.client.get("/index.json").get_data(as_text=True)):
            for word in ("cert_issuer", "cert_verified", "not_after", "days_left", "expired"):
                self.assertNotIn(word, text)

    def test_csv_and_json_have_canaries_with_blank_names(self):
        import data_access
        with self.app.app_context():
            conn = quantum_saas_app.db()
            data_access.init(conn)
            with conn:
                for name in ("zz-canary-one.example", "zz-canary-two.example"):
                    conn.execute("INSERT INTO data_canaries (domain, created_at, status) VALUES (?, '2026-11-21', 'active')", (name,))
        rows = list(csv.DictReader(io.StringIO(self.client.get("/index.csv").get_data(as_text=True))))
        hosts = {r["host"] for r in rows}
        self.assertTrue({"zz-canary-one.example", "zz-canary-two.example"} <= hosts)
        for r in rows:
            if r["host"].startswith("zz-canary"):
                self.assertEqual(r["name"], "")
                self.assertEqual(r["org_id"], "")
        body = json.loads(self.client.get("/index.json").get_data(as_text=True))
        self.assertEqual(body["meta"]["license"], "CC BY 4.0")
        self.assertTrue(any(r["host"].startswith("zz-canary") and r["name"] == "" for r in body["results"]))
        self.assertEqual(body["summary"]["overall_core"]["n"], 4)

    def test_correction_stored_in_dach_corrections(self):
        r = self.client.post("/index/correction", data={"lang": "de", "institution": "www.bank-one.sa", "name": "Test",
                                                        "email": "a@example.org", "message": "Please re-test", "rescan": "1"})
        self.assertEqual(r.status_code, 303)
        self.assertIn("sent=1", r.headers["Location"])
        with self.app.app_context():
            row = quantum_saas_app.db().execute("SELECT provider, wants_rescan FROM dach_corrections").fetchone()
        self.assertEqual(tuple(row), ("[PQ-INDEX] www.bank-one.sa", 1))
        bad = self.client.post("/index/correction", data={"institution": "www.not-listed.com", "name": "T",
                                                          "email": "a@example.org", "message": "hello"})
        self.assertIn("error=invalid", bad.headers["Location"])

    def test_sitemap_and_links(self):
        self.assertIn("/index?lang=de", self.client.get("/sitemap-pages.xml").get_data(as_text=True))
        self.assertIn("/index?lang=en", self.client.get("/?lang=en").get_data(as_text=True))
        self.assertEqual(self.client.get("/index/panel.csv").status_code, 200)

    def test_live_panel_feeds_site_allow_list(self):
        path = os.path.join(os.path.dirname(pq_index.__file__), "data", "pq_index_orgs.csv")
        self.assertIn(path, [str(p) for p in search_indexing.ORGS_CSV_CANDIDATES])
        if os.path.exists(path):
            self.assertIn("alahli.com", search_indexing._read_orgs_csv(search_indexing.ORGS_CSV_CANDIDATES[0]))

    def test_live_data_file_is_clean(self):
        path = os.path.join(os.path.dirname(pq_index.__file__), "data", "pq_index_2026-11.json")
        if not os.path.exists(path):
            self.skipTest("no live edition")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        keys = {k for r in data["results"] for k in r}
        self.assertFalse({k for k in keys if k.startswith("cert") or k in ("ip", "previously_contacted", "grade")})
        alahli = [r for r in data["results"] if r["host"] == "www.alahli.com"][0]
        self.assertEqual(alahli["status"], "not_measured")


if __name__ == "__main__":
    unittest.main()
