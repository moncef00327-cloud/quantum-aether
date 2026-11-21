"""A2A agent card + /a2a message/send (2026-11-21)."""
import copy
import tempfile
import unittest
from unittest.mock import Mock

import a2a_agent
import quantum_saas_app
from tests.test_app import RESULT


class A2ATests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.scanner = Mock(return_value=copy.deepcopy(RESULT))
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://ather-quantum.com",
                                                "SCANS_PER_HOUR": 1, "GLOBAL_SCANS_PER_HOUR": 10}, scanner=self.scanner)
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def send(self, text=None, data=None, method="message/send"):
        parts = ([{"kind": "text", "text": text}] if text else []) + ([{"kind": "data", "data": data}] if data else [])
        return self.client.post("/a2a", json={"jsonrpc": "2.0", "id": 7, "method": method,
                                              "params": {"message": {"role": "user", "messageId": "m1", "parts": parts}}})

    def test_agent_card(self):
        for path in ("/.well-known/agent-card.json", "/.well-known/agent.json"):
            c = self.client.get(path).json
            self.assertEqual(c["protocolVersion"], a2a_agent.PROTOCOL)
            self.assertEqual(c["url"], "https://ather-quantum.com/a2a")
            self.assertEqual(c["preferredTransport"], "JSONRPC")
            self.assertEqual({s["id"] for s in c["skills"]}, {"tls-evidence", "tls-scan", "paid-data"})
            self.assertFalse(c["capabilities"]["streaming"])

    def test_evidence_never_scans(self):
        r = self.send("Is example.com post-quantum ready?").json["result"]
        self.assertEqual(r["kind"], "message")
        self.assertEqual(r["role"], "agent")
        self.assertIn("example.com", r["parts"][0]["text"])
        self.assertEqual(r["parts"][1]["data"]["state"], "not_scanned")
        self.scanner.assert_not_called()

    def test_scan_by_text_and_rate_limit(self):
        r = self.send("please scan example.com").json["result"]
        self.assertIn("grade B", r["parts"][0]["text"])
        self.assertIn("scan_id", r["parts"][1]["data"])
        self.scanner.assert_called_once_with("example.com")
        again = self.send(data={"skill": "tls-scan", "domain": "example.com"}).json["result"]
        self.assertEqual(again["parts"][1]["data"]["error"], "rate_limited")

    def test_paid_data_and_errors(self):
        r = self.send(data={"skill": "paid-data"}).json["result"]
        self.assertIn("x402", r["parts"][0]["text"])
        self.assertIn("sector_snapshot", r["parts"][1]["data"])
        self.assertEqual(self.send("hi", method="tasks/get").json["error"]["code"], -32601)
        self.assertEqual(self.client.post("/a2a", json={"x": 1}).json["error"]["code"], -32600)
        self.assertIn("hostname", self.send("hello").json["result"]["parts"][0]["text"])

    def test_listed_for_agents(self):
        self.assertIn("/.well-known/agent-card.json", self.client.get("/llms.txt").get_data(as_text=True))
        self.assertEqual(self.client.get("/api/v1/agent/discovery").json["a2a_endpoint"], "https://ather-quantum.com/a2a")


if __name__ == "__main__":
    unittest.main()
