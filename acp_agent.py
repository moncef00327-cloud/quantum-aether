"""ACP (Agent Communication Protocol, IBM BeeAI -> Linux Foundation A2A) REST compatibility layer.

Inbound-only synchronous REST endpoints so ACP-compatible orchestrators can discover Quantum Aether
offline via Agent Manifests and invoke the same TLS evidence / scan / paid-data skills as A2A & MCP:
  GET  /acp/agents                 list available agents (manifest array)
  GET  /acp/agents/<name>          single agent manifest
  POST /acp/runs                   synchronous run returning MIME-typed parts + Ed25519 JWS receipt
"""
import datetime as dt
import json
import re
import uuid

from flask import current_app, jsonify, request
from werkzeug.exceptions import HTTPException

import a2a_agent
import agent_audit
import badge_evidence
import quantum_vuln_scanner
import receipts
import signed_receipts

AGENT_NAME = "quantum-aether"
ACP_VERSION = "0.2.0"
PAID_WORDS = re.compile(r"\b(buy|price|pay|report|x402|sector|snapshot|شراء|سعر|تقرير)\b", re.I)


def manifest(base: str, version: str) -> dict:
    return {
        "name": AGENT_NAME,
        "description": (
            "Post-quantum TLS readiness and evidence agent (X25519MLKEM768 / ML-KEM, FIPS 203). "
            "Reads stored TLS evidence (free, read-only), runs rate-limited port-443 probes (free), "
            "and attaches Ed25519 JWS signed scan receipts verifiable via /.well-known/jwks.json. "
            "External observations, not compliance certifications."
        ),
        "input_content_types": ["text/plain", "application/json"],
        "output_content_types": ["application/json", "text/plain"],
        "metadata": {
            "protocol": "acp",
            "protocol_version": ACP_VERSION,
            "version": version,
            "provider": {"name": "Quantum Aether", "url": base},
            "documentation_url": f"{base}/agents?lang=en",
            "a2a_agent_card": f"{base}/.well-known/agent-card.json",
            "a2a_endpoint": f"{base}/a2a",
            "mcp_endpoint": f"{base}/mcp",
            "jwks_uri": f"{base}/.well-known/jwks.json",
            "capabilities": {"streaming": False, "async_runs": False, "signed_receipts": True},
            "skills": ["tls-evidence", "tls-scan", "paid-data"],
            "services": a2a_agent.services_offer(base),
        },
    }


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_input(body: dict):
    """Extract (skill, domain) from ACP RunCreateRequest input messages/parts or direct JSON fields."""
    texts, data = [], {}
    if isinstance(body.get("skill"), str):
        data["skill"] = body["skill"]
    if isinstance(body.get("domain"), str):
        data["domain"] = body["domain"]
    raw_input = body.get("input")
    if isinstance(raw_input, str):
        texts.append(raw_input[:2000])
    elif isinstance(raw_input, dict):
        raw_input = [raw_input]
    if isinstance(raw_input, list):
        for item in raw_input[:16]:
            if isinstance(item, str):
                texts.append(item[:2000])
                continue
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("content"), str) and "parts" not in item:
                texts.append(item["content"][:2000])
            for part in (item.get("parts") or [])[:16]:
                if not isinstance(part, dict):
                    continue
                ctype = str(part.get("content_type") or "text/plain").split(";")[0].strip().lower()
                content = part.get("content")
                if ctype == "application/json":
                    if isinstance(content, dict):
                        data.update(content)
                    elif isinstance(content, str):
                        try:
                            parsed = json.loads(content[:4000])
                            if isinstance(parsed, dict):
                                data.update(parsed)
                        except ValueError:
                            texts.append(content[:2000])
                elif isinstance(content, str):
                    texts.append(content[:2000])
    joined = " ".join(texts)
    skill = data.get("skill") if data.get("skill") in ("tls-evidence", "tls-scan", "paid-data") else None
    domain = data.get("domain") if isinstance(data.get("domain"), str) else None
    if not domain:
        m = a2a_agent.HOST_RE.search(joined)
        domain = m.group(1) if m else None
    if not skill:
        if PAID_WORDS.search(joined) and not domain:
            skill = "paid-data"
        elif a2a_agent.SCAN_WORDS.search(joined):
            skill = "tls-scan"
        else:
            skill = "tls-evidence"
    return skill, domain


def _run_response(run_id: str, created_at: str, text: str, data: dict, status: str = "completed"):
    parts = [
        {"content_type": "text/plain", "content": text},
        {"content_type": "application/json", "content": json.dumps(data, ensure_ascii=False), "data": data},
    ]
    return jsonify({
        "run_id": run_id,
        "agent_name": AGENT_NAME,
        "status": status,
        "created_at": created_at,
        "finished_at": _utc_now(),
        "output": [{"role": "agent", "parts": parts}],
    })


