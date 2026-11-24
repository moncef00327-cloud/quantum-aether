#!/usr/bin/env python3
"""Quantum Aether v1 Signed TLS Receipt verifier for CI/CD and agents (Section 8).

Verifies an Ed25519 compact JWS receipt offline against the pinned issuer and JWKS URL,
enforcing every step of Section 8:
  1. Split compact JWS into 3 parts; parse unverified header.
  2. Reject wrong `typ`, unsupported `alg` (accepts EdDSA and Ed25519), or forbidden `jku`/`x5u`/`jwk`.
  3. Fetch JWKS from pinned URL (1h cache; refresh once on unknown `kid`, then reject);
     verify JWK is `kty=OKP` and `crv=Ed25519`.
  4. Verify Ed25519 signature.
  5. Verify `iss`, `exp`, `nbf` (60s leeway), and non-empty `jti`.
  6. Normalize expected target (`host:port`) and verify `sub` matches.
  7. Verify `policy_id` + `policy_version` are accepted and `result == "pass"`.
  8. Optional (`--check-live-spki`): connect live to host:port and compare `spki_sha256`.
  9. Decide strictly from decoded JWS claims, ignoring any accompanying unverified JSON.

Exit code: 0 on PASS, 1 on FAIL.
"""
import argparse
import base64
import hashlib
import ipaddress
import json
from pathlib import Path
import socket
import ssl
import sys
import time
import urllib.request

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

try:
    import idna as _idna
except ImportError:
    _idna = None

PINNED_ISSUER = "https://ather-quantum.com"
PINNED_JWKS_URI = f"{PINNED_ISSUER}/.well-known/jwks.json"
RECEIPT_TYP = "qa-tls-receipt+jwt"
ACCEPTED_ALGS = frozenset({"EdDSA", "Ed25519"})
FORBIDDEN_HEADERS = frozenset({"jku", "x5u", "jwk"})
ACCEPTED_POLICIES = frozenset({("qa-pqc-transport", "1.0")})
LEEWAY_S = 60
JWKS_CACHE_TTL_S = 3600


def _b64u_decode(text: str) -> bytes:
    if not isinstance(text, str) or not text:
        raise ValueError("invalid base64url segment")
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def normalize_target(host: str, port: int = 443) -> str:
    if not isinstance(host, str):
        raise ValueError("invalid target")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
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
        if _idna is not None:
            ascii_host = _idna.encode(h, uts46=True).decode("ascii")
        else:
            ascii_host = h.encode("idna").decode("ascii")
        ascii_host = ascii_host.lower().rstrip(".")
        if not ascii_host or len(ascii_host) > 253 or ".." in ascii_host:
            raise ValueError("invalid target")
        return f"{ascii_host}:{port}"
    return f"[{ip.compressed}]:{port}" if ip.version == 6 else f"{ip}:{port}"


