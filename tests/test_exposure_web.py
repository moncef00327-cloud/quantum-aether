import os
import shutil
import tempfile
import unittest
from contextlib import closing
from unittest import mock

import adoption
import exposure
import quantum_saas_app
import sales_db


class ExposureWebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp, "TRUSTED_PROXIES": 0},
                                               scanner=lambda d: (_ for _ in ()).throw(AssertionError("no scans")))
        self.client = self.app.test_client()
        import search_indexing
        # Stand-in notable institution (banks-dach sector tag alone is no longer a blanket ticket).
        search_indexing.set_extra_allow_hosts({"bank.example"})
        with closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db"))) as c:
            adoption.init(c)
            rows = [("2026-W44", "bank.example", None, "banks-dach", 0), ("2026-W45", "bank.example", None, "banks-dach", 0),
                    ("2026-W46", "bank.example", None, "banks-dach", 1), ("2026-W47", "bank.example", None, "banks-dach", 1),
                    ("2026-W47", "tail.example", 5000, None, 0), ("2026-W47", "top.example", 10, None, 1)]
            for week, dom, rank, sector, pq in rows:
                c.execute("INSERT INTO adoption_results (week, domain, rank, sector, ok, grade, grp, tls, pq, scanned_at, as_name) "
                          "VALUES (?, ?, ?, ?, 1, ?, ?, 'TLSv1.3', ?, ?, 'NET')",
                          (week, dom, rank, sector, "A" if pq else "C", "X25519MLKEM768" if pq else "x25519", pq,
                           adoption.week_monday(week).isoformat() + "T04:00:00+00:00"))
            c.commit()
            exposure.anchor_week(c, self.tmp, "2026-W46", stamp=lambda p: (open(p + ".ots", "wb").write(b"x") and 0, "ok"))

    def tearDown(self):
        import search_indexing
        search_indexing.reset_runtime_state()
        shutil.rmtree(self.tmp)

    def test_page_languages_and_indexing(self):
        for lang in ("en", "ar", "de"):
            r = self.client.get(f"/exposure/bank.example?lang={lang}")
            self.assertEqual(r.status_code, 200, lang)
            body = r.get_data(as_text=True)
            self.assertIn("2026-W46", body)
            self.assertIn("2026-11-09", body)  # PQ since Monday of W46
            self.assertIn("_ather-claim.bank.example", body)
            self.assertIn("/monitoring/trial", body)
            self.assertNotIn("noindex", r.headers.get("X-Robots-Tag", ""))  # 4 measured weeks
        tail = self.client.get("/exposure/tail.example")
        self.assertEqual(tail.status_code, 200)
        self.assertIn("noindex", tail.headers["X-Robots-Tag"])
        self.assertNotIn("noindex", self.client.get("/exposure/top.example").headers.get("X-Robots-Tag", ""))
        self.assertEqual(self.client.get("/exposure/unknown.example").status_code, 404)
        self.assertEqual(self.client.get("/exposure?lang=ar").status_code, 200)

    def test_api_anchor_files_and_sitemap(self):
        data = self.client.get("/api/v1/exposure/bank.example").get_json()
        self.assertEqual(data["first_pq_week"], "2026-W46")
        self.assertEqual(data["status"], "went_pq")
        self.assertTrue(any(r["anchor"] for r in data["timeline"]))
        self.assertEqual(self.client.get("/exposure/anchors/2026-W46.json").status_code, 200)
        self.assertEqual(self.client.get("/exposure/anchors/2026-W46.manifest.txt").status_code, 200)
        self.assertEqual(self.client.get("/exposure/anchors/..%2Fquantum_saas.db").status_code, 404)
        idx = self.client.get("/sitemap.xml").get_data(as_text=True)
        self.assertIn("sitemap-exposure-1.xml", idx)
        sm = self.client.get("/sitemap-exposure-1.xml").get_data(as_text=True)
        self.assertIn("/exposure/bank.example", sm)
        self.assertIn("/exposure/top.example", sm)
        self.assertNotIn("tail.example", sm)

    def test_claim_flow(self):
        with mock.patch.object(exposure, "verify_claim", return_value={"verified": True}):
            r = self.client.post("/exposure/bank.example/claim", data={"lang": "en"})
        self.assertEqual(r.status_code, 303)
        self.assertIn("claim=ok", r.headers["Location"])
        self.assertIn("Claimed by the domain owner", self.client.get("/exposure/bank.example?lang=en").get_data(as_text=True))
        r = self.client.post("/exposure/bank.example/claim", data={"lang": "en"})
        self.assertIn("claim=wait", r.headers["Location"])

    def test_mcp_tool(self):
        r = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                            "params": {"name": "exposure_window", "arguments": {"domain": "bank.example"}}},
                             headers={"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-06-18"})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()["result"]["structuredContent"]["first_pq_week"], "2026-W46")


if __name__ == "__main__":
    unittest.main()
