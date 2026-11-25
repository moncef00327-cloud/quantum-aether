"""Tests for ACP REST compatibility, Ed25519 JWS signed receipts (/.well-known/jwks.json),
privacy-safe agent protocol audit trail, and the MCP/A2A/ACP security guide.
"""
import copy
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock

import agent_audit
import quantum_saas_app
import signed_receipts
from tests.test_app import RESULT


class AcpJwsAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.scanner = Mock(return_value=copy.deepcopy(RESULT))
        self.app = quantum_saas_app.create_app({
            "TESTING": True,
            "DATA_DIR": self.tmp.name,
            "PUBLIC_URL": "https://ather-quantum.com",
            "SCANS_PER_HOUR": 1,
            "GLOBAL_SCANS_PER_HOUR": 10,
            "ADMIN_PASSWORD_HASH": "",
        }, scanner=self.scanner)
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_jwks_and_key_permissions(self):
        r = self.client.get("/.well-known/jwks.json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "*")
        keys = r.json["keys"]
        self.assertEqual(len(keys), 1)
        jwk = keys[0]
        self.assertEqual(jwk["kty"], "OKP")
        self.assertEqual(jwk["crv"], "Ed25519")
        self.assertEqual(jwk["alg"], "EdDSA")
        self.assertEqual(jwk["use"], "sig")
        self.assertTrue(jwk["kid"])
        self.assertTrue(jwk["x"])

        key_path = Path(self.tmp.name) / signed_receipts.KEY_FILENAME
        self.assertTrue(key_path.exists())
        mode = stat.S_IMODE(os.stat(key_path).st_mode)
        self.assertEqual(mode, 0o600)

        # Sign, verify, and reject tampered JWS
        tok = signed_receipts.sign_receipt(self.tmp.name, {"domain": "example.com", "grade": "A"}, "https://ather-quantum.com")
        hdr, payload = signed_receipts.verify_receipt(self.tmp.name, tok)
        self.assertEqual(hdr["alg"], "EdDSA")
        self.assertEqual(hdr["kid"], jwk["kid"])
        self.assertEqual(payload["domain"], "example.com")
        self.assertEqual(payload["iss"], "https://ather-quantum.com")

        h_part, p_part, s_part = tok.split(".")
        tampered = f"{h_part}.{p_part}A.{s_part}"
        with self.assertRaises(ValueError):
            signed_receipts.verify_receipt(self.tmp.name, tampered)

    def test_acp_agents_discovery_and_link_headers(self):
        r = self.client.get("/acp/agents")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "*")
        agents = r.json["agents"]
        self.assertEqual(len(agents), 1)
        m = agents[0]
        self.assertEqual(m["name"], "quantum-aether")
        self.assertIn("application/json", m["input_content_types"])
        self.assertEqual(m["metadata"]["jwks_uri"], "https://ather-quantum.com/.well-known/jwks.json")
        self.assertEqual(m["metadata"]["a2a_agent_card"], "https://ather-quantum.com/.well-known/agent-card.json")
        self.assertIn("29 EUR/month", m["metadata"]["services"]["monitoring"]["plans"]["starter"])

        r_one = self.client.get("/acp/agents/quantum-aether")
        self.assertEqual(r_one.status_code, 200)
        self.assertEqual(r_one.json["name"], "quantum-aether")

        r_404 = self.client.get("/acp/agents/unknown-agent")
        self.assertEqual(r_404.status_code, 404)

        # Link header advertises both acp-agents and jwks
        home_link = self.client.get("/?lang=en").headers.get("Link", "")
        self.assertIn('rel="acp-agents"', home_link)
        self.assertIn('rel="jwks"', home_link)

    def test_acp_runs_evidence_scan_ratelimit_and_paid_data(self):
        # 1) Read-only tls-evidence never scans and returns a verifiable JWS receipt
        r = self.client.post("/acp/runs", json={
            "agent_name": "quantum-aether",
            "mode": "sync",
            "input": [{"role": "user", "parts": [{"content_type": "text/plain", "content": "Is example.com post-quantum ready?"}]}],
        })
        self.assertEqual(r.status_code, 200)
        self.scanner.assert_not_called()
        body = r.json
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["agent_name"], "quantum-aether")
        data = body["output"][0]["parts"][1]["data"]
        self.assertEqual(data["state"], "not_scanned")
        self.assertEqual(data["jwks_url"], "https://ather-quantum.com/.well-known/jwks.json")
        _, claims = signed_receipts.verify_receipt(self.tmp.name, data["receipt_jws"])
        self.assertEqual(claims["domain"], "example.com")
        self.assertEqual(claims["kind"], "tls-evidence")

        # 2) Live tls-scan via application/json part scans once and returns signed receipt
        r_scan = self.client.post("/acp/runs", json={
            "agent_name": "quantum-aether",
            "input": [{"role": "user", "parts": [{"content_type": "application/json", "content": json.dumps({"skill": "tls-scan", "domain": "example.com"})}]}],
        })
        self.assertEqual(r_scan.status_code, 200)
        self.assertEqual(self.scanner.call_count, 1)
        scan_data = r_scan.json["output"][0]["parts"][1]["data"]
        self.assertEqual(scan_data["domain"], "example.com")
        self.assertTrue(scan_data["receipt_jws"])
        _, scan_claims = signed_receipts.verify_receipt(self.tmp.name, scan_data["receipt_jws"])
        self.assertEqual(scan_claims["kind"], "tls-scan")
        self.assertEqual(scan_claims["scan_id"], scan_data["scan_id"])

        # 3) Second scan hits rate limit cleanly and returns signed stored_evidence
        r_limit = self.client.post("/acp/runs", json={
            "agent_name": "quantum-aether",
            "input": [{"role": "user", "parts": [{"content_type": "text/plain", "content": "scan example.com"}]}],
        })
        self.assertEqual(r_limit.status_code, 200)
        self.assertEqual(self.scanner.call_count, 1)
        lim_data = r_limit.json["output"][0]["parts"][1]["data"]
        self.assertEqual(lim_data["error"], "rate_limited")
        _, lim_claims = signed_receipts.verify_receipt(self.tmp.name, lim_data["stored_evidence"]["receipt_jws"])
        self.assertEqual(lim_claims["domain"], "example.com")

        # 4) paid-data returns 29 EUR / 99 EUR / 490 EUR + x402
        r_paid = self.client.post("/acp/runs", json={
            "agent_name": "quantum-aether",
            "input": [{"role": "user", "parts": [{"content_type": "text/plain", "content": "How do I buy the full report?"}]}],
        })
        self.assertEqual(r_paid.status_code, 200)
        paid_text = r_paid.json["output"][0]["parts"][0]["content"]
        self.assertIn("29 EUR/mo", paid_text)
        self.assertIn("490 EUR", paid_text)
        self.assertIn("x402", paid_text)

        # 5) agent-affiliate returns programmatic registration instructions
        r_aff = self.client.post("/acp/runs", json={
            "agent_name": "quantum-aether",
            "input": [{"role": "user", "parts": [{"content_type": "text/plain", "content": "How does your agent affiliate referral commission work?"}]}],
        })
        self.assertEqual(r_aff.status_code, 200)
        aff_text = r_aff.json["output"][0]["parts"][0]["content"]
        self.assertIn("register_agent_affiliate", aff_text)
        self.assertIn("30%", aff_text)

        # 5b) tls-attestation returns 5.00 USDC details + free sample PDF without scanning
        r_att = self.client.post("/acp/runs", json={
            "agent_name": "quantum-aether",
            "input": [{"role": "user", "parts": [{"content_type": "text/plain", "content": "Give me the CycloneDX CBOM auditor PDF attestation details"}]}],
        })
        self.assertEqual(r_att.status_code, 200)
        self.assertEqual(self.scanner.call_count, 1)
        att_data = r_att.json["output"][0]["parts"][1]["data"]
        self.assertEqual(att_data["price_usd"], "5.00")
        self.assertIs(att_data["read_only"], False)
        self.assertEqual(att_data["sample_pdf"], "https://ather-quantum.com/api/v1/attestation/sample.pdf")

        # 5c) msp-pilot returns 290 EUR IT-Dienstleister Pilot without scanning
        r_pilot = self.client.post("/acp/runs", json={
            "agent_name": "quantum-aether",
            "input": [{"role": "user", "parts": [{"content_type": "text/plain", "content": "Tell me about the IT-Dienstleister MSP Pilot (290 EUR)"}]}],
        })
        self.assertEqual(r_pilot.status_code, 200)
        self.assertEqual(self.scanner.call_count, 1)
        p_data = r_pilot.json["output"][0]["parts"][1]["data"]
        self.assertEqual(p_data["price_eur"], "290")
        self.assertEqual(p_data["hostnames_limit"], 50)

        # 6) Unsupported mode rejected
        r_bad_mode = self.client.post("/acp/runs", json={"agent_name": "quantum-aether", "mode": "stream", "input": []})
        self.assertEqual(r_bad_mode.status_code, 400)

    def test_a2a_mcp_receipts_and_audit_trail(self):
        # Call A2A tls-evidence
        a2a_res = self.client.post("/a2a", headers={"User-Agent": "TestA2AClient/1.0"}, json={
            "jsonrpc": "2.0", "id": 1, "method": "message/send",
            "params": {"message": {"role": "user", "parts": [{"kind": "data", "data": {"skill": "tls-evidence", "domain": "example.com"}}]}},
        })
        self.assertEqual(a2a_res.status_code, 200)
        a2a_data = a2a_res.json["result"]["parts"][1]["data"]
        _, a2a_claims = signed_receipts.verify_receipt(self.tmp.name, a2a_data["receipt_jws"])
        self.assertEqual(a2a_claims["domain"], "example.com")

        # Call MCP initialize (must be tracked separately from real tool calls, using clientInfo.name)
        init_res = self.client.post("/mcp", headers={"User-Agent": "python-httpx/0.27"}, json={
            "jsonrpc": "2.0", "id": 99, "method": "initialize",
            "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "claude-ai", "version": "1.2"}},
        })
        self.assertEqual(init_res.status_code, 200)

        # Call MCP get_tls_evidence
        mcp_res = self.client.post("/mcp", headers={"User-Agent": "ClaudeDesktop/2.1"}, json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "get_tls_evidence", "arguments": {"domain": "example.com"}},
        })
        self.assertEqual(mcp_res.status_code, 200)
        mcp_data = mcp_res.json["result"]["structuredContent"]
        _, mcp_claims = signed_receipts.verify_receipt(self.tmp.name, mcp_data["receipt_jws"])
        self.assertEqual(mcp_claims["domain"], "example.com")

        # Call ACP tls-evidence
        self.client.post("/acp/runs", headers={"User-Agent": "BeeAI-ACP/0.2"}, json={
            "agent_name": "quantum-aether",
            "input": [{"role": "user", "parts": [{"content_type": "text/plain", "content": "Check example.com"}]}],
        })

        # Verify privacy-safe audit summary separates real calls from MCP initialize handshakes
        with self.app.app_context():
            s = agent_audit.summary(quantum_saas_app.db(), days=14)
        self.assertEqual(s["by_protocol"].get("a2a"), 1)
        self.assertEqual(s["by_protocol"].get("mcp"), 1)
        self.assertEqual(s["by_protocol"].get("acp"), 1)
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["init_total"], 1)
        clients = {row["client_name"] for row in s["rows"]}
        self.assertIn("claude-ai/1.2", clients)
        self.assertIn("TestA2AClient/1.0", clients)
        self.assertIn("ClaudeDesktop/2.1", clients)
        self.assertIn("BeeAI-ACP/0.2", clients)

    def test_guide_securing_mcp_a2a_acp_all_langs(self):
        for lang in ("en", "ar", "de"):
            r = self.client.get(f"/guides/securing-mcp-a2a-acp-agents-post-quantum-tls?lang={lang}")
            self.assertEqual(r.status_code, 200, lang)
            self.assertIn("FAQPage", r.text, lang)
            self.assertIn("X25519MLKEM768", r.text, lang)
            self.assertIn("jwks.json", r.text, lang)


if __name__ == "__main__":
    unittest.main()
