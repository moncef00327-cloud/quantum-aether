"""A2UI v0.8 extension support on A2A (/.well-known/agent-card.json, POST /a2a, GET /api/v1/a2ui/evidence/<domain>)."""
import copy
import json
import tempfile
import unittest
from unittest.mock import Mock

import a2a_agent
import a2ui_cards
import quantum_saas_app
from tests.test_app import RESULT


def _validate_a2ui_messages(tc: unittest.TestCase, msgs: list[dict]):
    tc.assertEqual(len(msgs), 3)
    tc.assertIn("surfaceUpdate", msgs[0])
    tc.assertIn("dataModelUpdate", msgs[1])
    tc.assertIn("beginRendering", msgs[2])

    su = msgs[0]["surfaceUpdate"]
    dmu = msgs[1]["dataModelUpdate"]
    br = msgs[2]["beginRendering"]
    tc.assertEqual(su["surfaceId"], dmu["surfaceId"])
    tc.assertEqual(su["surfaceId"], br["surfaceId"])
    tc.assertEqual(br["catalogId"], a2ui_cards.A2UI_CATALOG_ID)

    comp_ids = {c["id"] for c in su["components"]}
    tc.assertIn(br["root"], comp_ids)
    for c in su["components"]:
        comp = c["component"]
        if "Card" in comp:
            tc.assertIn(comp["Card"]["child"], comp_ids)
        for box in ("Column", "Row"):
            if box in comp:
                for child_id in comp[box]["children"]["explicitList"]:
                    tc.assertIn(child_id, comp_ids)
        if "Button" in comp:
            tc.assertIn(comp["Button"]["child"], comp_ids)


class A2UITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.scanner = Mock(return_value=copy.deepcopy(RESULT))
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://ather-quantum.com",
             "SCANS_PER_HOUR": 2, "GLOBAL_SCANS_PER_HOUR": 10},
            scanner=self.scanner,
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_agent_card_declares_a2ui_v08_extension_and_remains_signed(self):
        jwks = self.client.get("/.well-known/jwks.json").json
        card = self.client.get("/.well-known/agent-card.json").json
        exts = card["capabilities"]["extensions"]
        self.assertTrue(any(e["uri"] == a2ui_cards.A2UI_EXTENSION_URI and e["required"] is False for e in exts))
        self.assertIn(a2ui_cards.A2UI_MIME, card["defaultOutputModes"])
        hdr = a2a_agent.verify_agent_card_signature(card, jwks)
        self.assertEqual(hdr["alg"], "EdDSA")

        opt = self.client.options("/a2a")
        self.assertEqual(opt.status_code, 204)
        self.assertIn("X-A2A-Extensions", opt.headers.get("Access-Control-Allow-Headers", ""))

    def test_a2a_omits_a2ui_by_default_and_attaches_when_negotiated(self):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {"message": {"role": "user", "messageId": "m1", "parts": [{"kind": "text", "text": "Is example.com post-quantum ready?"}]}},
        }
        plain = self.client.post("/a2a", json=payload).json["result"]
        self.assertEqual(len(plain["parts"]), 2)

        with_hdr = self.client.post(
            "/a2a",
            json=payload,
            headers={"X-A2A-Extensions": a2ui_cards.A2UI_EXTENSION_URI},
        ).json["result"]
        self.assertEqual(len(with_hdr["parts"]), 5)
        a2ui_parts = [p for p in with_hdr["parts"] if (p.get("metadata") or {}).get("mimeType") == a2ui_cards.A2UI_MIME]
        self.assertEqual(len(a2ui_parts), 3)
        _validate_a2ui_messages(self, [p["data"] for p in a2ui_parts])
        self.scanner.assert_not_called()

    def test_a2a_tls_scan_and_info_skills_with_a2ui_flag(self):
        scan_res = self.client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "message/send",
                "params": {"message": {"role": "user", "messageId": "m2", "parts": [{"kind": "data", "data": {"skill": "tls-scan", "domain": "example.com", "a2ui": True}}]}},
            },
        ).json["result"]
        a2ui_msgs = [p["data"] for p in scan_res["parts"] if (p.get("metadata") or {}).get("mimeType") == a2ui_cards.A2UI_MIME]
        _validate_a2ui_messages(self, a2ui_msgs)
        dm = {e["key"]: e["valueString"] for e in a2ui_msgs[1]["dataModelUpdate"]["contents"]}
        self.assertEqual(dm["domain"], "example.com")
        self.assertEqual(dm["grade"], "B")
        self.assertIn("Ed25519 JWS", dm["receiptStatus"])

        pilot_res = self.client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "message/send",
                "params": {"message": {"role": "user", "messageId": "m3", "parts": [{"kind": "data", "data": {"skill": "msp-pilot", "lang": "de"}}]}},
            },
            headers={"X-A2A-Extensions": a2ui_cards.A2UI_EXTENSION_URI},
        ).json["result"]
        pilot_msgs = [p["data"] for p in pilot_res["parts"] if (p.get("metadata") or {}).get("mimeType") == a2ui_cards.A2UI_MIME]
        _validate_a2ui_messages(self, pilot_msgs)
        self.scanner.assert_called_once_with("example.com")

    def test_public_a2ui_evidence_endpoint_json_and_jsonl(self):
        for lang in ("en", "de", "ar"):
            r = self.client.get(f"/api/v1/a2ui/evidence/example.com?lang={lang}")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "*")
            body = r.json
            self.assertEqual(body["a2uiVersion"], a2ui_cards.A2UI_VERSION)
            self.assertEqual(body["extensionUri"], a2ui_cards.A2UI_EXTENSION_URI)
            self.assertEqual(body["domain"], "example.com")
            self.assertEqual(body["lang"], lang)
            _validate_a2ui_messages(self, body["messages"])

        r_jsonl = self.client.get("/api/v1/a2ui/evidence/example.com?format=jsonl")
        self.assertEqual(r_jsonl.status_code, 200)
        self.assertIn(a2ui_cards.A2UI_MIME, r_jsonl.content_type)
        lines = [json.loads(line) for line in r_jsonl.get_data(as_text=True).strip().splitlines()]
        _validate_a2ui_messages(self, lines)

        r_bad = self.client.get("/api/v1/a2ui/evidence/127.0.0.1")
        self.assertEqual(r_bad.status_code, 400)
        self.scanner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
