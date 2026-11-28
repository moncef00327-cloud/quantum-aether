"""Universal Commerce Protocol (UCP, 2026-08-25) profile, catalog & checkout handoff for Quantum Aether.

Exposes:
  * GET  /.well-known/ucp          (and /.well-known/ucp.json alias) — canonical UCP merchant profile
                                   with MCP (/mcp) as the primary commerce transport binding, plus REST and A2A.
  * GET  /api/v1/ucp/catalog       — machine-readable catalog of all existing Quantum Aether SKUs & prices.
  * POST /api/v1/ucp/checkout-sessions — stateless checkout session handoff returning exact price,
                                         continue_url, and MCP / x402 execution descriptors.

Never alters any existing payment settings or prices. Pure stdlib, zero external dependencies.
"""
from __future__ import annotations

import datetime as dt
import re
import uuid
from urllib.parse import quote

from flask import current_app, jsonify, request

import agent_audit
import x402_attestation
import x402_micro
import x402_pay

UCP_VERSION = "2026-08-25"
UCP_SPEC_BASE = f"https://ucp.dev/{UCP_VERSION}"


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _x402_enabled(cfg) -> bool:
    return bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", str(cfg.get("USDC_BASE_ADDR") or "")))


def catalog_items(base: str, cfg) -> list[dict]:
    """Return every existing Quantum Aether SKU with exact configured prices (zero price changes)."""
    b = base.rstrip("/")
    report_price = str(cfg.get("PRICE", "49"))
    report_ccy = str(cfg.get("CURRENCY", "USD"))
    sector_price = str(cfg.get("X402_SECTOR_PRICE") or "0.50")
    x402_on = _x402_enabled(cfg)

    return [
        {
            "id": "qa-batch-scan-10",
            "category": "micro_x402",
            "title": "Batch Post-Quantum TLS Scan (up to 10 domains)",
            "description": "Unthrottled parallel TLS 1.3 & X25519MLKEM768 scan of up to 10 public domains with Ed25519 JWS signed receipts and hidden server-preference downgrade detection.",
            "price": x402_micro.BATCH_PRICE_USD,
            "currency": "USDC",
            "billing": "one_time_per_call",
            "autonomous_agent_ready": x402_on,
            "mcp_tool": "batch_scan_tls",
            "http_endpoint": f"{b}/api/v1/x402/batch-scan",
            "checkout_url": f"{b}/agents?lang=en#mcp",
            "payment_methods": ["x402_base_usdc"],
            "free_alternative": f"POST {b}/api/v1/scan (single domain, rate-limited)",
        },
        {
            "id": "qa-live-cbom",
            "category": "micro_x402",
            "title": "Live CycloneDX 1.6 CBOM + Signed TLS Receipt",
            "description": "Fresh live port-443 PQ-TLS measurement + CycloneDX 1.6 Cryptographic Bill of Materials (CBOM) JSON + offline-verifiable Ed25519 JWS receipt.",
            "price": x402_micro.CBOM_PRICE_USD,
            "currency": "USDC",
            "billing": "one_time_per_call",
            "autonomous_agent_ready": x402_on,
            "mcp_tool": "get_live_cbom",
            "http_endpoint": f"{b}/api/v1/x402/cbom",
            "checkout_url": f"{b}/agents?lang=en#mcp",
            "payment_methods": ["x402_base_usdc"],
            "free_alternative": f"{b}/api/v1/attestation/sample",
        },
        {
            "id": "qa-sector-snapshot",
            "category": "micro_x402",
            "title": "Weekly Sector Post-Quantum TLS Snapshot",
            "description": "Read-only weekly adoption snapshot across an entire sector watch list (European/MENA banks, DACH government, cyber agencies, telecoms, insurers).",
            "price": sector_price,
            "currency": "USDC",
            "billing": "one_time_per_call",
            "autonomous_agent_ready": x402_on,
            "mcp_tool": "get_sector_snapshot",
            "http_endpoint": f"{b}/api/v1/agent/sector/{{sector}}",
            "checkout_url": f"{b}/adoption?lang=en",
            "payment_methods": ["x402_base_usdc"],
            "free_alternative": f"{b}/adoption?lang=en",
        },
        {
            "id": "qa-tls-attestation",
            "category": "reports",
            "title": "Auditor-Ready Signed PDF + CycloneDX 1.6 CBOM Attestation",
            "description": "Fresh live PQ-TLS measurement + Ed25519 JWS receipt + CycloneDX 1.6 CBOM + printable Auditor PDF with SHA-256 + bundle JWS signature.",
            "price": x402_attestation.PRICE_USD,
            "currency": "USDC",
            "billing": "one_time_per_call",
            "autonomous_agent_ready": x402_on,
            "mcp_tool": "get_tls_attestation",
            "http_endpoint": f"{b}/api/v1/attestation",
            "checkout_url": f"{b}/agents?lang=en#attestation",
            "sample_url": f"{b}/api/v1/attestation/sample.pdf",
            "payment_methods": ["x402_base_usdc"],
            "free_alternative": f"{b}/api/v1/attestation/sample.pdf",
        },
        {
            "id": "qa-full-report",
            "category": "reports",
            "title": "Full Post-Quantum TLS Remediation Report",
            "description": "Complete remediation report for a scanned domain with server configuration guidance, findings, and certificate breakdown.",
            "price": report_price,
            "currency": report_ccy,
            "billing": "one_time",
            "autonomous_agent_ready": x402_on,
            "mcp_tool": "get_full_report",
            "http_endpoint": f"{b}/api/v1/agent/report/{{scan_id}}",
            "checkout_url": f"{b}/pricing?lang=en",
            "sample_url": f"{b}/sample-report?lang=en",
            "payment_methods": ["x402_base_usdc", "paypal", "polygon_usdt", "arbitrum_usdc"],
            "free_alternative": f"{b}/sample-report?lang=en",
        },
        {
            "id": "qa-monitoring-starter",
            "category": "subscriptions",
            "title": "Daily PQ-TLS Monitoring — Starter (up to 10 domains)",
            "description": "Automated daily multi-IP post-quantum TLS regression & certificate monitoring with email alerts and 400-day CSV history. Starts with a 14-day free trial (no card).",
            "price": "29.00",
            "currency": "EUR",
            "billing": "monthly",
            "free_trial_days": 14,
            "autonomous_agent_ready": False,
            "human_signup_required": True,
            "mcp_tool": None,
            "http_endpoint": None,
            "checkout_url": f"{b}/monitoring#trial-form",
            "payment_methods": ["paypal"],
            "free_alternative": f"{b}/monitoring#trial-form",
        },
        {
            "id": "qa-monitoring-business",
            "category": "subscriptions",
            "title": "Daily PQ-TLS Monitoring — Business (up to 100 domains)",
            "description": "Automated daily PQ-TLS regression monitoring + weekly CT-log asset discovery across up to 100 domains with 400-day audit CSV history.",
            "price": "99.00",
            "currency": "EUR",
            "billing": "monthly",
            "free_trial_days": 14,
            "autonomous_agent_ready": False,
            "human_signup_required": True,
            "mcp_tool": None,
            "http_endpoint": None,
            "checkout_url": f"{b}/monitoring#trial-form",
            "payment_methods": ["paypal"],
            "free_alternative": f"{b}/monitoring#trial-form",
        },
        {
            "id": "qa-msp-pilot",
            "category": "enterprise",
            "title": "IT-Dienstleister / MSP Partner Pilot (up to 50 hostnames)",
            "description": "Fixed-scope partner pilot: up to 50 client hostnames measured for X25519MLKEM768 / BSI TR-02102-2 / NIS2, German Ampel PDF + Ed25519 signed receipts + optional white-label logo.",
            "price": "290.00",
            "currency": "EUR",
            "billing": "one_time",
            "autonomous_agent_ready": False,
            "human_signup_required": True,
            "mcp_tool": None,
            "http_endpoint": None,
            "checkout_url": f"{b}/partners?lang=de#msp-pilot",
            "sample_url": f"{b}/api/v1/attestation/sample.pdf",
            "payment_methods": ["invoice"],
            "free_alternative": f"{b}/api/v1/attestation/sample.pdf",
        },
        {
            "id": "qa-org-audit",
            "category": "enterprise",
            "title": "Organization Subdomain PQ-TLS & Compliance Audit",
            "description": "Estate-wide subdomain TLS inventory and SAMA / DORA / NIS2 post-quantum readiness audit delivered as an executive PDF report.",
            "price": "490.00",
            "currency": "EUR",
            "billing": "one_time",
            "autonomous_agent_ready": False,
            "human_signup_required": True,
            "mcp_tool": None,
            "http_endpoint": None,
            "checkout_url": f"{b}/audit?lang=en",
            "payment_methods": ["invoice"],
            "free_alternative": f"{b}/sample-report?lang=en",
        },
    ]