def register(bp, services, version: str):
    base = services["base"]

    def _audit(action: str, domain: str = "", status: str = "ok"):
        fn = services.get("audit")
        if fn:
            fn("acp", action, agent_audit.client_label(request.headers), domain or "", status)

    def _attach_receipt(data: dict, kind: str, b: str):
        sign = services.get("sign")
        if sign:
            data["receipt_jws"] = sign(signed_receipts.build_evidence_claims(data, kind=kind))
            data["jwks_url"] = f"{b}/.well-known/jwks.json"

    @bp.get("/acp/agents")
    def acp_list_agents():
        resp = jsonify({"agents": [manifest(base(), version)]})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp

    @bp.get("/acp/agents/<name>")
    def acp_get_agent(name):
        if name != AGENT_NAME:
            resp = jsonify({"error": "agent_not_found", "available_agents": [AGENT_NAME]})
            resp.headers["Access-Control-Allow-Origin"] = "*"
            return resp, 404
        resp = jsonify(manifest(base(), version))
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp

    @bp.route("/acp/runs", methods=["POST", "OPTIONS"])
    def acp_create_run():
        if request.method == "OPTIONS":
            resp = current_app.make_response(("", 204))
            resp.headers.update({
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            })
            return resp
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"error": "invalid_request", "message": "Expected a JSON object"}), 400
        req_agent = body.get("agent_name")
        if req_agent is not None and req_agent != AGENT_NAME:
            return jsonify({"error": "agent_not_found", "available_agents": [AGENT_NAME]}), 404
        mode = body.get("mode", "sync")
        if mode != "sync":
            return jsonify({"error": "unsupported_mode", "message": "Only mode='sync' is supported"}), 400

        run_id = str(uuid.uuid4())
        created_at = _utc_now()
        skill, domain = _parse_input(body)
        b = base()
        price_usd = str(current_app.config["PRICE"])
        sector_price_usd = str(current_app.config.get("X402_SECTOR_PRICE") or "0.50")

        if skill == "paid-data":
            offer = a2a_agent.services_offer(b, domain=domain, price_usd=price_usd, sector_price_usd=sector_price_usd)
            data = dict(offer, mcp=b + "/mcp", a2a=b + "/a2a", jwks_url=f"{b}/.well-known/jwks.json")
            _audit("paid-data", domain or "", "ok")
            text = (
                "Paid data is bought per call with x402 (USDC on Base) over HTTP or MCP (unpaid calls return the price "
                "challenge and never charge). Also available: 14-day free daily monitoring trial (Starter 29 EUR/mo, "
                f"Business 99 EUR/mo at {offer['monitoring']['trial_url']}) and organization compliance audit "
                f"(490 EUR at {offer['organization_audit']['url']})."
            )
            resp = _run_response(run_id, created_at, text, data)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Cache-Control"] = "no-store"
            return resp

        if not domain:
            _audit(skill, "", "missing_domain")
            resp = _run_response(
                run_id,
                created_at,
                "Send a public hostname in input parts, e.g. 'Is example.com post-quantum ready?' or {\"skill\":\"tls-scan\",\"domain\":\"example.com\"}.",
                {"skills": ["tls-evidence", "tls-scan", "paid-data"],
                 "services": a2a_agent.services_offer(b, price_usd=price_usd, sector_price_usd=sector_price_usd)},
            )
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Cache-Control"] = "no-store"
            return resp

        try:
            domain = quantum_vuln_scanner.normalize_domain(domain)
            if skill == "tls-scan":
                scan_id, raw = services["scan"](domain, "acp")
                offer = a2a_agent.services_offer(b, domain=domain, scan_id=scan_id, price_usd=price_usd, sector_price_usd=sector_price_usd)
                data = dict(services["summary"](scan_id, raw), services=offer)
                _attach_receipt(data, "tls-scan", b)
                _, _, _, dual = receipts.issue_and_store_receipt(services, raw, scan_id=scan_id, endpoint_type="acp")
                data.update(dual)
                pq = data.get("post_quantum_key_exchange")
                text = (
                    f"{domain}: grade {data.get('grade')}, key exchange {data.get('key_exchange_group') or 'unknown'}"
                    f"{' (post-quantum)' if pq else ''}. Signed Ed25519 JWS receipt included (JWKS: {b}/.well-known/jwks.json). "
                    f"Daily monitoring (14-day free trial, from 29 EUR/mo): {offer['monitoring']['trial_url']}"
                )
                _audit("tls-scan", domain, "ok")
            else:
                offer = a2a_agent.services_offer(b, domain=domain, price_usd=price_usd, sector_price_usd=sector_price_usd)
                data = dict(badge_evidence.for_domain(services["db"](), domain),
                            verification_url=b + "/verify/" + domain, services=offer)
                _attach_receipt(data, "tls-evidence", b)
                if data.get("state") == "not_scanned":
                    text = f"No stored evidence for {domain} yet (not proof of anything). Ask to 'scan {domain}' for a measurement."
                else:
                    obs = {"observed_pq": "negotiates post-quantum key exchange",
                           "observed_classical": "classical key exchange only",
                           "undetermined": "undetermined"}.get(data.get("observation_status"), "see data")
                    text = (
                        f"{domain}: {obs} (group {data.get('group') or 'unknown'}, grade {data.get('grade')}), "
                        f"checked {data.get('checked_at')}, evidence {data.get('state')}. Signed Ed25519 JWS receipt included. "
                        f"Daily monitoring (14-day free trial): {offer['monitoring']['trial_url']}"
                    )
                _audit("tls-evidence", domain, "ok")
        except quantum_vuln_scanner.ScanError as exc:
            _audit(skill, domain, f"error:{exc.code}")
            resp = _run_response(run_id, created_at, f"Could not measure {domain}: {exc}", {"error": exc.code}, status="failed")
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Cache-Control"] = "no-store"
            return resp
        except HTTPException as exc:
            if exc.code == 429:
                stored = dict(badge_evidence.for_domain(services["db"](), domain), verification_url=b + "/verify/" + domain)
                _attach_receipt(stored, "tls-evidence", b)
                _audit(skill, domain, "rate_limited")
                resp = _run_response(
                    run_id,
                    created_at,
                    "Scan rate limit reached; returning the latest stored evidence instead (no new probe was made).",
                    {"error": "rate_limited", "retry_after_seconds": 3600, "stored_evidence": stored},
                )
                resp.headers["Access-Control-Allow-Origin"] = "*"
                resp.headers["Cache-Control"] = "no-store"
                return resp
            raise

        resp = _run_response(run_id, created_at, text, data)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "no-store"
        return resp
