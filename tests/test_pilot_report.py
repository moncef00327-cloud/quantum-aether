"""Tests for the German MSP Pilot report builder (Ampel + signed receipts + partner logo)."""
import datetime as dt
import os
from pathlib import Path
import tempfile
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import quantum_vuln_scanner as qs
import receipts
from tools import build_pilot_report as bpr


def _make_key(path: Path):
    priv = Ed25519PrivateKey.generate()
    path.write_bytes(priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    os.chmod(path, 0o600)


def _fake_scan(host: str, port: int):
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    if host.startswith("broken."):
        raise qs.ScanError("tls_failure", "handshake failed")
    is_pq = host.startswith("pq.")
    return {
        "domain": host,
        "ip": "203.0.113.20",
        "port": port,
        "scanned_at": now.isoformat(),
        "scanner_version": "2.0",
        "legacy_tls_enabled": False,
        "client_offered_groups": ["X25519MLKEM768", "x25519", "secp256r1"],
        "key_exchange": {
            "version": "TLSv1.3",
            "group": "X25519MLKEM768" if is_pq else "x25519",
            "cipher": "TLS_AES_256_GCM_SHA384",
            "pq": is_pq,
            "hrr": False,
            "kx": "TLS1.3",
        },
        "certificate": {
            "verified": True,
            "chain_valid": True,
            "hostname_match": True,
            "key_algorithm": "ECDSA",
            "key_bits": 256,
            "curve": "secp256r1",
            "signature_algorithm": "ecdsa-with-SHA256",
            "not_after": (now + dt.timedelta(days=90)).isoformat(),
            "days_left": 90,
            "leaf_sha256": "1" * 64,
            "spki_sha256": "2" * 64,
            "negotiated_version": "TLSv1.3",
            "negotiated_cipher": "TLS_AES_256_GCM_SHA384",
        },
        "grade": "A" if is_pq else "B",
        "findings": [],
    }


class PilotReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.key_path = Path(self.tmp.name) / "qa-ed25519-2026-11.pem"
        _make_key(self.key_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_hosts_list_dedups_and_caps_at_50(self):
        lines = [f"host{i}.example.at" for i in range(60)] + ["HOST0.example.at.", "# comment", ""]
        targets = bpr.parse_hosts_list(lines, max_hosts=50)
        self.assertEqual(len(targets), 50)
        self.assertEqual(targets[0], ("host0.example.at", 443))

    def test_scan_sign_and_render_german_ampel_with_logo(self):
        svg_path = Path(self.tmp.name) / "logo.svg"
        svg_path.write_text("<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'></svg>", encoding="utf-8")
        logo_uri = bpr.encode_logo_data_uri(str(svg_path))
        self.assertTrue(logo_uri.startswith("data:image/svg+xml;base64,"))

        targets = [("pq.kunde.at", 443), ("login.kunde.at", 443), ("broken.kunde.at", 443)]
        entries = bpr.scan_and_sign_targets(
            targets,
            scanner=_fake_scan,
            key_path=self.key_path,
            kid="qa-ed25519-2026-11",
            base_domain="kunde.at",
            workers=1,
        )
        self.assertEqual(len(entries), 3)
        jwks = receipts.jwks_document(key_path=self.key_path, kid="qa-ed25519-2026-11")
        # Verify green receipt passes strict verify_receipt; red/yellow signatures verify with require_pass=False
        self.assertEqual(
            receipts.verify_receipt(entries[0]["signed_receipt_jws"], "pq.kunde.at:443", jwks_doc=jwks)["policy_verdict"]["grade"],
            "A+",
        )
        self.assertEqual(
            receipts.verify_receipt(entries[1]["signed_receipt_jws"], "login.kunde.at:443", jwks_doc=jwks, require_pass=False)["policy_verdict"]["grade"],
            "B",
        )
        self.assertEqual(
            receipts.verify_receipt(entries[2]["signed_receipt_jws"], "broken.kunde.at:443", jwks_doc=jwks, require_pass=False)["policy_verdict"]["fail_reasons"],
            ["HANDSHAKE_FAILED"],
        )

        html_out = bpr.render_pilot_html(
            org="Musterkunde GmbH",
            entries=entries,
            measured_utc="2026-11-24 03:00 UTC",
            partner_name="Alpen IT GmbH",
            logo_data_uri=logo_uri,
        )
        self.assertIn("Post-Quanten-TLS-Prüfbericht", html_out)
        self.assertIn("Alpen IT GmbH", html_out)
        self.assertIn("Grün (A+)", html_out)
        self.assertIn("Gelb (B)", html_out)
        self.assertIn("Rot (F)", html_out)
        self.assertIn("keine vollständige", html_out)
        self.assertIn("jwks.json", html_out)
        self.assertIn(logo_uri, html_out)


if __name__ == "__main__":
    unittest.main()
