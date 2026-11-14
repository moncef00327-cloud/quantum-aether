# scan_insights.py
# Free result page extras (2026-11-14): why post-quantum key exchange was not negotiated, the one config line for the
# detected stack (from config_gen, i.e. the verified guides), and a quick check of the usual subdomains
# (www/api/mail/auth/login): DNS, then a TLS handshake on 443 only for names that resolve. Computed once per scan,
# asynchronously after the page loaded, and cached in SQLite so reloading the page never re-probes.
import concurrent.futures as cf
import datetime as dt
import json
import socket
import ssl
import threading

import config_gen
import discovery

COMMON_PREFIXES = ("www", "api", "mail", "auth", "login")
HEADER_TIMEOUT = 3.0
TABS = ("nginx", "apache", "caddy", "haproxy", "cloudflare", "aws-alb", "cloudfront")
_running = threading.BoundedSemaphore(4)  # per gunicorn worker

SCHEMA = """
CREATE TABLE IF NOT EXISTS scan_insights (
    scan_id    TEXT PRIMARY KEY,
    data       TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def init(conn):
    conn.executescript(SCHEMA)


def reason(result):
    """Short code for why the observed connection is (not) post-quantum. Only uses what the scan measured."""
    kx = result.get("key_exchange") or {}
    version = kx.get("version") or (result.get("certificate") or {}).get("negotiated_version")
    if kx.get("pq"):
        return "pq_ok"
    if kx.get("error") and not kx.get("group"):
        return "undetermined"
    if version and "1.3" not in str(version):
        return "tls12"
    if kx.get("pq_hello_ok") is False:
        return "pq_hello_rejected"
    if kx.get("hrr"):
        return "hrr_classical"
    if kx.get("group"):
        return "classical_group"
    return "undetermined"


def detect_stack(server_header):
    s = (server_header or "").lower()
    if not s:
        return None
    for needle, stack in (("cloudflare", "cloudflare"), ("cloudfront", "cloudfront"), ("awselb", "aws-alb"),
                          ("nginx", "nginx"), ("openresty", "nginx"), ("apache", "apache"), ("caddy", "caddy"),
                          ("haproxy", "haproxy")):
        if needle in s:
            return stack
    return None


def fix_line(stack, lang):
    """The configuration line that enables X25519MLKEM768 for one stack, plus its note (from config_gen)."""
    server = config_gen.SERVERS.get(stack)
    if not server:
        return None
    key, variant = next(iter(server["variants"].items()))
    for step in variant["steps"]:
        if step["kind"] != config_gen.S_CONFIG:
            continue
        code = step.get("code") or ""
        line = next((l.strip(" \\") for l in code.splitlines() if "MLKEM" in l or "-PQ-" in l), "") or None
        note = (step.get("note") or {}).get(lang) or (step.get("note") or {}).get("en")
        requires = config_gen.OLD_OPENSSL.get(lang) or config_gen.OLD_OPENSSL["en"] if key == "openssl35" else None
        return {"stack": stack, "name": server["name"], "line": line, "note": note, "requires": requires,
                "guide": server.get("guide")}
    return None


def fix_tabs(lang):
    return [t for t in (fix_line(s, lang) for s in TABS) if t]


def server_header(ip, host, timeout=HEADER_TIMEOUT):
    """HEAD / over TLS on port 443 of the already validated public IP; returns the Server header or None."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((ip, 443), timeout=timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as tls:
                tls.settimeout(timeout)
                tls.sendall(f"HEAD / HTTP/1.1\r\nHost: {host}\r\nUser-Agent: QuantumAether-Scanner\r\n"
                            f"Connection: close\r\n\r\n".encode("ascii"))
                data = b""
                while b"\r\n\r\n" not in data and len(data) < 16384:
                    chunk = tls.recv(4096)
                    if not chunk:
                        break
                    data += chunk
    except (OSError, ssl.SSLError, ValueError, UnicodeError):
        return None
    for line in data.decode("latin-1").split("\r\n")[1:]:
        name, _, value = line.partition(":")
        if name.strip().lower() == "server":
            return value.strip()[:120] or None
    return None


def common_hosts(domain, probe=discovery.probe_host):
    base = discovery.base_domain(domain)
    names = [f"{p}.{base}" for p in COMMON_PREFIXES]
    names = [n for n in names if n != domain]
    out = []
    with cf.ThreadPoolExecutor(max_workers=len(names) or 1) as pool:
        for name, res in zip(names, pool.map(probe, names)):
            out.append(res if res else {"host": name, "status": "none"})
    return out


def compute(result, probe=discovery.probe_host, header=server_header):
    domain = result["domain"]
    raw_server = header(result.get("ip"), domain) if result.get("ip") else None
    hosts = common_hosts(domain, probe)
    return {"server": raw_server, "stack": detect_stack(raw_server), "hosts": hosts,
            "classical": [h["host"] for h in hosts if h.get("status") == "not_pq"],
            "computed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def get(conn, scan_id):
    row = conn.execute("SELECT data FROM scan_insights WHERE scan_id = ?", (scan_id,)).fetchone()
    return json.loads(row[0]) if row else None


def get_or_compute(conn, scan_id, result, probe=discovery.probe_host, header=server_header):
    cached = get(conn, scan_id)
    if cached is not None:
        return cached, "done"
    if not _running.acquire(blocking=False):
        return None, "busy"
    try:
        data = compute(result, probe, header)
    finally:
        _running.release()
    with conn:
        conn.execute("INSERT OR IGNORE INTO scan_insights (scan_id, data, created_at) VALUES (?, ?, ?)",
                     (scan_id, json.dumps(data), data["computed_at"]))
    return data, "done"