class JWKSCache:
    def __init__(self, jwks_uri: str = PINNED_JWKS_URI, ttl: int = JWKS_CACHE_TTL_S,
                 fetcher=None, jwks_file: str | None = None):
        self.jwks_uri = jwks_uri
        self.ttl = ttl
        self.fetcher = fetcher
        self.jwks_file = jwks_file
        self._doc = None
        self._fetched_at = 0.0

    def _fetch(self) -> dict:
        if self.jwks_file:
            return json.loads(Path(self.jwks_file).read_text(encoding="utf-8"))
        if self.fetcher is not None:
            return self.fetcher(self.jwks_uri)
        req = urllib.request.Request(self.jwks_uri, headers={"Accept": "application/jwk-set+json, application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def get_key(self, kid: str) -> Ed25519PublicKey:
        now = time.monotonic()
        refreshed = False
        if self._doc is None or (now - self._fetched_at) >= self.ttl:
            self._doc = self._fetch()
            self._fetched_at = now
            refreshed = True

        jwk = self._find(kid)
        if jwk is None and not refreshed:
            # Step 3: unknown kid -> refresh once, then reject
            self._doc = self._fetch()
            self._fetched_at = time.monotonic()
            jwk = self._find(kid)
        if jwk is None:
            raise ValueError(f"unknown kid: {kid}")
        if jwk.get("kty") != "OKP" or jwk.get("crv") != "Ed25519":
            raise ValueError("JWK is not OKP Ed25519")
        raw = _b64u_decode(jwk.get("x", ""))
        if len(raw) != 32:
            raise ValueError("invalid Ed25519 public key")
        return Ed25519PublicKey.from_public_bytes(raw)

    def _find(self, kid: str):
        for k in (self._doc or {}).get("keys") or []:
            if isinstance(k, dict) and k.get("kid") == kid:
                return k
        return None


def fetch_live_spki_sha256(host: str, port: int = 443, timeout: float = 8.0) -> str:
    """Connect over TLS to host:port and compute the live leaf certificate SPKI SHA-256 hex digest."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    cert = x509.load_der_x509_certificate(der)
    spki_der = cert.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
    return hashlib.sha256(spki_der).hexdigest()


def verify_receipt(
    token: str,
    expected_sub: str,
    *,
    jwks_cache: JWKSCache | None = None,
    issuer: str = PINNED_ISSUER,
    accepted_policies=ACCEPTED_POLICIES,
    leeway: int = LEEWAY_S,
    now: int | None = None,
    check_live_spki: bool = False,
) -> dict:
    # Step 1: split JWS and parse unverified header
    if not isinstance(token, str) or token.count(".") != 2:
        raise ValueError("malformed JWS")
    h_b64, p_b64, s_b64 = token.split(".")
    try:
        header = json.loads(_b64u_decode(h_b64).decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid JWS header: {exc}") from exc
    if not isinstance(header, dict):
        raise ValueError("header must be a JSON object")

    # Step 2: validate typ, alg, forbidden headers, kid
    if header.get("typ") != RECEIPT_TYP:
        raise ValueError(f"wrong typ: {header.get('typ')!r}")
    if header.get("alg") not in ACCEPTED_ALGS:
        raise ValueError(f"unsupported alg: {header.get('alg')!r}")
    if FORBIDDEN_HEADERS & header.keys():
        raise ValueError("forbidden header parameter present")
    kid = header.get("kid")
    if not isinstance(kid, str) or not kid:
        raise ValueError("missing kid")

    # Step 3: get pinned OKP Ed25519 key by kid
    cache = jwks_cache or JWKSCache()
    pub_key = cache.get_key(kid)

    # Step 4: verify Ed25519 signature
    try:
        sig = _b64u_decode(s_b64)
        if len(sig) != 64:
            raise ValueError("invalid signature length")
        pub_key.verify(sig, f"{h_b64}.{p_b64}".encode("ascii"))
    except InvalidSignature as exc:
        raise ValueError("invalid JWS signature") from exc

    # Step 9: decode payload strictly from JWS
    try:
        claims = json.loads(_b64u_decode(p_b64).decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"invalid JWS payload: {exc}") from exc
    if not isinstance(claims, dict):
        raise ValueError("payload must be a JSON object")

    # Step 5: iss, exp, nbf (with 60s leeway), jti
    for req in ("iss", "sub", "iat", "nbf", "exp", "jti"):
        if req not in claims or claims[req] is None:
            raise ValueError(f"missing required claim: {req}")
    if claims["iss"] != issuer.rstrip("/"):
        raise ValueError(f"wrong issuer: {claims['iss']!r}")
    if not isinstance(claims["jti"], str) or not claims["jti"].strip():
        raise ValueError("empty jti")
    ts = int(time.time()) if now is None else int(now)
    if ts + leeway < int(claims["nbf"]):
        raise ValueError("receipt not yet valid (nbf)")
    if ts - leeway >= int(claims["exp"]):
        raise ValueError("receipt expired (exp)")

    # Step 6: match sub
    if claims["sub"] != expected_sub:
        raise ValueError(f"receipt is for another host: got {claims['sub']!r}, expected {expected_sub!r}")

    # Step 7: policy & verdict
    v = claims.get("policy_verdict")
    if not isinstance(v, dict):
        raise ValueError("missing policy_verdict")
    if (v.get("policy_id"), v.get("policy_version")) not in set(accepted_policies):
        raise ValueError(f"policy not accepted: {v.get('policy_id')} {v.get('policy_version')}")
    if v.get("result") != "pass":
        raise ValueError(f"policy failed: {v.get('fail_reasons') or []}")

    # Step 8 (optional): live SPKI comparison
    if check_live_spki:
        expected_spki = ((claims.get("tls_audit") or {}).get("cert") or {}).get("spki_sha256")
        if not expected_spki:
            raise ValueError("receipt does not contain spki_sha256")
        target = claims.get("target") or {}
        live_spki = fetch_live_spki_sha256(target["host"], int(target.get("port", 443)))
        if live_spki.lower() != str(expected_spki).lower():
            raise ValueError(f"live SPKI mismatch: receipt={expected_spki}, live={live_spki}")

    return claims


def _extract_token(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("{"):
        doc = json.loads(text)
        # Step 9: extract ONLY signed_receipt_jws, never trust accompanying `receipt`
        token = doc.get("signed_receipt_jws") or (doc.get("structuredContent") or {}).get("signed_receipt_jws")
        if not token:
            raise ValueError("JSON input does not contain signed_receipt_jws")
        return str(token).strip()
    return text


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify a Quantum Aether v1 signed TLS receipt")
    parser.add_argument("--host", required=True, help="Expected target hostname or IP")
    parser.add_argument("--port", type=int, default=443, help="Expected target port (default: 443)")
    parser.add_argument("--token", help="Compact JWS string (otherwise reads --file or stdin)")
    parser.add_argument("--file", help="File containing compact JWS or API JSON response")
    parser.add_argument("--issuer", default=PINNED_ISSUER, help=f"Pinned issuer (default: {PINNED_ISSUER})")
    parser.add_argument("--jwks-uri", default=None, help="Pinned JWKS URI (default: <issuer>/.well-known/jwks.json)")
    parser.add_argument("--jwks-file", default=None, help="Local JWKS JSON file for offline verification")
    parser.add_argument("--check-live-spki", action="store_true", help="Compare spki_sha256 with live TLS handshake")
    parser.add_argument("--json", action="store_true", help="Print verified claims JSON on success")
    args = parser.parse_args(argv)

    try:
        expected_sub = normalize_target(args.host, args.port)
        if args.token:
            token = args.token.strip()
        elif args.file:
            token = _extract_token(Path(args.file).read_text(encoding="utf-8"))
        else:
            token = _extract_token(sys.stdin.read())
        jwks_uri = args.jwks_uri or f"{args.issuer.rstrip('/')}/.well-known/jwks.json"
        cache = JWKSCache(jwks_uri=jwks_uri, jwks_file=args.jwks_file)
        claims = verify_receipt(
            token,
            expected_sub,
            jwks_cache=cache,
            issuer=args.issuer,
            check_live_spki=args.check_live_spki,
        )
    except Exception as exc:
        print(f"VERIFY FAILED: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(claims, indent=2, ensure_ascii=False))
    else:
        v = claims["policy_verdict"]
        t = claims["tls_audit"]
        print(
            f"OK: {claims['sub']} PASS ({v['grade']}) under {v['policy_id']} {v['policy_version']} "
            f"[{t['tls_version']}, {t['negotiated_group']}] jti={claims['jti']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
