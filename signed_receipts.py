"""Cryptographically signed TLS evidence receipts (Ed25519 JWS, RFC 7515).

Delegates key management, JWKS publication (`/.well-known/jwks.json`), discovery,
policy page, and v1 receipt routes to `receipts.py` while keeping compact legacy
claim helpers for A2A/ACP/MCP evidence responses.
"""
import base64
import json
import time

from cryptography.exceptions import InvalidSignature

import receipts

KEY_FILENAME = receipts.KEY_FILENAME
RECEIPT_TYP = receipts.RECEIPT_TYP


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def _key_bundle(data_dir, key_path=None, kid=None):
    priv, active_kid, active_jwk, _ = receipts.load_signing_bundle(
        key_path=key_path, kid=kid, data_dir=data_dir
    )
    return priv, active_kid, active_jwk


def jwks(data_dir, key_path=None, kid=None) -> dict:
    return receipts.jwks_document(key_path=key_path, kid=kid, data_dir=data_dir)


def build_evidence_claims(data: dict, kind: str = "tls-evidence") -> dict:
    """Extract compact, verifiable TLS observation claims from a scan/evidence/exposure dict."""
    fields = (
        "domain", "scan_id", "observation_status", "state", "grade",
        "post_quantum_key_exchange", "key_exchange_group", "group", "tls_version",
        "checked_at", "expires_at", "measured_at", "source", "verification_url",
        "first_observed", "first_pq_week", "latest_week", "latest_status",
    )
    claims = {"kind": kind}
    for key in fields:
        val = data.get(key)
        if val is not None:
            claims[key] = val
    return claims


def sign_receipt(data_dir, claims: dict, issuer: str, key_path=None, kid=None) -> str:
    """Return an RFC 7515 compact JWS (EdDSA / Ed25519) over the observation claims."""
    priv, active_kid, _ = _key_bundle(data_dir, key_path=key_path, kid=kid)
    header = {"alg": "EdDSA", "typ": RECEIPT_TYP, "kid": active_kid}
    payload = dict(claims)
    payload["iss"] = issuer
    payload["iat"] = int(time.time())
    h_b64 = _b64u_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    p_b64 = _b64u_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig = priv.sign(signing_input)
    return f"{h_b64}.{p_b64}.{_b64u_encode(sig)}"


def verify_receipt(data_dir, token: str, key_path=None, kid=None):
    """Verify a compact Ed25519 JWS receipt against this server's public key; return (header, payload)."""
    if not isinstance(token, str) or token.count(".") != 2:
        raise ValueError("Malformed compact JWS")
    h_b64, p_b64, s_b64 = token.split(".")
    try:
        header = json.loads(_b64u_decode(h_b64).decode("utf-8"))
        payload = json.loads(_b64u_decode(p_b64).decode("utf-8"))
        sig = _b64u_decode(s_b64)
    except Exception as exc:
        raise ValueError(f"Invalid JWS encoding: {exc}") from exc
    priv, active_kid, _ = _key_bundle(data_dir, key_path=key_path, kid=kid)
    if header.get("alg") not in ("EdDSA", "Ed25519"):
        raise ValueError("Unsupported JWS alg")
    if header.get("kid") != active_kid:
        raise ValueError("Unknown JWS kid")
    try:
        priv.public_key().verify(sig, f"{h_b64}.{p_b64}".encode("ascii"))
    except InvalidSignature as exc:
        raise ValueError("Invalid JWS signature") from exc
    return header, payload


def register(bp, services):
    receipts.register_routes(bp, services)
