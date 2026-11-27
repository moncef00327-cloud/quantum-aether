#!/usr/bin/env python3
"""Self-describing, zero-dependency CLI for Quantum Aether Post-Quantum TLS API.

Designed for both humans and shell-capable AI agents (Claude Code, Codex, Antigravity, OpenClaw, Hermes):
  python3 tools/qa_cli.py --usage
  python3 tools/qa_cli.py --schema
  python3 tools/qa_cli.py scan cloudflare.com [--port 443]
  python3 tools/qa_cli.py evidence example.com
  python3 tools/qa_cli.py mcp-index [--status classical|pq_hybrid|pq_not_preferred|tls12] [--limit 20]
  python3 tools/qa_cli.py fix nginx|apache|haproxy|caddy|go|cloudflare
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://ather-quantum.com"
UA = "QuantumAetherCLI/2.0 (+https://ather-quantum.com/agents)"

FIX_SNIPPETS = {
    "nginx": (
        "# Nginx (OpenSSL 3.5+ required for X25519MLKEM768)\n"
        "ssl_protocols TLSv1.2 TLSv1.3;\n"
        "ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;\n"
        "ssl_conf_command Groups X25519MLKEM768:X25519:prime256v1;\n"
        "# Put X25519MLKEM768 FIRST so browsers do not downgrade to classical X25519."
    ),
    "apache": (
        "# Apache httpd (OpenSSL 3.5+)\n"
        "SSLProtocol -all +TLSv1.2 +TLSv1.3\n"
        "SSLOpenSSLConfCmd Groups X25519MLKEM768:X25519:prime256v1"
    ),
    "haproxy": (
        "# HAProxy 3.1+ (OpenSSL 3.5+)\n"
        "ssl-default-bind-options ssl-min-ver TLSv1.2\n"
        "ssl-default-bind-curves X25519MLKEM768:X25519:P-256"
    ),
    "caddy": (
        "# Caddy built with Go 1.24+\n"
        "# X25519MLKEM768 is enabled and preferred by default in Go 1.24+ crypto/tls.\n"
        "# Upgrade Caddy to a Go 1.24+ build and re-scan to verify Grade A."
    ),
    "go": (
        "// Go 1.24+ enables X25519MLKEM768 by default in crypto/tls.\n"
        "// Ensure tls.Config.CurvePreferences is unset or places tls.X25519MLKEM768 first."
    ),
    "cloudflare": (
        "# Cloudflare proxies negotiate X25519MLKEM768 with browsers by default.\n"
        "# Enable orange-cloud proxying + TLS 1.3 and verify with: qa_cli.py scan <your-domain>"
    ),
}

CLI_SCHEMA = {
    "name": "qa-tls",
    "version": "2.0.0",
    "homepage": BASE,
    "mcp_url": f"{BASE}/mcp",
    "jwks_url": f"{BASE}/.well-known/jwks.json",
    "commands": {
        "scan": {
            "description": "Run a live post-quantum TLS scan and receive an Ed25519 JWS signed receipt.",
            "args": {"host": "string (public domain)", "port": "integer (default 443)"},
            "endpoint": f"POST {BASE}/api/v1/scan",
        },
        "evidence": {
            "description": "Read stored TLS evidence for a domain without starting a new network probe.",
            "args": {"domain": "string (public domain)"},
            "endpoint": f"GET {BASE}/api/v1/badge/<domain>",
        },
        "mcp-index": {
            "description": "Query the live Reverse MCP Server Post-Quantum TLS Leaderboard.",
            "args": {"status": "optional filter (pq_hybrid|pq_not_preferred|classical|tls12)", "limit": "integer (default 20)"},
            "endpoint": f"GET {BASE}/api/v1/mcp-index",
        },
        "fix": {
            "description": "Print copy-paste X25519MLKEM768 server configuration for a stack.",
            "args": {"stack": list(FIX_SNIPPETS.keys())},
        },
    },
}


def _request_json(url: str, *, payload: dict | None = None, timeout: float = 20.0) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read(2_000_000).decode("utf-8", "replace"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="qa-tls", description="Quantum Aether Post-Quantum TLS CLI for humans & AI agents")
    ap.add_argument("--usage", action="store_true", help="print compact machine-readable usage summary")
    ap.add_argument("--schema", action="store_true", help="print full JSON command schema for AI agents")
    ap.add_argument("--base", default=BASE, help=f"API base URL (default {BASE})")
    sub = ap.add_subparsers(dest="cmd")

    p_scan = sub.add_parser("scan", help="live PQ-TLS scan + Ed25519 JWS signed receipt")
    p_scan.add_argument("host")
    p_scan.add_argument("--port", type=int, default=443)

    p_ev = sub.add_parser("evidence", help="read stored TLS evidence without scanning")
    p_ev.add_argument("domain")

    p_idx = sub.add_parser("mcp-index", help="query live Remote MCP Server PQ-TLS Index")
    p_idx.add_argument("--status", choices=("pq_hybrid", "pq_not_preferred", "classical", "tls12"))
    p_idx.add_argument("--limit", type=int, default=20)

    p_fix = sub.add_parser("fix", help="print copy-paste X25519MLKEM768 config for a server stack")
    p_fix.add_argument("stack", choices=tuple(FIX_SNIPPETS.keys()))

    args = ap.parse_args(argv)
    if args.schema:
        print(json.dumps(CLI_SCHEMA, indent=2))
        return 0
    if args.usage or not args.cmd:
        print(
            "qa-tls (Quantum Aether CLI v2.0 — zero API key required)\n"
            "  qa-tls scan <host> [--port 443]            Live PQ-TLS scan + Ed25519 JWS receipt\n"
            "  qa-tls evidence <domain>                   Read stored evidence without scanning\n"
            "  qa-tls mcp-index [--status ...] [--limit]  Live Remote MCP PQ-TLS Leaderboard\n"
            "  qa-tls fix <nginx|apache|haproxy|caddy|go|cloudflare>\n"
            "  qa-tls --schema                            Full JSON schema for AI agents\n"
            f"Remote MCP: {BASE}/mcp  |  Docs: {BASE}/agents"
        )
        return 0

    base = args.base.rstrip("/")
    try:
        if args.cmd == "scan":
            out = _request_json(f"{base}/api/v1/scan", payload={"host": args.host, "port": args.port})
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "evidence":
            dom = urllib.parse.quote(args.domain.strip(), safe="")
            out = _request_json(f"{base}/api/v1/badge/{dom}")
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "mcp-index":
            out = _request_json(f"{base}/api/v1/mcp-index")
            rows = out.get("results") or []
            if args.status:
                rows = [r for r in rows if r.get("status") == args.status]
            print(json.dumps({"summary": out.get("summary"), "results": rows[: max(1, args.limit)]}, indent=2, ensure_ascii=False))
            return 0
        if args.cmd == "fix":
            print(FIX_SNIPPETS[args.stack])
            return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:500]
        print(json.dumps({"error": f"HTTP {exc.code}", "detail": body}), file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
