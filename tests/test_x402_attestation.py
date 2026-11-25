"""Tests for the paid auditor-ready PQ-TLS attestation bundle (x402_attestation.py, v2)."""
import base64
import copy
import hashlib
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import urlsplit

import quantum_saas_app
import receipts
import signed_receipts
from tests.test_app import RESULT


class X402AttestationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.scanner = Mock(return_value=copy.deepcopy(RESULT))
        self.app = quantum_saas_app.create_app({
            "TESTING": True,
            "DATA_DIR": self.tmp.name,
            "PUBLIC_URL": "https://ather-quantum.com",
            "USDC_BASE_ADDR": "0x" + "44" * 20,
            "SCANS_PER_HOUR": 5,
            "GLOBAL_SCANS_PER_HOUR": 20,
        }, scanner=self.scanner)
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_unpaid_returns_402_and_never_scans(self):
        r = self.client.get("/api/v1/attestation?domain=example.com")
        self.assertEqual(r.status_code, 402)
        self.assertIn("PAYMENT-REQUIRED", r.headers)
        challenge = json.loads(base64.b64decode(r.headers["PAYMENT-REQUIRED"]).decode("utf-8"))
        self.assertEqual(challenge["accepts"][0]["amount"], "5000000")  # 5.00 USDC (6 decimals)
        self.scanner.assert_not_called()

    def test_paid_attestation_delivers_pdf_cbom_and_verifiable_bundle_jws(self):
        r402 = self.client.get("/api/v1/attestation?domain=example.com")
        challenge = json.loads(base64.b64decode(r402.headers["PAYMENT-REQUIRED"]).decode("utf-8"))
        pay_payload = {
            "x402Version": 2,
            "resource": challenge["resource"],
            "accepted": challenge["accepts"][0],
        }
        sig_hdr = base64.b64encode(json.dumps(pay_payload).encode("utf-8")).decode("ascii")

        verified = Mock()
        verified.raise_for_status.return_value = None
        verified.json.return_value = {"isValid": True}
        settled = Mock()
        settled.raise_for_status.return_value = None
        settled.json.return_value = {"success": True, "transaction": "0x" + "ef" * 32, "network": "eip155:8453"}

        with patch("x402_pay.requests.post", side_effect=[verified, settled]):
            r = self.client.get("/api/v1/attestation?domain=example.com", headers={"PAYMENT-SIGNATURE": sig_hdr})

        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["type"], "qa-pq-tls-attestation")
        self.assertEqual(body["version"], "2")
        self.assertEqual(body["domain"], "example.com")
        self.assertTrue(body["att_id"].startswith("qa_att_"))
        self.assertIn("signed_receipt", body)
        self.assertIn("signed_receipt_jws", body["signed_receipt"])

        # CycloneDX 1.6 CBOM included
        self.assertEqual(body["cbom"]["bomFormat"], "CycloneDX")
        self.assertEqual(body["cbom"]["specVersion"], "1.6")
        self.assertTrue(body["cbom"]["components"])

        # Explicit methodology & limits
        self.assertIn("limits", body["methodology"])
        self.assertGreaterEqual(len(body["methodology"]["limits"]), 3)

        # Bundle-level Ed25519 JWS verifies offline
        bundle_jws = body["integrity"]["bundle_jws"]
        self.assertTrue(bundle_jws)
        hdr, claims = signed_receipts.verify_receipt(self.tmp.name, bundle_jws)
        self.assertEqual(hdr["alg"], "EdDSA")
        self.assertEqual(claims["kind"], "qa-pq-tls-attestation-v2")
        self.assertEqual(claims["att_id"], body["att_id"])
        self.assertEqual(claims["pdf_sha256"], body["auditor_pdf"]["sha256"])

        # Token-protected auditor PDF download works and matches SHA-256
        dl = urlsplit(body["auditor_pdf"]["download_url"])
        pdf_path = f"{dl.path}?{dl.query}"
        pdf_resp = self.client.get(pdf_path)
        self.assertEqual(pdf_resp.status_code, 200)
        self.assertEqual(pdf_resp.mimetype, "application/pdf")
        self.assertTrue(pdf_resp.data.startswith(b"%PDF"))
        self.assertEqual(hashlib.sha256(pdf_resp.data).hexdigest(), body["auditor_pdf"]["sha256"])
        self.assertEqual(pdf_resp.headers.get("X-Attestation-SHA256"), body["auditor_pdf"]["sha256"])
        self.assertIn("no-store", pdf_resp.headers.get("Cache-Control", ""))
        self.assertEqual(pdf_resp.headers.get("X-Robots-Tag"), "noindex")
        self.assertEqual(pdf_resp.headers.get("Referrer-Policy"), "no-referrer")

        # Missing or wrong token rejected
        self.assertEqual(self.client.get(dl.path).status_code, 403)
        self.assertEqual(self.client.get(f"{dl.path}?token=wrongtoken").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/attestation/qa_att_" + "0" * 24 + ".pdf?token=abc").status_code, 404)

    def test_docs_and_mcp_expose_v2_pdf_attestation(self):
        oa = self.client.get("/openapi.yaml").get_data(as_text=True)
        self.assertIn("/api/v1/attestation:", oa)
        self.assertIn("/api/v1/attestation/{att_id}.pdf:", oa)
        llms = self.client.get("/llms.txt").get_data(as_text=True)
        self.assertIn("get_tls_attestation", llms)
        self.assertIn("CycloneDX 1.6", llms)
        for lang in ("en", "ar"):
            html = self.client.get(f"/agents?lang={lang}").get_data(as_text=True)
            self.assertIn("CycloneDX 1.6", html)
            self.assertIn("5.00 USDC", html)
        r_mcp = self.client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "get_tls_attestation", "arguments": {"domain": "example.com"}},
        })
        self.assertEqual(r_mcp.status_code, 200)
        self.assertTrue(r_mcp.get_json()["result"]["isError"])  # x402 PaymentRequired challenge

    def test_sample_attestation_pdf_json_and_commercial_crosslinks(self):
        # Sample endpoints are free, read-only, clearly labeled as examples, and never scan
        r_json = self.client.get("/api/v1/attestation/sample")
        self.assertEqual(r_json.status_code, 200)
        sj = r_json.get_json()
        self.assertTrue(sj["is_example"])
        self.assertFalse(sj["is_live"])
        self.assertEqual(sj["cbom"]["bomFormat"], "CycloneDX")
        self.assertTrue(sj["auditor_pdf"]["download_url"].endswith("/api/v1/attestation/sample.pdf"))

        r_pdf = self.client.get("/api/v1/attestation/sample.pdf")
        self.assertEqual(r_pdf.status_code, 200)
        self.assertEqual(r_pdf.mimetype, "application/pdf")
        self.assertTrue(r_pdf.data.startswith(b"%PDF"))
        self.scanner.assert_not_called()

        # Cross-links visible on /agents, /pricing, and /partners
        for lang in ("en", "ar"):
            self.assertIn("/api/v1/attestation/sample.pdf", self.client.get(f"/agents?lang={lang}").get_data(as_text=True))
        for lang in ("en", "de", "ar"):
            pricing = self.client.get(f"/pricing?lang={lang}").get_data(as_text=True)
            self.assertIn("290 €", pricing, lang)
            self.assertIn("5.00 USDC", pricing, lang)
            self.assertIn("/api/v1/attestation/sample.pdf", pricing, lang)
            partners_html = self.client.get(f"/partners?lang={lang}").get_data(as_text=True)
            self.assertIn("register_agent_affiliate", partners_html, lang)

    def test_metadata_unifies_read_only_false_payment_reqs_and_mcp_e2e_offline_verify(self):
        # 1) read_only=False & payment requirements consistent across EVERY discovery surface
        svc = self.client.get("/.well-known/agent-service.json").get_json()
        self.assertIs(svc["endpoints"]["attestation"]["read_only"], False)
        self.assertIs(svc["endpoints"]["attestation"]["starts_scan"], True)
        att_meta = svc["pricing"]["attestation"]
        self.assertIs(att_meta["read_only"], False)
        self.assertIs(att_meta["starts_scan"], True)
        self.assertIs(att_meta["payment_authorization_required"], True)
        self.assertIs(att_meta["buyer_wallet_required"], True)
        self.assertIn("spend", att_meta["spend_policy_note"].lower())

        for card_path in ("/.well-known/mcp/server-card.json", "/mcp/server-card"):
            card = self.client.get(card_path).get_json()
            self.assertIs(card["attestation"]["read_only"], False, card_path)
            self.assertIs(card["attestation"]["buyer_wallet_required"], True, card_path)
            tool_card = next(t for t in card["tools"] if t["name"] == "get_tls_attestation")
            self.assertIs(tool_card["annotations"]["readOnlyHint"], False, card_path)
            self.assertIn("buyer wallet", tool_card["description"].lower(), card_path)
            self.assertIn("spend", tool_card["description"].lower(), card_path)

        cat = self.client.get("/.well-known/api-catalog").get_json()
        self.assertIn("https://ather-quantum.com/api/v1/attestation", {i["anchor"] for i in cat["linkset"]})

        oa = self.client.get("/openapi.yaml").get_data(as_text=True)
        for token in ("AttestationBundleV2:", "bundle_jws:", "auditor_pdf:", "/api/v1/attestation/sample:"):
            self.assertIn(token, oa)

        # 2) Unpaid MCP call returns 402 challenge as isError=True and NEVER scans
        r_unpaid = self.client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 10, "method": "tools/call",
            "params": {"name": "get_tls_attestation", "arguments": {"domain": "example.com"}},
        }).get_json()["result"]
        self.assertTrue(r_unpaid["isError"])
        challenge = r_unpaid["structuredContent"]
        self.assertEqual(challenge["accepts"][0]["amount"], "5000000")
        self.scanner.assert_not_called()

        # 3) Mocked paid MCP call settles and delivers a locally verifiable bundle (JWKS + PDF SHA-256)
        pay_meta = {
            "x402/payment": {
                "x402Version": 2,
                "resource": challenge["resource"],
                "accepted": challenge["accepts"][0],
            }
        }
        verified = Mock(); verified.raise_for_status.return_value = None; verified.json.return_value = {"isValid": True}
        settled = Mock(); settled.raise_for_status.return_value = None; settled.json.return_value = {
            "success": True, "transaction": "0x" + "cd" * 32, "network": "eip155:8453"
        }
        with patch("x402_pay.requests.post", side_effect=[verified, settled]):
            r_paid = self.client.post("/mcp", json={
                "jsonrpc": "2.0", "id": 11, "method": "tools/call",
                "params": {"name": "get_tls_attestation", "arguments": {"domain": "example.com"}, "_meta": pay_meta},
            }).get_json()["result"]

        self.assertFalse(r_paid["isError"])
        bundle = r_paid["structuredContent"]
        self.assertEqual(bundle["version"], "2")
        self.assertEqual(bundle["cbom"]["bomFormat"], "CycloneDX")
        self.assertEqual(r_paid["_meta"]["x402/payment-response"]["transaction"], "0x" + "cd" * 32)

        # Verify BOTH signatures offline against live /.well-known/jwks.json
        jwks = self.client.get("/.well-known/jwks.json").get_json()
        rcpt_claims = receipts.verify_receipt(
            bundle["signed_receipt"]["signed_receipt_jws"],
            "example.com:443",
            jwks_doc=jwks,
            require_pass=False,
        )
        self.assertEqual(rcpt_claims["sub"], "example.com:443")

        bhdr, bclaims = signed_receipts.verify_receipt(self.tmp.name, bundle["integrity"]["bundle_jws"])
        self.assertEqual(bhdr["alg"], "EdDSA")
        self.assertEqual(bclaims["pdf_sha256"], bundle["auditor_pdf"]["sha256"])

        dl = urlsplit(bundle["auditor_pdf"]["download_url"])
        pdf_r = self.client.get(f"{dl.path}?{dl.query}")
        self.assertEqual(pdf_r.status_code, 200)
        self.assertEqual(hashlib.sha256(pdf_r.data).hexdigest(), bundle["auditor_pdf"]["sha256"])


if __name__ == "__main__":
    unittest.main()
