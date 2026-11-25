"""A2A (Agent2Agent, protocol 0.3) agent card + JSON-RPC endpoint, 2026-11-21.

Lets other AI agents discover Quantum Aether and call it directly (inbound only; we never message other agents).
Skills:
  tls-evidence     free, read-only: stored post-quantum TLS evidence for a domain (never scans)
  tls-scan         free, rate-limited: new TLS measurement (same limits and code path as the MCP scan_tls tool)
  tls-attestation  how to preview/buy the paid Auditor-Ready PDF + CycloneDX 1.6 CBOM attestation (5.00 USDC x402)
  paid-data        how to buy attestation / full report / sector snapshot via x402 (payment happens over HTTP or MCP)
  agent-affiliate  programmatic AI Agent Affiliate Programme (30% recurring monitoring commission)
Supported JSON-RPC methods (A2A 0.3.0): `message/send`, `tasks/get`, and `tasks/cancel`.
"""
import base64
import datetime as dt
import json
import re
import sqlite3
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from flask import current_app, jsonify, request
from werkzeug.exceptions import HTTPException

import agent_audit
import badge_evidence
import quantum_vuln_scanner
import receipts
import sector_snapshot
import signed_receipts

PROTOCOL = "0.3.0"
HOST_RE = re.compile(r"(?<![@\w.-])((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})(?![\w-])", re.I)
SCAN_WORDS = re.compile(r"\b(scan|rescan|measure|check now|fresh|افحص|فحص)\b", re.I)
AFFILIATE_WORDS = re.compile(r"\b(affiliate|referral|partner|commission|ref\s*code|عمولة|إحالة|شراكة|شريك)\b", re.I)
ATTESTATION_WORDS = re.compile(r"\b(attestation|cbom|cyclonedx|auditor\s+pdf|audit\s+pdf|sample\.pdf|شهادة\s+تدقيق|ملف\s+المدقق)\b", re.I)
MSP_PILOT_WORDS = re.compile(r"\b(msp|pilot|it[- ]?dienstleister|white[- ]?label|ampel|50\s+hostnames?|290\s*€|290\s*eur|بايلوت)\b", re.I)
VALID_SKILLS = ("tls-evidence", "tls-scan", "tls-attestation", "msp-pilot", "paid-data", "agent-affiliate")


