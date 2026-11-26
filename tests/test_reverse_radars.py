"""Tests for Reverse MSP Radar (tools/msp_reverse_radar.py) and Reverse MCP Security Index (/mcp-index)."""
import json
import os
import tempfile
import unittest

import quantum_saas_app as app_mod
from tools import mcp_security_index as mcp_idx_tool
from tools import msp_reverse_radar as msp_radar


class MSPRadarTests(unittest.TestCase):
    def test_strict_b2b_email_filter_rejects_security_and_third_party(self):
        self.assertFalse(msp_radar.is_valid_b2b_email("security@firma.de", "firma.de"))
        self.assertFalse(msp_radar.is_valid_b2b_email("csirt@firma.de", "firma.de"))
        self.assertFalse(msp_radar.is_valid_b2b_email("datenschutz@firma.de", "firma.de"))
        self.assertFalse(msp_radar.is_valid_b2b_email("abuse@firma.de", "firma.de"))
        self.assertFalse(msp_radar.is_valid_b2b_email("info@other-agency.de", "firma.de"))
        self.assertTrue(msp_radar.is_valid_b2b_email("kontakt@firma.de", "firma.de"))
        self.assertTrue(msp_radar.is_valid_b2b_email("vertrieb@sub.firma.de", "firma.de"))

    def test_pick_best_b2b_email_ranks_sales_and_kontakt_above_generic(self):
        best = msp_radar.pick_best_b2b_email(
            ["security@acme.de", "datenschutz@acme.de", "info@acme.de", "vertrieb@acme.de"],
            "acme.de",
        )
        self.assertEqual(best, "vertrieb@acme.de")

    def test_render_msp_email_handles_all_tls_states(self):
        secret = "test-secret-key"
        base = {
            "domain": "systemhaus.de",
            "handshake_host": "www.systemhaus.de",
            "email": "kontakt@systemhaus.de",
            "tls_version": "TLSv1.3",
            "group": "x25519",
            "pq": False,
            "pq_supported_not_preferred": True,
            "pq_supported_group": "X25519MLKEM768",
            "grade": "B",
        }
        m1 = msp_radar.render_msp_email(base, secret)
        self.assertIn("unterstützt zwar X25519MLKEM768", m1["text"])
        self.assertIn("290 €", m1["text"])
        self.assertIn("/u/", m1["text"])
        self.assertEqual(m1["headers"]["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

        classical = dict(base, pq_supported_not_preferred=False, pq_supported_group="")
        m2 = msp_radar.render_msp_email(classical, secret)
        self.assertIn("klassischem Schlüsselaustausch x25519", m2["text"])

        pq_ok = dict(classical, pq=True, group="X25519MLKEM768", grade="A")
        m3 = msp_radar.render_msp_email(pq_ok, secret)
        self.assertIn("bereits TLSv1.3 mit X25519MLKEM768", m3["text"])


class MCPIndexTests(unittest.TestCase):
    def test_fetch_and_classify_and_summarize(self):
        sample_doc = {
            "servers": [
                {
                    "server": {
                        "name": "io.test/alpha",
                        "title": "Alpha MCP",
                        "remotes": [{"type": "streamable-http", "url": "https://mcp.alpha.example.org/mcp"}],
                    },
                    "_meta": {"io.modelcontextprotocol.registry/official": {"status": "active", "isLatest": True}},
                },
                {
                    "server": {
                        "name": "io.test/local",
                        "remotes": [{"type": "streamable-http", "url": "https://localhost:8080/mcp"}],
                    },
                    "_meta": {"io.modelcontextprotocol.registry/official": {"status": "active", "isLatest": True}},
                },
            ],
            "metadata": {},
        }
        hosts, total = mcp_idx_tool.fetch_remote_mcp_hosts(max_pages=1, limit=10, getter=lambda _u: sample_doc)
        self.assertEqual(total, 2)
        self.assertEqual([h["host"] for h in hosts], ["mcp.alpha.example.org"])

        self.assertEqual(mcp_idx_tool.classify_kx({"version": "TLSv1.3", "pq": True}), "pq_hybrid")
        self.assertEqual(
            mcp_idx_tool.classify_kx({"version": "TLSv1.3", "pq": False, "pq_supported_not_preferred": True}),
            "pq_not_preferred",
        )
        self.assertEqual(mcp_idx_tool.classify_kx({"version": "TLSv1.3", "pq": False}), "classical")
        self.assertEqual(mcp_idx_tool.classify_kx({"version": "TLSv1.2", "pq": False}), "tls12")

        summary = mcp_idx_tool.summarize(
            [
                {"host": "a.test", "status": "pq_hybrid", "group": "X25519MLKEM768"},
                {"host": "b.test", "status": "pq_not_preferred", "group": "x25519"},
                {"host": "c.test", "status": "classical", "group": "x25519"},
                {"host": "d.test", "status": "unreachable", "group": None},
            ],
            registry_entries=10,
        )
        self.assertEqual(summary["measured"], 3)
        self.assertEqual(summary["pq_hybrid"], 1)
        self.assertEqual(summary["pq_not_preferred"], 1)
        self.assertEqual(summary["pq_pct"], 33.3)

    def test_mcp_index_routes_en_ar_de_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            snap = {
                "summary": {
                    "updated_at": "2026-11-26T20:30:00Z",
                    "registry_entries_checked": 200,
                    "total_hosts": 2,
                    "measured": 2,
                    "pq_hybrid": 1,
                    "pq_pct": 50.0,
                    "pq_not_preferred": 1,
                    "classical": 0,
                    "tls12": 0,
                    "unreachable": 0,
                    "top_groups": [{"group": "X25519MLKEM768", "count": 1}],
                },
                "results": [
                    {
                        "host": "ather-quantum.com",
                        "server_name": "io.github.moncef00327-cloud/quantum-aether",
                        "title": "Quantum Aether",
                        "tls_version": "TLSv1.3",
                        "group": "X25519MLKEM768",
                        "pq": True,
                        "pq_supported_not_preferred": False,
                        "pq_supported_group": None,
                        "status": "pq_hybrid",
                    },
                    {
                        "host": "misconfig.mcp.test",
                        "server_name": "test/misconfig",
                        "title": "Misconfig MCP",
                        "tls_version": "TLSv1.3",
                        "group": "x25519",
                        "pq": False,
                        "pq_supported_not_preferred": True,
                        "pq_supported_group": "X25519MLKEM768",
                        "status": "pq_not_preferred",
                    },
                ],
            }
            with open(os.path.join(tmp, "mcp_index.json"), "w", encoding="utf-8") as f:
                json.dump(snap, f)

            app = app_mod.create_app({"TESTING": True, "DATA_DIR": tmp, "DB_PATH": os.path.join(tmp, "test.db")})
            client = app.test_client()
            for lang in ("en", "ar", "de"):
                r = client.get(f"/mcp-index?lang={lang}")
                self.assertEqual(r.status_code, 200, lang)
                body = r.get_data(as_text=True)
                self.assertIn("ather-quantum.com", body)
                self.assertIn("misconfig.mcp.test", body)
            rj = client.get("/api/v1/mcp-index")
            self.assertEqual(rj.status_code, 200)
            payload = rj.get_json()
            self.assertEqual(payload["summary"]["measured"], 2)
            self.assertEqual(payload["summary"]["pq_not_preferred"], 1)


if __name__ == "__main__":
    unittest.main()
