"""Tests for autonomous-agent x402 micro-SKUs: $0.10 batch-scan and $0.25 live CycloneDX 1.6 CBOM JSON."""
import base64
import json
import os
import tempfile
import unittest
from unittest import mock

import quantum_saas_app as app_mod

PAY_TO = "0x1111111111111111111111111111111111111111"
FAKE_SCAN = {
    "domain": "cloudflare.com",
    "ip": "104.16.132.229",
    "port": 443,
    "scanned_at": "2026-11-27T04:00:00+00:00",
    "scanner_version": "2.0",
    "grade": "A",
    "key_exchange": {"version": "TLSv1.3", "cipher": "TLS_AES_128_GCM_SHA256", "group": "X25519MLKEM768", "pq": True, "hrr": False, "kx": "TLS1.3"},
    "certificate": {"verified": True, "key_algorithm": "ECDSA", "key_bits": 256, "curve": "secp256r1", "signature_algorithm": "ecdsa-with-SHA256", "subject": "cloudflare.com", "issuer": "Google Trust Services", "days_left": 60, "leaf_sha256": "aa" * 32, "spki_sha256": "bb" * 32},
    "findings": [{"code": "KX_PQ_HYBRID", "status": "ok", "params": {"group": "X25519MLKEM768"}}],
    "endpoints": [{"ip": "104.16.132.229", "family": 4, "group": "X25519MLKEM768", "pq": True, "version": "TLSv1.3", "error": None, "undetermined": False}],
}


def _make_payment_sig(challenge: dict) -> str:
    payload = {
        "x402Version": 2,
        "resource": challenge["resource"],
        "accepted": challenge["accepts"][0],
        "payload": {"signature": "0x" + "ab" * 65},
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


class X402MicroTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = app_mod.create_app({
            "TESTING": True,
            "DATA_DIR": self.tmp.name,
            "DB_PATH": os.path.join(self.tmp.name, "test.db"),
            "USDC_BASE_ADDR": PAY_TO,
            "PUBLIC_URL": "https://ather-quantum.com",
        })
        self.tx_counter = 0

        def fake_facilitator(path, body):
            if path == "/verify":
                return {"isValid": True}
            self.tx_counter += 1
            return {"success": True, "network": "eip155:8453", "transaction": "0x" + f"{self.tx_counter:064x}"}

        self.app.extensions["x402_facilitator"] = fake_facilitator
        self.client = self.app.test_client()

    def test_batch_scan_402_validation_and_paid_settlement(self):
        # 1) Invalid batch rejected with 400 before payment
        r_bad = self.client.post("/api/v1/x402/batch-scan", json={"domains": ["localhost"]})
        self.assertEqual(r_bad.status_code, 400)
        r_many = self.client.post("/api/v1/x402/batch-scan", json={"domains": [f"d{i}.example.com" for i in range(11)]})
        self.assertEqual(r_many.status_code, 400)

        # 2) Unpaid valid request returns 402 with $0.10 (100000 units) Base USDC challenge + bazaar extension
        r402 = self.client.post("/api/v1/x402/batch-scan", json={"domains": ["cloudflare.com", "github.com"]})
        self.assertEqual(r402.status_code, 402)
        ch = json.loads(base64.b64decode(r402.headers["PAYMENT-REQUIRED"]).decode())
        self.assertEqual(ch["accepts"][0]["amount"], "100000")
        self.assertEqual(ch["accepts"][0]["network"], "eip155:8453")
        self.assertIn("bazaar", ch["extensions"])

        # 3) Paid request runs scans and returns signed receipts
        def fake_scan(dom, timeout=6.0):
            d = dict(FAKE_SCAN, domain=dom)
            if dom == "github.com":
                d["grade"] = "B"
                d["key_exchange"] = {"version": "TLSv1.3", "group": "x25519", "pq": False, "pq_supported_not_preferred": True, "pq_supported_group": "X25519MLKEM768", "hrr": False, "kx": "TLS1.3"}
            return d

        with mock.patch("quantum_vuln_scanner.scan_full", side_effect=fake_scan):
            r200 = self.client.post(
                "/api/v1/x402/batch-scan",
                json={"domains": ["cloudflare.com", "github.com"]},
                headers={"PAYMENT-SIGNATURE": _make_payment_sig(ch)},
            )
        self.assertEqual(r200.status_code, 200)
        body = r200.get_json()
        self.assertEqual(body["sku"], "x402_batch_scan_v1")
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["summary"]["pq_hybrid"], 1)
        self.assertEqual(body["summary"]["pq_supported_not_preferred"], 1)
        self.assertEqual(len(body["results"]), 2)
        self.assertIn("signed_receipt", body["results"][0])

    def test_cbom_402_validation_and_paid_settlement(self):
        # 1) Invalid domain -> 400
        self.assertEqual(self.client.get("/api/v1/x402/cbom?domain=127.0.0.1").status_code, 400)

        # 2) Unpaid -> 402 with $0.25 (250000 units)
        r402 = self.client.get("/api/v1/x402/cbom?domain=cloudflare.com")
        self.assertEqual(r402.status_code, 402)
        ch = json.loads(base64.b64decode(r402.headers["PAYMENT-REQUIRED"]).decode())
        self.assertEqual(ch["accepts"][0]["amount"], "250000")
        self.assertIn("bazaar", ch["extensions"])

        # 3) Paid -> 200 with CycloneDX 1.6 CBOM + signed_receipt
        with mock.patch("quantum_vuln_scanner.scan_full", return_value=FAKE_SCAN):
            r200 = self.client.get(
                "/api/v1/x402/cbom?domain=cloudflare.com",
                headers={"PAYMENT-SIGNATURE": _make_payment_sig(ch)},
            )
        self.assertEqual(r200.status_code, 200)
        body = r200.get_json()
        self.assertEqual(body["sku"], "x402_cbom_v1")
        self.assertEqual(body["domain"], "cloudflare.com")
        self.assertEqual(body["cbom"]["bomFormat"], "CycloneDX")
        self.assertIn("signed_receipt", body)


if __name__ == "__main__":
    unittest.main()
