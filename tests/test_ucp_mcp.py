"""Tests for UCP (Universal Commerce Protocol) & strengthened MCP hub (batch_scan_tls, get_live_cbom, index, catalog, A2UI)."""
import copy
import json
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import a2ui_cards
import quantum_saas_app
import ucp_commerce
from tests.test_app import RESULT


class UcpAndMcpHubTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.scanner = Mock(return_value=copy.deepcopy(RESULT))
        self.app = quantum_saas_app.create_app(
            {
                "TESTING": True,
                "DATA_DIR": self.tmp.name,
                "PUBLIC_URL": "https://ather-quantum.com",
                "USDC_BASE_ADDR": "0x" + "55" * 20,
                "SCANS_PER_HOUR": 2,
                "GLOBAL_SCANS_PER_HOUR": 10,
            },
            scanner=self.scanner,
        )
        self.tx_n = 0

        def fake_facilitator(path, body):
            if path == "/verify":
                return {"isValid": True}
            self.tx_n += 1
            return {"success": True, "network": "eip155:8453", "transaction": "0x" + f"{self.tx_n:064x}"}

        self.app.extensions["x402_facilitator"] = fake_facilitator
        self.client = self.app.test_client()

    def rpc(self, method, params=None, path="/mcp"):
        body = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            body["params"] = params
        return self.client.post(path, json=body)

    def test_ucp_profile_catalog_and_checkout_sessions(self):
        for p in ("/.well-known/ucp", "/.well-known/ucp.json"):
            r = self.client.get(p)
            self.assertEqual(r.status_code, 200, p)
            self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "*")
            doc = r.json
            self.assertEqual(doc["ucp"]["version"], ucp_commerce.UCP_VERSION)
            services = doc["ucp"]["services"]["dev.ucp.shopping"]
            mcp_srv = next(s for s in services if s["transport"] == "mcp")
            self.assertTrue(mcp_srv["preferred"])
            self.assertEqual(mcp_srv["endpoint"], "https://ather-quantum.com/mcp")
            self.assertIn("dev.ucp.shopping.catalog", doc["ucp"]["capabilities"])
            self.assertIn("dev.ucp.shopping.checkout", doc["ucp"]["capabilities"])
            self.assertEqual(doc["merchant"]["jwks_uri"], "https://ather-quantum.com/.well-known/jwks.json")

        cat = self.client.get("/api/v1/ucp/catalog")
        self.assertEqual(cat.status_code, 200)
        skus = {i["id"]: i for i in cat.json["items"]}
        self.assertEqual(skus["qa-batch-scan-10"]["price"], "0.10")
        self.assertEqual(skus["qa-batch-scan-10"]["mcp_tool"], "batch_scan_tls")
        self.assertEqual(skus["qa-live-cbom"]["price"], "0.25")
        self.assertEqual(skus["qa-live-cbom"]["mcp_tool"], "get_live_cbom")
        self.assertEqual(skus["qa-msp-pilot"]["price"], "290.00")

        chk = self.client.post("/api/v1/ucp/checkout-sessions", json={"sku": "qa-batch-scan-10", "domain": "cloudflare.com"})
        self.assertEqual(chk.status_code, 201)
        self.assertEqual(chk.json["status"], "ready_for_complete")
        self.assertEqual(chk.json["mcp_execution"]["tool"], "batch_scan_tls")
        self.assertEqual(chk.json["totals"]["total"], "0.10")

        chk_mon = self.client.post(
            "/api/v1/ucp/checkout-sessions",
            json={"line_items": [{"item": {"id": "qa-monitoring-starter"}, "quantity": 1}], "domain": "example.com"},
        )
        self.assertEqual(chk_mon.status_code, 201)
        self.assertIn("/monitoring?domain=example.com#trial-form", chk_mon.json["continue_url"])

        bad = self.client.post("/api/v1/ucp/checkout-sessions", json={"sku": "does-not-exist"})
        self.assertEqual(bad.status_code, 400)
        self.scanner.assert_not_called()

    def test_mcp_free_read_only_tools_and_resources_bridge_ucp_index_and_a2ui(self):
        # Seed a mock mcp_index.json snapshot
        snap = {
            "summary": {"measured": 2, "pq_hybrid": 1, "pq_not_preferred": 1, "classical": 0},
            "results": [
                {"host": "pq.example.com", "status": "pq_hybrid", "grade": "A"},
                {"host": "pref.example.com", "status": "pq_not_preferred", "grade": "B"},
            ],
        }
        with open(os.path.join(self.tmp.name, "mcp_index.json"), "w", encoding="utf-8") as f:
            json.dump(snap, f)

        for path in ("/mcp", "/mcp/free"):
            r_idx = self.rpc("tools/call", {"name": "get_mcp_security_index", "arguments": {"status": "pq_not_preferred"}}, path=path).json["result"]
            self.assertFalse(r_idx["isError"])
            self.assertEqual(r_idx["structuredContent"]["total_matching"], 1)
            self.assertEqual(r_idx["structuredContent"]["results"][0]["host"], "pref.example.com")

            r_cat = self.rpc("tools/call", {"name": "get_commerce_catalog", "arguments": {"category": "micro_x402"}}, path=path).json["result"]
            self.assertFalse(r_cat["isError"])
            self.assertEqual({i["id"] for i in r_cat["structuredContent"]["items"]}, {"qa-batch-scan-10", "qa-live-cbom", "qa-sector-snapshot"})

            r_ui = self.rpc("tools/call", {"name": "get_a2ui_card", "arguments": {"domain": "example.com", "lang": "ar"}}, path=path).json["result"]
            self.assertFalse(r_ui["isError"])
            self.assertEqual(r_ui["structuredContent"]["extensionUri"], a2ui_cards.A2UI_EXTENSION_URI)
            self.assertEqual(len(r_ui["structuredContent"]["messages"]), 3)

        # New MCP resources & prompt
        for uri in ("qa://mcp-index", "qa://ucp/catalog", "qa://a2ui/evidence/example.com"):
            rr = self.rpc("resources/read", {"uri": uri})
            self.assertEqual(rr.status_code, 200, uri)
            self.assertTrue(rr.json["result"]["contents"])
        p = self.rpc("prompts/get", {"name": "batch_pqc_triage", "arguments": {"domains": "a.com,b.com"}}).json["result"]
        self.assertIn("batch_scan_tls", p["messages"][0]["content"]["text"])
        self.scanner.assert_not_called()

    def test_mcp_x402_micro_tools_batch_scan_and_live_cbom(self):
        # 1) batch_scan_tls unpaid -> 402 x402 challenge ($0.10 = 100000 units), then paid -> settled
        ch_res = self.rpc("tools/call", {"name": "batch_scan_tls", "arguments": {"domains": ["cloudflare.com", "example.com"]}}).json["result"]
        self.assertTrue(ch_res["isError"])
        challenge = ch_res["structuredContent"]
        self.assertEqual(challenge["accepts"][0]["amount"], "100000")

        payment = {"x402Version": 2, "resource": challenge["resource"], "accepted": challenge["accepts"][0], "payload": {"signature": "0x" + "ab" * 65}}
        with patch("quantum_vuln_scanner.scan_full", side_effect=lambda dom, timeout=6.0: dict(copy.deepcopy(RESULT), domain=dom)):
            paid = self.rpc(
                "tools/call",
                {"name": "batch_scan_tls", "arguments": {"domains": ["cloudflare.com", "example.com"]}, "_meta": {"x402/payment": payment}},
            ).json["result"]
        self.assertFalse(paid["isError"])
        self.assertEqual(paid["structuredContent"]["sku"], "x402_batch_scan_v1")
        self.assertEqual(paid["structuredContent"]["count"], 2)
        self.assertIn("x402/payment-response", paid["_meta"])

        # 2) get_live_cbom unpaid -> 402 x402 challenge ($0.25 = 250000 units), then paid -> CycloneDX 1.6 CBOM
        ch_cbom = self.rpc("tools/call", {"name": "get_live_cbom", "arguments": {"domain": "example.com"}}).json["result"]
        self.assertTrue(ch_cbom["isError"])
        c2 = ch_cbom["structuredContent"]
        self.assertEqual(c2["accepts"][0]["amount"], "250000")
        p2 = {"x402Version": 2, "resource": c2["resource"], "accepted": c2["accepts"][0], "payload": {"signature": "0x" + "cd" * 65}}
        paid_cbom = self.rpc(
            "tools/call",
            {"name": "get_live_cbom", "arguments": {"domain": "example.com"}, "_meta": {"x402/payment": p2}},
        ).json["result"]
        self.assertFalse(paid_cbom["isError"])
        self.assertEqual(paid_cbom["structuredContent"]["sku"], "x402_cbom_v1")
        self.assertEqual(paid_cbom["structuredContent"]["cbom"]["bomFormat"], "CycloneDX")
        self.assertEqual(paid_cbom["structuredContent"]["cbom"]["specVersion"], "1.6")

        # Paid tools excluded from /mcp/free
        blocked = self.rpc("tools/call", {"name": "batch_scan_tls", "arguments": {"domains": ["example.com"]}}, path="/mcp/free").json
        self.assertEqual(blocked["error"]["code"], -32602)

    def test_discovery_surfaces_advertise_ucp_and_upgraded_mcp(self):
        self.assertIn('rel="ucp-profile"', self.client.get("/").headers.get("Link", ""))
        self.assertIn("/.well-known/ucp", self.client.get("/robots.txt").get_data(as_text=True))
        llms = self.client.get("/llms.txt").get_data(as_text=True)
        self.assertIn("/.well-known/ucp", llms)
        self.assertIn("batch_scan_tls", llms)
        self.assertIn("get_live_cbom", llms)
        x402 = self.client.get("/.well-known/x402").json
        ep_map = {e["id"]: e for e in x402["endpoints"]}
        self.assertEqual(ep_map["batch_scan"]["mcp_tool"], "batch_scan_tls")
        self.assertEqual(ep_map["live_cbom"]["mcp_tool"], "get_live_cbom")


if __name__ == "__main__":
    unittest.main()
