"""Cryptographically signed TLS evidence receipts (Ed25519 JWS, RFC 7515) + /.well-known/jwks.json.

Each live scan or stored evidence lookup returned over MCP, A2A, or ACP can carry a compact JWS
signed with the server's Ed25519 key (stored in DATA_DIR/receipt_ed25519.pem, mode 0600, never
committed to git). Verifiers fetch the public OKP JWK from GET /.well-known/jwks.json.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from flask import jsonify

KEY_FILENAME = "receipt_ed25519.pem"
RECEIPT_TYP = "qa-tls-receipt+jwt"
_CACHE = {}


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def _jwk_thumbprint(x_b64u: str) -> str:
    """RFC 7638 JWK thumbprint for an OKP Ed25519 key."""
    canonical = json.dumps({"crv": "Ed25519", "kty": "OKP", "x": x_b64u}, separators=(",", ":"), sort_keys=True)
    return _b64u_encode(hashlib.sha256(canonical.encode("ascii")).digest())[:22]


def _key_bundle(data_dir):
    root = Path(data_dir).resolve()
    key_path = root / KEY_FILENAME
    cache_key = str(key_path)
    cached = _CACHE.get(cache_key)
    if cached and key_path.exists():
        return cached
    root.mkdir(parents=True, exist_ok=True)
    if key_path.exists():
        priv = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    else:
        priv = Ed25519PrivateKey.generate()
        pem = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        tmp_path = root / f".{KEY_FILENAME}.{os.getpid()}.tmp"
        fd = os.open(str(tmp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(pem)
        except Exception:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        try:
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, key_path)
        except OSError:
            tmp_path.unlink(missing_ok=True)
            if key_path.exists():
                priv = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
            else:
                raise
    pub_raw = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    x_b64u = _b64u_encode(pub_raw)
    kid = _jwk_thumbprint(x_b64u)
    jwk = {"kty": "OKP", "crv": "Ed25519", "use": "sig", "alg": "EdDSA", "kid": kid, "x": x_b64u}
    bundle = (priv, kid, jwk)
    _CACHE[cache_key] = bundle
    return bundle


def jwks(data_dir) -> dict:
    _, _, jwk = _key_bundle(data_dir)
    return {"keys": [dict(jwk)]}


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


def sign_receipt(data_dir, claims: dict, issuer: str) -> str:
    """Return an RFC 7515 compact JWS (EdDSA / Ed25519) over the observation claims."""
    priv, kid, _ = _key_bundle(data_dir)
    header = {"alg": "EdDSA", "typ": RECEIPT_TYP, "kid": kid}
    payload = dict(claims)
    payload["iss"] = issuer
    payload["iat"] = int(time.time())
    h_b64 = _b64u_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    p_b64 = _b64u_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig = priv.sign(signing_input)
    return f"{h_b64}.{p_b64}.{_b64u_encode(sig)}"


def verify_receipt(data_dir, token: str):
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
    priv, kid, _ = _key_bundle(data_dir)
    if header.get("alg") != "EdDSA":
        raise ValueError("Unsupported JWS alg")
    if header.get("kid") != kid:
        raise ValueError("Unknown JWS kid")
    try:
        priv.public_key().verify(sig, f"{h_b64}.{p_b64}".encode("ascii"))
    except InvalidSignature as exc:
        raise ValueError("Invalid JWS signature") from exc
    return header, payload


def register(bp, services):
    @bp.get("/.well-known/jwks.json")
    def well_known_jwks():
        resp = jsonify(jwks(services["data_dir"]()))
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp
