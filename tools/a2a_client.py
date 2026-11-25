#!/usr/bin/env python3
"""Controlled A2A (Agent2Agent) inspection and single-target outreach CLI.

Safe by default:
  * --inspect <url>  Fetch and summarize another agent's /.well-known/agent-card.json (read-only).
  * --draft <url>    Fetch the card and print the exact JSON-RPC 2.0 message/send payload (sends nothing).
  * --send <url>     Explicitly send ONE JSON-RPC 2.0 message/send to ONE target agent, logging it to
                     prevent duplicate messages. No bulk lists, no cron/timer automation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

SITE = "https://ather-quantum.com"
OUR_CARD = f"{SITE}/.well-known/agent-card.json"
USER_AGENT = f"QuantumAetherA2A/1.0 (+{OUR_CARD})"
DEFAULT_LOG_PATH = os.path.join(os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas"), "a2a_contacted.json")


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _http_json(url: str, *, method: str = "GET", body: dict | None = None, timeout: float = 15.0) -> tuple[int, dict | str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(250_000).decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                return resp.status, raw[:1000]
    except urllib.error.HTTPError as exc:
        raw = exc.read(20_000).decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw[:1000]


def candidate_card_urls(target: str) -> list[str]:
    u = target.strip()
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    parsed = urllib.parse.urlsplit(u)
    if parsed.path.endswith(".json"):
        return [u]
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return [f"{origin}/.well-known/agent-card.json", f"{origin}/.well-known/agent.json"]


def fetch_agent_card(target: str, *, fetcher=_http_json, timeout: float = 15.0) -> tuple[str, dict]:
    errors = []
    for url in candidate_card_urls(target):
        try:
            status, payload = fetcher(url, method="GET", body=None, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{url}: {type(exc).__name__}: {exc}")
            continue
        if status == 200 and isinstance(payload, dict) and (payload.get("name") or payload.get("url") or payload.get("skills")):
            return url, payload
        errors.append(f"{url}: HTTP {status}")
    raise RuntimeError("Could not fetch A2A agent card: " + "; ".join(errors))


def summarize_card(card_url: str, card: dict) -> dict:
    endpoint = card.get("url")
    if not endpoint and isinstance(card.get("supportedInterfaces"), list) and card["supportedInterfaces"]:
        first = card["supportedInterfaces"][0]
        if isinstance(first, dict):
            endpoint = first.get("url")
    sec_schemes = card.get("securitySchemes") or {}
    security = card.get("security") or []
    skills = [
        {"id": s.get("id"), "name": s.get("name"), "tags": s.get("tags") or []}
        for s in (card.get("skills") or [])
        if isinstance(s, dict)
    ]
    return {
        "card_url": card_url,
        "name": card.get("name") or "(unnamed)",
        "protocol_version": card.get("protocolVersion") or "",
        "endpoint": endpoint or "",
        "preferred_transport": card.get("preferredTransport") or "",
        "auth_required": bool(sec_schemes or security),
        "security_schemes": list(sec_schemes.keys()) if isinstance(sec_schemes, dict) else [],
        "capabilities": card.get("capabilities") or {},
        "skills": skills,
    }


def build_intro_payload(
    summary: dict,
    *,
    custom_text: str | None = None,
    domain: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Build a concise, factual A2A JSON-RPC 2.0 message/send introducing Quantum Aether."""
    if custom_text:
        text = custom_text.strip()
    else:
        target_name = summary.get("name") or "agent"
        text = (
            f"Hello {target_name} — Quantum Aether ({OUR_CARD}) provides post-quantum TLS readiness evidence "
            f"(X25519MLKEM768 / ML-KEM, FIPS 203) over A2A ({SITE}/a2a) and MCP ({SITE}/mcp). "
            f"Free stored evidence and rate-limited scans include Ed25519 JWS receipts ({SITE}/.well-known/jwks.json). "
            f"For compliance workflows, we also offer a paid Auditor-Ready Signed PDF + CycloneDX 1.6 CBOM Attestation "
            f"(5.00 USDC on Base via x402; free read-only sample PDF: {SITE}/api/v1/attestation/sample.pdf) and a "
            f"programmatic AI Agent Affiliate Programme (30% recurring monitoring commission via MCP register_agent_affiliate). "
            f"External observations, not compliance certifications."
        )
    data_part = {
        "from_agent": "Quantum Aether",
        "agent_card": OUR_CARD,
        "a2a_endpoint": f"{SITE}/a2a",
        "mcp_endpoint": f"{SITE}/mcp",
        "jwks_url": f"{SITE}/.well-known/jwks.json",
        "free_sample_pdf": f"{SITE}/api/v1/attestation/sample.pdf",
        "attestation_price": "5.00 USDC (Base, x402 v2, buyer wallet required)",
        "affiliate_register": f"{SITE}/api/v1/agent/affiliate/register",
    }
    if domain:
        data_part["domain"] = domain
    return {
        "jsonrpc": "2.0",
        "id": request_id or f"qa-{uuid.uuid4().hex[:12]}",
        "method": "message/send",
        "params": {
            "message": {
                "kind": "message",
                "role": "user",
                "messageId": str(uuid.uuid4()),
                "parts": [
                    {"kind": "text", "text": text},
                    {"kind": "data", "data": data_part},
                ],
            }
        },
    }