def services_offer(base, domain=None, scan_id=None, price_usd="49", sector_price_usd="0.50", attestation_price_usd="5.00"):
    q = f"?domain={domain}" if domain else ""
    return {
        "monitoring": {
            "summary": "Daily post-quantum TLS regression & certificate monitoring (14-day free trial, up to 10 domains, no card)",
            "plans": {"starter": "29 EUR/month (up to 10 domains)", "business": "99 EUR/month (up to 100 domains)"},
            "trial_url": f"{base}/monitoring{q}#trial-form",
            "pricing_url": f"{base}/pricing",
        },
        "tls_attestation": {
            "price_usd": str(attestation_price_usd),
            "currency": "USDC",
            "network": "Base",
            "scheme": "x402 v2 exact",
            "read_only": False,
            "starts_scan": True,
            "buyer_wallet_required": True,
            "payment_authorization_required": True,
            "how": ("Paid per call with x402 v2 (5.00 USDC on Base) over HTTP POST /api/v1/attestation or MCP tool "
                    "get_tls_attestation using an x402-compatible client with a funded buyer wallet. Unpaid calls "
                    "return HTTP 402 with payment requirements and never charge; agents should not auto-retry paid "
                    "calls without explicit spend approval."),
            "http": f"{base}/api/v1/attestation",
            "mcp_tool": "get_tls_attestation",
            "sample_json": f"{base}/api/v1/attestation/sample",
            "sample_pdf": f"{base}/api/v1/attestation/sample.pdf",
            "deliverables": [
                "Ed25519 JWS signed TLS receipt",
                "CycloneDX 1.6 CBOM JSON",
                "Printable Auditor-Ready PDF (token-gated URL, 7-day expiry)",
                "Bundle-level Ed25519 JWS integrity signature",
            ],
            "note": "External point-in-time port-443 TLS observation, not a compliance certification.",
        },
        "full_report": {
            "price_usd": str(price_usd),
            "how": "PayPal, on-chain USDC/USDT, or x402 v2 exact USDC on Base",
            "http": f"{base}/api/v1/agent/report/{scan_id or '{scan_id}'}",
            "mcp_tool": "get_full_report",
            "needs": "scan_id from tls-scan",
        },
        "msp_pilot": {
            "price_eur": "290",
            "currency": "EUR",
            "hostnames_limit": 50,
            "partner_slots": 3,
            "deliverables": [
                "German/English Ampel PDF report for up to 50 client hostnames",
                "Offline-verifiable Ed25519 JWS signed TLS receipts per hostname",
                "Optional partner white-label logo",
            ],
            "summary": "IT-Dienstleister / MSP Partner Pilot: up to 50 hostnames, German Ampel PDF + signed receipts + optional logo (3 partner slots, 290 EUR one-time)",
            "url": f"{base}/partners?lang=de#msp-pilot",
            "url_en": f"{base}/partners?lang=en#msp-pilot",
            "sample_pdf": f"{base}/api/v1/attestation/sample.pdf",
        },
        "organization_audit": {
            "price_eur": "490",
            "summary": "Estate-wide subdomain TLS inventory & compliance audit (SAMA / DORA / NIS2) with PDF report",
            "url": f"{base}/audit{q}",
        },
        "sector_snapshot": {
            "price_usd": str(sector_price_usd),
            "how": "x402 v2 exact USDC on Base",
            "http": f"{base}/api/v1/agent/sector/{{sector}}",
            "mcp_tool": "get_sector_snapshot",
            "sectors": sector_snapshot.keys(),
        },
        "partner_affiliate": {
            "summary": "30% of monitoring (12 months) + 20% of one-time reports/audits; monthly manual payout by owner (PayPal or USDC, 30-day hold, min $50)",
            "register_http": f"{base}/api/v1/agent/affiliate/register",
            "mcp_tool": "register_agent_affiliate",
            "terms_url": f"{base}/partners?lang=en",
        },
        "mcp_endpoint": f"{base}/mcp",
        "acp_agents": f"{base}/acp/agents",
        "jwks_url": f"{base}/.well-known/jwks.json",
        "llms_txt": f"{base}/llms.txt",
        "terms": f"{base}/agb?lang=en",
    }