def catalog_payload(base: str, cfg, *, category: str = "all") -> dict:
    b = base.rstrip("/")
    items = catalog_items(b, cfg)
    cat = (category or "all").strip().lower()
    if cat != "all":
        items = [it for it in items if it["category"] == cat]
    return {
        "ucp_version": UCP_VERSION,
        "merchant": {"name": "Quantum Aether", "url": b, "mcp_endpoint": f"{b}/mcp"},
        "category": cat,
        "count": len(items),
        "items": items,
        "checkout_sessions_endpoint": f"{b}/api/v1/ucp/checkout-sessions",
        "ucp_profile": f"{b}/.well-known/ucp",
        "x402_discovery": f"{b}/.well-known/x402",
        "note": "External point-in-time port-443 TLS observations, not legal compliance certifications.",
    }


def ucp_profile(base: str, cfg) -> dict:
    """Canonical /.well-known/ucp discovery profile placing MCP as the primary commerce transport."""
    b = base.rstrip("/")
    pay_to = x402_pay.receiver() or ""
    handlers = [
        {
            "id": "x402_base_usdc",
            "name": "x402 v2 Exact USDC on Base",
            "version": "2",
            "enabled": bool(pay_to),
            "spec": "https://x402.org",
            "config": {
                "network": x402_pay.NETWORK,
                "asset": x402_pay.ASSET,
                "scheme": "exact",
                "payTo": pay_to,
                "facilitator": x402_pay.FACILITATOR,
                "discovery_url": f"{b}/.well-known/x402",
            },
        },
        {
            "id": "paypal",
            "name": "PayPal Checkout",
            "enabled": bool(cfg.get("PAYPAL_CLIENT_ID") and cfg.get("PAYPAL_CLIENT_SECRET")),
            "config": {"checkout_url": f"{b}/pricing?lang=en"},
        },
        {
            "id": "polygon_usdt",
            "name": "Direct Stablecoin Transfer (Polygon USDT / Base & Arbitrum USDC)",
            "enabled": True,
            "config": {"mcp_tools": ["create_full_report_order", "verify_full_report_payment"]},
        },
        {
            "id": "invoice",
            "name": "B2B Invoice (MSP Pilot & Organization Audit)",
            "enabled": True,
            "config": {"msp_pilot_url": f"{b}/partners?lang=de#msp-pilot", "audit_url": f"{b}/audit?lang=en"},
        },
    ]

    return {
        "ucp": {
            "version": UCP_VERSION,
            "services": {
                "dev.ucp.shopping": [
                    {
                        "version": UCP_VERSION,
                        "spec": f"{UCP_SPEC_BASE}/specification/overview",
                        "transport": "mcp",
                        "endpoint": f"{b}/mcp",
                        "schema": f"{UCP_SPEC_BASE}/services/shopping/mcp.openrpc.json",
                        "server_card": f"{b}/.well-known/mcp/server-card.json",
                        "preferred": True,
                    },
                    {
                        "version": UCP_VERSION,
                        "spec": f"{UCP_SPEC_BASE}/specification/overview",
                        "transport": "rest",
                        "endpoint": f"{b}/api/v1/ucp",
                        "schema": f"{b}/openapi.json",
                    },
                    {
                        "version": UCP_VERSION,
                        "spec": f"{UCP_SPEC_BASE}/specification/overview",
                        "transport": "a2a",
                        "endpoint": f"{b}/.well-known/agent-card.json",
                    },
                ]
            },
            "capabilities": {
                "dev.ucp.shopping.catalog": [
                    {
                        "version": UCP_VERSION,
                        "spec": f"{UCP_SPEC_BASE}/specification/shopping/catalog",
                        "schema": f"{UCP_SPEC_BASE}/schemas/shopping/catalog.json",
                        "endpoint": f"{b}/api/v1/ucp/catalog",
                        "mcp_tool": "get_commerce_catalog",
                    }
                ],
                "dev.ucp.shopping.checkout": [
                    {
                        "version": UCP_VERSION,
                        "spec": f"{UCP_SPEC_BASE}/specification/shopping/checkout",
                        "schema": f"{UCP_SPEC_BASE}/schemas/shopping/checkout.json",
                        "endpoint": f"{b}/api/v1/ucp/checkout-sessions",
                    }
                ],
            },
            "payment_handlers": handlers,
        },
        "merchant": {
            "name": "Quantum Aether",
            "description": "Post-quantum TLS readiness observatory (X25519MLKEM768), Ed25519 signed receipts, CycloneDX 1.6 CBOM, daily PQ-TLS monitoring, and IT-Dienstleister MSP Pilot.",
            "url": b,
            "support_email": "contact@mail.ather-quantum.com",
            "terms_url": f"{b}/agb?lang=en",
            "privacy_url": f"{b}/datenschutz?lang=en",
            "jwks_uri": f"{b}/.well-known/jwks.json",
            "a2ui_extension": "https://a2ui.org/a2a-extension/a2ui/v0.8",
            "acp_agents": f"{b}/acp/agents",
        },
    }


