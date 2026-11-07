# quantum_vuln_scanner.py
# فحص جاهزية خادم HTTPS لعصر الحوسبة الكمومية (Post-Quantum TLS readiness).
#
# يجري الفحص اتصالين عاديين بالمنفذ 443 كما يفعل أي متصفح:
#   1) ClientHello من TLS 1.3 يعرض تبادل المفاتيح الهجين X25519MLKEM768 (الذي تستخدمه
#      Chrome وFirefox)، ثم يقرأ ServerHello ليعرف المجموعة التي اختارها الخادم ويغلق الاتصال.
#   2) مصافحة TLS كاملة عبر وحدة ssl لقراءة الشهادة والتحقق منها.
# لا تُرسل أي بيانات تطبيق ولا تُجرَّب أي ثغرة.
#
# الاستخدام: python quantum_vuln_scanner.py example.com [--json]
import argparse
import datetime as dt
import ipaddress
import json
import re
import secrets
import socket
import ssl
import sys
import time
from urllib.parse import urlsplit

import certifi
from cryptography import x509
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed448, ed25519, rsa, x25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.x509.oid import ExtensionOID, NameOID

SCANNER_VERSION = "2.0"
PORT = 443
TIMEOUT = 8.0

X25519MLKEM768 = 0x11EC
X25519 = 0x001D
GROUP_NAMES = {
    0x0017: "secp256r1", 0x0018: "secp384r1", 0x0019: "secp521r1",
    0x001D: "x25519", 0x001E: "x448",
    0x0100: "ffdhe2048", 0x0101: "ffdhe3072", 0x0102: "ffdhe4096",
    0x0200: "MLKEM512", 0x0201: "MLKEM768", 0x0202: "MLKEM1024",
    0x11EB: "SecP256r1MLKEM768", 0x11EC: "X25519MLKEM768", 0x11ED: "SecP384r1MLKEM1024",
    0x6399: "X25519Kyber768Draft00",
}
PQ_GROUPS = {0x0200, 0x0201, 0x0202, 0x11EB, 0x11EC, 0x11ED, 0x6399}
TLS_VERSIONS = {0x0304: "TLSv1.3", 0x0303: "TLSv1.2", 0x0302: "TLSv1.1", 0x0301: "TLSv1.0", 0x0300: "SSLv3"}

CIPHER_NAMES = {
    0x1301: "TLS_AES_128_GCM_SHA256", 0x1302: "TLS_AES_256_GCM_SHA384",
    0x1303: "TLS_CHACHA20_POLY1305_SHA256",
    0xC02B: "ECDHE-ECDSA-AES128-GCM-SHA256", 0xC02F: "ECDHE-RSA-AES128-GCM-SHA256",
    0xC02C: "ECDHE-ECDSA-AES256-GCM-SHA384", 0xC030: "ECDHE-RSA-AES256-GCM-SHA384",
    0xCCA9: "ECDHE-ECDSA-CHACHA20-POLY1305", 0xCCA8: "ECDHE-RSA-CHACHA20-POLY1305",
    0xC013: "ECDHE-RSA-AES128-SHA", 0xC014: "ECDHE-RSA-AES256-SHA",
    0x009C: "AES128-GCM-SHA256", 0x009D: "AES256-GCM-SHA384",
    0x002F: "AES128-SHA", 0x0035: "AES256-SHA",
}
ECDHE_SUITES = {0xC02B, 0xC02F, 0xC02C, 0xC030, 0xCCA9, 0xCCA8, 0xC013, 0xC014}
RSA_KX_SUITES = {0x009C, 0x009D, 0x002F, 0x0035}
CIPHER_SUITES = [0x1301, 0x1302, 0x1303, *sorted(ECDHE_SUITES), *sorted(RSA_KX_SUITES)]
SIGNATURE_ALGORITHMS = [0x0403, 0x0804, 0x0401, 0x0503, 0x0805, 0x0501, 0x0806, 0x0601, 0x0807, 0x0808, 0x0201, 0x0203]

