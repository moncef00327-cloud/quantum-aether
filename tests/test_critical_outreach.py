"""Unit tests for critical-case TLS outreach templates & classification (tools/critical_outreach.py)."""
import datetime as dt
import os
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import receipts
from tools import critical_outreach as co


def _make_key(path: Path):
    priv = Ed25519PrivateKey.generate()
    path.write_bytes(priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    os.chmod(path, 0o600)


def _scan(host="bank.example.de", *, tls_version="TLSv1.2", group="secp256r1", kx_type="ECDHE",
          pq=False, legacy=False, chain_valid=True, hostname_match=True, days_left=60):
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    return {
        "domain": host,
        "ip": "203.0.113.50",
        "port": 443,
        "scanned_at": now.isoformat(),
        "scanner_version": "2.0",
        "legacy_tls_enabled": legacy,
        "client_offered_groups": ["X25519MLKEM768", "x25519", "secp256r1"],
        "key_exchange": {"version": tls_version, "group": group, "cipher": "ECDHE-RSA-AES128-GCM-SHA256",
                         "pq": pq, "hrr": False, "kx": kx_type},
        "certificate": {"verified": chain_valid and hostname_match and days_left > 0,
                        "chain_valid": chain_valid, "hostname_match": hostname_match,
                        "key_algorithm": "RSA", "key_bits": 2048, "signature_algorithm": "sha256WithRSAEncryption",
                        "not_after": (now + dt.timedelta(days=days_left)).isoformat(),
                        "days_left": days_left, "leaf_sha256": "a" * 64, "spki_sha256": "b" * 64,
                        "negotiated_version": tls_version, "negotiated_cipher": "ECDHE-RSA-AES128-GCM-SHA256"},
        "grade": "C",
        "findings": [],
    }


class CriticalOutreachTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.key_path = Path(self.tmp.name) / "qa-ed25519-2026-11.pem"
        _make_key(self.key_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_classify_critical_findings_and_skips_healthy_hosts(self):
        # Healthy PQ A+ host -> not critical
        ok_raw = _scan(tls_version="TLSv1.3", group="X25519MLKEM768", kx_type="TLS1.3", pq=True, legacy=False)
        ok_claims = receipts.build_receipt_claims(ok_raw)
        self.assertEqual(co.classify_critical(ok_raw, ok_claims), [])

        # Standard classical TLS 1.3 without legacy -> not critical (handled by regular outreach)
        b_raw = _scan(tls_version="TLSv1.3", group="x25519", kx_type="TLS1.3", pq=False, legacy=False)
        b_claims = receipts.build_receipt_claims(b_raw)
        self.assertEqual(co.classify_critical(b_raw, b_claims), [])

        # Silent PQ regression on TLS 1.3 -> critical!
        self.assertEqual(co.classify_critical(b_raw, b_claims, prev_pq=True), ["SILENT_PQ_REGRESSION"])

        # Expired cert + legacy TLS + static RSA + TLS 1.2 -> all flagged in priority order
        bad_raw = _scan(tls_version="TLSv1.2", kx_type="RSA", legacy=True, chain_valid=False, hostname_match=False, days_left=-3)
        bad_claims = receipts.build_receipt_claims(bad_raw)
        codes = co.classify_critical(bad_raw, bad_claims)
        self.assertEqual(codes, [
            "CERT_EXPIRED", "CERT_CHAIN_INVALID", "CERT_HOSTNAME_MISMATCH",
            "STATIC_RSA_KX", "LEGACY_TLS_ENABLED", "TLS_1_2_ONLY",
        ])

    def test_trilingual_render_includes_signed_receipt_and_unsubscribe(self):
        raw = _scan(host="bank.example.de", tls_version="TLSv1.2", legacy=True)
        claims = receipts.build_receipt_claims(raw)
        signed, _ = receipts.sign_receipt(claims, key_path=self.key_path, kid="qa-ed25519-2026-11")
        codes = co.classify_critical(raw, signed)
        for lang, expected_phrase in (
            ("de", "Kritischer TLS-Befund"),
            ("en", "TLS finding observed"),
            ("ar", "رصد حالة TLS حرجة"),
        ):
            mail = co.render_critical_email(
                domain="bank.example.de", host="bank.example.de", email="security@bank.example.de",
                lang=lang, claims=signed, codes=codes, secret="test-secret", date="2026-11-24",
            )
            self.assertIn(expected_phrase, mail["subject"], lang)
            self.assertIn(signed["jti"], mail["text"], lang)
            self.assertIn("/.well-known/jwks.json", mail["text"], lang)
            self.assertIn("/u/", mail["text"], lang)
            self.assertIn("Braunau am Inn", mail["text"], lang)
            self.assertIn("List-Unsubscribe", mail["headers"], lang)
            self.assertEqual(mail["headers"]["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")

    def test_pick_language_routes_dach_arab_and_global(self):
        self.assertEqual(co.pick_language({"domain": "firma.at", "country": "AT"}), "de")
        self.assertEqual(co.pick_language({"domain": "bank.sa", "country": "SA"}), "ar")
        self.assertEqual(co.pick_language({"domain": "corp.com", "region": "Arab world"}), "ar")
        self.assertEqual(co.pick_language({"domain": "corp.com", "country": "US"}), "en")


if __name__ == "__main__":
    unittest.main()
