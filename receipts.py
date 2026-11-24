"""Signed TLS Scan Receipts — Quantum Aether v1.

Standalone module implementing the Quantum Aether v1 signed TLS receipt specification:
- Target normalization (`normalize_target`)
- Ed25519 JWS signing and verification (RFC 7515 compact JWS, typ=qa-tls-receipt+jwt)
- JWKS publication (`/.well-known/jwks.json`, Content-Type: application/jwk-set+json)
  and discovery (`/.well-known/qa-receipt-configuration`)
- Named, versioned policy engine (`qa-pqc-transport` 1.0) and public policy page
- SQLite persistence (`receipts` table, no private keys stored)
- CI/CD HTTP API (`POST /api/v1/scan`, `GET /api/v1/receipts/<jti>`)
"""
import base64
import datetime as dt
import hashlib
import html
import ipaddress
import json
import os
from pathlib import Path
import secrets
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from flask import Response, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

try:
    import idna as _idna
except ImportError:  # pragma: no cover
    _idna = None

ISSUER = "https://ather-quantum.com"
RECEIPT_TYP = "qa-tls-receipt+jwt"
RECEIPT_VERSION = "1.0"
RECEIPT_LIFETIME_S = 86400
DEFAULT_LEEWAY_S = 60

POLICY_ID = "qa-pqc-transport"
POLICY_VERSION = "1.0"
POLICY_PATH = f"/policies/{POLICY_ID}/{POLICY_VERSION}"
ACCEPTED_POLICIES = {(POLICY_ID, POLICY_VERSION)}

HYBRID_PQ_GROUPS = frozenset({
    "X25519MLKEM768",
    "SecP256r1MLKEM768",
    "SecP384r1MLKEM1024",
})

IANA_GROUP_CANONICAL = {
    "x25519": "X25519",
    "x448": "X448",
    "secp256r1": "secp256r1",
    "secp384r1": "secp384r1",
    "secp521r1": "secp521r1",
    "x25519mlkem768": "X25519MLKEM768",
    "secp256r1mlkem768": "SecP256r1MLKEM768",
    "secp384r1mlkem1024": "SecP384r1MLKEM1024",
    "mlkem512": "MLKEM512",
    "mlkem768": "MLKEM768",
    "mlkem1024": "MLKEM1024",
}

FORBIDDEN_HEADERS = frozenset({"jku", "x5u", "jwk"})
ACCEPTED_ALGS = frozenset({"EdDSA", "Ed25519"})
KEY_FILENAME = "receipt_ed25519.pem"
DEFAULT_RETENTION_DAYS = 90

_KEY_CACHE = {}

SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts (
    jti          TEXT PRIMARY KEY,
    sub          TEXT NOT NULL,
    kid          TEXT NOT NULL,
    iat          INTEGER NOT NULL,
    exp          INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    jws          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS receipts_sub_exp ON receipts (sub, exp);
"""

RECEIPT_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["receipt", "signed_receipt_jws", "verify"],
    "properties": {
        "receipt": {
            "type": "object",
            "required": [
                "iss", "sub", "iat", "nbf", "exp", "jti", "rcpt_ver",
                "target", "scan", "tls_audit", "policy_verdict",
            ],
            "properties": {
                "iss": {"type": "string"},
                "sub": {"type": "string"},
                "iat": {"type": "integer"},
                "nbf": {"type": "integer"},
                "exp": {"type": "integer"},
                "jti": {"type": "string"},
                "rcpt_ver": {"type": "string"},
                "target": {"type": "object"},
                "scan": {"type": "object"},
                "tls_audit": {"type": "object"},
                "policy_verdict": {
                    "type": "object",
                    "required": ["policy_id", "policy_version", "policy_uri", "result", "grade", "fail_reasons", "warnings"],
                },
            },
        },
        "signed_receipt_jws": {"type": "string"},
        "verify": {
            "type": "object",
            "required": ["issuer", "jwks_uri", "typ", "authoritative"],
            "properties": {
                "issuer": {"type": "string"},
                "jwks_uri": {"type": "string"},
                "typ": {"type": "string"},
                "authoritative": {"type": "string", "const": "signed_receipt_jws"},
            },
        },
    },
    "additionalProperties": True,
}


# ---------------------------------------------------------------- Base64url & time helpers

def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(text: str) -> bytes:
    if not isinstance(text, str) or not text:
        raise ValueError("invalid base64url segment")
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def _rfc3339_utc(value) -> str:
    """Format a datetime, unix timestamp, or ISO string as RFC 3339 UTC ending with 'Z'."""
    if value is None:
        return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, (int, float)):
        return dt.datetime.fromtimestamp(int(value), tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, dt.datetime):
        t = value.replace(tzinfo=dt.timezone.utc) if value.tzinfo is None else value.astimezone(dt.timezone.utc)
        return t.strftime("%Y-%m-%dT%H:%M:%SZ")
    parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    t = parsed.replace(tzinfo=dt.timezone.utc) if parsed.tzinfo is None else parsed.astimezone(dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_rfc3339(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=dt.timezone.utc) if parsed.tzinfo is None else parsed.astimezone(dt.timezone.utc)


def _canonical_group(group: str | None) -> str | None:
    if not group:
        return None
    return IANA_GROUP_CANONICAL.get(str(group).lower(), str(group))


# ---------------------------------------------------------------- Target normalization (Section 9)

def normalize_target(host: str, port: int = 443) -> str:
    """Normalize a target into canonical `host:port` (or `[ipv6]:port`) form per Section 9."""
    if not isinstance(host, str):
        raise ValueError("invalid target")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError("invalid target")
    h = host.strip().lower().rstrip(".")
    if not h or any(ch in h for ch in "/?#@\\") or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in h):
        raise ValueError("invalid target")
    try:
        ip = ipaddress.ip_address(h.strip("[]"))
    except ValueError:
        if ":" in h:
            raise ValueError("pass the port separately")
        if "[" in h or "]" in h:
            raise ValueError("invalid target")
        try:
            if _idna is not None:
                ascii_host = _idna.encode(h, uts46=True).decode("ascii")
            else:
                ascii_host = h.encode("idna").decode("ascii")
        except Exception as exc:
            raise ValueError("invalid target") from exc
        ascii_host = ascii_host.lower().rstrip(".")
        if not ascii_host or len(ascii_host) > 253 or ".." in ascii_host:
            raise ValueError("invalid target")
        return f"{ascii_host}:{port}"
    return f"[{ip.compressed}]:{port}" if ip.version == 6 else f"{ip}:{port}"


def split_normalized_sub(sub: str) -> tuple[str, int]:
    """Split a canonical `host:port` or `[ipv6]:port` string into `(host, port)`."""
    if not isinstance(sub, str) or ":" not in sub:
        raise ValueError("invalid normalized sub")
    s = sub.strip()
    if s.startswith("["):
        idx = s.rfind("]:")
        if idx < 0:
            raise ValueError("invalid normalized sub")
        host, port_s = s[1:idx], s[idx + 2:]
    else:
        host, port_s = s.rsplit(":", 1)
    try:
        port = int(port_s)
    except ValueError as exc:
        raise ValueError("invalid port") from exc
    canonical = normalize_target(host, port)
    if canonical.startswith("["):
        return canonical[1:canonical.rfind("]:")], port
    return canonical.rsplit(":", 1)[0], port


def parse_host_port_input(host: str, port: int | None = None) -> tuple[str, int, str]:
    """Parse caller input (`host` + optional `port`, or `host:port` when `port` is None).

    Returns `(clean_host, port, normalized_sub)`.
    """
    if not isinstance(host, str) or not host.strip():
        raise ValueError("invalid target")
    raw = host.strip()
    if port is None:
        if raw.startswith("[") and "]:" in raw:
            h_part, p_part = raw[1:raw.rfind("]:")], raw[raw.rfind("]:") + 2:]
            if not p_part.isdigit():
                raise ValueError("invalid port")
            port_val = int(p_part)
            sub = normalize_target(h_part, port_val)
            return split_normalized_sub(sub)[0], port_val, sub
        # Hostname with explicit :port (not bare IPv6)
        if raw.count(":") == 1:
            h_part, p_part = raw.rsplit(":", 1)
            if p_part.isdigit():
                port_val = int(p_part)
                sub = normalize_target(h_part, port_val)
                return split_normalized_sub(sub)[0], port_val, sub
        port_val = 443
    else:
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError("invalid port")
        port_val = port
    sub = normalize_target(raw, port_val)
    clean_host, clean_port = split_normalized_sub(sub)
    return clean_host, clean_port, sub


# ---------------------------------------------------------------- Key management & JWKS (Sections 4, 5, 9, 10)

def _public_jwk(priv_or_pub, kid: str) -> dict:
    pub = priv_or_pub.public_key() if isinstance(priv_or_pub, Ed25519PrivateKey) else priv_or_pub
    raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    x = _b64u_encode(raw)
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "kid": kid,
        "use": "sig",
        "alg": "EdDSA",
        "x": x,
    }


def _default_kid_for(path: Path, x_b64u: str) -> str:
    stem = path.stem
    if stem.startswith("qa-ed25519-"):
        return stem
    canonical = json.dumps({"crv": "Ed25519", "kty": "OKP", "x": x_b64u}, separators=(",", ":"), sort_keys=True)
    return _b64u_encode(hashlib.sha256(canonical.encode("ascii")).digest())[:22]


def _load_or_create_key(key_path: Path, create_if_missing: bool) -> Ed25519PrivateKey:
    if key_path.exists():
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError(f"Signing key {key_path} is not Ed25519")
        return key
    if not create_if_missing:
        raise FileNotFoundError(f"Signing key not found: {key_path}")
    key_path.parent.mkdir(parents=True, exist_ok=True)
    priv = Ed25519PrivateKey.generate()
    pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    tmp_path = key_path.parent / f".{key_path.name}.{os.getpid()}.tmp"
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
            return serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        raise
    return priv


def _load_public_or_private_key(path: Path):
    raw = path.read_bytes()
    try:
        key = serialization.load_pem_private_key(raw, password=None)
        if isinstance(key, Ed25519PrivateKey):
            return key.public_key()
    except ValueError:
        pass
    key = serialization.load_pem_public_key(raw)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError(f"Key {path} is not Ed25519")
    return key


def _parse_extra_keys(spec: str | None) -> list[tuple[str, Path]]:
    """Parse optional rotation keys from `QA_SIGNING_EXTRA_KEYS` (`kid1=/path/one.pem,kid2=/path/two.pem`)."""
    if not spec:
        return []
    out = []
    for item in str(spec).split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            k, p = item.split("=", 1)
            out.append((k.strip(), Path(p.strip())))
        else:
            p = Path(item)
            out.append((p.stem, p))
    return out


def load_signing_bundle(*, key_path=None, kid: str | None = None, data_dir=None, extra_keys=None):
    """Load and cache `(private_key, active_kid, active_jwk, all_jwks)`.

    Uses explicit `key_path`, then `QA_SIGNING_KEY_PATH` env var (unless a `data_dir` fallback is requested
    without an explicit env var), and finally `data_dir/receipt_ed25519.pem` for dev/tests.
    """
    env_path = os.environ.get("QA_SIGNING_KEY_PATH", "").strip()
    env_kid = os.environ.get("QA_SIGNING_KID", "").strip()
    env_extra = os.environ.get("QA_SIGNING_EXTRA_KEYS", "").strip()

    if key_path:
        resolved_path = Path(key_path).resolve()
        create = False
        chosen_kid = (kid or env_kid or "").strip()
    elif data_dir is not None and not env_path:
        resolved_path = (Path(data_dir).resolve() / KEY_FILENAME)
        create = True
        chosen_kid = (kid or env_kid or "").strip()
    elif env_path:
        resolved_path = Path(env_path).resolve()
        create = False
        chosen_kid = (kid or env_kid or "").strip()
    elif data_dir is not None:
        resolved_path = (Path(data_dir).resolve() / KEY_FILENAME)
        create = True
        chosen_kid = (kid or "").strip()
    else:
        raise RuntimeError("QA_SIGNING_KEY_PATH (or data_dir) is required to load signing key")

    extra_list = list(extra_keys) if extra_keys is not None else _parse_extra_keys(env_extra)
    cache_key = (str(resolved_path), chosen_kid, tuple((k, str(p)) for k, p in extra_list))
    cached = _KEY_CACHE.get(cache_key)
    if cached and resolved_path.exists():
        try:
            mtime = resolved_path.stat().st_mtime_ns
            if cached[0] == mtime:
                return cached[1]
        except OSError:
            pass

    priv = _load_or_create_key(resolved_path, create_if_missing=create)
    pub_raw = priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    x_b64u = _b64u_encode(pub_raw)
    active_kid = chosen_kid or _default_kid_for(resolved_path, x_b64u)
    active_jwk = _public_jwk(priv, active_kid)

    jwks_list = [active_jwk]
    seen_kids = {active_kid}
    for extra_kid, extra_path in extra_list:
        if not extra_kid or extra_kid in seen_kids or not extra_path.exists():
            continue
        pub_key = _load_public_or_private_key(extra_path)
        jwks_list.append(_public_jwk(pub_key, extra_kid))
        seen_kids.add(extra_kid)

    bundle = (priv, active_kid, active_jwk, jwks_list)
    try:
        mtime = resolved_path.stat().st_mtime_ns
        _KEY_CACHE[cache_key] = (mtime, bundle)
    except OSError:
        pass
    return bundle


def jwks_document(*, key_path=None, kid: str | None = None, data_dir=None, extra_keys=None) -> dict:
    """Return the public JWKS document (`{"keys": [...]}`), never containing private component `d`."""
    _, _, _, all_jwks = load_signing_bundle(key_path=key_path, kid=kid, data_dir=data_dir, extra_keys=extra_keys)
    return {"keys": [dict(k) for k in all_jwks]}


def discovery_configuration(issuer: str = ISSUER) -> dict:
    base = issuer.rstrip("/")
    return {
        "issuer": base,
        "jwks_uri": f"{base}/.well-known/jwks.json",
        "receipt_typ": RECEIPT_TYP,
        "receipt_versions": [RECEIPT_VERSION],
        "max_receipt_lifetime_s": RECEIPT_LIFETIME_S,
        "policies": [
            {
                "id": POLICY_ID,
                "version": POLICY_VERSION,
                "uri": f"{base}{POLICY_PATH}",
            }
        ],
    }


# ---------------------------------------------------------------- Policy qa-pqc-transport 1.0 (Section 7)

def evaluate_policy_v1(tls_audit: dict, observed_at: str, issuer: str = ISSUER) -> dict:
    """Evaluate `qa-pqc-transport` version `1.0` over `tls_audit` and `observed_at`."""
    policy_uri = f"{issuer.rstrip('/')}{POLICY_PATH}"
    tls_version = tls_audit.get("tls_version")
    negotiated_group = tls_audit.get("negotiated_group")
    hybrid_pq = bool(tls_audit.get("hybrid_pq_key_exchange"))
    pq_auth = bool(tls_audit.get("pq_authentication"))
    legacy_tls = tls_audit.get("legacy_tls_enabled")
    cert = tls_audit.get("cert")

    if tls_audit.get("handshake_failed") or (tls_version is None and cert is None):
        return {
            "policy_id": POLICY_ID,
            "policy_version": POLICY_VERSION,
            "policy_uri": policy_uri,
            "result": "fail",
            "grade": "F",
            "fail_reasons": ["HANDSHAKE_FAILED"],
            "warnings": [],
        }

    fail_reasons: list[str] = []
    warnings: list[str] = []

    if tls_version != "TLSv1.3":
        fail_reasons.append("TLS_VERSION_BELOW_1_3")
    if not (hybrid_pq and negotiated_group in HYBRID_PQ_GROUPS):
        fail_reasons.append("NO_HYBRID_PQ_GROUP")

    cert_dict = cert if isinstance(cert, dict) else {}
    chain_valid = cert_dict.get("chain_valid") is True
    hostname_match = cert_dict.get("hostname_match") is True
    if not chain_valid:
        fail_reasons.append("CERT_CHAIN_INVALID")
    if not hostname_match:
        fail_reasons.append("CERT_HOSTNAME_MISMATCH")

    obs_dt = _parse_rfc3339(observed_at)
    not_after_raw = cert_dict.get("not_after")
    cert_expired = True
    days_remaining = None
    if not_after_raw:
        try:
            na_dt = _parse_rfc3339(not_after_raw)
            delta = na_dt - obs_dt
            cert_expired = delta.total_seconds() <= 0
            days_remaining = delta.total_seconds() / 86400.0
        except ValueError:
            cert_expired = True
    if cert_expired:
        fail_reasons.append("CERT_EXPIRED")
    elif days_remaining is not None and days_remaining < 30.0:
        warnings.append("CERT_EXPIRES_SOON")

    if legacy_tls is True:
        warnings.append("LEGACY_TLS_ENABLED")
    if not pq_auth:
        warnings.append("CLASSICAL_CERT_SIGNATURE")

    cert_ok = chain_valid and hostname_match and not cert_expired
    if not cert_ok or tls_version not in ("TLSv1.3", "TLSv1.2"):
        grade, result = "F", "fail"
    elif not fail_reasons:
        if legacy_tls is False and "CERT_EXPIRES_SOON" not in warnings:
            grade, result = "A+", "pass"
        else:
            grade, result = "A", "pass"
    elif tls_version == "TLSv1.3":
        grade, result = "B", "fail"
    else:
        grade, result = "C", "fail"

    return {
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "policy_uri": policy_uri,
        "result": result,
        "grade": grade,
        "fail_reasons": fail_reasons,
        "warnings": warnings,
    }


# ---------------------------------------------------------------- Claim builder (Section 3)

def _format_key_type(cert: dict) -> str:
    alg = str(cert.get("key_algorithm") or "unknown")
    bits = cert.get("key_bits")
    curve = str(cert.get("curve") or "").lower()
    if alg == "ECDSA":
        curve_map = {"secp256r1": "EC-P256", "secp384r1": "EC-P384", "secp521r1": "EC-P521"}
        if curve in curve_map:
            return curve_map[curve]
        if bits:
            return f"EC-P{bits}"
        return "EC"
    if alg == "RSA" and bits:
        return f"RSA-{bits}"
    return alg


def _is_pq_signature(sig_alg: str | None) -> bool:
    if not sig_alg:
        return False
    low = str(sig_alg).lower()
    return any(tok in low for tok in ("ml-dsa", "mldsa", "dilithium", "slh-dsa", "sphincs", "falcon"))


def _format_scanner_version(raw_ver: str | None) -> str:
    v = str(raw_ver or "1.0.0").strip()
    if v.startswith("qa-scanner/"):
        return v
    if v.count(".") == 1:
        v = f"{v}.0"
    return f"qa-scanner/{v}"


def build_receipt_claims(
    scan_result: dict,
    *,
    scan_id: str | None = None,
    endpoint_type: str | None = None,
    discovered_manifest: str | None = None,
    vantage: str | None = None,
    issuer: str = ISSUER,
) -> dict:
    """Build unsigned v1 receipt claims from a `quantum_vuln_scanner` result dict."""
    raw_host = scan_result.get("domain") or scan_result.get("host") or ""
    port = int(scan_result.get("port") or 443)
    sub = normalize_target(raw_host, port)
    clean_host, clean_port = split_normalized_sub(sub)

    kx = scan_result.get("key_exchange") or {}
    cert = scan_result.get("certificate") or {}
    observed_at = _rfc3339_utc(scan_result.get("scanned_at"))

    tls_version = kx.get("version") or cert.get("negotiated_version")
    negotiated_group = _canonical_group(kx.get("group"))
    cipher_suite = kx.get("cipher") or cert.get("negotiated_cipher")
    hybrid_pq = bool(kx.get("pq")) and negotiated_group in HYBRID_PQ_GROUPS and not kx.get("hrr") and not kx.get("error")

    sig_alg = cert.get("signature_algorithm")
    pq_auth = _is_pq_signature(sig_alg)
    legacy_tls = scan_result.get("legacy_tls_enabled")

    chain_valid = cert.get("chain_valid")
    if chain_valid is None:
        chain_valid = bool(cert.get("verified"))
    hostname_match = cert.get("hostname_match")
    if hostname_match is None:
        hostname_match = bool(cert.get("verified"))

    not_after = _rfc3339_utc(cert["not_after"]) if cert.get("not_after") else None

    offered_raw = scan_result.get("client_offered_groups") or ["X25519MLKEM768", "X25519", "secp256r1"]
    offered_groups = [_canonical_group(g) for g in offered_raw if g]

    tls_audit = {
        "tls_version": tls_version,
        "negotiated_group": negotiated_group,
        "cipher_suite": cipher_suite,
        "hybrid_pq_key_exchange": hybrid_pq,
        "pq_authentication": pq_auth,
        "legacy_tls_enabled": legacy_tls,
        "cert": {
            "chain_valid": bool(chain_valid),
            "hostname_match": bool(hostname_match),
            "key_type": _format_key_type(cert),
            "sig_alg": sig_alg,
            "not_after": not_after,
            "leaf_sha256": cert.get("leaf_sha256"),
            "spki_sha256": cert.get("spki_sha256"),
        },
    }

    verdict = evaluate_policy_v1(tls_audit, observed_at, issuer=issuer)

    target_obj = {
        "host": clean_host,
        "port": clean_port,
        "sni": clean_host,
        "resolved_ip": scan_result.get("ip"),
    }
    if endpoint_type:
        target_obj["endpoint_type"] = endpoint_type
    if discovered_manifest:
        target_obj["discovered_manifest"] = discovered_manifest

    chosen_vantage = vantage or os.environ.get("QA_VANTAGE", "eu-central")
    chosen_scan_id = scan_id or f"scn_{secrets.token_hex(8)}"

    return {
        "sub": sub,
        "rcpt_ver": RECEIPT_VERSION,
        "target": target_obj,
        "scan": {
            "scan_id": chosen_scan_id,
            "observed_at": observed_at,
            "scanner_version": _format_scanner_version(scan_result.get("scanner_version")),
            "vantage": chosen_vantage,
            "client_offered_groups": offered_groups,
        },
        "tls_audit": tls_audit,
        "policy_verdict": verdict,
    }


def build_failed_receipt_claims(
    host: str,
    port: int = 443,
    *,
    resolved_ip: str | None = None,
    scan_id: str | None = None,
    endpoint_type: str | None = None,
    discovered_manifest: str | None = None,
    vantage: str | None = None,
    scanner_version: str = "2.0",
    issuer: str = ISSUER,
) -> dict:
    """Build unsigned v1 receipt claims for a failed TLS handshake (Section 3 & 7)."""
    sub = normalize_target(host, port)
    clean_host, clean_port = split_normalized_sub(sub)
    observed_at = _rfc3339_utc(None)

    tls_audit = {
        "tls_version": None,
        "negotiated_group": None,
        "cipher_suite": None,
        "hybrid_pq_key_exchange": False,
        "pq_authentication": False,
        "legacy_tls_enabled": None,
        "cert": None,
    }
    verdict = evaluate_policy_v1({**tls_audit, "handshake_failed": True}, observed_at, issuer=issuer)

    target_obj = {
        "host": clean_host,
        "port": clean_port,
        "sni": clean_host,
        "resolved_ip": resolved_ip,
    }
    if endpoint_type:
        target_obj["endpoint_type"] = endpoint_type
    if discovered_manifest:
        target_obj["discovered_manifest"] = discovered_manifest

    return {
        "sub": sub,
        "rcpt_ver": RECEIPT_VERSION,
        "target": target_obj,
        "scan": {
            "scan_id": scan_id or f"scn_{secrets.token_hex(8)}",
            "observed_at": observed_at,
            "scanner_version": _format_scanner_version(scanner_version),
            "vantage": vantage or os.environ.get("QA_VANTAGE", "eu-central"),
            "client_offered_groups": ["X25519MLKEM768", "X25519", "secp256r1"],
        },
        "tls_audit": tls_audit,
        "policy_verdict": verdict,
    }


# ---------------------------------------------------------------- Signing & verification (Sections 4 & 8)

def sign_receipt(
    claims: dict,
    *,
    key_path=None,
    kid: str | None = None,
    data_dir=None,
    extra_keys=None,
    issuer: str = ISSUER,
    now: int | None = None,
) -> tuple[dict, str]:
    """Sign receipt claims with Ed25519 compact JWS. Returns `(signed_claims, jws_token)`."""
    priv, active_kid, _, _ = load_signing_bundle(
        key_path=key_path, kid=kid, data_dir=data_dir, extra_keys=extra_keys
    )
    ts = int(time.time()) if now is None else int(now)
    signed_claims = {
        "iss": issuer.rstrip("/"),
        "sub": claims["sub"],
        "iat": ts,
        "nbf": ts,
        "exp": ts + RECEIPT_LIFETIME_S,
        "jti": "qa_rcpt_" + secrets.token_hex(16),
    }
    for k, v in claims.items():
        if k not in ("iss", "iat", "nbf", "exp", "jti"):
            signed_claims[k] = v

    header = {"alg": "EdDSA", "kid": active_kid, "typ": RECEIPT_TYP}
    h_b64 = _b64u_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    p_b64 = _b64u_encode(json.dumps(signed_claims, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig = priv.sign(signing_input)
    token = f"{h_b64}.{p_b64}.{_b64u_encode(sig)}"
    return signed_claims, token


def parse_unverified_header(token: str) -> dict:
    if not isinstance(token, str) or token.count(".") != 2:
        raise ValueError("malformed JWS")
    h_b64 = token.split(".", 1)[0]
    try:
        header = json.loads(_b64u_decode(h_b64).decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid JWS header: {exc}") from exc
    if not isinstance(header, dict):
        raise ValueError("JWS header must be an object")
    return header


def _ed25519_key_from_jwk(jwk: dict) -> Ed25519PublicKey:
    if not isinstance(jwk, dict):
        raise ValueError("invalid JWK")
    if jwk.get("kty") != "OKP" or jwk.get("crv") != "Ed25519":
        raise ValueError("JWK must be OKP Ed25519")
    x_raw = _b64u_decode(jwk.get("x", ""))
    if len(x_raw) != 32:
        raise ValueError("invalid Ed25519 public key length")
    return Ed25519PublicKey.from_public_bytes(x_raw)


def verify_receipt(
    token: str,
    expected_sub: str,
    *,
    jwks_doc: dict,
    issuer: str = ISSUER,
    accepted_policies=None,
    leeway: int = DEFAULT_LEEWAY_S,
    now: int | None = None,
    require_pass: bool = True,
) -> dict:
    """Verify a v1 signed TLS receipt following Section 8 steps 1–7 & 9."""
    if not isinstance(token, str) or token.count(".") != 2:
        raise ValueError("malformed JWS")
    h_b64, p_b64, s_b64 = token.split(".")
    header = parse_unverified_header(token)

    # Step 2: strict header validation
    if header.get("typ") != RECEIPT_TYP:
        raise ValueError("wrong typ")
    if header.get("alg") not in ACCEPTED_ALGS:
        raise ValueError("unsupported alg")
    if FORBIDDEN_HEADERS & header.keys():
        raise ValueError("forbidden header")
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise ValueError("missing kid")

    # Step 3: key lookup by kid & OKP/Ed25519 check
    keys = (jwks_doc or {}).get("keys") or []
    matching = [k for k in keys if isinstance(k, dict) and k.get("kid") == kid]
    if not matching:
        raise ValueError(f"unknown kid: {kid}")
    pub_key = _ed25519_key_from_jwk(matching[0])

    # Step 4: verify signature
    try:
        sig = _b64u_decode(s_b64)
        if len(sig) != 64:
            raise ValueError("invalid signature length")
        pub_key.verify(sig, f"{h_b64}.{p_b64}".encode("ascii"))
    except InvalidSignature as exc:
        raise ValueError("invalid signature") from exc

    try:
        claims = json.loads(_b64u_decode(p_b64).decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid payload: {exc}") from exc
    if not isinstance(claims, dict):
        raise ValueError("payload must be an object")

    # Step 5: issuer, temporal claims (with leeway), jti
    for req in ("iss", "sub", "iat", "nbf", "exp", "jti"):
        if req not in claims or claims[req] is None:
            raise ValueError(f"missing required claim: {req}")
    if claims["iss"] != issuer.rstrip("/"):
        raise ValueError("wrong issuer")
    if not isinstance(claims["jti"], str) or not claims["jti"].strip():
        raise ValueError("empty jti")
    ts = int(time.time()) if now is None else int(now)
    try:
        nbf = int(claims["nbf"])
        exp = int(claims["exp"])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid temporal claim") from exc
    if ts + leeway < nbf:
        raise ValueError("receipt not yet valid (nbf)")
    if ts - leeway >= exp:
        raise ValueError("receipt expired (exp)")

    # Step 6: match normalized sub
    if claims["sub"] != expected_sub:
        raise ValueError("receipt is for another host")

    # Step 7: policy & verdict check
    verdict = claims.get("policy_verdict")
    if not isinstance(verdict, dict):
        raise ValueError("missing policy_verdict")
    policies = ACCEPTED_POLICIES if accepted_policies is None else set(accepted_policies)
    if (verdict.get("policy_id"), verdict.get("policy_version")) not in policies:
        raise ValueError("policy not accepted")
    if require_pass and verdict.get("result") != "pass":
        raise ValueError(f"policy failed: {verdict.get('fail_reasons') or []}")

    return claims


# ---------------------------------------------------------------- Dual response formatting (Section 6)

def format_summary_text(claims: dict) -> str:
    sub = claims.get("sub", "?")
    v = claims.get("policy_verdict") or {}
    audit = claims.get("tls_audit") or {}
    cert = audit.get("cert") or {}
    verdict_word = "PASS" if v.get("result") == "pass" else "FAIL"
    grade = v.get("grade") or "F"
    pol = f"{v.get('policy_id', POLICY_ID)} {v.get('policy_version', POLICY_VERSION)}"
    exp_iso = _rfc3339_utc(claims["exp"]) if claims.get("exp") is not None else "unknown"

    if audit.get("tls_version") is None:
        reasons = ", ".join(v.get("fail_reasons") or ["HANDSHAKE_FAILED"])
        return f"{sub} {verdict_word} ({grade}) under {pol}: {reasons}. Receipt valid until {exp_iso}."

    tls_ver = audit.get("tls_version") or "unknown"
    grp = audit.get("negotiated_group") or "unknown"
    cert_note = (
        "Certificate signature is post-quantum."
        if audit.get("pq_authentication")
        else f"Certificate signature is classical ({cert.get('key_type') or 'classical'})."
    )
    extra = ""
    if v.get("result") != "pass" and v.get("fail_reasons"):
        extra = f" Fail reasons: {', '.join(v['fail_reasons'])}."
    return (
        f"{sub} {verdict_word} ({grade}) under {pol}: {tls_ver}, {grp} negotiated. "
        f"{cert_note}{extra} Receipt valid until {exp_iso}."
    )


def format_dual_response(claims: dict, token: str, *, issuer: str = ISSUER) -> tuple[str, dict]:
    """Return `(summary_text, structuredContent)` per Section 6."""
    base = issuer.rstrip("/")
    structured = {
        "receipt": claims,
        "signed_receipt_jws": token,
        "verify": {
            "issuer": base,
            "jwks_uri": f"{base}/.well-known/jwks.json",
            "typ": RECEIPT_TYP,
            "authoritative": "signed_receipt_jws",
        },
    }
    return format_summary_text(claims), structured


# ---------------------------------------------------------------- SQLite persistence (Section 11)

def init(conn) -> None:
    conn.executescript(SCHEMA)


def save_receipt(conn, claims: dict, jws: str, kid: str) -> None:
    init(conn)
    payload_json = json.dumps(claims, separators=(",", ":"), ensure_ascii=False)
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO receipts (jti, sub, kid, iat, exp, payload_json, jws) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                claims["jti"],
                claims["sub"],
                kid,
                int(claims["iat"]),
                int(claims["exp"]),
                payload_json,
                jws,
            ),
        )


def get_receipt_by_jti(conn, jti: str) -> dict | None:
    init(conn)
    row = conn.execute(
        "SELECT jti, sub, kid, iat, exp, payload_json, jws FROM receipts WHERE jti = ?",
        (jti,),
    ).fetchone()
    if not row:
        return None
    return {
        "jti": row["jti"],
        "sub": row["sub"],
        "kid": row["kid"],
        "iat": int(row["iat"]),
        "exp": int(row["exp"]),
        "receipt": json.loads(row["payload_json"]),
        "jws": row["jws"],
    }


def get_latest_receipt_for_sub(conn, sub: str) -> dict | None:
    init(conn)
    row = conn.execute(
        "SELECT jti, sub, kid, iat, exp, payload_json, jws FROM receipts "
        "WHERE sub = ? ORDER BY exp DESC, iat DESC LIMIT 1",
        (sub,),
    ).fetchone()
    if not row:
        return None
    return {
        "jti": row["jti"],
        "sub": row["sub"],
        "kid": row["kid"],
        "iat": int(row["iat"]),
        "exp": int(row["exp"]),
        "receipt": json.loads(row["payload_json"]),
        "jws": row["jws"],
    }


def prune_expired(conn, retention_days: int = DEFAULT_RETENTION_DAYS, now: int | None = None) -> int:
    init(conn)
    cutoff = (int(time.time()) if now is None else int(now)) - int(retention_days) * 86400
    with conn:
        cur = conn.execute("DELETE FROM receipts WHERE exp < ?", (cutoff,))
        return cur.rowcount


# ---------------------------------------------------------------- Public policy document (Section 7)

def policy_document(issuer: str = ISSUER) -> dict:
    base = issuer.rstrip("/")
    return {
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "policy_uri": f"{base}{POLICY_PATH}",
        "immutable": True,
        "pass_requirements": [
            "tls_audit.tls_version == 'TLSv1.3'",
            "tls_audit.negotiated_group in ['X25519MLKEM768', 'SecP256r1MLKEM768', 'SecP384r1MLKEM1024']",
            "tls_audit.cert.chain_valid == true",
            "tls_audit.cert.hostname_match == true",
            "tls_audit.cert.not_after > scan.observed_at",
        ],
        "grades": {
            "A+": {"result": "pass", "criteria": "All 5 pass requirements + legacy_tls_enabled == false + certificate valid >= 30 days after observed_at"},
            "A": {"result": "pass", "criteria": "All 5 pass requirements without both A+ criteria"},
            "B": {"result": "fail", "criteria": "TLSv1.3 and valid certificate, without hybrid PQ key exchange"},
            "C": {"result": "fail", "criteria": "TLSv1.2 maximum and valid certificate"},
            "F": {"result": "fail", "criteria": "Invalid/mismatched/expired certificate, below TLSv1.2, or handshake failure"},
        },
        "fail_reasons": [
            "TLS_VERSION_BELOW_1_3",
            "NO_HYBRID_PQ_GROUP",
            "CERT_CHAIN_INVALID",
            "CERT_HOSTNAME_MISMATCH",
            "CERT_EXPIRED",
            "HANDSHAKE_FAILED",
        ],
        "warnings": [
            "CERT_EXPIRES_SOON",
            "LEGACY_TLS_ENABLED",
            "CLASSICAL_CERT_SIGNATURE",
        ],
        "jwks_uri": f"{base}/.well-known/jwks.json",
        "configuration_uri": f"{base}/.well-known/qa-receipt-configuration",
    }


def _policy_html(issuer: str) -> str:
    doc = policy_document(issuer)
    base = html.escape(issuer.rstrip("/"))
    uri = html.escape(doc["policy_uri"])
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quantum Aether Policy: qa-pqc-transport 1.0</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;max-width:860px;margin:2rem auto;padding:0 1.25rem;line-height:1.6;color:#111}}
code{{background:#f3f4f6;padding:.15rem .35rem;border-radius:4px;font-size:.92em}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}
th,td{{border:1px solid #d1d5db;padding:.55rem .7rem;text-align:left}}
th{{background:#f9fafb}}
.note{{background:#f8fafc;border-left:4px solid #0f766e;padding:.75rem 1rem;margin:1rem 0}}
</style>
</head>
<body>
<h1>Policy: <code>qa-pqc-transport</code> v1.0</h1>
<p>Canonical URI: <code>{uri}</code></p>
<div class="note"><strong>Immutability guarantee:</strong> Published policy versions are never altered retroactively. Any change to grading or pass rules is published under a new version (e.g., 1.1 or 2.0).</div>
<h2>Pass Requirements (<code>result: "pass"</code>)</h2>
<ol>
<li><code>tls_audit.tls_version</code> is <code>TLSv1.3</code>.</li>
<li><code>tls_audit.negotiated_group</code> is an approved hybrid post-quantum group: <code>X25519MLKEM768</code>, <code>SecP256r1MLKEM768</code>, or <code>SecP384r1MLKEM1024</code>.</li>
<li><code>tls_audit.cert.chain_valid</code> is <code>true</code>.</li>
<li><code>tls_audit.cert.hostname_match</code> is <code>true</code>.</li>
<li><code>tls_audit.cert.not_after</code> is strictly after <code>scan.observed_at</code>.</li>
</ol>
<h2>Grades</h2>
<table>
<thead><tr><th>Grade</th><th>Criteria</th><th>Result</th></tr></thead>
<tbody>
<tr><td><strong>A+</strong></td><td>All 5 pass requirements + <code>legacy_tls_enabled == false</code> + certificate valid at least 30 days after <code>observed_at</code></td><td><code>pass</code></td></tr>
<tr><td><strong>A</strong></td><td>All 5 pass requirements without both A+ criteria</td><td><code>pass</code></td></tr>
<tr><td><strong>B</strong></td><td>TLS 1.3 and valid certificate, without hybrid PQ key exchange</td><td><code>fail</code></td></tr>
<tr><td><strong>C</strong></td><td>TLS 1.2 maximum and valid certificate</td><td><code>fail</code></td></tr>
<tr><td><strong>F</strong></td><td>Invalid/mismatched/expired certificate, below TLS 1.2, or handshake failure</td><td><code>fail</code></td></tr>
</tbody>
</table>
<h2>Reason &amp; Warning Codes</h2>
<table>
<thead><tr><th>Code</th><th>Type</th><th>Meaning</th></tr></thead>
<tbody>
<tr><td><code>TLS_VERSION_BELOW_1_3</code></td><td>fail</td><td>Negotiated TLS version is below 1.3</td></tr>
<tr><td><code>NO_HYBRID_PQ_GROUP</code></td><td>fail</td><td>Negotiated key-exchange group is not an approved hybrid PQ group</td></tr>
<tr><td><code>CERT_CHAIN_INVALID</code></td><td>fail</td><td>Certificate chain does not verify to a trusted root</td></tr>
<tr><td><code>CERT_HOSTNAME_MISMATCH</code></td><td>fail</td><td>Certificate does not match target host</td></tr>
<tr><td><code>CERT_EXPIRED</code></td><td>fail</td><td><code>not_after</code> is at or before <code>observed_at</code></td></tr>
<tr><td><code>HANDSHAKE_FAILED</code></td><td>fail</td><td>TLS handshake failed; <code>tls_audit</code> fields are null</td></tr>
<tr><td><code>CERT_EXPIRES_SOON</code></td><td>warning</td><td>Certificate expires in fewer than 30 days</td></tr>
<tr><td><code>LEGACY_TLS_ENABLED</code></td><td>warning</td><td>Server accepts TLS 1.1 or older</td></tr>
<tr><td><code>CLASSICAL_CERT_SIGNATURE</code></td><td>warning</td><td><code>pq_authentication</code> is <code>false</code> (classical RSA/ECDSA/EdDSA certificate)</td></tr>
</tbody>
</table>
<p>Verify receipts using JWKS at <a href="{base}/.well-known/jwks.json"><code>{base}/.well-known/jwks.json</code></a> and discovery at <a href="{base}/.well-known/qa-receipt-configuration"><code>{base}/.well-known/qa-receipt-configuration</code></a>. JSON representation is available via <code>Accept: application/json</code> or <code>?format=json</code>.</p>
</body>
</html>"""


# ---------------------------------------------------------------- Flask route registration (Sections 5, 6, 11)

def key_config_from_app(services: dict) -> dict:
    cfg = current_app.config
    data_dir = services["data_dir"]() if services.get("data_dir") else cfg.get("DATA_DIR")
    key_path = cfg.get("QA_SIGNING_KEY_PATH")
    kid = cfg.get("QA_SIGNING_KID")
    extra = cfg.get("QA_SIGNING_EXTRA_KEYS")
    if key_path is None and not cfg.get("TESTING"):
        key_path = os.environ.get("QA_SIGNING_KEY_PATH") or None
    if kid is None and not cfg.get("TESTING"):
        kid = os.environ.get("QA_SIGNING_KID") or None
    if extra is None and not cfg.get("TESTING"):
        extra = os.environ.get("QA_SIGNING_EXTRA_KEYS") or None
    extra_parsed = _parse_extra_keys(extra) if isinstance(extra, str) else extra
    return {"key_path": key_path, "kid": kid, "data_dir": data_dir, "extra_keys": extra_parsed}


def issue_and_store_receipt(
    services: dict,
    scan_result: dict,
    *,
    scan_id: str | None = None,
    endpoint_type: str | None = None,
    discovered_manifest: str | None = None,
) -> tuple[dict, str, str, dict]:
    """Build claims, sign, persist into SQLite `receipts`, and return `(claims, jws, summary_text, dual_body)`."""
    issuer = services["base"]().rstrip("/")
    kcfg = key_config_from_app(services)
    vantage = current_app.config.get("QA_VANTAGE") or os.environ.get("QA_VANTAGE", "eu-central")
    claims = build_receipt_claims(
        scan_result,
        scan_id=scan_id,
        endpoint_type=endpoint_type,
        discovered_manifest=discovered_manifest,
        vantage=vantage,
        issuer=issuer,
    )
    signed_claims, token = sign_receipt(claims, issuer=issuer, **kcfg)
    _, active_kid, _, _ = load_signing_bundle(**kcfg)
    save_receipt(services["db"](), signed_claims, token, active_kid)
    summary_text, dual = format_dual_response(signed_claims, token, issuer=issuer)
    return signed_claims, token, summary_text, dual


def issue_and_store_failed_receipt(
    services: dict,
    host: str,
    port: int = 443,
    *,
    resolved_ip: str | None = None,
    scan_id: str | None = None,
    endpoint_type: str | None = None,
    discovered_manifest: str | None = None,
) -> tuple[dict, str, str, dict]:
    issuer = services["base"]().rstrip("/")
    kcfg = key_config_from_app(services)
    vantage = current_app.config.get("QA_VANTAGE") or os.environ.get("QA_VANTAGE", "eu-central")
    claims = build_failed_receipt_claims(
        host,
        port,
        resolved_ip=resolved_ip,
        scan_id=scan_id,
        endpoint_type=endpoint_type,
        discovered_manifest=discovered_manifest,
        vantage=vantage,
        issuer=issuer,
    )
    signed_claims, token = sign_receipt(claims, issuer=issuer, **kcfg)
    _, active_kid, _, _ = load_signing_bundle(**kcfg)
    save_receipt(services["db"](), signed_claims, token, active_kid)
    summary_text, dual = format_dual_response(signed_claims, token, issuer=issuer)
    return signed_claims, token, summary_text, dual


def register_routes(bp, services: dict) -> None:
    base = services["base"]

    @bp.get("/.well-known/jwks.json")
    def well_known_jwks():
        doc = jwks_document(**key_config_from_app(services))
        resp = Response(
            json.dumps(doc, separators=(",", ":")),
            status=200,
            mimetype="application/jwk-set+json",
        )
        resp.headers["Cache-Control"] = "public, max-age=3600"
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    @bp.get("/.well-known/qa-receipt-configuration")
    def well_known_receipt_configuration():
        resp = jsonify(discovery_configuration(base()))
        resp.headers["Cache-Control"] = "public, max-age=3600"
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    @bp.get(POLICY_PATH)
    def policy_qa_pqc_transport_v1():
        wants_json = (
            request.args.get("format") == "json"
            or (
                request.accept_mimetypes.accept_json
                and not request.accept_mimetypes.accept_html
            )
        )
        if wants_json:
            resp = jsonify(policy_document(base()))
        else:
            resp = Response(_policy_html(base()), status=200, mimetype="text/html; charset=utf-8")
        resp.headers["Cache-Control"] = "public, max-age=86400"
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    @bp.post("/api/v1/scan")
    def api_v1_scan_receipt():
        import adoption
        import quantum_vuln_scanner
        import search_indexing

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="invalid_request", message="Expected a JSON object"), 400
        raw_host = body.get("host") if body.get("host") is not None else body.get("domain")
        raw_port = body.get("port", 443)
        endpoint_type = body.get("endpoint_type")
        discovered_manifest = body.get("discovered_manifest")
        if endpoint_type is not None and (not isinstance(endpoint_type, str) or len(endpoint_type) > 64):
            return jsonify(error="invalid_endpoint_type"), 400
        if discovered_manifest is not None and (not isinstance(discovered_manifest, str) or len(discovered_manifest) > 256):
            return jsonify(error="invalid_discovered_manifest"), 400
        if isinstance(raw_port, bool) or not isinstance(raw_port, int):
            return jsonify(error="invalid_port", message="port must be an integer between 1 and 65535"), 400
        try:
            clean_host, clean_port, sub = parse_host_port_input(str(raw_host or ""), raw_port)
        except ValueError as exc:
            return jsonify(error="invalid_target", message=str(exc)), 400

        conn = services["db"]()
        # Reject blocklisted / opted-out domains (Section 9)
        try:
            ipaddress.ip_address(clean_host)
            is_ip = True
        except ValueError:
            is_ip = False
        if not is_ip and (search_indexing.is_excluded(clean_host) or adoption.opted_out(clean_host, adoption.load_optout(conn=conn))):
            return jsonify(error="domain_blocked", message="Receipts are not issued for blocked or opted-out domains"), 403

        # Per-target hourly cap (Section 9)
        per_target_cap = int(current_app.config.get("RECEIPTS_PER_TARGET_PER_HOUR", 20))
        init(conn)
        hour_ago = int(time.time()) - 3600
        recent_for_sub = conn.execute(
            "SELECT COUNT(*) FROM receipts WHERE sub = ? AND iat >= ?",
            (sub, hour_ago),
        ).fetchone()[0]
        if recent_for_sub >= per_target_cap:
            return jsonify(error="target_rate_limited", message="Hourly scan limit reached for this target", retry_after_seconds=3600), 429

        # Execute scan using standard service path for port 443 hostnames, or target scanner otherwise
        try:
            if not is_ip and clean_port == 443 and services.get("scan"):
                scan_id, raw = services["scan"](clean_host, "api")
            else:
                # Enforce client/global rate limit via claim helper if exposed
                if services.get("claim_attempt"):
                    services["claim_attempt"]()
                scan_id = f"scn_{secrets.token_hex(8)}"
                target_scanner = services.get("scan_target") or quantum_vuln_scanner.scan_target
                raw = target_scanner(clean_host, clean_port)
        except HTTPException as exc:
            if exc.code == 429:
                return jsonify(error="rate_limited", retry_after_seconds=3600), 429
            raise
        except quantum_vuln_scanner.ScanError as exc:
            if exc.code in ("private_address", "invalid_domain", "invalid_port"):
                return jsonify(error=exc.code, message=str(exc)), 400
            if exc.code in ("tls_failure", "connect_failure"):
                # Section 3 & 7: issue a signed receipt even on handshake failure (HANDSHAKE_FAILED)
                _, _, _, dual = issue_and_store_failed_receipt(
                    services,
                    clean_host,
                    clean_port,
                    endpoint_type=endpoint_type,
                    discovered_manifest=discovered_manifest,
                )
                return jsonify(dual), 200
            return jsonify(error=exc.code, message=str(exc)), 400

        _, _, _, dual = issue_and_store_receipt(
            services,
            raw,
            scan_id=scan_id,
            endpoint_type=endpoint_type,
            discovered_manifest=discovered_manifest,
        )
        return jsonify(dual), 200

    @bp.get("/api/v1/receipts/<jti>")
    def api_v1_get_receipt(jti):
        row = get_receipt_by_jti(services["db"](), jti)
        if not row:
            return jsonify(error="receipt_not_found", message="Unknown receipt ID"), 404
        now_ts = int(time.time())
        if row["exp"] <= now_ts:
            return jsonify(
                error="RECEIPT_EXPIRED",
                message="Receipt expired. Request a new scan via POST /api/v1/scan or scan_tls.",
                jti=row["jti"],
                sub=row["sub"],
                expired_at=_rfc3339_utc(row["exp"]),
            ), 410
        _, dual = format_dual_response(row["receipt"], row["jws"], issuer=base())
        resp = jsonify(dual)
        remaining = max(0, row["exp"] - now_ts)
        resp.headers["Cache-Control"] = f"public, max-age={min(300, remaining)}"
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp
