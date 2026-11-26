#!/usr/bin/env python3
"""Reverse MCP Security Index builder: scans public remote HTTPS MCP servers from the Official MCP Registry.

Usage:
  python3 tools/mcp_security_index.py [--limit 150] [--max-pages 15] [--out /var/lib/quantum_saas/mcp_index.json]

Measures ONE public TLS handshake (plus PQ-preference check on classical TLS 1.3) per unique remote MCP host,
and optionally discovers /.well-known/agent-card.json endpoints for A2A outreach.
"""
from __future__ import annotations

import argparse
from collections import Counter
import concurrent.futures
import datetime as dt
import ipaddress
import json
import os
from pathlib import Path
import pwd
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import quantum_vuln_scanner as qs  # noqa: E402

DATA_DIR = os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas")
DEFAULT_OUT = os.path.join(DATA_DIR, "mcp_index.json")
DEFAULT_A2A_CARDS_OUT = os.path.join(DATA_DIR, "mcp_a2a_cards.json")
REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0/servers"
USER_AGENT = "QuantumAetherMCPIndex/1.0 (+https://ather-quantum.com/mcp-index)"

SKIP_HOSTS = {
    "localhost", "127.0.0.1", "0.0.0.0", "example.com", "example.org", "example.net",
    "mcp.example.com", "your-domain.com", "yourdomain.com",
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def keep_owner(path: str) -> None:
    try:
        pw = pwd.getpwnam("quantum")
        os.chown(path, pw.pw_uid, pw.pw_gid)
    except (KeyError, OSError):
        pass


def _get_json(url: str, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read(2_000_000).decode("utf-8", "replace"))


def _clean_host(url: str) -> str | None:
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if not u.startswith("https://"):
        return None
    if "{" in u or "}" in u or "<" in u or ">" in u or " " in u:
        return None
    parsed = urllib.parse.urlsplit(u)
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or "." not in host or host in SKIP_HOSTS:
        return None
    if host.endswith((".local", ".internal", ".test", ".example", ".invalid", ".localhost")):
        return None
    try:
        ipaddress.ip_address(host)
        return None
    except ValueError:
        pass
    try:
        return qs.normalize_domain(host)
    except qs.ScanError:
        return None


def fetch_remote_mcp_hosts(max_pages: int = 15, limit: int = 150, getter=_get_json) -> tuple[list[dict], int]:
    """Fetch unique remote HTTPS MCP hosts from the Official MCP Registry."""
    hosts: dict[str, dict] = {}
    cursor = None
    total_entries = 0

    for _ in range(max_pages):
        url = f"{REGISTRY_URL}?limit=100"
        if cursor:
            url += f"&cursor={urllib.parse.quote(cursor, safe='')}"
        try:
            doc = getter(url)
        except Exception:
            break
        servers = doc.get("servers") if isinstance(doc, dict) else []
        if not servers:
            break
        for entry in servers:
            if not isinstance(entry, dict):
                continue
            total_entries += 1
            meta = (entry.get("_meta") or {}).get("io.modelcontextprotocol.registry/official") or {}
            if meta.get("status") and meta.get("status") != "active":
                continue
            if meta.get("isLatest") is False:
                continue
            srv = entry.get("server") or {}
            remotes = srv.get("remotes") or []
            if not isinstance(remotes, list):
                continue
            for rem in remotes:
                if not isinstance(rem, dict):
                    continue
                rem_url = (rem.get("url") or "").strip()
                host = _clean_host(rem_url)
                if not host or host in hosts:
                    continue
                hosts[host] = {
                    "host": host,
                    "server_name": str(srv.get("name") or host)[:140],
                    "title": str(srv.get("title") or srv.get("name") or host)[:140],
                    "description": str(srv.get("description") or "")[:240],
                    "remote_url": rem_url[:240],
                    "transport": str(rem.get("type") or "streamable-http")[:40],
                    "updated_at": str(meta.get("updatedAt") or "")[:30],
                }
                if len(hosts) >= limit:
                    return list(hosts.values()), total_entries
        cursor = (doc.get("metadata") or {}).get("nextCursor") if isinstance(doc, dict) else None
        if not cursor:
            break

    return list(hosts.values()), total_entries


def classify_kx(kx: dict) -> str:
    if kx.get("error") or kx.get("hrr") or not kx.get("version"):
        return "unreachable"
    if kx.get("pq"):
        return "pq_hybrid"
    if kx.get("pq_supported_not_preferred"):
        return "pq_not_preferred"
    if kx.get("version") == "TLSv1.3":
        return "classical"
    return "tls12"


def scan_one_mcp(item: dict, timeout: float = 6.0, check_a2a: bool = True) -> tuple[dict, dict | None]:
    host = item["host"]
    row = dict(item)
    row["scanned_at"] = now_iso()
    try:
        ip = qs.resolve_public_ip(host)
        kx = qs.probe_key_exchange(ip, host, timeout=timeout)
        row.update({
            "tls_version": kx.get("version"),
            "group": kx.get("group"),
            "pq": bool(kx.get("pq")),
            "pq_supported_not_preferred": bool(kx.get("pq_supported_not_preferred")),
            "pq_supported_group": kx.get("pq_supported_group"),
            "hrr": bool(kx.get("hrr")),
            "error": kx.get("error"),
            "status": classify_kx(kx),
        })
    except Exception as exc:  # noqa: BLE001
        row.update({
            "tls_version": None,
            "group": None,
            "pq": False,
            "pq_supported_not_preferred": False,
            "pq_supported_group": None,
            "hrr": False,
            "error": f"{type(exc).__name__}: {exc}"[:140],
            "status": "unreachable",
        })

    a2a_card = None
    if check_a2a and row["status"] != "unreachable" and "ather-quantum.com" not in host:
        a2a_card = probe_a2a_card(host, timeout=3.5)
    return row, a2a_card


def probe_a2a_card(host: str, timeout: float = 3.5) -> dict | None:
    """Check whether an MCP server host also exposes an open A2A Agent Card."""
    card_url = f"https://{host}/.well-known/agent-card.json"
    req = urllib.request.Request(card_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "json" not in ctype:
                return None
            card = json.loads(resp.read(150_000).decode("utf-8", "replace"))
    except Exception:
        return None
    if not isinstance(card, dict):
        return None
    if card.get("security") or card.get("securitySchemes"):
        return None
    endpoint = str(card.get("url") or "").strip()
    name = str(card.get("name") or host).strip()
    if not endpoint.startswith("https://") or not name:
        return None
    skills_text = " ".join(
        f"{s.get('id', '')} {s.get('name', '')} {' '.join(s.get('tags') or [])}"
        for s in (card.get("skills") or [])
        if isinstance(s, dict)
    )
    return {
        "source": "mcp-registry-a2a",
        "host": host.removeprefix("www."),
        "name": name[:140],
        "description": str(card.get("description") or "")[:300],
        "card_url": card_url,
        "endpoint": endpoint,
        "skills_text": skills_text[:400],
    }


def summarize(rows: list[dict], registry_entries: int) -> dict:
    counts = Counter(r["status"] for r in rows)
    measured = len(rows) - counts["unreachable"]
    pq_n = counts["pq_hybrid"]
    groups = Counter(r["group"] for r in rows if r.get("group") and r["status"] != "unreachable")
    return {
        "updated_at": now_iso(),
        "scanner_version": qs.SCANNER_VERSION,
        "registry_entries_checked": registry_entries,
        "total_hosts": len(rows),
        "measured": measured,
        "pq_hybrid": pq_n,
        "pq_pct": round((100.0 * pq_n / measured), 1) if measured else 0.0,
        "pq_not_preferred": counts["pq_not_preferred"],
        "classical": counts["classical"],
        "tls12": counts["tls12"],
        "unreachable": counts["unreachable"],
        "top_groups": [{"group": g, "count": c} for g, c in groups.most_common(8)],
    }


def build_index(
    *,
    limit: int = 150,
    max_pages: int = 15,
    workers: int = 12,
    timeout: float = 6.0,
    out_path: str = DEFAULT_OUT,
    a2a_cards_out: str = DEFAULT_A2A_CARDS_OUT,
    check_a2a: bool = True,
) -> dict:
    candidates, total_entries = fetch_remote_mcp_hosts(max_pages=max_pages, limit=limit)
    rows: list[dict] = []
    a2a_cards: list[dict] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futs = [pool.submit(scan_one_mcp, c, timeout, check_a2a) for c in candidates]
        for fut in concurrent.futures.as_completed(futs):
            row, card = fut.result()
            rows.append(row)
            if card:
                a2a_cards.append(card)

    order = {"pq_not_preferred": 0, "tls12": 1, "classical": 2, "pq_hybrid": 3, "unreachable": 4}
    rows.sort(key=lambda r: (order.get(r["status"], 9), r["host"]))

    payload = {
        "summary": summarize(rows, total_entries),
        "results": rows,
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, out)
    keep_owner(str(out))

    if a2a_cards_out:
        aout = Path(a2a_cards_out)
        aout.parent.mkdir(parents=True, exist_ok=True)
        atmp = aout.with_suffix(".json.tmp")
        atmp.write_text(
            json.dumps({"updated_at": now_iso(), "count": len(a2a_cards), "cards": a2a_cards}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(atmp, aout)
        keep_owner(str(aout))

    return payload


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=150, help="max unique remote MCP hosts to scan (default 150)")
    ap.add_argument("--max-pages", type=int, default=15, help="max Official MCP Registry pages to crawl (default 15)")
    ap.add_argument("--workers", type=int, default=12, help="parallel TLS workers (default 12)")
    ap.add_argument("--timeout", type=float, default=6.0, help="per-host TLS timeout in seconds (default 6.0)")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--a2a-cards-out", default=DEFAULT_A2A_CARDS_OUT)
    ap.add_argument("--no-a2a", action="store_true", help="skip probing /.well-known/agent-card.json")
    a = ap.parse_args(argv)
    payload = build_index(
        limit=a.limit,
        max_pages=a.max_pages,
        workers=a.workers,
        timeout=a.timeout,
        out_path=a.out,
        a2a_cards_out="" if a.no_a2a else a.a2a_cards_out,
        check_a2a=not a.no_a2a,
    )
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
