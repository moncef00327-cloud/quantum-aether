"""A2A (Agent2Agent, protocol 0.3) agent card + stateless JSON-RPC endpoint, 2026-11-21.

Lets other AI agents discover Quantum Aether and call it directly (inbound only; we never message other agents).
Skills:
  tls-evidence  free, read-only: stored post-quantum TLS evidence for a domain (never scans)
  tls-scan      free, rate-limited: new TLS measurement (same limits and code path as the MCP scan_tls tool)
  paid-data     how to buy the full report / sector snapshot via x402 (payment itself happens over HTTP or MCP)
Only `message/send` is implemented (no streaming, no tasks, no push notifications); replies are complete Messages.
"""
import re
import uuid

from flask import current_app, jsonify, request
from werkzeug.exceptions import HTTPException

import badge_evidence
import quantum_vuln_scanner
import sector_snapshot

PROTOCOL = "0.3.0"
HOST_RE = re.compile(r"(?<![@\w.-])((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})(?![\w-])", re.I)
SCAN_WORDS = re.compile(r"\b(scan|rescan|measure|check now|fresh|افحص|فحص)\b", re.I)


def card(base, version):
    return {
        "protocolVersion": PROTOCOL,
        "name": "Quantum Aether",
        "description": ("Post-quantum TLS evidence for any public website: does it negotiate hybrid post-quantum key "
                        "exchange (X25519MLKEM768)? Free stored evidence and free rate-limited scans; paid full reports "
                        "and weekly sector snapshots via x402 (USDC on Base). External observations, not compliance "
                        "certifications. Also available as an MCP server at " + base + "/mcp."),
        "url": base + "/a2a",
        "preferredTransport": "JSONRPC",
        "version": version,
        "provider": {"organization": "Quantum Aether", "url": base},
        "documentationUrl": base + "/agents?lang=en",
        "iconUrl": base + "/static/favicon.svg",
        "capabilities": {"streaming": False, "pushNotifications": False, "stateTransitionHistory": False},
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["application/json", "text/plain"],
        "skills": [
            {"id": "tls-evidence", "name": "Read post-quantum TLS evidence",
             "description": "Stored evidence for one domain: observation state, negotiated key-exchange group, grade, "
                            "checked_at/expires_at. Never starts a network scan. Free.",
             "tags": ["post-quantum", "tls", "x25519mlkem768", "security", "evidence"],
             "examples": ["Is example.com post-quantum ready?", '{"skill":"tls-evidence","domain":"example.com"}']},
            {"id": "tls-scan", "name": "Measure a website now",
             "description": "New rate-limited TLS 1.3 measurement of a public hostname on port 443. Stores a publicly "
                            "accessible result. Free.",
             "tags": ["post-quantum", "tls", "scan"],
             "examples": ["scan example.com", '{"skill":"tls-scan","domain":"example.com"}']},
            {"id": "paid-data", "name": "Full report and sector snapshots (x402)",
             "description": "Returns how to buy: full remediation report per scan, or a weekly sector snapshot "
                            "(" + ", ".join(sector_snapshot.keys()[:6]) + " ...), paid per call with x402 USDC on Base "
                            "via HTTP or the MCP tools get_full_report / get_sector_snapshot.",
             "tags": ["x402", "paid", "report", "dataset"],
             "examples": ['{"skill":"paid-data"}', "How do I buy the full report?"]},
        ],
    }


def _message(text, data, context_id=None):
    parts = [{"kind": "text", "text": text}]
    if data is not None:
        parts.append({"kind": "data", "data": data})
    msg = {"kind": "message", "role": "agent", "messageId": str(uuid.uuid4()), "parts": parts}
    if context_id:
        msg["contextId"] = context_id
    return msg


def _read_request(message):
    """-> (skill, domain) from text and/or data parts."""
    text, data = [], {}
    for p in message.get("parts") or []:
        if not isinstance(p, dict):
            continue
        if p.get("kind") == "text" and isinstance(p.get("text"), str):
            text.append(p["text"][:2000])
        elif p.get("kind") == "data" and isinstance(p.get("data"), dict):
            data.update(p["data"])
    joined = " ".join(text)
    skill = data.get("skill") if data.get("skill") in ("tls-evidence", "tls-scan", "paid-data") else None
    domain = data.get("domain") if isinstance(data.get("domain"), str) else None
    if not domain:
        m = HOST_RE.search(joined)
        domain = m.group(1) if m else None
    if not skill:
        if re.search(r"\b(buy|price|pay|report|x402|sector|snapshot|شراء|سعر|تقرير)\b", joined, re.I) and not domain:
            skill = "paid-data"
        elif SCAN_WORDS.search(joined):
            skill = "tls-scan"
        else:
            skill = "tls-evidence"
    return skill, domain