HRR_RANDOM = bytes.fromhex("CF21AD74E59A6111BE1D8C021E65B891C2A211167ABB8C5E079E09E2C8A8339C")
ALERTS = {
    0: "close_notify", 10: "unexpected_message", 20: "bad_record_mac", 40: "handshake_failure",
    42: "bad_certificate", 47: "illegal_parameter", 50: "decode_error", 70: "protocol_version",
    71: "insufficient_security", 80: "internal_error", 86: "inappropriate_fallback",
    109: "missing_extension", 110: "unsupported_extension", 112: "unrecognized_name",
    120: "no_application_protocol",
}
CLASSICAL_KEY_ALGORITHMS = ("RSA", "ECDSA", "Ed25519", "Ed448", "DSA")

_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


class ScanError(Exception):
    """خطأ يمنع الفحص: نطاق غير صالح، عنوان داخلي، تعذّر الاتصال..."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class TLSAlert(Exception):
    def __init__(self, description: int):
        super().__init__(f"TLS alert: {ALERTS.get(description, description)}")
        self.description = description


# ---------------------------------------------------------------- الإدخال والشبكة

def normalize_domain(raw: str) -> str:
    if not isinstance(raw, str):
        raise ScanError("invalid_domain", "enter a domain name or an HTTP(S) URL")
    value = raw.strip()
    if not value or len(value) > 4096 or "\\" in value or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
        raise ScanError("invalid_domain", "invalid domain name")
    try:
        parsed = urlsplit(value if "://" in value else "//" + value)
        if parsed.scheme not in ("", "http", "https") or parsed.username is not None or parsed.password is not None:
            raise ValueError("unsupported scheme or credentials")
        if parsed.port == 0:
            raise ValueError("invalid port")
        # A URL may be pasted, but this service always measures HTTPS on port 443.
        value = (parsed.hostname or "").lower().rstrip(".")
    except ValueError as exc:
        raise ScanError("invalid_domain", "enter a domain name or an HTTP(S) URL without credentials") from exc
    try:
        value = value.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ScanError("invalid_domain", "invalid domain name") from exc
    labels = value.split(".")
    if len(value) > 253 or len(labels) < 2 or not all(_LABEL.match(label) for label in labels):
        raise ScanError("invalid_domain", "invalid domain name")
    if labels[-1].isdigit():
        raise ScanError("invalid_domain", "enter a domain name, not an IP address")
    return value


def resolve_public_ip(host: str) -> str:
    try:
        infos = socket.getaddrinfo(host, PORT, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ScanError("dns_failure", f"could not resolve {host}") from exc
    ipv4, ipv6 = [], []
    for family, _, _, _, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.version == 6 and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        # نرفض النطاق كله إذا أشار أي سجل إلى عنوان داخلي أو محجوز (حماية من SSRF).
        if not ip.is_global or ip.is_multicast:
            raise ScanError("private_address", f"{host} points to a non-public address")
        (ipv4 if ip.version == 4 else ipv6).append(str(ip))
    if not ipv4 and not ipv6:
        raise ScanError("dns_failure", f"no address for {host}")
    return (ipv4 or ipv6)[0]


def _connect(ip: str, timeout: float) -> socket.socket:
    try:
        return socket.create_connection((ip, PORT), timeout=timeout)
    except OSError as exc:
        raise ScanError("connect_failure", f"could not connect to port {PORT}: {exc}") from exc


# ---------------------------------------------------------------- بناء ClientHello

def _u16(n: int) -> bytes:
    return n.to_bytes(2, "big")


def _vec8(data: bytes) -> bytes:
    return len(data).to_bytes(1, "big") + data


def _vec16(data: bytes) -> bytes:
    return _u16(len(data)) + data


def _ext(ext_type: int, data: bytes) -> bytes:
    return _u16(ext_type) + _vec16(data)


def mlkem768_encapsulation_key() -> bytes:
    """مفتاح تغليف ML-KEM-768 صالح الصيغة (FIPS 203): 3x256 معاملاً < q مرمّزة 12 بت + بذرة 32 بايت.

    يكفي لكي يقبل الخادم ClientHello؛ الفحص يُغلق الاتصال بعد ServerHello ولا يحتاج المفتاح السري.
    """
    coefficients = [secrets.randbelow(3329) for _ in range(768)]
    packed = bytearray()
    for a, b in zip(coefficients[0::2], coefficients[1::2]):
        packed += bytes((a & 0xFF, (a >> 8) | ((b & 0x0F) << 4), b >> 4))
    return bytes(packed) + secrets.token_bytes(32)


def build_client_hello(host: str, groups: list, key_shares: list) -> bytes:
    extensions = b"".join([
        _ext(0x0000, _vec16(b"\x00" + _vec16(host.encode("ascii")))),  # server_name
        _ext(0x000A, _vec16(b"".join(_u16(g) for g in groups))),      # supported_groups
        _ext(0x000B, _vec8(b"\x00")),                                  # ec_point_formats
        _ext(0x000D, _vec16(b"".join(_u16(s) for s in SIGNATURE_ALGORITHMS))),
        _ext(0x0010, _vec16(_vec8(b"http/1.1"))),                      # ALPN
        _ext(0x0017, b""),                                             # extended_master_secret
        _ext(0x002B, _vec8(_u16(0x0304) + _u16(0x0303))),              # supported_versions
        _ext(0x002D, _vec8(b"\x01")),                                  # psk_key_exchange_modes
        _ext(0x0033, _vec16(b"".join(_u16(g) + _vec16(k) for g, k in key_shares))),
        _ext(0xFF01, b"\x00"),                                         # renegotiation_info
    ])
    body = (
        _u16(0x0303) + secrets.token_bytes(32) + _vec8(secrets.token_bytes(32))
        + _vec16(b"".join(_u16(c) for c in CIPHER_SUITES)) + _vec8(b"\x00") + _vec16(extensions)
    )
    handshake = b"\x01" + len(body).to_bytes(3, "big") + body
    return b"\x16\x03\x01" + _u16(len(handshake)) + handshake


# ---------------------------------------------------------------- قراءة رد الخادم

class _HandshakeReader:
    def __init__(self, sock, limit: int = 65536, timeout: float = TIMEOUT):
        self.sock = sock
        self.buffer = b""
        self.received = 0
        self.limit = limit
        self.deadline = time.monotonic() + timeout

    def _recv_exact(self, n: int) -> bytes:
        if n < 0 or self.received + n > self.limit:
            raise ValueError("response larger than expected")
        data = b""
        while len(data) < n:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('TLS probe deadline exceeded')
            if hasattr(self.sock, 'settimeout'):
                self.sock.settimeout(remaining)
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("server closed the connection")
            data += chunk
        self.received += n
        if self.received > self.limit:
            raise ValueError("response larger than expected")
        return data

    def next_message(self):
        while True:
            if len(self.buffer) >= 4:
                length = int.from_bytes(self.buffer[1:4], "big")
                if length + 4 > self.limit:
                    raise ValueError("handshake larger than expected")
                if len(self.buffer) >= 4 + length:
                    msg_type, body = self.buffer[0], self.buffer[4:4 + length]
                    self.buffer = self.buffer[4 + length:]
                    return msg_type, body
            header = self._recv_exact(5)
            content_type, length = header[0], int.from_bytes(header[3:5], "big")
            payload = self._recv_exact(length)
            if content_type == 0x15:
                raise TLSAlert(payload[1] if len(payload) > 1 else 0)
            if content_type == 0x14:  # ChangeCipherSpec للتوافق
                continue
            if content_type != 0x16:
                raise ValueError(f"unexpected record type {content_type}")
            self.buffer += payload


def parse_server_hello(body: bytes) -> dict:
    if len(body) < 38:
        raise ValueError("truncated ServerHello")
    legacy_version = int.from_bytes(body[0:2], "big")
    random = body[2:34]
    if body[34] > 32:
        raise ValueError("invalid ServerHello session ID")
    pos = 35 + body[34]
    if pos + 3 > len(body):
        raise ValueError("truncated ServerHello cipher")
    cipher = int.from_bytes(body[pos:pos + 2], "big")
    if body[pos + 2] != 0:
        raise ValueError("unexpected TLS compression")
    pos += 3
    extensions = {}
    if pos < len(body):
        if pos + 2 > len(body):
            raise ValueError("truncated ServerHello extension length")
        end = pos + 2 + int.from_bytes(body[pos:pos + 2], "big")
        if end != len(body):
            raise ValueError("invalid ServerHello extension boundary")
        pos += 2
        while pos + 4 <= end:
            ext_type = int.from_bytes(body[pos:pos + 2], "big")
            ext_len = int.from_bytes(body[pos + 2:pos + 4], "big")
            if pos + 4 + ext_len > end or ext_type in extensions:
                raise ValueError("invalid or duplicate ServerHello extension")
            extensions[ext_type] = body[pos + 4:pos + 4 + ext_len]
            pos += 4 + ext_len
        if pos != end:
            raise ValueError("truncated ServerHello extension header")
    version = legacy_version
    if 0x002B in extensions:
        if len(extensions[0x002B]) != 2:
            raise ValueError("invalid supported_versions extension")
        version = int.from_bytes(extensions[0x002B][:2], "big")
    group = None
    if 0x0033 in extensions:
        share = extensions[0x0033]
        if random == HRR_RANDOM:
            if len(share) != 2 or version != 0x0304:
                raise ValueError("invalid HelloRetryRequest key share")
        elif len(share) < 5 or int.from_bytes(share[2:4], "big") != len(share) - 4:
            raise ValueError("truncated ServerHello key share")
        group = int.from_bytes(share[:2], "big")
        expected = {X25519: 32, X25519MLKEM768: 1120}.get(group)
        if random != HRR_RANDOM and expected is not None and len(share) - 4 != expected:
            raise ValueError("invalid key share length")
    return {"hrr": random == HRR_RANDOM, "version": version, "cipher": cipher, "group": group}


def _tls12_named_group(reader: _HandshakeReader):
    for _ in range(8):
        msg_type, body = reader.next_message()
        if msg_type == 12:  # ServerKeyExchange
            if body[:1] == b"\x03":  # named_curve
                return int.from_bytes(body[1:3], "big")
            return None
        if msg_type == 14:  # ServerHelloDone
            return None
    return None


def read_server_response(sock, timeout=TIMEOUT) -> dict:
    reader = _HandshakeReader(sock, timeout=timeout)
    msg_type, body = reader.next_message()
    if msg_type != 2:
        raise ValueError(f"expected ServerHello, got handshake type {msg_type}")
    hello = parse_server_hello(body)
    if hello["version"] >= 0x0304 or hello["hrr"]:
        hello["kx"] = "TLS1.3"
    elif hello["cipher"] in ECDHE_SUITES:
        hello["kx"] = "ECDHE"
        hello["group"] = _tls12_named_group(reader)
    elif hello["cipher"] in RSA_KX_SUITES:
        hello["kx"] = "RSA"
    else:
        hello["kx"] = "unknown"
    return hello


# ---------------------------------------------------------------- المجسّات

def _hello_attempt(ip: str, host: str, offer_pq: bool, timeout: float) -> dict:
    x25519_public = x25519.X25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    if offer_pq:
        groups = [X25519MLKEM768, X25519, 0x0017, 0x0018, 0x11EB, 0x11ED]
        shares = [(X25519MLKEM768, mlkem768_encapsulation_key() + x25519_public), (X25519, x25519_public)]
    else:
        groups = [X25519, 0x0017, 0x0018]
        shares = [(X25519, x25519_public)]
    with _connect(ip, timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(build_client_hello(host, groups, shares))
        hello = read_server_response(sock, timeout=timeout)
        if hello['cipher'] not in CIPHER_SUITES or (hello['group'] is not None and hello['group'] not in groups):
            raise ValueError('server selected an unoffered TLS parameter')
        if hello['version'] not in (0x0303, 0x0304):
            raise ValueError('server selected an unoffered TLS version')
        return hello


def probe_key_exchange(ip: str, host: str, timeout: float = TIMEOUT) -> dict:
    result = {"pq_hello_ok": None, "pq_hello_error": None, "error": None}
    for offer_pq in (True, False):
        try:
            hello = _hello_attempt(ip, host, offer_pq, timeout)
        except (TLSAlert, ConnectionError, ValueError, OSError, ScanError) as exc:
            if offer_pq:
                result["pq_hello_ok"] = False
                result["pq_hello_error"] = str(exc)
                continue
            result["error"] = str(exc)
            return result
        if offer_pq:
            result["pq_hello_ok"] = True
        group = hello["group"]
        result.update({
            "version": TLS_VERSIONS.get(hello["version"], hex(hello["version"])),
            "cipher": CIPHER_NAMES.get(hello["cipher"], hex(hello["cipher"])),
            "group": GROUP_NAMES.get(group, hex(group)) if group is not None else None,
            "pq": group in PQ_GROUPS and not hello["hrr"],
            "hrr": hello["hrr"],
            "negotiation_observed": not hello["hrr"] and group is not None,
            "kx": hello["kx"],
        })
        return result
    return result


def _name_attr(name: x509.Name, oid) -> str:
    values = name.get_attributes_for_oid(oid)
    return str(values[0].value) if values else ""


def describe_certificate(cert: x509.Certificate) -> dict:
    try:
        key = cert.public_key()
    except (UnsupportedAlgorithm, ValueError):
        key = None
    if isinstance(key, rsa.RSAPublicKey):
        algorithm, bits = "RSA", key.key_size
    elif isinstance(key, ec.EllipticCurvePublicKey):
        algorithm, bits = "ECDSA", key.curve.key_size
    elif isinstance(key, ed25519.Ed25519PublicKey):
        algorithm, bits = "Ed25519", 256
    elif isinstance(key, ed448.Ed448PublicKey):
        algorithm, bits = "Ed448", 456
    elif isinstance(key, dsa.DSAPublicKey):
        algorithm, bits = "DSA", key.key_size
    else:
        algorithm, bits = "unknown", None
    signature_oid = cert.signature_algorithm_oid
    not_after = cert.not_valid_after_utc
    try:
        sans = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
        dns_names = sans.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        dns_names = []
    return {
        "key_algorithm": algorithm,
        "key_bits": bits,
        "curve": key.curve.name if isinstance(key, ec.EllipticCurvePublicKey) else None,
        "signature_algorithm": getattr(signature_oid, "_name", signature_oid.dotted_string),
        "subject": _name_attr(cert.subject, NameOID.COMMON_NAME),
        "issuer": _name_attr(cert.issuer, NameOID.ORGANIZATION_NAME) or _name_attr(cert.issuer, NameOID.COMMON_NAME),
        "not_after": not_after.isoformat(),
        "days_left": (not_after - dt.datetime.now(dt.timezone.utc)).days,
        "san_count": len(dns_names),
        "sans": dns_names[:10],
    }


def _ssl_handshake(ip: str, host: str, context: ssl.SSLContext, timeout: float):
    with _connect(ip, timeout) as raw:
        with context.wrap_socket(raw, server_hostname=host) as tls:
            return tls.getpeercert(binary_form=True), tls.version(), tls.cipher()


def probe_certificate(ip: str, host: str, timeout: float = TIMEOUT) -> dict:
    info = {"verified": True, "verify_error": None}
    try:
        try:
            # certifi: نفس جذور Mozilla على Windows وLinux، فلا تختلف النتيجة باختلاف الجهاز.
            verified = ssl.create_default_context(cafile=certifi.where())
            der, version, cipher = _ssl_handshake(ip, host, verified, timeout)
        except ssl.SSLCertVerificationError as exc:
            info.update(verified=False, verify_error=exc.verify_message or str(exc))
            unverified = ssl.create_default_context()
            unverified.check_hostname = False
            unverified.verify_mode = ssl.CERT_NONE
            der, version, cipher = _ssl_handshake(ip, host, unverified, timeout)
    except (ssl.SSLError, OSError) as exc:
        raise ScanError("tls_failure", f"TLS handshake failed: {exc}") from exc
    try:
        info.update(describe_certificate(x509.load_der_x509_certificate(der)))
    except (ValueError, UnsupportedAlgorithm) as exc:
        raise ScanError('tls_failure', 'could not parse the server certificate') from exc
    info["negotiated_version"] = version
    info["negotiated_cipher"] = cipher[0] if cipher else None
    return info


# ---------------------------------------------------------------- التقييم

def assess(kx: dict, cert: dict) -> dict:
    findings = []

    def add(code, status, **params):
        findings.append({"code": code, "status": status, "params": params})

    version = kx.get("version") or cert.get("negotiated_version")
    if kx.get("error"):
        add("KX_PROBE_FAILED", "warning", error=kx["error"])
    elif kx.get("hrr"):
        add("KX_RETRY_REQUESTED", "warning", group=kx.get("group") or "?")
    elif kx.get("pq"):
        add("KX_PQ_HYBRID", "ok", group=kx.get("group") or "?")
    elif version == "TLSv1.3":
        add("KX_CLASSICAL", "warning", group=kx.get("group") or "?")
    elif version == "TLSv1.2":
        add("TLS12_ONLY", "warning")
        if kx.get("kx") == "RSA":
            add("KX_RSA_STATIC", "critical")
        else:
            add("KX_CLASSICAL", "warning", group=kx.get("group") or "ECDHE")
    else:
        add("TLS_LEGACY", "critical", version=version or "?")
    if kx.get("pq_hello_ok") is False and not kx.get("error"):
        add("KX_PQ_HELLO_REJECTED", "warning", error=kx.get("pq_hello_error") or "")

    if not cert.get("verified"):
        add("CERT_INVALID", "critical", error=cert.get("verify_error") or "")
    elif cert.get("days_left") is not None and cert["days_left"] < 14:
        add("CERT_EXPIRING", "warning", days=cert["days_left"])
    algorithm, bits = cert.get("key_algorithm"), cert.get("key_bits")
    if algorithm == "RSA" and bits and bits < 2048:
        add("CERT_WEAK_RSA", "critical", bits=bits)
    if algorithm in CLASSICAL_KEY_ALGORITHMS:
        add("CERT_SHOR_VULNERABLE", "info", algorithm=f"{algorithm}-{bits}" if bits else algorithm)
    elif algorithm == "unknown":
        add("CERT_UNKNOWN_ALGORITHM", "info")

    if any(f["status"] == "critical" for f in findings):
        grade = "F"
    elif kx.get("pq") and not kx.get("hrr") and not kx.get("error") and version == "TLSv1.3":
        grade = "A"
    elif version == "TLSv1.3":
        grade = "B"
    elif version == "TLSv1.2":
        grade = "C"
    else:
        grade = "F"
    return {"grade": grade, "findings": findings}


def scan(raw_domain: str, timeout: float = TIMEOUT) -> dict:
    domain = normalize_domain(raw_domain)
    ip = resolve_public_ip(domain)
    kx = probe_key_exchange(ip, domain, timeout)
    cert = probe_certificate(ip, domain, timeout)
    return {
        "domain": domain,
        "ip": ip,
        "port": PORT,
        "scanned_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scanner_version": SCANNER_VERSION,
        "key_exchange": kx,
        "certificate": cert,
        **assess(kx, cert),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Post-quantum TLS readiness scan")
    parser.add_argument("domain")
    parser.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = parser.parse_args(argv)
    try:
        result = scan(args.domain)
    except ScanError as exc:
        print(f"[{exc.code}] {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    kx, cert = result["key_exchange"], result["certificate"]
    print(f"Host: {result['domain']} ({result['ip']})")
    print(f"  Grade: {result['grade']}")
    print(f"  TLS: {kx.get('version') or cert.get('negotiated_version')}, key exchange: {kx.get('group')}"
          f"{' (post-quantum hybrid)' if kx.get('pq') else ''}")
    print(f"  Certificate: {cert['key_algorithm']}-{cert['key_bits']}, {cert['signature_algorithm']},"
          f" expires in {cert['days_left']} days, verified={cert['verified']}")
    for finding in result["findings"]:
        print(f"  [{finding['status'].upper()}] {finding['code']} {finding['params'] or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
