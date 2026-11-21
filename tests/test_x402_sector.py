"""Paid read-only x402 sector snapshot (HTTP + remote MCP), 2026-11-21."""
import base64
import copy
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock

import adoption
import agent_discovery
import quantum_saas_app
import sector_snapshot
import x402_pay
from tests.test_app import RESULT

KEY = sector_snapshot.DEFAULT_SECTOR
TX = "0x" + "cd" * 32


class SectorX402Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://ather-quantum.com",
             "PAYPAL_CLIENT_ID": "", "PAYPAL_CLIENT_SECRET": "", "USDC_BASE_ADDR": "0x" + "44" * 20},
            scanner=Mock(return_value=copy.deepcopy(RESULT)))
        self.client = self.app.test_client()
        self.calls = []

        def facilitator(path, body):
            self.calls.append(path)
            return {"isValid": True} if path == "/verify" else {"success": True, "transaction": TX, "network": "eip155:8453"}
        self.app.extensions["x402_facilitator"] = facilitator
        domains = sector_snapshot.sectors()[KEY]["domains"][:3]
        conn = sqlite3.connect(f"{self.tmp.name}/quantum_saas.db")
        adoption.init(conn)
        with conn:
            for i, d in enumerate(domains):
                conn.execute("INSERT INTO adoption_results (week, domain, rank, sector, ok, grade, grp, tls, pq, scanned_at, unsure) "
                             "VALUES ('2026-W47', ?, NULL, ?, 1, ?, ?, 'TLSv1.3', ?, '2026-11-19T10:00:00Z', 0)",
                             (d, KEY, "A" if i == 0 else "B", "X25519MLKEM768" if i == 0 else "x25519", 1 if i == 0 else 0))
        conn.close()
        self.domains = domains

    def tearDown(self):
        self.tmp.cleanup()

    def rpc(self, method, params=None):
        body = {"jsonrpc": "2.0", "id": 1, "method": method, **({"params": params} if params is not None else {})}
        return self.client.post("/mcp", json=body)

    def test_units_exact(self):
        self.assertEqual(x402_pay.units("0.50"), "500000")
        self.assertEqual(x402_pay.units("49.00"), "49000000")
        self.assertEqual(x402_pay.units("0.001"), "1000")

    def test_tool_is_read_only_and_states_x402_price(self):
        tools = {t["name"]: t for t in self.rpc("tools/list").json["result"]["tools"]}
        t = tools["get_sector_snapshot"]
        self.assertTrue(t["annotations"]["readOnlyHint"])
        self.assertIn("x402", t["description"])
        self.assertIn("$0.50 USDC", t["description"])
        self.assertIn(KEY, t["inputSchema"]["properties"]["sector"]["enum"])
        self.assertNotIn("get_sector_snapshot", agent_discovery.SECURITY_COPILOT_TOOLS)

    def test_call_without_payment_returns_challenge_and_never_charges(self):
        r = self.rpc("tools/call", {"name": "get_sector_snapshot", "arguments": {}}).json["result"]
        self.assertTrue(r["isError"])
        ch = r["structuredContent"]
        self.assertEqual(ch["x402Version"], 2)
        self.assertEqual(ch["accepts"][0]["amount"], "500000")
        self.assertEqual(ch["accepts"][0]["network"], "eip155:8453")
        self.assertTrue(ch["resource"]["url"].endswith(f"/api/v1/agent/sector/{KEY}"))
        self.assertEqual(self.calls, [])
        self.assertNotIn("domains", json.dumps(ch))

    def test_paid_call_returns_snapshot_once_per_transaction(self):
        ch = self.rpc("tools/call", {"name": "get_sector_snapshot", "arguments": {"sector": KEY}}).json["result"]["structuredContent"]
        payload = {"x402Version": 2, "resource": ch["resource"], "accepted": ch["accepts"][0]}
        paid = self.rpc("tools/call", {"name": "get_sector_snapshot", "arguments": {"sector": KEY}, "_meta": {"x402/payment": payload}}).json["result"]
        self.assertFalse(paid["isError"])
        snap = paid["structuredContent"]
        self.assertEqual(snap["sector"], KEY)
        self.assertEqual(snap["summary"]["post_quantum"], 1)
        self.assertEqual({d["domain"] for d in snap["domains"]}, set(self.domains))
        self.assertEqual(paid["_meta"]["x402/payment-response"]["transaction"], TX)
        self.assertEqual(self.calls, ["/verify", "/settle"])
        again = self.rpc("tools/call", {"name": "get_sector_snapshot", "arguments": {"sector": KEY}, "_meta": {"x402/payment": payload}}).json["result"]
        self.assertTrue(again["isError"])
        self.assertEqual(again["structuredContent"]["error"], "payment_already_consumed")

    def test_wrong_amount_rejected_before_facilitator(self):
        ch = self.rpc("tools/call", {"name": "get_sector_snapshot", "arguments": {}}).json["result"]["structuredContent"]
        accepted = dict(ch["accepts"][0], amount="1")
        r = self.rpc("tools/call", {"name": "get_sector_snapshot", "arguments": {},
                                    "_meta": {"x402/payment": {"x402Version": 2, "resource": ch["resource"], "accepted": accepted}}}).json["result"]
        self.assertTrue(r["isError"])
        self.assertIn("does not match", r["structuredContent"]["error"])
        self.assertEqual(self.calls, [])

    def test_unknown_sector_and_http_endpoint(self):
        self.assertEqual(self.rpc("tools/call", {"name": "get_sector_snapshot", "arguments": {"sector": "nope"}}).json["error"]["code"], -32602)
        self.assertEqual(self.client.get("/api/v1/agent/sector/nope").status_code, 404)
        r = self.client.get(f"/api/v1/agent/sector/{KEY}")
        self.assertEqual(r.status_code, 402)
        self.assertEqual(json.loads(base64.b64decode(r.headers["PAYMENT-REQUIRED"]))["accepts"][0]["amount"], "500000")

    def test_unavailable_without_receiver(self):
        self.app.config["USDC_BASE_ADDR"] = ""
        self.assertEqual(self.client.get(f"/api/v1/agent/sector/{KEY}").status_code, 503)

    def test_service_info_lists_product(self):
        m = self.client.get("/api/v1/agent/discovery").json
        self.assertEqual(m["pricing"]["sector_snapshot"]["amount"], "0.50")
        self.assertEqual(m["pricing"]["sector_snapshot"]["mcp_tool"], "get_sector_snapshot")


if __name__ == "__main__":
    unittest.main()