def card(base, version):
    return {
        "protocolVersion": PROTOCOL,
        "name": "Quantum Aether",
        "description": ("Post-quantum TLS evidence for any public website: does it negotiate hybrid post-quantum key "
                        "exchange (X25519MLKEM768)? Free stored evidence and free rate-limited scans with Ed25519 JWS "
                        "signed receipts (/.well-known/jwks.json); Auditor-Ready Signed PDF + CycloneDX 1.6 CBOM "
                        "Attestation (5.00 USDC on Base via x402; free read-only sample at /api/v1/attestation/sample.pdf); "
                        "daily monitoring (14-day free trial, 29 EUR/mo Starter, 99 EUR/mo Business), MSP Partner Pilot "
                        "(290 EUR, up to 50 hostnames), organization compliance audits (490 EUR), paid full reports / "
                        "weekly sector snapshots via x402, and a programmatic AI Agent Affiliate Programme (30% monitoring "
                        "12m / 20% one-time, monthly manual owner payout via POST /api/v1/agent/affiliate/register or MCP "
                        "register_agent_affiliate). External observations, not compliance certifications. Also available "
                        "via MCP (" + base + "/mcp) and ACP (" + base + "/acp/agents)."),
        "url": base + "/a2a",
        "preferredTransport": "JSONRPC",
        "supportedInterfaces": [
            {"url": base + "/a2a", "protocolBinding": "JSONRPC", "protocolVersion": PROTOCOL},
        ],
        "version": version,
        "provider": {"organization": "Quantum Aether", "url": base},
        "documentationUrl": base + "/agents?lang=en",
        "iconUrl": base + "/static/favicon.svg",
        "jwksUri": base + "/.well-known/jwks.json",
        "acpAgentsUrl": base + "/acp/agents",
        "supportsAuthenticatedExtendedCard": False,
        "securitySchemes": {},
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
                            "accessible result and issues a v1 Ed25519 JWS signed receipt. Free.",
             "tags": ["post-quantum", "tls", "scan", "signed-receipt", "ed25519"],
             "examples": ["scan example.com", '{"skill":"tls-scan","domain":"example.com"}']},
            {"id": "tls-attestation", "name": "Auditor-ready signed PDF + CycloneDX CBOM attestation (5.00 USDC)",
             "description": "Returns specifications and free archived sample links (/api/v1/attestation/sample and "
                            "/api/v1/attestation/sample.pdf) for the paid Auditor-Ready TLS Attestation bundle: fresh "
                            "port-443 measurement + Ed25519 JWS receipt + CycloneDX 1.6 CBOM + printable PDF + bundle "
                            "JWS signature. Execution is NOT read-only (starts_scan=true) and costs 5.00 USDC on Base "
                            "via x402 HTTP (POST /api/v1/attestation) or MCP tool get_tls_attestation using an x402 "
                            "buyer wallet with payment authorization. External observation, not a compliance certification.",
             "tags": ["attestation", "cbom", "cyclonedx", "pdf", "nis2", "dora", "x402", "paid", "ed25519"],
             "examples": ['{"skill":"tls-attestation"}', "How do I get a CycloneDX CBOM and auditor PDF attestation?"]},
            {"id": "msp-pilot", "name": "IT-Dienstleister / MSP Partner Pilot (50 hostnames, 290 EUR)",
             "description": "Returns details and booking links for the IT-Dienstleister / MSP Partner Pilot: "
                            "up to 50 client hostnames checked for X25519MLKEM768 / BSI TR-02102-2 / NIS2 readiness, "
                            "German Ampel PDF report + offline-verifiable Ed25519 signed receipts + optional partner "
                            "white-label logo, 290 EUR one-time (3 partner slots). Includes free sample PDF preview.",
             "tags": ["msp", "it-dienstleister", "pilot", "dach", "bsi", "nis2", "dora", "white-label", "pdf", "290eur"],
             "examples": ['{"skill":"msp-pilot"}', "Tell me about the 290 EUR IT-Dienstleister MSP Pilot"]},
            {"id": "paid-data", "name": "Attestation, full report, and sector snapshots (x402)",
             "description": "Returns how to buy: Auditor-Ready PDF + CycloneDX CBOM attestation (5.00 USDC), full "
                            "remediation report per scan, or a weekly sector snapshot "
                            "(" + ", ".join(sector_snapshot.keys()[:6]) + " ...), paid per call with x402 USDC on Base "
                            "via HTTP or MCP tools get_tls_attestation / get_full_report / get_sector_snapshot.",
             "tags": ["x402", "paid", "report", "attestation", "dataset"],
             "examples": ['{"skill":"paid-data"}', "How do I buy the full report?"]},
            {"id": "agent-affiliate", "name": "AI Agent Affiliate Programme (30% recurring)",
             "description": "Returns programmatic self-registration details for AI agents and operators to get an "
                            "instant ?ref=CODE link: 30% of monitoring payments for 12 months and 20% of one-time "
                            "reports/audits, paid monthly manually by the owner (PayPal or USDC, 30-day hold, min $50).",
             "tags": ["affiliate", "referral", "partner", "commission", "monetization", "mcp"],
             "examples": ['{"skill":"agent-affiliate"}', "How do AI agents earn referral commission?"]},
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
    skill = data.get("skill") if data.get("skill") in VALID_SKILLS else None
    domain = data.get("domain") if isinstance(data.get("domain"), str) else None
    if not domain:
        m = HOST_RE.search(joined)
        domain = m.group(1) if m else None
    if not skill:
        if MSP_PILOT_WORDS.search(joined):
            skill = "msp-pilot"
        elif ATTESTATION_WORDS.search(joined):
            skill = "tls-attestation"
        elif AFFILIATE_WORDS.search(joined) and not domain:
            skill = "agent-affiliate"
        elif re.search(r"\b(buy|price|pay|report|x402|sector|snapshot|شراء|سعر|تقرير)\b", joined, re.I) and not domain:
            skill = "paid-data"
        elif SCAN_WORDS.search(joined):
            skill = "tls-scan"
        else:
            skill = "tls-evidence"
    return skill, domain


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(text: str) -> bytes:
    pad = "=" * ((4 - len(text) % 4) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def _canonical_card_bytes(card_obj: dict) -> bytes:
    unsigned = {k: v for k, v in card_obj.items() if k != "signatures"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_agent_card(card_obj: dict, services: dict, base_url: str) -> dict:
    """Return a copy of the Agent Card signed with detached JWS (RFC 7515 + RFC 8785 JCS) using active Ed25519 key."""
    out = dict(card_obj)
    try:
        priv, active_kid, _, _ = receipts.load_signing_bundle(**receipts.key_config_from_app(services))
        protected_hdr = {
            "alg": "EdDSA",
            "kid": active_kid,
            "typ": "JOSE",
            "jku": base_url.rstrip("/") + "/.well-known/jwks.json",
        }
        protected_b64 = _b64u_encode(
            json.dumps(protected_hdr, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        payload_b64 = _b64u_encode(_canonical_card_bytes(out))
        sig_b64 = _b64u_encode(priv.sign(f"{protected_b64}.{payload_b64}".encode("ascii")))
        out["signatures"] = [{"protected": protected_b64, "signature": sig_b64}]
    except Exception:
        pass
    return out


def verify_agent_card_signature(signed_card: dict, jwks_doc: dict) -> dict:
    """Verify the first detached EdDSA AgentCardSignature against a JWKS document. Raises ValueError on failure."""
    sigs = signed_card.get("signatures")
    if not isinstance(sigs, list) or not sigs:
        raise ValueError("Agent card has no signatures")
    entry = sigs[0]
    protected_b64 = entry.get("protected") or ""
    sig_b64 = entry.get("signature") or ""
    hdr = json.loads(_b64u_decode(protected_b64).decode("utf-8"))
    if hdr.get("alg") not in ("EdDSA", "Ed25519"):
        raise ValueError(f"Unsupported alg: {hdr.get('alg')}")
    kid = hdr.get("kid")
    keys = {k.get("kid"): k for k in (jwks_doc.get("keys") or []) if isinstance(k, dict)}
    jwk = keys.get(kid)
    if not jwk or jwk.get("kty") != "OKP" or jwk.get("crv") != "Ed25519":
        raise ValueError(f"Signing key {kid!r} not found in JWKS")
    pub = Ed25519PublicKey.from_public_bytes(_b64u_decode(jwk["x"]))
    payload_b64 = _b64u_encode(_canonical_card_bytes(signed_card))
    pub.verify(_b64u_decode(sig_b64), f"{protected_b64}.{payload_b64}".encode("ascii"))
    return hdr


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_tasks_table(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS a2a_tasks ("
        "id TEXT PRIMARY KEY, context_id TEXT, task_json TEXT NOT NULL, created_at TEXT NOT NULL)"
    )


def _store_completed_task(conn, task_id: str, context_id: str, user_msg: dict, agent_msg: dict) -> None:
    if not task_id:
        return
    now = _utc_now()
    task = {
        "id": task_id,
        "contextId": context_id,
        "kind": "task",
        "status": {
            "state": "completed",
            "timestamp": now,
            "message": agent_msg,
        },
        "history": [user_msg, agent_msg],
    }
    try:
        _ensure_tasks_table(conn)
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO a2a_tasks (id, context_id, task_json, created_at) VALUES (?, ?, ?, ?)",
                (task_id, context_id, json.dumps(task, ensure_ascii=False), now),
            )
            conn.execute(
                "DELETE FROM a2a_tasks WHERE id NOT IN "
                "(SELECT id FROM a2a_tasks ORDER BY created_at DESC LIMIT 500)"
            )
    except sqlite3.Error:
        pass


def _lookup_task(conn, task_id: str) -> dict | None:
    try:
        _ensure_tasks_table(conn)
        row = conn.execute("SELECT task_json FROM a2a_tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None
        return json.loads(row[0])
    except (sqlite3.Error, ValueError):
        return None


def register(bp, services, version):
    base = services["base"]

    def well_known():
        b = base()
        resp = jsonify(sign_agent_card(card(b, version), services, b))
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp

    bp.add_url_rule("/.well-known/agent-card.json", "a2a_agent_card", well_known)
    bp.add_url_rule("/.well-known/agent.json", "a2a_agent_card_legacy", well_known)

    def err(code, message, rid=None, status=200, data=None):
        e = {"code": code, "message": message}
        if data is not None:
            e["data"] = data
        return jsonify(jsonrpc="2.0", id=rid, error=e), status

    @bp.route("/a2a", methods=["GET", "POST", "OPTIONS"])
    def a2a_endpoint():
        if request.method == "OPTIONS":
            resp = current_app.make_response(("", 204))
            resp.headers.update({"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                                 "Access-Control-Allow-Headers": "Content-Type"})
            return resp
        if request.method == "GET":
            b = base()
            info = dict(sign_agent_card(card(b, version), services, b),
                        how_to_call="POST JSON-RPC 2.0 methods 'message/send', 'tasks/get', or 'tasks/cancel' to this URL",
                        services=services_offer(b, price_usd=current_app.config["PRICE"],
                                                sector_price_usd=current_app.config.get("X402_SECTOR_PRICE") or "0.50"))
            resp = jsonify(info)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Cache-Control"] = "public, max-age=3600"
            return resp
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
            return err(-32600, "Invalid JSON-RPC request")
        rid, method, params = body.get("id"), body.get("method"), body.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return err(-32602, "params must be an object", rid)

        if method == "tasks/get":
            task_id = params.get("id")
            if not isinstance(task_id, str) or not task_id.strip():
                return err(-32602, "params.id is required", rid)
            task_id = task_id.strip()
            task = _lookup_task(services["db"](), task_id)
            if task is None:
                return err(-32001, "Task not found", rid, data={"taskId": task_id})
            hist_len = params.get("historyLength")
            if isinstance(hist_len, int) and not isinstance(hist_len, bool) and hist_len >= 0:
                hist = task.get("history") or []
                task = dict(task, history=[] if hist_len == 0 else hist[-hist_len:])
            return jsonify(jsonrpc="2.0", id=rid, result=task)

        if method == "tasks/cancel":
            task_id = params.get("id")
            if not isinstance(task_id, str) or not task_id.strip():
                return err(-32602, "params.id is required", rid)
            task_id = task_id.strip()
            task = _lookup_task(services["db"](), task_id)
            if task is None:
                return err(-32001, "Task not found", rid, data={"taskId": task_id})
            return err(-32002, "Task is not cancelable", rid, data={"taskId": task_id, "state": "completed"})

        if method != "message/send":
            return err(-32601, "Supported methods: message/send, tasks/get, tasks/cancel (no streaming or push notifications)", rid)
        message = params.get("message")
        if not isinstance(message, dict) or message.get("role") != "user":
            return err(-32602, "params.message with role 'user' is required", rid)
        ctx = message.get("contextId") if isinstance(message.get("contextId"), str) else str(uuid.uuid4())
        req_task_id = message.get("taskId") if isinstance(message.get("taskId"), str) and message.get("taskId").strip() else None
        skill, domain = _read_request(message)
        b = base()
        price_usd = str(current_app.config["PRICE"])
        sector_price_usd = str(current_app.config.get("X402_SECTOR_PRICE") or "0.50")

        def _reply(text_msg, data_obj):
            agent_msg = _message(text_msg, data_obj, ctx)
            conn = services["db"]()
            _store_completed_task(conn, agent_msg["messageId"], ctx, message, agent_msg)
            if req_task_id and req_task_id != agent_msg["messageId"]:
                _store_completed_task(conn, req_task_id, ctx, message, agent_msg)
            return jsonify(jsonrpc="2.0", id=rid, result=agent_msg)
        def _audit(action, dom="", status="ok"):
            fn = services.get("audit")
            if fn:
                fn("a2a", action, agent_audit.client_label(request.headers), dom or "", status)

        def _attach_receipt(payload, kind):
            sign = services.get("sign")
            if sign:
                payload["receipt_jws"] = sign(signed_receipts.build_evidence_claims(payload, kind=kind))
                payload["jwks_url"] = b + "/.well-known/jwks.json"

        if skill == "msp-pilot":
            offer = services_offer(b, domain=domain, price_usd=price_usd, sector_price_usd=sector_price_usd)
            pilot = dict(offer["msp_pilot"], mcp=b + "/mcp", services=offer)
            _audit("msp-pilot", domain or "", "ok")
            return _reply(
                "IT-Dienstleister / MSP Partner Pilot (290 EUR one-time, 3 partner slots): up to 50 client hostnames "
                "measured for post-quantum TLS (X25519MLKEM768 / BSI TR-02102-2 / NIS2), delivered as a German Ampel "
                "PDF report (optional partner white-label logo) + offline-verifiable Ed25519 JWS signed receipts. "
                f"Book or request details (no upfront payment): {pilot['url']} (DE) / {pilot['url_en']} (EN). "
                f"Free archived single-host sample PDF: {pilot['sample_pdf']}.",
                pilot)
        if skill == "tls-attestation":
            offer = services_offer(b, domain=domain, price_usd=price_usd, sector_price_usd=sector_price_usd)
            att = dict(offer["tls_attestation"], example_request={"domain": domain or "example.com"},
                       mcp=b + "/mcp", services=offer)
            _audit("tls-attestation", domain or "", "ok")
            return _reply(
                "Auditor-Ready TLS Attestation (5.00 USDC on Base via x402 v2; NOT read-only — triggers a fresh "
                "port-443 TLS measurement and requires an x402-compatible client with a funded buyer wallet and "
                "payment authorization; unpaid calls return HTTP 402 and never charge). Delivers an Ed25519 JWS "
                "receipt, CycloneDX 1.6 CBOM, printable Auditor PDF, and bundle signature via POST "
                f"{b}/api/v1/attestation or MCP tool get_tls_attestation. Preview free archived samples first: "
                f"{att['sample_pdf']} and {att['sample_json']}. External observation, not a compliance certification.",
                att)
        if skill == "agent-affiliate":
            offer = services_offer(b, domain=domain, price_usd=price_usd, sector_price_usd=sector_price_usd)
            data = dict(offer["partner_affiliate"], mcp=b + "/mcp", services=offer)
            _audit("agent-affiliate", domain or "", "ok")
            return _reply(
                "AI Agent Affiliate Programme: call MCP tool register_agent_affiliate or POST "
                f"{b}/api/v1/agent/affiliate/register with name, contact_email, payout_method (usdc|paypal), "
                "payout_destination, and consent_terms=true to receive an instant ?ref=CODE link. Earns 30% of "
                "monitoring payments for 12 months and 20% of one-time reports/audits; paid monthly manually by "
                f"the owner after a 30-day hold (min $50). Terms: {b}/partners?lang=en", data)
        if skill == "paid-data":
            offer = services_offer(b, domain=domain, price_usd=price_usd, sector_price_usd=sector_price_usd)
            data = dict(offer, mcp=b + "/mcp")
            _audit("paid-data", domain or "", "ok")
            return _reply(
                "Paid data is bought per call with x402 (USDC on Base) over HTTP or MCP (unpaid calls return the price "
                "challenge and never charge): Auditor-Ready PDF + CycloneDX CBOM attestation (5.00 USDC; free sample "
                f"PDF at {offer['tls_attestation']['sample_pdf']}), full report, or weekly sector snapshot. Also "
                f"available: 14-day free daily monitoring trial (Starter 29 EUR/mo, Business 99 EUR/mo at "
                f"{offer['monitoring']['trial_url']}), MSP Partner Pilot (290 EUR at {offer['msp_pilot']['url']}), and "
                f"organization compliance audit (490 EUR at {offer['organization_audit']['url']}).", data)
        if not domain:
            _audit(skill, "", "missing_domain")
            return _reply(
                "Send a public hostname, e.g. 'Is example.com post-quantum ready?' or {\"skill\":\"tls-scan\",\"domain\":\"example.com\"}.",
                {"skills": list(VALID_SKILLS),
                 "services": services_offer(b, price_usd=price_usd, sector_price_usd=sector_price_usd)})
        try:
            domain = quantum_vuln_scanner.normalize_domain(domain)
            if skill == "tls-scan":
                scan_id, raw = services["scan"](domain, "a2a")
                offer = services_offer(b, domain=domain, scan_id=scan_id, price_usd=price_usd, sector_price_usd=sector_price_usd)
                data = dict(services["summary"](scan_id, raw), services=offer)
                _attach_receipt(data, "tls-scan")
                _, _, _, dual = receipts.issue_and_store_receipt(services, raw, scan_id=scan_id, endpoint_type="a2a")
                data.update(dual)
                pq = data.get("post_quantum_key_exchange")
                text = (f"{domain}: grade {data.get('grade')}, key exchange {data.get('key_exchange_group') or 'unknown'}"
                        f"{' (post-quantum)' if pq else ''}. Full report via x402: use scan_id {scan_id}. "
                        f"Daily monitoring (14-day free trial, from 29 EUR/mo): {offer['monitoring']['trial_url']}")
                _audit("tls-scan", domain, "ok")
            else:
                offer = services_offer(b, domain=domain, price_usd=price_usd, sector_price_usd=sector_price_usd)
                data = dict(badge_evidence.for_domain(services["db"](), domain),
                            verification_url=b + "/verify/" + domain, services=offer)
                _attach_receipt(data, "tls-evidence")
                if data.get("state") == "not_scanned":
                    text = f"No stored evidence for {domain} yet (not proof of anything). Ask to 'scan {domain}' for a measurement."
                else:
                    obs = {"observed_pq": "negotiates post-quantum key exchange", "observed_classical": "classical key exchange only",
                           "undetermined": "undetermined"}.get(data.get("observation_status"), "see data")
                    text = (f"{domain}: {obs} (group {data.get('group') or 'unknown'}, grade {data.get('grade')}), "
                            f"checked {data.get('checked_at')}, evidence {data.get('state')}. Ask to 'scan' for a fresh measurement. "
                            f"Daily monitoring (14-day free trial): {offer['monitoring']['trial_url']}")
                _audit("tls-evidence", domain, "ok")
        except quantum_vuln_scanner.ScanError as exc:
            _audit(skill, domain, f"error:{exc.code}")
            return _reply(f"Could not measure {domain}: {exc}", {"error": exc.code})
        except HTTPException as exc:
            if exc.code == 429:
                stored = dict(badge_evidence.for_domain(services["db"](), domain), verification_url=b + "/verify/" + domain)
                _attach_receipt(stored, "tls-evidence")
                _audit(skill, domain, "rate_limited")
                return _reply(
                    "Scan rate limit reached; returning the latest stored evidence instead (no new probe was made).",
                    {"error": "rate_limited", "retry_after_seconds": 3600, "stored_evidence": stored})
            raise
        return _reply(text, data)
