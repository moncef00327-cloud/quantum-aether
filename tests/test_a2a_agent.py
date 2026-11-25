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
            self.assertEqual(c["supportedInterfaces"][0]["url"], "https://ather-quantum.com/a2a")
            self.assertEqual(c["supportedInterfaces"][0]["protocolBinding"], "JSONRPC")
            self.assertFalse(c["supportsAuthenticatedExtendedCard"])
            self.assertEqual(c["securitySchemes"], {})
            self.assertEqual(
                {s["id"] for s in c["skills"]},
                {"tls-evidence", "tls-scan", "tls-attestation", "msp-pilot", "paid-data", "agent-affiliate", "qa-assistant"},
            )
            self.assertFalse(c["capabilities"]["streaming"])

    def test_msp_pilot_skill_290_eur(self):
        r = self.send("Tell me about the 290 EUR IT-Dienstleister MSP Pilot").json["result"]
        txt = r["parts"][0]["text"]
        data = r["parts"][1]["data"]
        self.assertIn("290 EUR", txt)
        self.assertIn("50 client hostnames", txt)
        self.assertIn("/partners?lang=de#msp-pilot", txt)
        self.assertEqual(data["price_eur"], "290")
        self.assertEqual(data["hostnames_limit"], 50)
        self.assertEqual(data["partner_slots"], 3)
        self.scanner.assert_not_called()

    def test_tls_attestation_skill_and_msp_pilot(self):
        r = self.send("How do I get a CycloneDX CBOM and auditor PDF attestation for example.com?").json["result"]
        txt = r["parts"][0]["text"]
        data = r["parts"][1]["data"]
        self.assertIn("5.00 USDC", txt)
        self.assertIn("/api/v1/attestation/sample.pdf", txt)
        self.assertIn("get_tls_attestation", txt)
        self.assertEqual(data["price_usd"], "5.00")
        self.assertIs(data["read_only"], False)
        self.assertIs(data["starts_scan"], True)
        self.assertIs(data["buyer_wallet_required"], True)
        self.assertIs(data["payment_authorization_required"], True)
        self.assertEqual(data["sample_pdf"], "https://ather-quantum.com/api/v1/attestation/sample.pdf")
        self.assertEqual(data["example_request"]["domain"], "example.com")
        self.assertEqual(data["services"]["msp_pilot"]["price_eur"], "290")
        self.scanner.assert_not_called()

    def test_agent_affiliate_skill(self):
        r = self.send("How do AI agents earn referral commission?").json["result"]
        self.assertIn("register_agent_affiliate", r["parts"][0]["text"])
        self.assertIn("/api/v1/agent/affiliate/register", r["parts"][0]["text"])
        self.assertEqual(r["parts"][1]["data"]["mcp_tool"], "register_agent_affiliate")
        self.scanner.assert_not_called()

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
        self.assertEqual(self.send("hi", method="tasks/pushNotificationConfig/set").json["error"]["code"], -32601)
        self.assertEqual(self.client.post("/a2a", json={"x": 1}).json["error"]["code"], -32600)
        self.assertIn("hostname", self.send("hello").json["result"]["parts"][0]["text"])

    def test_tasks_get_tasks_cancel_and_signed_agent_card(self):
        # 1) Signed Agent Card verifies offline against /.well-known/jwks.json
        jwks = self.client.get("/.well-known/jwks.json").json
        card = self.client.get("/.well-known/agent-card.json").json
        self.assertTrue(card.get("signatures"))
        hdr = a2a_agent.verify_agent_card_signature(card, jwks)
        self.assertEqual(hdr["alg"], "EdDSA")
        self.assertEqual(hdr["jku"], "https://ather-quantum.com/.well-known/jwks.json")

        # Tampering with the card must fail verification
        tampered = dict(card, name="Tampered Agent")
        with self.assertRaises(Exception):
            a2a_agent.verify_agent_card_signature(tampered, jwks)

        # 2) tasks/get with missing id -> -32602; unknown id -> -32001 (A2A 0.3.0 TaskNotFound)
        r_missing = self.client.post("/a2a", json={"jsonrpc": "2.0", "id": 10, "method": "tasks/get", "params": {}})
        self.assertEqual(r_missing.json["error"]["code"], -32602)

        r_unknown = self.client.post("/a2a", json={"jsonrpc": "2.0", "id": 11, "method": "tasks/get", "params": {"id": "nonexistent-task"}})
        self.assertEqual(r_unknown.status_code, 200)
        self.assertEqual(r_unknown.json["error"]["code"], -32001)

        # 3) Completed message/send is retrievable via tasks/get (and historyLength works)
        msg = self.send("Is example.com post-quantum ready?").json["result"]
        tid = msg["messageId"]
        r_task = self.client.post("/a2a", json={"jsonrpc": "2.0", "id": 12, "method": "tasks/get", "params": {"id": tid, "historyLength": 1}})
        self.assertEqual(r_task.status_code, 200)
        task = r_task.json["result"]
        self.assertEqual(task["kind"], "task")
        self.assertEqual(task["id"], tid)
        self.assertEqual(task["status"]["state"], "completed")
        self.assertEqual(len(task["history"]), 1)

        # 4) tasks/cancel: unknown -> -32001, completed -> -32002 (TaskNotCancelable)
        r_c_miss = self.client.post("/a2a", json={"jsonrpc": "2.0", "id": 13, "method": "tasks/cancel", "params": {"id": "missing"}})
        self.assertEqual(r_c_miss.json["error"]["code"], -32001)
        r_c_done = self.client.post("/a2a", json={"jsonrpc": "2.0", "id": 14, "method": "tasks/cancel", "params": {"id": tid}})
        self.assertEqual(r_c_done.json["error"]["code"], -32002)

    def test_listed_for_agents(self):
        self.assertIn("/.well-known/agent-card.json", self.client.get("/llms.txt").get_data(as_text=True))
        self.assertEqual(self.client.get("/api/v1/agent/discovery").json["a2a_endpoint"], "https://ather-quantum.com/a2a")

    def test_get_a2a_and_service_offers_and_crawler_link_headers(self):
        get_a2a = self.client.get("/a2a")
        self.assertEqual(get_a2a.status_code, 200)
        self.assertEqual(get_a2a.json["url"], "https://ather-quantum.com/a2a")
        self.assertIn("monitoring", get_a2a.json["services"])
        self.assertIn("organization_audit", get_a2a.json["services"])

        ev = self.send("Is example.com post-quantum ready?").json["result"]["parts"][1]["data"]
        self.assertIn("services", ev)
        self.assertIn("/monitoring?domain=example.com#trial-form", ev["services"]["monitoring"]["trial_url"])
        self.assertIn("/audit?domain=example.com", ev["services"]["organization_audit"]["url"])

        paid = self.send(data={"skill": "paid-data"}).json["result"]
        self.assertIn("29 EUR/mo", paid["parts"][0]["text"])
        self.assertEqual(paid["parts"][1]["data"]["organization_audit"]["price_eur"], "490")

        for path in ("/", "/api/v1/badge/example.com"):
            link = self.client.get(path).headers.get("Link", "")
            self.assertIn("/.well-known/agent-card.json", link, path)
            self.assertIn("/.well-known/mcp.json", link, path)
            self.assertIn("/llms.txt", link, path)

    def test_qa_assistant_multilingual_and_top_search_bar(self):
        # Arabic nginx config inquiry
        r_cfg = self.send("إعدادات nginx لتفعيل X25519MLKEM768", data={"lang": "ar"}).json["result"]
        self.assertIn("X25519MLKEM768", r_cfg["parts"][0]["text"])
        d_cfg = r_cfg["parts"][1]["data"]
        self.assertEqual(d_cfg["topic"], "config")
        self.assertEqual(d_cfg["server"], "nginx")
        self.assertIn("ssl_ecdh_curve X25519MLKEM768", d_cfg["code"])

        # German BSI/NIS2 deadlines inquiry
        r_dl = self.send("Welche Fristen gelten für BSI, NIS2 und DORA?", data={"lang": "de"}).json["result"]
        d_dl = r_dl["parts"][1]["data"]
        self.assertEqual(d_dl["topic"], "deadlines")
        self.assertTrue(d_dl["points"])
        self.assertIn("/deadlines?lang=de", d_dl["actions"][0]["url"])

        # English pricing inquiry
        r_pr = self.send("What are the plans and pricing?", data={"lang": "en"}).json["result"]
        d_pr = r_pr["parts"][1]["data"]
        self.assertEqual(d_pr["topic"], "pricing")
        self.assertTrue(any("290" in pt for pt in d_pr["points"]))

        # Signed receipts inquiry
        r_rc = self.send("How do I verify an Ed25519 signed receipt offline?").json["result"]
        self.assertEqual(r_rc["parts"][1]["data"]["topic"], "signed-receipts")
        self.assertIn("qa_verify.py", r_rc["parts"][1]["data"]["code"])

        # MCP/A2A inquiry
        r_mcp = self.send("How do I connect MCP in Cursor or Claude?").json["result"]
        self.assertEqual(r_mcp["parts"][1]["data"]["topic"], "mcp-a2a")
        self.assertIn("claude mcp add", r_mcp["parts"][1]["data"]["code"])

        # Domain whose name overlaps a CDN (cloudflare.com) must still check TLS evidence, not CDN config
        for q, l in (("Is cloudflare.com post-quantum ready?", "en"), ("هل cloudflare.com جاهز لما بعد الكم؟", "ar")):
            r_cf = self.send(q, data={"lang": l}).json["result"]
            self.assertEqual(r_cf["parts"][1]["data"]["domain"], "cloudflare.com", q)
            self.assertNotEqual(r_cf["parts"][1]["data"].get("topic"), "config", q)

        # Arabic real-world spelling variations (definite article 'ال', bare alef 'ا', subscription/pricing/contact)
        for q in ("الاسعار", "ما هي الأسعار والباقات؟", "اشتراك", "الدفع"):
            r_ar_p = self.send(q, data={"lang": "ar"}).json["result"]
            self.assertEqual(r_ar_p["parts"][1]["data"]["topic"], "pricing", q)
        r_ar_c = self.send("تواصل معكم", data={"lang": "ar"}).json["result"]
        self.assertEqual(r_ar_c["parts"][1]["data"]["topic"], "contact")
        self.assertTrue(r_ar_c["parts"][1]["data"]["allow_contact"])

        # Top-of-page A2A search & Q&A bar rendered cleanly in AR, EN, DE
        for path, needle in (
            ("/?lang=ar", "اسأل وكيل A2A"),
            ("/?lang=en", "Ask A2A agent"),
            ("/?lang=de", "A2A-Assistent fragen"),
            ("/partners?lang=de", "data-qa-agent-bar"),
        ):
            html = self.client.get(path).get_data(as_text=True)
            self.assertIn("data-qa-agent-bar", html, path)
            self.assertIn(needle, html, path)
            self.assertIn("/static/a2a-search.js", html, path)
        self.scanner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
