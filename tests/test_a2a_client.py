"""Tests for tools/a2a_client.py (inspect, draft, single-target send + duplicate guard)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import a2a_client  # noqa: E402


SAMPLE_CARD = {
    "protocolVersion": "0.3.0",
    "name": "Example Security Agent",
    "url": "https://partner.example/a2a",
    "preferredTransport": "JSONRPC",
    "securitySchemes": {},
    "capabilities": {"streaming": False},
    "skills": [{"id": "security-check", "name": "Security Check", "tags": ["tls"]}],
}


class A2AClientTests(unittest.TestCase):
    def test_candidate_urls_and_fetch_fallback(self):
        self.assertEqual(
            a2a_client.candidate_card_urls("partner.example"),
            ["https://partner.example/.well-known/agent-card.json", "https://partner.example/.well-known/agent.json"],
        )
        self.assertEqual(
            a2a_client.candidate_card_urls("https://partner.example/.well-known/agent-card.json"),
            ["https://partner.example/.well-known/agent-card.json"],
        )

        calls = []

        def fake_fetch(url, *, method="GET", body=None, timeout=15.0):
            calls.append(url)
            if url.endswith("agent-card.json"):
                return 404, "not found"
            return 200, SAMPLE_CARD

        card_url, card = a2a_client.fetch_agent_card("https://partner.example", fetcher=fake_fetch)
        self.assertEqual(card_url, "https://partner.example/.well-known/agent.json")
        self.assertEqual(card["name"], "Example Security Agent")
        self.assertEqual(len(calls), 2)

    def test_summarize_and_build_intro_payload(self):
        summary = a2a_client.summarize_card("https://partner.example/.well-known/agent-card.json", SAMPLE_CARD)
        self.assertEqual(summary["endpoint"], "https://partner.example/a2a")
        self.assertFalse(summary["auth_required"])
        payload = a2a_client.build_intro_payload(summary, domain="partner.example", request_id="req-1")
        self.assertEqual(payload["jsonrpc"], "2.0")
        self.assertEqual(payload["id"], "req-1")
        self.assertEqual(payload["method"], "message/send")
        parts = payload["params"]["message"]["parts"]
        self.assertIn("/api/v1/attestation/sample.pdf", parts[0]["text"])
        self.assertIn("290 EUR", parts[0]["text"])
        self.assertEqual(parts[1]["data"]["msp_pilot_eur"], "290")
        self.assertEqual(parts[1]["data"]["purchase_options"]["autonomous_x402_attestation"]["mcp_tool"], "get_tls_attestation")
        self.assertIn("5.00 USDC", parts[0]["text"])
        self.assertEqual(parts[1]["data"]["agent_card"], "https://ather-quantum.com/.well-known/agent-card.json")
        self.assertEqual(parts[1]["data"]["domain"], "partner.example")

    def test_send_logs_and_blocks_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "a2a_contacted.json")
            sent_bodies = []

            def fake_post(url, *, method="GET", body=None, timeout=20.0):
                self.assertEqual(method, "POST")
                sent_bodies.append((url, body))
                return 200, {"jsonrpc": "2.0", "id": body["id"], "result": {"kind": "message"}}

            summary = a2a_client.summarize_card("https://partner.example/.well-known/agent-card.json", SAMPLE_CARD)
            payload = a2a_client.build_intro_payload(summary, request_id="req-2")

            rec = a2a_client.send_message(summary["endpoint"], payload, log_path=log_path, fetcher=fake_post)
            self.assertEqual(rec["http_status"], 200)
            self.assertEqual(len(sent_bodies), 1)

            # Second send to same endpoint must be blocked unless force=True
            with self.assertRaises(RuntimeError):
                a2a_client.send_message(summary["endpoint"], payload, log_path=log_path, fetcher=fake_post)
            self.assertEqual(len(sent_bodies), 1)

            # Explicit force=True succeeds
            rec2 = a2a_client.send_message(summary["endpoint"], payload, log_path=log_path, force=True, fetcher=fake_post)
            self.assertEqual(rec2["http_status"], 200)
            self.assertEqual(len(sent_bodies), 2)


if __name__ == "__main__":
    unittest.main()