def _load_log(log_path: str | Path) -> dict:
    p = Path(log_path)
    if not p.exists():
        return {"sent": {}}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("sent"), dict):
            return raw
    except Exception:
        pass
    return {"sent": {}}


def _save_log(log_path: str | Path, doc: dict) -> None:
    p = Path(log_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


def send_message(
    endpoint: str,
    payload: dict,
    *,
    log_path: str | Path = DEFAULT_LOG_PATH,
    force: bool = False,
    fetcher=_http_json,
    timeout: float = 20.0,
) -> dict:
    if not endpoint.startswith(("http://", "https://")):
        raise ValueError(f"Invalid A2A endpoint URL: {endpoint!r}")
    log = _load_log(log_path)
    key = endpoint.rstrip("/").lower()
    if key in log["sent"] and not force:
        raise RuntimeError(f"Already contacted {endpoint} on {log['sent'][key].get('sent_at')}; pass --force to override.")
    status, resp = fetcher(endpoint, method="POST", body=payload, timeout=timeout)
    record = {
        "endpoint": endpoint,
        "sent_at": _utc_now(),
        "request_id": payload.get("id"),
        "http_status": status,
        "response_excerpt": resp if isinstance(resp, dict) else str(resp)[:500],
    }
    log["sent"][key] = record
    _save_log(log_path, log)
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Inspect a target A2A Agent Card or send one explicit A2A message.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", metavar="URL", help="Fetch and summarize target /.well-known/agent-card.json (read-only)")
    mode.add_argument("--draft", metavar="URL", help="Fetch card and print exact message/send JSON payload without sending")
    mode.add_argument("--send", metavar="URL", help="Explicitly send ONE message/send to ONE target agent and log it")
    ap.add_argument("--message", help="Optional custom text message instead of the standard Quantum Aether introduction")
    ap.add_argument("--domain", help="Optional domain field to include in the data part")
    ap.add_argument("--log", default=DEFAULT_LOG_PATH, help="Contact log JSON path (prevents duplicate sends)")
    ap.add_argument("--force", action="store_true", help="Allow sending even if this endpoint was already logged")
    args = ap.parse_args(argv)

    target = args.inspect or args.draft or args.send
    card_url, card = fetch_agent_card(target)
    summary = summarize_card(card_url, card)
    if args.inspect:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    payload = build_intro_payload(summary, custom_text=args.message, domain=args.domain)
    if args.draft:
        print(json.dumps({"target": summary, "dry_run": True, "payload": payload}, indent=2, ensure_ascii=False))
        return 0

    if not summary["endpoint"]:
        raise SystemExit("Target agent card did not advertise an A2A endpoint URL.")
    result = send_message(summary["endpoint"], payload, log_path=args.log, force=args.force)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