def register(bp, services):
    base = services["base"]

    def _audit(action, dom="", status="ok"):
        fn = services.get("audit")
        if fn:
            fn("ucp", action, agent_audit.client_label(request.headers), dom or "", status)

    @bp.get("/.well-known/ucp")
    @bp.get("/.well-known/ucp.json")
    def well_known_ucp():
        b = base().rstrip("/")
        _audit("profile", "", "ok")
        resp = jsonify(ucp_profile(b, current_app.config))
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "public, max-age=300"
        resp.headers["Link"] = f'<{b}/.well-known/ucp>; rel="canonical"'
        return resp

    @bp.get("/api/v1/ucp/catalog")
    def ucp_catalog():
        cat = (request.args.get("category") or "all").strip().lower()
        _audit("catalog", cat, "ok")
        resp = jsonify(catalog_payload(base(), current_app.config, category=cat))
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "public, max-age=300"
        return resp

    @bp.route("/api/v1/ucp/checkout-sessions", methods=["POST", "OPTIONS"])
    def ucp_checkout_sessions():
        if request.method == "OPTIONS":
            resp = current_app.make_response(("", 204))
            resp.headers.update({
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, UCP-Agent",
            })
            return resp

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="invalid_request", message="JSON object body is required"), 400

        sku = body.get("sku") or body.get("item_id")
        if not sku and isinstance(body.get("line_items"), list) and body["line_items"]:
            first = body["line_items"][0]
            if isinstance(first, dict):
                item_obj = first.get("item") if isinstance(first.get("item"), dict) else first
                sku = item_obj.get("id") or item_obj.get("sku")
        sku = str(sku or "").strip()

        b = base().rstrip("/")
        items_by_id = {it["id"]: it for it in catalog_items(b, current_app.config)}
        item = items_by_id.get(sku)
        if not item:
            return jsonify(
                error="unknown_sku",
                message=f"Unknown SKU '{sku}'. Query GET {b}/api/v1/ucp/catalog for available items.",
                available_skus=list(items_by_id.keys()),
            ), 400

        domain = str(body.get("domain") or "").strip()
        scan_id = str(body.get("scan_id") or "").strip()
        sector = str(body.get("sector") or "banks-europe").strip()

        continue_url = item["checkout_url"]
        if sku in ("qa-monitoring-starter", "qa-monitoring-business") and domain:
            continue_url = f"{b}/monitoring?domain={quote(domain, safe='')}#trial-form"
        elif sku == "qa-org-audit" and domain:
            continue_url = f"{b}/audit?domain={quote(domain, safe='')}"
        elif sku == "qa-full-report" and scan_id:
            continue_url = f"{b}/scan/{quote(scan_id, safe='')}"

        mcp_exec = None
        if item.get("mcp_tool"):
            args_hint = {}
            if sku == "qa-batch-scan-10":
                args_hint = {"domains": [domain] if domain else ["cloudflare.com", "github.com"]}
            elif sku in ("qa-live-cbom", "qa-tls-attestation"):
                args_hint = {"domain": domain or "example.com"}
            elif sku == "qa-sector-snapshot":
                args_hint = {"sector": sector}
            elif sku == "qa-full-report":
                args_hint = {"scan_id": scan_id or "<scan_id_from_scan_tls>"}
            mcp_exec = {
                "endpoint": f"{b}/mcp",
                "transport": "streamable-http",
                "tool": item["mcp_tool"],
                "arguments": args_hint,
                "payment_protocol": "x402 v2 exact (Base USDC via _meta['x402/payment'])",
            }

        session = {
            "id": "ucp_chk_" + uuid.uuid4().hex[:16],
            "ucp": {"version": UCP_VERSION, "capabilities": ["dev.ucp.shopping.checkout"]},
            "status": "ready_for_complete",
            "created_at": _utc_now(),
            "currency": item["currency"],
            "line_items": [{"item": {"id": item["id"], "title": item["title"]}, "quantity": 1, "unit_price": item["price"]}],
            "totals": {"subtotal": item["price"], "total": item["price"], "currency": item["currency"]},
            "payment_methods": item["payment_methods"],
            "continue_url": continue_url,
            "mcp_execution": mcp_exec,
            "x402_endpoint": item.get("http_endpoint"),
            "free_alternative": item.get("free_alternative"),
            "note": "No funds have been charged. Complete via MCP/x402 with explicit spend authorization or open continue_url.",
        }
        _audit("checkout_session", sku, "ok")
        resp = jsonify(session)
        resp.status_code = 201
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "no-store"
        return resp
