"""Comprehensive tests for Quantum Aether v1 Signed TLS Receipts (Section 11 checklist)."""
import base64
import copy
import datetime as dt
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import adoption
import quantum_saas_app
import quantum_vuln_scanner
import receipts
from tools import qa_verify


def _make_pem_key(path: Path) -> Ed25519PrivateKey:
    priv = Ed25519PrivateKey.generate()
    pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    path.write_bytes(pem)
    os.chmod(path, 0o600)
    return priv


def _pq_scan_result(host="mcp.example.com", port=443, *, legacy_tls=False, days_left=90,
                    group="X25519MLKEM768", tls_version="TLSv1.3", pq=True,
                    chain_valid=True, hostname_match=True):
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    not_after = now + dt.timedelta(days=days_left)
    return {
        "domain": host,
        "ip": "203.0.113.10",
        "port": port,
        "scanned_at": now.isoformat(),
        "scanner_version": "2.0",
        "legacy_tls_enabled": legacy_tls,
        "client_offered_groups": ["X25519MLKEM768", "x25519", "secp256r1"],
        "key_exchange": {
            "version": tls_version,
            "group": group,
            "cipher": "TLS_AES_256_GCM_SHA384",
            "pq": pq,
            "pq_hello_ok": True,
            "hrr": False,
            "kx": "TLS1.3" if tls_version == "TLSv1.3" else "ECDHE",
        },
        "certificate": {
            "verified": chain_valid and hostname_match and days_left > 0,
            "chain_valid": chain_valid,
            "hostname_match": hostname_match,
            "verify_error": None,
            "key_algorithm": "ECDSA",
            "key_bits": 256,
            "curve": "secp256r1",
            "signature_algorithm": "ecdsa-with-SHA256",
            "subject": host,
            "issuer": "Test CA",
            "not_after": not_after.isoformat(),
            "days_left": days_left,
            "san_count": 1,
            "sans": [host],
            "leaf_sha256": "a" * 64,
            "spki_sha256": "b" * 64,
            "negotiated_version": tls_version,
            "negotiated_cipher": "TLS_AES_256_GCM_SHA384",
        },
        "grade": "A" if pq else "B",
        "findings": [],
    }


def _reencode_custom_jws(priv: Ed25519PrivateKey, header: dict, payload: dict) -> str:
    h_b64 = receipts._b64u_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = receipts._b64u_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = priv.sign(f"{h_b64}.{p_b64}".encode("ascii"))
    return f"{h_b64}.{p_b64}.{receipts._b64u_encode(sig)}"


class ReceiptCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.key_path = Path(self.tmp.name) / "qa-ed25519-2026-11.pem"
        self.priv = _make_pem_key(self.key_path)
        self.kid = "qa-ed25519-2026-11"
        self.jwks = receipts.jwks_document(key_path=self.key_path, kid=self.kid)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sign_and_verify_payload_exact_match(self):
        claims = receipts.build_receipt_claims(
            _pq_scan_result(),
            scan_id="scn_7d4e8a903f9c2e7a",
            endpoint_type="mcp_remote",
            discovered_manifest="/.well-known/agent-card.json",
            vantage="eu-central",
        )
        signed_claims, token = receipts.sign_receipt(claims, key_path=self.key_path, kid=self.kid)
        # Signature must be 64 bytes -> 86 base64url chars
        self.assertEqual(len(token.split(".")[2]), 86)
        verified = receipts.verify_receipt(token, "mcp.example.com:443", jwks_doc=self.jwks)
        self.assertEqual(verified, signed_claims)
        self.assertEqual(verified["rcpt_ver"], "1.0")
        self.assertEqual(verified["policy_verdict"]["grade"], "A+")
        self.assertEqual(verified["policy_verdict"]["result"], "pass")
        self.assertEqual(verified["policy_verdict"]["fail_reasons"], [])
        self.assertIn("CLASSICAL_CERT_SIGNATURE", verified["policy_verdict"]["warnings"])
        self.assertFalse(verified["tls_audit"]["pq_authentication"])
        self.assertTrue(verified["tls_audit"]["hybrid_pq_key_exchange"])
        self.assertEqual(verified["tls_audit"]["cert"]["leaf_sha256"], "a" * 64)
        self.assertEqual(verified["tls_audit"]["cert"]["spki_sha256"], "b" * 64)
        self.assertEqual(verified["exp"] - verified["iat"], 86400)
        self.assertEqual(verified["nbf"], verified["iat"])
        self.assertTrue(verified["jti"].startswith("qa_rcpt_"))
        self.assertEqual(len(verified["jti"]), len("qa_rcpt_") + 32)

    def test_tampering_any_payload_field_fails_verification(self):
        claims = receipts.build_receipt_claims(_pq_scan_result())
        signed, token = receipts.sign_receipt(claims, key_path=self.key_path, kid=self.kid)
        h_b64, _, s_b64 = token.split(".")
        tampered_claims = copy.deepcopy(signed)
        tampered_claims["policy_verdict"]["grade"] = "A"
        bad_p = receipts._b64u_encode(json.dumps(tampered_claims, separators=(",", ":")).encode("utf-8"))
        with self.assertRaisesRegex(ValueError, "invalid signature"):
            receipts.verify_receipt(f"{h_b64}.{bad_p}.{s_b64}", "mcp.example.com:443", jwks_doc=self.jwks)

    def test_wrong_typ_forbidden_headers_and_alg_rejected(self):
        claims = receipts.build_receipt_claims(_pq_scan_result())
        signed, _ = receipts.sign_receipt(claims, key_path=self.key_path, kid=self.kid)

        # Wrong typ
        tok = _reencode_custom_jws(self.priv, {"alg": "EdDSA", "kid": self.kid, "typ": "JWT"}, signed)
        with self.assertRaisesRegex(ValueError, "wrong typ"):
            receipts.verify_receipt(tok, "mcp.example.com:443", jwks_doc=self.jwks)

        # Forbidden jku / x5u / jwk
        for bad_hdr in ("jku", "x5u", "jwk"):
            hdr = {"alg": "EdDSA", "kid": self.kid, "typ": receipts.RECEIPT_TYP, bad_hdr: "https://evil.test/jwks.json"}
            tok = _reencode_custom_jws(self.priv, hdr, signed)
            with self.subTest(bad_hdr=bad_hdr), self.assertRaisesRegex(ValueError, "forbidden header"):
                receipts.verify_receipt(tok, "mcp.example.com:443", jwks_doc=self.jwks)

        # Unsupported alg
        tok = _reencode_custom_jws(self.priv, {"alg": "HS256", "kid": self.kid, "typ": receipts.RECEIPT_TYP}, signed)
        with self.assertRaisesRegex(ValueError, "unsupported alg"):
            receipts.verify_receipt(tok, "mcp.example.com:443", jwks_doc=self.jwks)

        # RFC 9864 explicit Ed25519 alg is accepted by verifier
        tok_ed = _reencode_custom_jws(self.priv, {"alg": "Ed25519", "kid": self.kid, "typ": receipts.RECEIPT_TYP}, signed)
        self.assertEqual(receipts.verify_receipt(tok_ed, "mcp.example.com:443", jwks_doc=self.jwks)["sub"], "mcp.example.com:443")

    def test_expired_and_future_nbf_rejected(self):
        now = 1800000000
        claims = receipts.build_receipt_claims(_pq_scan_result())
        _, token = receipts.sign_receipt(claims, key_path=self.key_path, kid=self.kid, now=now)

        # Expired beyond 60s leeway
        with self.assertRaisesRegex(ValueError, "expired"):
            receipts.verify_receipt(token, "mcp.example.com:443", jwks_doc=self.jwks, now=now + 86400 + 61)

        # Within leeway still accepted
        self.assertEqual(
            receipts.verify_receipt(token, "mcp.example.com:443", jwks_doc=self.jwks, now=now + 86400 + 30)["sub"],
            "mcp.example.com:443",
        )

        # nbf in future beyond 60s leeway
        with self.assertRaisesRegex(ValueError, "not yet valid"):
            receipts.verify_receipt(token, "mcp.example.com:443", jwks_doc=self.jwks, now=now - 61)

    def test_wrong_sub_rejected(self):
        claims = receipts.build_receipt_claims(_pq_scan_result(host="mcp.example.com", port=443))
        _, token = receipts.sign_receipt(claims, key_path=self.key_path, kid=self.kid)
        with self.assertRaisesRegex(ValueError, "another host"):
            receipts.verify_receipt(token, "other.example.com:443", jwks_doc=self.jwks)
        with self.assertRaisesRegex(ValueError, "another host"):
            receipts.verify_receipt(token, "mcp.example.com:8443", jwks_doc=self.jwks)

    def test_unaccepted_policy_or_fail_result_rejected(self):
        # Policy fail (classical TLS 1.3 -> grade B, result=fail)
        claims_b = receipts.build_receipt_claims(_pq_scan_result(group="x25519", pq=False))
        self.assertEqual(claims_b["policy_verdict"]["grade"], "B")
        self.assertEqual(claims_b["policy_verdict"]["result"], "fail")
        self.assertIn("NO_HYBRID_PQ_GROUP", claims_b["policy_verdict"]["fail_reasons"])
        _, tok_b = receipts.sign_receipt(claims_b, key_path=self.key_path, kid=self.kid)
        with self.assertRaisesRegex(ValueError, "policy failed"):
            receipts.verify_receipt(tok_b, "mcp.example.com:443", jwks_doc=self.jwks)

        # Unaccepted policy version
        claims_pass = receipts.build_receipt_claims(_pq_scan_result())
        _, tok_pass = receipts.sign_receipt(claims_pass, key_path=self.key_path, kid=self.kid)
        with self.assertRaisesRegex(ValueError, "policy not accepted"):
            receipts.verify_receipt(
                tok_pass, "mcp.example.com:443", jwks_doc=self.jwks,
                accepted_policies={("qa-pqc-transport", "2.0")},
            )

    def test_policy_grading_matrix(self):
        # A+ : all 5 + no legacy TLS + >= 30 days
        c_aplus = receipts.build_receipt_claims(_pq_scan_result(legacy_tls=False, days_left=45))
        self.assertEqual((c_aplus["policy_verdict"]["grade"], c_aplus["policy_verdict"]["result"]), ("A+", "pass"))

        # A : legacy TLS enabled
        c_a_leg = receipts.build_receipt_claims(_pq_scan_result(legacy_tls=True, days_left=45))
        self.assertEqual((c_a_leg["policy_verdict"]["grade"], c_a_leg["policy_verdict"]["result"]), ("A", "pass"))
        self.assertIn("LEGACY_TLS_ENABLED", c_a_leg["policy_verdict"]["warnings"])

        # A : cert expires < 30 days
        c_a_soon = receipts.build_receipt_claims(_pq_scan_result(legacy_tls=False, days_left=15))
        self.assertEqual((c_a_soon["policy_verdict"]["grade"], c_a_soon["policy_verdict"]["result"]), ("A", "pass"))
        self.assertIn("CERT_EXPIRES_SOON", c_a_soon["policy_verdict"]["warnings"])

        # C : TLS 1.2 + valid cert
        c_c = receipts.build_receipt_claims(_pq_scan_result(tls_version="TLSv1.2", group="x25519", pq=False))
        self.assertEqual((c_c["policy_verdict"]["grade"], c_c["policy_verdict"]["result"]), ("C", "fail"))
        self.assertIn("TLS_VERSION_BELOW_1_3", c_c["policy_verdict"]["fail_reasons"])

        # F : expired / mismatch / invalid chain / handshake failed
        c_exp = receipts.build_receipt_claims(_pq_scan_result(days_left=-2))
        self.assertEqual(c_exp["policy_verdict"]["grade"], "F")
        self.assertIn("CERT_EXPIRED", c_exp["policy_verdict"]["fail_reasons"])

        c_mis = receipts.build_receipt_claims(_pq_scan_result(hostname_match=False))
        self.assertEqual(c_mis["policy_verdict"]["grade"], "F")
        self.assertIn("CERT_HOSTNAME_MISMATCH", c_mis["policy_verdict"]["fail_reasons"])

        c_chain = receipts.build_receipt_claims(_pq_scan_result(chain_valid=False))
        self.assertEqual(c_chain["policy_verdict"]["grade"], "F")
        self.assertIn("CERT_CHAIN_INVALID", c_chain["policy_verdict"]["fail_reasons"])

        c_fail = receipts.build_failed_receipt_claims("mcp.example.com", 443)
        self.assertEqual(c_fail["policy_verdict"]["grade"], "F")
        self.assertEqual(c_fail["policy_verdict"]["fail_reasons"], ["HANDSHAKE_FAILED"])
        self.assertIsNone(c_fail["tls_audit"]["tls_version"])
        self.assertIsNone(c_fail["tls_audit"]["cert"])

    def test_normalization_cases(self):
        self.assertEqual(receipts.normalize_target("MCP.Example.COM.", 443), "mcp.example.com:443")
        self.assertEqual(receipts.normalize_target("  Example.DE. ", 8443), "example.de:8443")
        self.assertEqual(receipts.normalize_target("bücher.de", 443), "xn--bcher-kva.de:443")
        self.assertEqual(receipts.normalize_target("2001:0db8::1", 443), "[2001:db8::1]:443")
        self.assertEqual(receipts.normalize_target("[2001:db8::1]", 8443), "[2001:db8::1]:8443")
        self.assertEqual(receipts.normalize_target("203.0.113.10", 443), "203.0.113.10:443")
        for bad_host, bad_port in [
            ("example.com:443", 443),
            ("example.com/path", 443),
            ("user@example.com", 443),
            ("example.com?x=1", 443),
            ("example.com#frag", 443),
            ("example.com", 0),
            ("example.com", 70000),
            ("", 443),
        ]:
            with self.subTest(bad_host=bad_host, bad_port=bad_port), self.assertRaises(ValueError):
                receipts.normalize_target(bad_host, bad_port)

    def test_jwks_has_current_kid_never_private_d_and_supports_rotation(self):
        self.assertEqual(len(self.jwks["keys"]), 1)
        jwk = self.jwks["keys"][0]
        self.assertEqual(jwk["kid"], self.kid)
        self.assertEqual(jwk["kty"], "OKP")
        self.assertEqual(jwk["crv"], "Ed25519")
        self.assertEqual(jwk["use"], "sig")
        self.assertEqual(jwk["alg"], "EdDSA")
        self.assertEqual(len(jwk["x"]), 43)
        self.assertNotIn("d", jwk)

        # Rotation: publish both new and old keys simultaneously
        new_key_path = Path(self.tmp.name) / "qa-ed25519-2027-02.pem"
        _make_pem_key(new_key_path)
        rotated_jwks = receipts.jwks_document(
            key_path=new_key_path,
            kid="qa-ed25519-2027-02",
            extra_keys=[(self.kid, self.key_path)],
        )
        self.assertEqual({k["kid"] for k in rotated_jwks["keys"]}, {"qa-ed25519-2027-02", self.kid})
        for k in rotated_jwks["keys"]:
            self.assertNotIn("d", k)

        # Receipts from both old and new key verify under rotated JWKS
        _, old_tok = receipts.sign_receipt(receipts.build_receipt_claims(_pq_scan_result()), key_path=self.key_path, kid=self.kid)
        _, new_tok = receipts.sign_receipt(receipts.build_receipt_claims(_pq_scan_result()), key_path=new_key_path, kid="qa-ed25519-2027-02")
        self.assertEqual(receipts.verify_receipt(old_tok, "mcp.example.com:443", jwks_doc=rotated_jwks)["sub"], "mcp.example.com:443")
        self.assertEqual(receipts.verify_receipt(new_tok, "mcp.example.com:443", jwks_doc=rotated_jwks)["sub"], "mcp.example.com:443")

    def test_scanner_rejects_private_ips_after_dns_and_literals(self):
        for bad_ip in ("127.0.0.1", "10.0.0.1", "192.168.1.5", "::1", "169.254.169.254"):
            with self.subTest(bad_ip=bad_ip):
                with self.assertRaises(quantum_vuln_scanner.ScanError) as ctx:
                    quantum_vuln_scanner.resolve_public_target(bad_ip, 443)
                self.assertEqual(ctx.exception.code, "private_address")
                addrinfo = [(socket.AF_INET6 if ":" in bad_ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (bad_ip, 443))]
                with mock.patch("socket.getaddrinfo", return_value=addrinfo):
                    with self.assertRaises(quantum_vuln_scanner.ScanError) as ctx2:
                        quantum_vuln_scanner.resolve_public_target("internal.example.com", 443)
                    self.assertEqual(ctx2.exception.code, "private_address")


class ReceiptHttpMcpAndCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.key_path = Path(self.tmp.name) / "qa-ed25519-2026-11.pem"
        _make_pem_key(self.key_path)
        self.scanner = mock.Mock(side_effect=lambda host: _pq_scan_result(host=host))
        self.app = quantum_saas_app.create_app({
            "TESTING": True,
            "DATA_DIR": self.tmp.name,
            "PUBLIC_URL": "https://ather-quantum.com",
            "QA_SIGNING_KEY_PATH": str(self.key_path),
            "QA_SIGNING_KID": "qa-ed25519-2026-11",
            "QA_VANTAGE": "eu-central",
            "SCANS_PER_HOUR": 10,
            "GLOBAL_SCANS_PER_HOUR": 20,
        }, scanner=self.scanner)
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_jwks_discovery_and_policy_routes(self):
        r_jwks = self.client.get("/.well-known/jwks.json")
        self.assertEqual(r_jwks.status_code, 200)
        self.assertEqual(r_jwks.mimetype, "application/jwk-set+json")
        self.assertEqual(r_jwks.headers.get("Cache-Control"), "public, max-age=3600")
        self.assertEqual(r_jwks.headers.get("Access-Control-Allow-Origin"), "*")
        jwks_doc = r_jwks.get_json()
        self.assertEqual(jwks_doc["keys"][0]["kid"], "qa-ed25519-2026-11")
        self.assertNotIn("d", jwks_doc["keys"][0])

        r_cfg = self.client.get("/.well-known/qa-receipt-configuration")
        self.assertEqual(r_cfg.status_code, 200)
        cfg = r_cfg.get_json()
        self.assertEqual(cfg["issuer"], "https://ather-quantum.com")
        self.assertEqual(cfg["jwks_uri"], "https://ather-quantum.com/.well-known/jwks.json")
        self.assertEqual(cfg["receipt_typ"], "qa-tls-receipt+jwt")
        self.assertEqual(cfg["max_receipt_lifetime_s"], 86400)
        self.assertEqual(cfg["policies"][0]["uri"], "https://ather-quantum.com/policies/qa-pqc-transport/1.0")

        r_pol_html = self.client.get("/policies/qa-pqc-transport/1.0")
        self.assertEqual(r_pol_html.status_code, 200)
        self.assertIn("qa-pqc-transport", r_pol_html.text)
        self.assertIn("X25519MLKEM768", r_pol_html.text)

        r_pol_json = self.client.get("/policies/qa-pqc-transport/1.0?format=json")
        self.assertEqual(r_pol_json.status_code, 200)
        self.assertEqual(r_pol_json.get_json()["policy_id"], "qa-pqc-transport")

    def test_http_ci_scan_get_receipt_expired_and_blocked(self):
        r = self.client.post("/api/v1/scan", json={"host": "MCP.Example.com.", "port": 443, "endpoint_type": "mcp_remote"})
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertEqual(body["receipt"]["sub"], "mcp.example.com:443")
        self.assertEqual(body["verify"]["authoritative"], "signed_receipt_jws")
        jwks_doc = self.client.get("/.well-known/jwks.json").get_json()
        verified = receipts.verify_receipt(body["signed_receipt_jws"], "mcp.example.com:443", jwks_doc=jwks_doc)
        self.assertEqual(verified, body["receipt"])

        # GET /api/v1/receipts/<jti>
        jti = body["receipt"]["jti"]
        r_get = self.client.get(f"/api/v1/receipts/{jti}")
        self.assertEqual(r_get.status_code, 200)
        self.assertEqual(r_get.get_json()["signed_receipt_jws"], body["signed_receipt_jws"])

        # Unknown jti -> 404
        self.assertEqual(self.client.get("/api/v1/receipts/qa_rcpt_missing").status_code, 404)

        # Expire receipt in DB -> 410 RECEIPT_EXPIRED
        with self.app.app_context():
            conn = quantum_saas_app.db()
            with conn:
                conn.execute("UPDATE receipts SET exp = ? WHERE jti = ?", (int(time.time()) - 10, jti))
        r_exp = self.client.get(f"/api/v1/receipts/{jti}")
        self.assertEqual(r_exp.status_code, 410)
        self.assertEqual(r_exp.get_json()["error"], "RECEIPT_EXPIRED")

        # Opted-out domain -> 403, no receipt issued
        with self.app.app_context():
            adoption.record_optout(quantum_saas_app.db(), "optedout.example.com", method="test")
        r_blk = self.client.post("/api/v1/scan", json={"host": "optedout.example.com", "port": 443})
        self.assertEqual(r_blk.status_code, 403)
        self.assertEqual(r_blk.get_json()["error"], "domain_blocked")

        # Handshake failure still issues a signed FAIL receipt
        self.scanner.side_effect = quantum_vuln_scanner.ScanError("tls_failure", "handshake failed")
        r_fail = self.client.post("/api/v1/scan", json={"host": "broken.example.com", "port": 443})
        self.assertEqual(r_fail.status_code, 200)
        fail_body = r_fail.get_json()
        self.assertEqual(fail_body["receipt"]["policy_verdict"]["result"], "fail")
        self.assertEqual(fail_body["receipt"]["policy_verdict"]["fail_reasons"], ["HANDSHAKE_FAILED"])
        # Signature itself is valid (require_pass=False), policy check rejects it (require_pass=True)
        verified_fail = receipts.verify_receipt(
            fail_body["signed_receipt_jws"], "broken.example.com:443", jwks_doc=jwks_doc, require_pass=False
        )
        self.assertEqual(verified_fail, fail_body["receipt"])

    def test_mcp_dual_format_output_schema_and_expired_evidence(self):
        tools = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).get_json()["result"]["tools"]
        by_name = {t["name"]: t for t in tools}
        self.assertIn("outputSchema", by_name["scan_tls"])
        self.assertIn("outputSchema", by_name["get_tls_evidence"])

        res = self.client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "scan_tls", "arguments": {"host": "mcp.example.com", "port": 443, "endpoint_type": "mcp_remote"}},
        }).get_json()["result"]
        self.assertFalse(res["isError"])
        self.assertIn("PASS (A+)", res["content"][0]["text"])
        sc = res["structuredContent"]
        jti = sc["receipt"]["jti"]

        # Retrieve via get_tls_evidence by jti and by host:port
        ev_jti = self.client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "get_tls_evidence", "arguments": {"jti": jti}},
        }).get_json()["result"]
        self.assertFalse(ev_jti["isError"])
        self.assertEqual(ev_jti["structuredContent"]["signed_receipt_jws"], sc["signed_receipt_jws"])

        ev_host = self.client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "get_tls_evidence", "arguments": {"host": "mcp.example.com:443"}},
        }).get_json()["result"]
        self.assertFalse(ev_host["isError"])
        self.assertEqual(ev_host["structuredContent"]["receipt"]["jti"], jti)

        # Expire in DB -> get_tls_evidence returns RECEIPT_EXPIRED
        with self.app.app_context():
            conn = quantum_saas_app.db()
            with conn:
                conn.execute("UPDATE receipts SET exp = ? WHERE jti = ?", (int(time.time()) - 5, jti))
        ev_exp = self.client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "get_tls_evidence", "arguments": {"jti": jti}},
        }).get_json()["result"]
        self.assertTrue(ev_exp["isError"])
        self.assertEqual(ev_exp["structuredContent"]["error"], "RECEIPT_EXPIRED")

    def test_qa_verify_cli_exit_codes_and_ignores_fake_receipt_json(self):
        r = self.client.post("/api/v1/scan", json={"host": "mcp.example.com", "port": 443})
        body = r.get_json()
        jwks_file = Path(self.tmp.name) / "jwks.json"
        jwks_file.write_text(json.dumps(self.client.get("/.well-known/jwks.json").get_json()), encoding="utf-8")

        # Tamper accompanying readable `receipt` while keeping valid JWS -> verifier uses JWS only (Step 9)
        api_file = Path(self.tmp.name) / "api_resp.json"
        fake_body = copy.deepcopy(body)
        fake_body["receipt"]["policy_verdict"]["result"] = "fail"
        api_file.write_text(json.dumps(fake_body), encoding="utf-8")

        rc_ok = qa_verify.main(["--host", "MCP.Example.COM.", "--port", "443", "--file", str(api_file), "--jwks-file", str(jwks_file)])
        self.assertEqual(rc_ok, 0)

        # Wrong host -> exit 1
        rc_wrong_host = qa_verify.main(["--host", "other.example.com", "--port", "443", "--file", str(api_file), "--jwks-file", str(jwks_file)])
        self.assertEqual(rc_wrong_host, 1)

        # Failed policy receipt -> exit 1 and prints fail_reasons
        self.scanner.side_effect = lambda host: _pq_scan_result(host=host, group="x25519", pq=False)
        r_b = self.client.post("/api/v1/scan", json={"host": "classical.example.com", "port": 443})
        fail_file = Path(self.tmp.name) / "fail_resp.json"
        fail_file.write_text(json.dumps(r_b.get_json()), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[1] / "tools" / "qa_verify.py"),
             "--host", "classical.example.com", "--file", str(fail_file), "--jwks-file", str(jwks_file)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("NO_HYBRID_PQ_GROUP", proc.stderr)


if __name__ == "__main__":
    unittest.main()