def register(bp, services, version):
    base = services["base"]

    def well_known():
        resp = jsonify(card(base(), version))
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp

    bp.add_url_rule("/.well-known/agent-card.json", "a2a_agent_card", well_known)
    bp.add_url_rule("/.well-known/agent.json", "a2a_agent_card_legacy", well_known)

    def err(code, message, rid=None, status=200):
        return jsonify(jsonrpc="2.0", id=rid, error={"code": code, "message": message}), status

    @bp.route("/a2a", methods=["POST", "OPTIONS"])
    def a2a_endpoint():
        if request.method == "OPTIONS":
            resp = current_app.make_response(("", 204))
            resp.headers.update({"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST",
                                 "Access-Control-Allow-Headers": "Content-Type"})
            return resp
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
            return err(-32600, "Invalid JSON-RPC request")
        rid, method, params = body.get("id"), body.get("method"), body.get("params") or {}
        if method != "message/send":
            return err(-32601, "Only message/send is supported (no streaming, tasks or push notifications)", rid)
        message = params.get("message") if isinstance(params, dict) else None
        if not isinstance(message, dict) or message.get("role") != "user":
            return err(-32602, "params.message with role 'user' is required", rid)
        ctx = message.get("contextId") if isinstance(message.get("contextId"), str) else None
        skill, domain = _read_request(message)
        b = base()
        if skill == "paid-data":
            data = {"full_report": {"price_usd": str(current_app.config["PRICE"]), "how": "x402 v2 exact USDC on Base",
                                    "http": b + "/api/v1/agent/report/{scan_id}", "mcp_tool": "get_full_report",
                                    "needs": "scan_id from tls-scan"},
                    "sector_snapshot": {"price_usd": str(current_app.config.get("X402_SECTOR_PRICE") or "0.50"),
                                        "how": "x402 v2 exact USDC on Base", "http": b + "/api/v1/agent/sector/{sector}",
                                        "mcp_tool": "get_sector_snapshot", "sectors": sector_snapshot.keys()},
                    "mcp": b + "/mcp", "terms": b + "/agb?lang=en"}
            return jsonify(jsonrpc="2.0", id=rid, result=_message(
                "Paid data is bought per call with x402 (USDC on Base) over HTTP or MCP. Unpaid calls return the price "
                "challenge and never charge.", data, ctx))
        if not domain:
            return jsonify(jsonrpc="2.0", id=rid, result=_message(
                "Send a public hostname, e.g. 'Is example.com post-quantum ready?' or {\"skill\":\"tls-scan\",\"domain\":\"example.com\"}.",
                {"skills": ["tls-evidence", "tls-scan", "paid-data"]}, ctx))
        try:
            domain = quantum_vuln_scanner.normalize_domain(domain)
            if skill == "tls-scan":
                scan_id, raw = services["scan"](domain, "a2a")
                data = services["summary"](scan_id, raw)
                pq = data.get("post_quantum_key_exchange")
                text = (f"{domain}: grade {data.get('grade')}, key exchange {data.get('key_exchange_group') or 'unknown'}"
                        f"{' (post-quantum)' if pq else ''}. Full report via x402: use scan_id {scan_id}.")
            else:
                data = dict(badge_evidence.for_domain(services["db"](), domain), verification_url=b + "/verify/" + domain)
                if data.get("state") == "not_scanned":
                    text = f"No stored evidence for {domain} yet (not proof of anything). Ask to 'scan {domain}' for a measurement."
                else:
                    obs = {"observed_pq": "negotiates post-quantum key exchange", "observed_classical": "classical key exchange only",
                           "undetermined": "undetermined"}.get(data.get("observation_status"), "see data")
                    text = (f"{domain}: {obs} (group {data.get('group') or 'unknown'}, grade {data.get('grade')}), "
                            f"checked {data.get('checked_at')}, evidence {data.get('state')}. Ask to 'scan' for a fresh measurement.")
        except quantum_vuln_scanner.ScanError as exc:
            return jsonify(jsonrpc="2.0", id=rid, result=_message(f"Could not measure {domain}: {exc}",
                                                                   {"error": exc.code}, ctx))
        except HTTPException as exc:
            if exc.code == 429:
                return jsonify(jsonrpc="2.0", id=rid, result=_message(
                    "Scan rate limit reached; try again in an hour or read stored evidence instead.",
                    {"error": "rate_limited", "retry_after_seconds": 3600}, ctx))
            raise
        return jsonify(jsonrpc="2.0", id=rid, result=_message(text, data, ctx))
