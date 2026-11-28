"""Universal Commerce Protocol (UCP v2026-08-25) conformant profile, MCP server (/ucp/mcp) & REST API (/api/v1/ucp).

Implements official UCP 2026-08-25 capabilities:
  * dev.ucp.shopping.catalog.search  (search_catalog)
  * dev.ucp.shopping.catalog.lookup  (lookup_catalog, get_product)
  * dev.ucp.shopping.checkout        (create_checkout, get_checkout, update_checkout, complete_checkout, cancel_checkout)

Transports:
  * MCP  : POST /ucp/mcp (exactly the 8 spec tools; does NOT modify /mcp or /mcp/free)
  * REST : /api/v1/ucp/catalog/{search,lookup,product} and /api/v1/ucp/checkout-sessions[/{id}[/{complete,cancel}]]
  * A2A  : /.well-known/agent-card.json

Also serves:
  * GET /.well-known/ucp and /.well-known/ucp.json (identical, public, application/json)
  * GET /ucp/handlers/{x402,paypal,stablecoin_transfer,invoice}[.json] (authority-bound payment handler specs & schemas)
  * GET /api/v1/ucp/catalog (legacy endpoint preserved with "deprecated": true and links to new endpoints)

HARD CONSTRAINTS:
  * Never alters any price value, product, or payment configuration.
  * Every UCP price uses exact Decimal -> int minor units and ISO 4217 currencies (USD / EUR).
"""
from __future__ import annotations

import base64
import datetime as dt
from decimal import Decimal, ROUND_HALF_UP
import json
import re
import sqlite3
import uuid
from urllib.parse import quote, urlsplit

from flask import Response, current_app, jsonify, request

import agent_audit
import receipts
import x402_attestation
import x402_micro
import x402_pay

UCP_VERSION = "2026-08-25"
UCP_SPEC_BASE = f"https://ucp.dev/{UCP_VERSION}"
UCP_PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26")

CAP_SEARCH = "dev.ucp.shopping.catalog.search"
CAP_LOOKUP = "dev.ucp.shopping.catalog.lookup"
CAP_CHECKOUT = "dev.ucp.shopping.checkout"

HANDLER_NS = {
    "x402": "com.ather-quantum.x402",
    "paypal": "com.ather-quantum.paypal",
    "stablecoin_transfer": "com.ather-quantum.stablecoin_transfer",
    "invoice": "com.ather-quantum.invoice",
}

HANDLER_IDS = {
    "x402": "x402_base_usdc",
    "paypal": "paypal",
    "stablecoin_transfer": "stablecoin_transfer",
    "invoice": "invoice",
}

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _expires_at(hours: int = 6) -> str:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_minor_units(amount_str: str) -> int:
    """Convert a decimal major-unit price string to integer ISO 4217 minor units using Decimal (never float)."""
    dec = Decimal(str(amount_str).strip())
    minor = (dec * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(minor)


def _x402_enabled(cfg) -> bool:
    return bool(re.fullmatch(r"0x[0-9a-fA-F]{40}", str(cfg.get("USDC_BASE_ADDR") or "")))


def _iso_currency(raw_ccy: str) -> str:
    ccy = str(raw_ccy or "USD").strip().upper()
    if ccy == "USDC":
        return "USD"
    if re.fullmatch(r"[A-Z]{3}", ccy):
        return ccy
    return "USD"


def _valid_http_uri(val) -> bool:
    if not isinstance(val, str) or not val.strip():
        return False
    p = urlsplit(val.strip())
    return p.scheme in ("http", "https") and bool(p.netloc)


def _valid_uuid(val) -> bool:
    return isinstance(val, str) and bool(UUID_RE.fullmatch(val.strip()))


# ---------------------------------------------------------------------------
# 1. Product Catalog (Legacy + Official UCP 2026-08-25 Models)
# ---------------------------------------------------------------------------

def catalog_items(base: str, cfg) -> list[dict]:
    """Legacy catalog item list (preserved verbatim for GET /api/v1/ucp/catalog & /admin/agents-live)."""
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


def _product_handler_ids(raw_item: dict) -> list[str]:
    pm = raw_item.get("payment_methods") or []
    out = []
    if "x402_base_usdc" in pm:
        out.append(HANDLER_IDS["x402"])
    if "paypal" in pm:
        out.append(HANDLER_IDS["paypal"])
    if "polygon_usdt" in pm or "arbitrum_usdc" in pm:
        out.append(HANDLER_IDS["stablecoin_transfer"])
    if "invoice" in pm:
        out.append(HANDLER_IDS["invoice"])
    return out


def ucp_products(base: str, cfg) -> list[dict]:
    """Return all 9 Quantum Aether products in official UCP 2026-08-25 Product schema shape."""
    b = base.rstrip("/")
    out = []
    for raw in catalog_items(b, cfg):
        pid = raw["id"]
        amount = to_minor_units(raw["price"])
        ccy = _iso_currency(raw["currency"])
        price_obj = {"amount": amount, "currency": ccy}
        desc_obj = {"plain": raw["description"]}
        variant_id = f"{pid}:default"
        meta = {
            "category": raw["category"],
            "billing": raw["billing"],
            "autonomous_agent_ready": bool(raw.get("autonomous_agent_ready")),
            "human_signup_required": bool(raw.get("human_signup_required", False)),
            "mcp_tool": raw.get("mcp_tool"),
            "http_endpoint": raw.get("http_endpoint"),
            "checkout_url": raw["checkout_url"],
            "free_alternative": raw.get("free_alternative"),
            "payment_handlers": _product_handler_ids(raw),
            "settlement_note": (
                "Settled in USDC on Base (eip155:8453) via com.ather-quantum.x402."
                if raw["currency"] == "USDC" else None
            ),
        }
        if raw.get("sample_url"):
            meta["sample_url"] = raw["sample_url"]
        if raw.get("free_trial_days"):
            meta["free_trial_days"] = raw["free_trial_days"]

        product = {
            "id": pid,
            "handle": pid,
            "title": raw["title"],
            "description": desc_obj,
            "url": raw["checkout_url"],
            "categories": [{"value": raw["category"], "taxonomy": "merchant"}],
            "price_range": {"min": dict(price_obj), "max": dict(price_obj)},
            "variants": [
                {
                    "id": variant_id,
                    "sku": pid,
                    "handle": pid,
                    "title": raw["title"],
                    "description": desc_obj,
                    "url": raw["checkout_url"],
                    "price": dict(price_obj),
                    "availability": {"available": True, "status": "in_stock"},
                }
            ],
            "tags": ["post-quantum", "tls", "pqc", raw["category"], ccy.lower()],
            "metadata": meta,
        }
        out.append(product)
    return out


def catalog_payload(base: str, cfg, *, category: str = "all") -> dict:
    """Legacy GET /api/v1/ucp/catalog payload preserved intact + deprecation notice & new UCP links."""
    b = base.rstrip("/")
    items = catalog_items(b, cfg)
    cat = (category or "all").strip().lower()
    if cat != "all":
        items = [it for it in items if it["category"] == cat]
    return {
        "deprecated": True,
        "deprecation_notice": (
            "Legacy catalog shape kept for backward compatibility. Use UCP 2026-08-25 endpoints "
            "(/ucp/mcp or POST /api/v1/ucp/catalog/search, /catalog/lookup, /catalog/product) for spec-conformant payloads."
        ),
        "replacement_endpoints": {
            "ucp_profile": f"{b}/.well-known/ucp",
            "ucp_mcp": f"{b}/ucp/mcp",
            "catalog_search": f"{b}/api/v1/ucp/catalog/search",
            "catalog_lookup": f"{b}/api/v1/ucp/catalog/lookup",
            "catalog_product": f"{b}/api/v1/ucp/catalog/product",
            "checkout_sessions": f"{b}/api/v1/ucp/checkout-sessions",
        },
        "ucp_version": UCP_VERSION,
        "merchant": {"name": "Quantum Aether", "url": b, "mcp_endpoint": f"{b}/mcp", "ucp_mcp_endpoint": f"{b}/ucp/mcp"},
        "category": cat,
        "count": len(items),
        "items": items,
        "checkout_sessions_endpoint": f"{b}/api/v1/ucp/checkout-sessions",
        "ucp_profile": f"{b}/.well-known/ucp",
        "x402_discovery": f"{b}/.well-known/x402",
        "note": "External point-in-time port-443 TLS observations, not legal compliance certifications.",
    }


# ---------------------------------------------------------------------------
# 2. Authority-Bound Payment Handlers & Profile (/.well-known/ucp)
# ---------------------------------------------------------------------------

def payment_handler_schemas(base: str) -> dict[str, dict]:
    """JSON Schemas hosted on ather-quantum.com/ucp/handlers/<key>.json matching com.ather-quantum.* namespaces."""
    b = base.rstrip("/")
    return {
        "x402": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"{b}/ucp/handlers/x402.json",
            "title": "Quantum Aether x402 Base USDC Payment Handler",
            "description": "Autonomous agent settlement in USDC on Base (eip155:8453) via x402 v2 exact EIP-3009 transfer authorization.",
            "type": "object",
            "required": ["id", "handler_id", "type", "credential"],
            "properties": {
                "id": {"type": "string"},
                "handler_id": {"const": HANDLER_IDS["x402"]},
                "type": {"const": "x402_eip3009_usdc"},
                "credential": {
                    "type": "object",
                    "required": ["type"],
                    "properties": {
                        "type": {"const": "x402_payment_signature"},
                        "token": {"type": "string", "description": "Base64url-encoded x402 v2 PAYMENT-SIGNATURE payload."},
                        "payload": {"type": "object", "description": "Decoded x402 v2 payment authorization object."},
                    },
                },
            },
        },
        "paypal": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"{b}/ucp/handlers/paypal.json",
            "title": "Quantum Aether PayPal Checkout Handler",
            "description": "Human-approved PayPal checkout flow for full remediation reports and monthly monitoring subscriptions.",
            "type": "object",
            "required": ["id", "handler_id", "type"],
            "properties": {
                "id": {"type": "string"},
                "handler_id": {"const": HANDLER_IDS["paypal"]},
                "type": {"const": "paypal_checkout"},
            },
        },
        "stablecoin_transfer": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"{b}/ucp/handlers/stablecoin_transfer.json",
            "title": "Quantum Aether Direct Stablecoin Transfer Handler",
            "description": "Direct on-chain stablecoin transfer (Polygon USDT / Base & Arbitrum USDC) verified by confirmed tx_hash.",
            "type": "object",
            "required": ["id", "handler_id", "type"],
            "properties": {
                "id": {"type": "string"},
                "handler_id": {"const": HANDLER_IDS["stablecoin_transfer"]},
                "type": {"const": "onchain_stablecoin"},
            },
        },
        "invoice": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"{b}/ucp/handlers/invoice.json",
            "title": "Quantum Aether B2B Invoice Handler",
            "description": "Human B2B invoice ordering for the 290 EUR MSP Partner Pilot and 490 EUR Organization Audit.",
            "type": "object",
            "required": ["id", "handler_id", "type"],
            "properties": {
                "id": {"type": "string"},
                "handler_id": {"const": HANDLER_IDS["invoice"]},
                "type": {"const": "b2b_invoice"},
            },
        },
    }


def payment_handlers_registry(base: str, cfg, *, for_response: bool = False, allowed_ids: set[str] | None = None) -> dict:
    """Return UCP 2026-08-25 payment_handlers map keyed by authority-bound reverse-domain names."""
    b = base.rstrip("/")
    pay_to = x402_pay.receiver() or ""
    all_handlers = {
        HANDLER_NS["x402"]: [
            {
                "id": HANDLER_IDS["x402"],
                "version": UCP_VERSION,
                "spec": f"{b}/ucp/handlers/x402",
                "schema": f"{b}/ucp/handlers/x402.json",
                "available_instruments": [{"type": "x402_eip3009_usdc"}],
                "config": {
                    "enabled": bool(pay_to),
                    "x402_version": 2,
                    "scheme": "exact",
                    "network": x402_pay.NETWORK,
                    "asset": x402_pay.ASSET,
                    "settlement_currency": "USDC",
                    "decimals": 6,
                    "payTo": pay_to,
                    "facilitator": x402_pay.FACILITATOR,
                    "discovery_url": f"{b}/.well-known/x402",
                },
            }
        ],
        HANDLER_NS["paypal"]: [
            {
                "id": HANDLER_IDS["paypal"],
                "version": UCP_VERSION,
                "spec": f"{b}/ucp/handlers/paypal",
                "schema": f"{b}/ucp/handlers/paypal.json",
                "available_instruments": [{"type": "paypal_checkout"}],
                "config": {
                    "enabled": bool(cfg.get("PAYPAL_CLIENT_ID") and cfg.get("PAYPAL_CLIENT_SECRET")),
                    "checkout_url": f"{b}/pricing?lang=en",
                },
            }
        ],
        HANDLER_NS["stablecoin_transfer"]: [
            {
                "id": HANDLER_IDS["stablecoin_transfer"],
                "version": UCP_VERSION,
                "spec": f"{b}/ucp/handlers/stablecoin_transfer",
                "schema": f"{b}/ucp/handlers/stablecoin_transfer.json",
                "available_instruments": [{"type": "onchain_stablecoin"}],
                "config": {
                    "enabled": True,
                    "networks": ["polygon-usdt", "arbitrum-usdc", "base-usdc"],
                    "mcp_tools": ["create_full_report_order", "verify_full_report_payment"],
                },
            }
        ],
        HANDLER_NS["invoice"]: [
            {
                "id": HANDLER_IDS["invoice"],
                "version": UCP_VERSION,
                "spec": f"{b}/ucp/handlers/invoice",
                "schema": f"{b}/ucp/handlers/invoice.json",
                "available_instruments": [{"type": "b2b_invoice"}],
                "config": {
                    "enabled": True,
                    "msp_pilot_url": f"{b}/partners?lang=de#msp-pilot",
                    "audit_url": f"{b}/audit?lang=en",
                },
            }
        ],
    }
    if allowed_ids is None:
        return all_handlers
    filtered = {}
    for ns, entries in all_handlers.items():
        kept = [e for e in entries if e["id"] in allowed_ids]
        if kept:
            filtered[ns] = kept
    return filtered or all_handlers


def _public_jwk_keys(services: dict | None) -> list[dict]:
    """Return the exact same public Ed25519 keys as /.well-known/jwks.json (never includes private key material)."""
    try:
        doc = receipts.jwks_document(**receipts.key_config_from_app(services or {}))
        keys = doc.get("keys") or []
        out = []
        for k in keys:
            if not isinstance(k, dict) or not k.get("kid") or not k.get("kty"):
                continue
            clean = {
                "kid": k["kid"],
                "kty": k["kty"],
                "crv": k.get("crv", "Ed25519"),
                "x": k.get("x", ""),
                "use": k.get("use", "sig"),
                "alg": k.get("alg", "EdDSA"),
            }
            out.append(clean)
        return out
    except Exception:
        return []


def ucp_profile(base: str, cfg, services: dict | None = None) -> dict:
    """Canonical /.well-known/ucp Business Profile conforming to UCP 2026-08-25 schemas/profile.json."""
    b = base.rstrip("/")
    profile = {
        "ucp": {
            "version": UCP_VERSION,
            "services": {
                "dev.ucp.shopping": [
                    {
                        "version": UCP_VERSION,
                        "spec": f"{UCP_SPEC_BASE}/specification/overview/",
                        "transport": "mcp",
                        "endpoint": f"{b}/ucp/mcp",
                        "schema": f"{UCP_SPEC_BASE}/services/shopping/mcp.openrpc.json",
                    },
                    {
                        "version": UCP_VERSION,
                        "spec": f"{UCP_SPEC_BASE}/specification/overview/",
                        "transport": "rest",
                        "endpoint": f"{b}/api/v1/ucp",
                        "schema": f"{UCP_SPEC_BASE}/services/shopping/rest.openapi.json",
                    },
                    {
                        "version": UCP_VERSION,
                        "spec": f"{UCP_SPEC_BASE}/specification/overview/",
                        "transport": "a2a",
                        "endpoint": f"{b}/.well-known/agent-card.json",
                    },
                ]
            },
            "capabilities": {
                CAP_SEARCH: [
                    {
                        "version": UCP_VERSION,
                        "spec": f"{UCP_SPEC_BASE}/specification/shopping/catalog/search/",
                        "schema": f"{UCP_SPEC_BASE}/schemas/shopping/catalog_search.json",
                    }
                ],
                CAP_LOOKUP: [
                    {
                        "version": UCP_VERSION,
                        "spec": f"{UCP_SPEC_BASE}/specification/shopping/catalog/lookup/",
                        "schema": f"{UCP_SPEC_BASE}/schemas/shopping/catalog_lookup.json",
                    }
                ],
                CAP_CHECKOUT: [
                    {
                        "version": UCP_VERSION,
                        "spec": f"{UCP_SPEC_BASE}/specification/shopping/checkout/",
                        "schema": f"{UCP_SPEC_BASE}/schemas/shopping/checkout.json",
                    }
                ],
            },
            "payment_handlers": payment_handlers_registry(b, cfg),
        },
        "keys": _public_jwk_keys(services),
    }
    return profile


# ---------------------------------------------------------------------------
# 3. UCP Business Operations: Catalog Search, Lookup, Get Product
# ---------------------------------------------------------------------------

def _ucp_catalog_meta(cap: str) -> dict:
    return {
        "version": UCP_VERSION,
        "status": "success",
        "capabilities": {cap: [{"version": UCP_VERSION}]},
    }


def _ucp_error_response(code: str, content: str, *, severity: str = "recoverable", path: str | None = None, continue_url: str | None = None) -> dict:
    msg = {
        "type": "error",
        "code": code,
        "content": content,
        "content_type": "plain",
        "severity": severity,
    }
    if path:
        msg["path"] = path
    out = {
        "ucp": {"version": UCP_VERSION, "status": "error"},
        "messages": [msg],
    }
    if continue_url:
        out["continue_url"] = continue_url
    return out


def _matches_filters(prod: dict, filters: dict | None) -> bool:
    if not isinstance(filters, dict) or not filters:
        return True
    cats = filters.get("categories")
    if isinstance(cats, list) and cats:
        prod_cats = {str(c.get("value") or "").lower() for c in (prod.get("categories") or []) if isinstance(c, dict)}
        if not any(str(c).lower() in prod_cats for c in cats):
            return False
    price_f = filters.get("price")
    if isinstance(price_f, dict):
        p_amt = prod["price_range"]["min"]["amount"]
        p_ccy = prod["price_range"]["min"]["currency"]
        if price_f.get("currency") and str(price_f["currency"]).upper() != p_ccy:
            return False
        if isinstance(price_f.get("min"), int) and p_amt < price_f["min"]:
            return False
        if isinstance(price_f.get("max"), int) and p_amt > price_f["max"]:
            return False
    return True


def op_search_catalog(base: str, cfg, req: dict | None) -> dict:
    req = req if isinstance(req, dict) else {}
    query = str(req.get("query") or "").strip().lower()
    filters = req.get("filters") if isinstance(req.get("filters"), dict) else None
    pagination = req.get("pagination") if isinstance(req.get("pagination"), dict) else {}
    limit = pagination.get("limit") if isinstance(pagination.get("limit"), int) and pagination.get("limit") > 0 else 20
    limit = min(limit, 50)

    products = ucp_products(base, cfg)
    matched = []
    for p in products:
        if not _matches_filters(p, filters):
            continue
        if query:
            hay = " ".join([
                p["id"], p["title"], p["description"]["plain"],
                " ".join(p.get("tags") or []),
                str(p.get("metadata", {}).get("mcp_tool") or ""),
            ]).lower()
            if not all(tok in hay for tok in query.split()):
                continue
        matched.append(p)

    page = matched[:limit]
    has_next = len(matched) > len(page)
    pag = {"has_next_page": has_next, "total_count": len(matched)}
    if has_next:
        pag["cursor"] = str(len(page))
    return {
        "ucp": _ucp_catalog_meta(CAP_SEARCH),
        "products": page,
        "pagination": pag,
    }


def _index_products(base: str, cfg):
    prods = ucp_products(base, cfg)
    by_id = {}
    for p in prods:
        by_id[p["id"]] = (p, "featured")
        for v in p["variants"]:
            by_id[v["id"]] = (p, "exact")
            if v.get("sku") and v["sku"] not in by_id:
                by_id[v["sku"]] = (p, "exact")
    return prods, by_id


def op_lookup_catalog(base: str, cfg, req: dict | None) -> dict:
    if not isinstance(req, dict) or not isinstance(req.get("ids"), list) or not req["ids"]:
        return _ucp_error_response("invalid_request", "catalog.ids must be a non-empty array of identifiers", path="$.ids")
    filters = req.get("filters") if isinstance(req.get("filters"), dict) else None
    _, by_id = _index_products(base, cfg)

    grouped: dict[str, tuple[dict, list[dict]]] = {}
    missing = []
    for raw_id in req["ids"]:
        rid = str(raw_id or "").strip()
        hit = by_id.get(rid)
        if not hit:
            missing.append(rid)
            continue
        prod, match_kind = hit
        if not _matches_filters(prod, filters):
            continue
        pid = prod["id"]
        if pid not in grouped:
            grouped[pid] = (json.loads(json.dumps(prod)), [])
        grouped[pid][1].append({"id": rid, "match": match_kind})

    out_products = []
    for prod, inputs in grouped.values():
        prod["variants"][0]["inputs"] = inputs
        out_products.append(prod)

    resp = {
        "ucp": _ucp_catalog_meta(CAP_LOOKUP),
        "products": out_products,
    }
    if missing:
        resp["messages"] = [
            {
                "type": "warning",
                "code": "not_found",
                "content": f"Identifiers not found: {', '.join(missing)}",
                "content_type": "plain",
            }
        ]
    return resp


def op_get_product(base: str, cfg, req: dict | None) -> dict:
    if not isinstance(req, dict) or not isinstance(req.get("id"), str) or not req["id"].strip():
        return _ucp_error_response("invalid_request", "catalog.id is required", path="$.id")
    rid = req["id"].strip()
    _, by_id = _index_products(base, cfg)
    hit = by_id.get(rid)
    if not hit:
        return _ucp_error_response("not_found", f"Product or variant '{rid}' not found", severity="unrecoverable", path="$.id")
    prod, _ = hit
    return {
        "ucp": _ucp_catalog_meta(CAP_LOOKUP),
        "product": prod,
    }


# ---------------------------------------------------------------------------
# 4. Stateful Checkout Lifecycle & Idempotency (SQLite)
# ---------------------------------------------------------------------------

def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS ucp_checkouts ("
        "id TEXT PRIMARY KEY, status TEXT NOT NULL, currency TEXT NOT NULL, "
        "payload_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS ucp_idempotency ("
        "checkout_id TEXT NOT NULL, op TEXT NOT NULL, idem_key TEXT NOT NULL, "
        "response_json TEXT NOT NULL, created_at TEXT NOT NULL, "
        "PRIMARY KEY (checkout_id, op, idem_key))"
    )


def _save_checkout(conn: sqlite3.Connection, checkout: dict) -> None:
    now = _utc_now()
    _ensure_tables(conn)
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO ucp_checkouts (id, status, currency, payload_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM ucp_checkouts WHERE id = ?), ?), ?)",
            (checkout["id"], checkout["status"], checkout["currency"], json.dumps(checkout, ensure_ascii=False), checkout["id"], now, now),
        )
        conn.execute(
            "DELETE FROM ucp_checkouts WHERE id NOT IN (SELECT id FROM ucp_checkouts ORDER BY updated_at DESC LIMIT 1000)"
        )


def _load_checkout(conn: sqlite3.Connection, checkout_id: str) -> dict | None:
    try:
        _ensure_tables(conn)
        row = conn.execute("SELECT payload_json FROM ucp_checkouts WHERE id = ?", (checkout_id,)).fetchone()
        return json.loads(row[0]) if row else None
    except (sqlite3.Error, ValueError):
        return None


def _get_idem(conn: sqlite3.Connection, checkout_id: str, op: str, idem_key: str) -> dict | None:
    try:
        _ensure_tables(conn)
        row = conn.execute(
            "SELECT response_json FROM ucp_idempotency WHERE checkout_id = ? AND op = ? AND idem_key = ?",
            (checkout_id, op, idem_key),
        ).fetchone()
        return json.loads(row[0]) if row else None
    except (sqlite3.Error, ValueError):
        return None


def _save_idem(conn: sqlite3.Connection, checkout_id: str, op: str, idem_key: str, response: dict) -> None:
    _ensure_tables(conn)
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO ucp_idempotency (checkout_id, op, idem_key, response_json, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (checkout_id, op, idem_key, json.dumps(response, ensure_ascii=False), _utc_now()),
        )
        conn.execute(
            "DELETE FROM ucp_idempotency WHERE rowid NOT IN (SELECT rowid FROM ucp_idempotency ORDER BY created_at DESC LIMIT 2000)"
        )


def _legal_links(base: str) -> list[dict]:
    b = base.rstrip("/")
    return [
        {"type": "privacy_policy", "url": f"{b}/datenschutz?lang=en", "title": "Privacy Policy"},
        {"type": "terms_of_service", "url": f"{b}/agb?lang=en", "title": "Terms of Service"},
    ]


def _continue_url_for_products(base: str, resolved_prods: list[dict], domain: str = "") -> str:
    b = base.rstrip("/")
    if not resolved_prods:
        return f"{b}/pricing?lang=en"
    first = resolved_prods[0]
    pid = first["id"]
    url = first["url"]
    if pid in ("qa-monitoring-starter", "qa-monitoring-business") and domain:
        return f"{b}/monitoring?domain={quote(domain, safe='')}#trial-form"
    if pid == "qa-org-audit" and domain:
        return f"{b}/audit?domain={quote(domain, safe='')}"
    return url


def _build_checkout_object(
    base: str,
    cfg,
    checkout_id: str,
    raw_lines: list,
    *,
    buyer: dict | None = None,
    payment: dict | None = None,
    expires_at: str | None = None,
    domain_hint: str = "",
) -> tuple[dict | None, dict | None]:
    """Validate line_items and construct a schema-conformant UCP Checkout object (or error_response)."""
    b = base.rstrip("/")
    if not isinstance(raw_lines, list) or not raw_lines:
        return None, _ucp_error_response("invalid_request", "checkout.line_items must be a non-empty array", path="$.line_items")

    _, by_id = _index_products(b, cfg)
    line_items = []
    currencies = set()
    resolved_prods = []
    allowed_handlers: set[str] | None = None
    subtotal = 0

    for idx, entry in enumerate(raw_lines):
        if not isinstance(entry, dict):
            return None, _ucp_error_response("invalid_request", f"line_items[{idx}] must be an object", path=f"$.line_items[{idx}]")
        item_obj = entry.get("item") if isinstance(entry.get("item"), dict) else {}
        req_id = str(item_obj.get("id") or "").strip()
        qty = entry.get("quantity", 1)
        if not req_id:
            return None, _ucp_error_response("invalid_request", f"line_items[{idx}].item.id is required", path=f"$.line_items[{idx}].item.id")
        if isinstance(qty, bool) or not isinstance(qty, int) or qty < 1:
            return None, _ucp_error_response("invalid_request", f"line_items[{idx}].quantity must be an integer >= 1", path=f"$.line_items[{idx}].quantity")

        hit = by_id.get(req_id)
        if not hit:
            return None, _ucp_error_response(
                "item_unavailable",
                f"Unknown product or variant '{req_id}'. Call search_catalog to discover valid IDs.",
                severity="recoverable",
                path=f"$.line_items[{idx}].item.id",
            )
        prod, _ = hit
        var = prod["variants"][0]
        unit_price = var["price"]["amount"]
        ccy = var["price"]["currency"]
        currencies.add(ccy)
        if len(currencies) > 1:
            return None, _ucp_error_response(
                "mixed_currency",
                "A single checkout session cannot mix USD and EUR line items. Create separate checkouts per currency.",
                severity="recoverable",
                path=f"$.line_items[{idx}]",
            )

        line_amount = unit_price * qty
        subtotal += line_amount
        resolved_prods.append(prod)
        p_handlers = set(prod["metadata"].get("payment_handlers") or [])
        allowed_handlers = p_handlers if allowed_handlers is None else (allowed_handlers & p_handlers)

        li_id = str(entry.get("id") or f"li_{idx + 1}")
        line_items.append({
            "id": li_id,
            "item": {
                "id": var["id"],
                "title": var["title"],
                "price": unit_price,
            },
            "quantity": qty,
            "totals": [
                {"type": "subtotal", "display_text": "Subtotal", "amount": line_amount},
                {"type": "total", "display_text": "Total", "amount": line_amount},
            ],
        })

    currency = next(iter(currencies))
    human_only = any(p["metadata"].get("human_signup_required") for p in resolved_prods)
    continue_url = _continue_url_for_products(b, resolved_prods, domain=domain_hint)
    messages = []

    has_instrument = isinstance(payment, dict) and isinstance(payment.get("instruments"), list) and len(payment["instruments"]) > 0
    if human_only:
        status = "requires_escalation"
        messages.append({
            "type": "error",
            "code": "human_checkout_required",
            "content": "This product requires human signup or B2B invoice approval. Continue at continue_url.",
            "content_type": "plain",
            "severity": "requires_buyer_input",
        })
    elif has_instrument:
        status = "ready_for_complete"
    else:
        status = "incomplete"
        messages.append({
            "type": "info",
            "code": "payment_required",
            "content": (
                "Attach a com.ather-quantum.x402 payment instrument (or complete via continue_url) "
                "before calling complete_checkout."
            ),
            "content_type": "plain",
        })

    checkout = {
        "ucp": {
            "version": UCP_VERSION,
            "status": "success",
            "capabilities": {CAP_CHECKOUT: [{"version": UCP_VERSION}]},
            "payment_handlers": payment_handlers_registry(b, cfg, for_response=True, allowed_ids=allowed_handlers or None),
        },
        "id": checkout_id,
        "status": status,
        "currency": currency,
        "line_items": line_items,
        "totals": [
            {"type": "subtotal", "display_text": "Subtotal", "amount": subtotal},
            {"type": "total", "display_text": "Total", "amount": subtotal},
        ],
        "links": _legal_links(b),
        "continue_url": continue_url,
        "expires_at": expires_at or _expires_at(6),
    }
    if messages:
        checkout["messages"] = messages
    if isinstance(buyer, dict) and buyer:
        checkout["buyer"] = buyer
    if isinstance(payment, dict) and payment:
        checkout["payment"] = payment
    return checkout, None


def op_create_checkout(conn: sqlite3.Connection, base: str, cfg, checkout_req: dict) -> dict:
    cid = "chk_" + uuid.uuid4().hex[:16]
    checkout, err = _build_checkout_object(
        base,
        cfg,
        cid,
        checkout_req.get("line_items"),
        buyer=checkout_req.get("buyer"),
        payment=checkout_req.get("payment"),
        domain_hint=str(checkout_req.get("domain") or ""),
    )
    if err is not None:
        return err
    _save_checkout(conn, checkout)
    return checkout


def op_get_checkout(conn: sqlite3.Connection, checkout_id: str) -> dict:
    found = _load_checkout(conn, checkout_id)
    if not found:
        return _ucp_error_response("not_found", f"Checkout session '{checkout_id}' not found", severity="unrecoverable")
    return found


def op_update_checkout(conn: sqlite3.Connection, base: str, cfg, checkout_id: str, checkout_req: dict) -> dict:
    existing = _load_checkout(conn, checkout_id)
    if not existing:
        return _ucp_error_response("not_found", f"Checkout session '{checkout_id}' not found", severity="unrecoverable")
    if existing["status"] == "complete_in_progress":
        # Per UCP 2026-08-25 spec: leave checkout unchanged and return current checkout with recoverable error Message.
        unchanged = json.loads(json.dumps(existing))
        msgs = list(unchanged.get("messages") or [])
        msgs.append({
            "type": "error",
            "code": "checkout_in_progress",
            "content": "Update checkout is not permitted while status is complete_in_progress.",
            "content_type": "plain",
            "severity": "recoverable",
        })
        unchanged["messages"] = msgs
        return unchanged
    if existing["status"] in ("completed", "canceled"):
        return _ucp_error_response(
            "checkout_closed",
            f"Checkout '{checkout_id}' is already {existing['status']} and cannot be updated.",
            severity="unrecoverable",
        )

    updated, err = _build_checkout_object(
        base,
        cfg,
        checkout_id,
        checkout_req.get("line_items"),
        buyer=checkout_req.get("buyer") if "buyer" in checkout_req else existing.get("buyer"),
        payment=checkout_req.get("payment") if "payment" in checkout_req else existing.get("payment"),
        expires_at=existing.get("expires_at"),
        domain_hint=str(checkout_req.get("domain") or ""),
    )
    if err is not None:
        return err
    _save_checkout(conn, updated)
    return updated


def _settle_x402_instrument(conn: sqlite3.Connection, checkout: dict, instrument: dict) -> tuple[bool, str, str]:
    """Verify & settle an x402 Base USDC instrument using existing x402_pay codepath (zero config changes)."""
    cred = instrument.get("credential") if isinstance(instrument.get("credential"), dict) else {}
    payload = cred.get("payload")
    token = cred.get("token")
    if payload is None and isinstance(token, str) and token.strip():
        try:
            pad = "=" * (-len(token.strip()) % 4)
            payload = json.loads(base64.urlsafe_b64decode(token.strip() + pad).decode("utf-8"))
        except Exception:
            return False, "Invalid base64url x402 payment token", ""
    if not isinstance(payload, dict):
        return False, "x402 instrument credential must provide payload or base64url token", ""

    pay_to = x402_pay.receiver()
    if not pay_to:
        return False, "x402 Base USDC receiver is not configured on this server", ""

    # Convert USD minor units (2 decimals) -> exact USDC 6-decimal atomic units using Decimal (10^4 scale)
    total_minor = next((t["amount"] for t in checkout["totals"] if t["type"] == "total"), 0)
    usd_str = str((Decimal(total_minor) / Decimal("100")).quantize(Decimal("0.01")))
    required_units = x402_pay.units(usd_str)
    req_spec = {
        "scheme": "exact",
        "network": x402_pay.NETWORK,
        "amount": required_units,
        "asset": x402_pay.ASSET,
        "payTo": pay_to,
        "maxTimeoutSeconds": 300,
    }
    accepted = payload.get("accepted") if isinstance(payload.get("accepted"), dict) else {}
    if accepted:
        if str(accepted.get("network") or "") != x402_pay.NETWORK:
            return False, f"Payment network mismatch (expected {x402_pay.NETWORK})", ""
        if str(accepted.get("payTo") or "").lower() != pay_to.lower():
            return False, "Payment recipient (payTo) mismatch", ""
        if str(accepted.get("amount") or "") != required_units:
            return False, f"Payment amount mismatch (expected {required_units} USDC atomic units)", ""

    facilitator = current_app.extensions.get("x402_facilitator")
    if facilitator:
        ver = facilitator("/verify", {"x402Version": 2, "paymentPayload": payload, "paymentRequirements": req_spec})
        if not (isinstance(ver, dict) and ver.get("isValid")):
            return False, f"x402 verification rejected: {ver}", ""
        stl = facilitator("/settle", {"x402Version": 2, "paymentPayload": payload, "paymentRequirements": req_spec})
        if not (isinstance(stl, dict) and stl.get("success")):
            return False, f"x402 settlement rejected: {stl}", ""
        tx_hash = str(stl.get("transaction") or "")
        return True, "", tx_hash

    # Live PayAI facilitator path via existing x402_pay._post_facilitator
    try:
        ver = x402_pay._post_facilitator("/verify", {"x402Version": 2, "paymentPayload": payload, "paymentRequirements": req_spec})
        if not (isinstance(ver, dict) and ver.get("isValid")):
            return False, "x402 payment verification failed", ""
        stl = x402_pay._post_facilitator("/settle", {"x402Version": 2, "paymentPayload": payload, "paymentRequirements": req_spec})
        if not (isinstance(stl, dict) and stl.get("success")):
            return False, "x402 payment settlement failed", ""
        return True, "", str(stl.get("transaction") or "")
    except Exception as exc:  # noqa: BLE001
        return False, f"x402 settlement error: {exc}", ""


def op_complete_checkout(conn: sqlite3.Connection, base: str, cfg, checkout_id: str, checkout_req: dict, idem_key: str) -> dict:
    cached = _get_idem(conn, checkout_id, "complete", idem_key)
    if cached is not None:
        return cached

    existing = _load_checkout(conn, checkout_id)
    if not existing:
        return _ucp_error_response("not_found", f"Checkout session '{checkout_id}' not found", severity="unrecoverable")
    if existing["status"] == "canceled":
        return _ucp_error_response("checkout_canceled", f"Checkout '{checkout_id}' is canceled", severity="unrecoverable")
    if existing["status"] == "completed":
        _save_idem(conn, checkout_id, "complete", idem_key, existing)
        return existing

    if existing["status"] == "requires_escalation":
        out = json.loads(json.dumps(existing))
        out["messages"] = [
            {
                "type": "error",
                "code": "human_checkout_required",
                "content": "Complete this order on the merchant page at continue_url.",
                "content_type": "plain",
                "severity": "requires_buyer_review",
            }
        ]
        _save_idem(conn, checkout_id, "complete", idem_key, out)
        return out

    # Transition to complete_in_progress before settlement
    in_prog = json.loads(json.dumps(existing))
    if isinstance(checkout_req, dict) and isinstance(checkout_req.get("payment"), dict):
        in_prog["payment"] = checkout_req["payment"]
    in_prog["status"] = "complete_in_progress"
    _save_checkout(conn, in_prog)

    payment = in_prog.get("payment") if isinstance(in_prog.get("payment"), dict) else {}
    instruments = payment.get("instruments") if isinstance(payment.get("instruments"), list) else []
    selected = next((i for i in instruments if isinstance(i, dict) and i.get("selected")), instruments[0] if instruments else None)

    if not isinstance(selected, dict):
        in_prog["status"] = "incomplete"
        in_prog["messages"] = [
            {
                "type": "error",
                "code": "payment_failed",
                "content": "A payment instrument (e.g. handler_id 'x402_base_usdc') is required to complete checkout.",
                "content_type": "plain",
                "severity": "recoverable",
            }
        ]
        _save_checkout(conn, in_prog)
        _save_idem(conn, checkout_id, "complete", idem_key, in_prog)
        return in_prog

    handler_id = str(selected.get("handler_id") or "")
    if handler_id != HANDLER_IDS["x402"]:
        in_prog["status"] = "requires_escalation"
        in_prog["messages"] = [
            {
                "type": "error",
                "code": "human_checkout_required",
                "content": f"Payment handler '{handler_id}' requires buyer confirmation at continue_url.",
                "content_type": "plain",
                "severity": "requires_buyer_review",
            }
        ]
        _save_checkout(conn, in_prog)
        _save_idem(conn, checkout_id, "complete", idem_key, in_prog)
        return in_prog

    ok, err_msg, tx_hash = _settle_x402_instrument(conn, in_prog, selected)
    if not ok:
        in_prog["status"] = "incomplete"
        in_prog["messages"] = [
            {
                "type": "error",
                "code": "payment_failed",
                "content": err_msg,
                "content_type": "plain",
                "severity": "recoverable",
            }
        ]
        _save_checkout(conn, in_prog)
        _save_idem(conn, checkout_id, "complete", idem_key, in_prog)
        return in_prog

    b = base.rstrip("/")
    order_id = "ord_ucp_" + uuid.uuid4().hex[:14]
    in_prog["status"] = "completed"
    in_prog["order"] = {
        "id": order_id,
        "label": f"Quantum Aether Order {order_id}",
        "permalink_url": f"{b}/api/v1/ucp/checkout-sessions/{checkout_id}",
    }
    in_prog["messages"] = [
        {
            "type": "info",
            "code": "order_completed",
            "content": f"Payment settled via x402 Base USDC{f' (tx {tx_hash})' if tx_hash else ''}.",
            "content_type": "plain",
        }
    ]
    _save_checkout(conn, in_prog)
    _save_idem(conn, checkout_id, "complete", idem_key, in_prog)
    return in_prog


def op_cancel_checkout(conn: sqlite3.Connection, checkout_id: str, idem_key: str) -> dict:
    cached = _get_idem(conn, checkout_id, "cancel", idem_key)
    if cached is not None:
        return cached

    existing = _load_checkout(conn, checkout_id)
    if not existing:
        return _ucp_error_response("not_found", f"Checkout session '{checkout_id}' not found", severity="unrecoverable")
    if existing["status"] == "completed":
        return _ucp_error_response("checkout_completed", f"Checkout '{checkout_id}' is already completed and cannot be canceled.", severity="unrecoverable")
    if existing["status"] == "canceled":
        _save_idem(conn, checkout_id, "cancel", idem_key, existing)
        return existing

    canceled = json.loads(json.dumps(existing))
    canceled["status"] = "canceled"
    canceled["messages"] = [
        {"type": "info", "code": "checkout_canceled", "content": "Checkout session canceled.", "content_type": "plain"}
    ]
    _save_checkout(conn, canceled)
    _save_idem(conn, checkout_id, "cancel", idem_key, canceled)
    return canceled


# ---------------------------------------------------------------------------
# 5. Dedicated UCP MCP Server (/ucp/mcp) — Exactly the 8 Spec Tools
# ---------------------------------------------------------------------------

META_SCHEMA = {
    "type": "object",
    "required": ["ucp-agent"],
    "properties": {
        "ucp-agent": {
            "type": "object",
            "required": ["profile"],
            "properties": {"profile": {"type": "string", "format": "uri"}},
        },
        "idempotency-key": {"type": "string", "format": "uuid"},
    },
    "additionalProperties": True,
}

META_IDEM_SCHEMA = {
    "type": "object",
    "required": ["ucp-agent", "idempotency-key"],
    "properties": META_SCHEMA["properties"],
    "additionalProperties": True,
}

UCP_MCP_TOOLS = [
    {
        "name": "search_catalog",
        "title": "Search UCP product catalog",
        "description": "Search Quantum Aether products using free-text query, filters, and pagination (UCP 2026-08-25).",
        "inputSchema": {
            "type": "object",
            "required": ["meta", "catalog"],
            "properties": {"meta": META_SCHEMA, "catalog": {"type": "object"}},
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "lookup_catalog",
        "title": "Batch lookup UCP products or variants",
        "description": "Batch lookup products or variants by product ID, variant ID, or SKU (UCP 2026-08-25).",
        "inputSchema": {
            "type": "object",
            "required": ["meta", "catalog"],
            "properties": {
                "meta": META_SCHEMA,
                "catalog": {"type": "object", "required": ["ids"], "properties": {"ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}}},
            },
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "get_product",
        "title": "Get UCP product details",
        "description": "Retrieve complete product details by product or variant ID (UCP 2026-08-25).",
        "inputSchema": {
            "type": "object",
            "required": ["meta", "catalog"],
            "properties": {
                "meta": META_SCHEMA,
                "catalog": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}},
            },
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "create_checkout",
        "title": "Create a UCP checkout session",
        "description": "Create a new checkout session with line_items in a single ISO 4217 currency (UCP 2026-08-25). checkout must not contain id.",
        "inputSchema": {
            "type": "object",
            "required": ["meta", "checkout"],
            "properties": {"meta": META_SCHEMA, "checkout": {"type": "object", "required": ["line_items"]}},
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
    },
    {
        "name": "get_checkout",
        "title": "Get a UCP checkout session",
        "description": "Retrieve the current state of a checkout session by top-level id (UCP 2026-08-25).",
        "inputSchema": {
            "type": "object",
            "required": ["meta", "id"],
            "properties": {"meta": META_SCHEMA, "id": {"type": "string"}},
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "update_checkout",
        "title": "Update a UCP checkout session",
        "description": "Full replacement update of a checkout session by top-level id (UCP 2026-08-25). Blocked while complete_in_progress.",
        "inputSchema": {
            "type": "object",
            "required": ["meta", "id", "checkout"],
            "properties": {"meta": META_SCHEMA, "id": {"type": "string"}, "checkout": {"type": "object", "required": ["line_items"]}},
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
    {
        "name": "complete_checkout",
        "title": "Complete a UCP checkout session",
        "description": "Complete a checkout session and settle payment idempotently using meta.idempotency-key (UUID) (UCP 2026-08-25).",
        "inputSchema": {
            "type": "object",
            "required": ["meta", "id", "checkout"],
            "properties": {"meta": META_IDEM_SCHEMA, "id": {"type": "string"}, "checkout": {"type": "object"}},
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True},
    },
    {
        "name": "cancel_checkout",
        "title": "Cancel a UCP checkout session",
        "description": "Cancel an open checkout session idempotently using meta.idempotency-key (UUID) (UCP 2026-08-25).",
        "inputSchema": {
            "type": "object",
            "required": ["meta", "id"],
            "properties": {"meta": META_IDEM_SCHEMA, "id": {"type": "string"}},
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
    },
]

UCP_MCP_TOOL_NAMES = {t["name"] for t in UCP_MCP_TOOLS}


def _validate_mcp_meta(args: dict, *, require_idempotency: bool = False) -> tuple[str | None, str | None]:
    """Return (idem_key, protocol_error_message)."""
    meta = args.get("meta")
    if not isinstance(meta, dict):
        return None, "meta object with meta['ucp-agent'].profile is required"
    agent = meta.get("ucp-agent")
    if not isinstance(agent, dict) or not _valid_http_uri(agent.get("profile")):
        return None, "meta['ucp-agent'].profile must be a valid HTTP(S) URI"
    idem = meta.get("idempotency-key")
    if require_idempotency:
        if not _valid_uuid(idem):
            return None, "meta['idempotency-key'] must be a valid UUID string"
        return idem.strip().lower(), None
    if idem is not None and not _valid_uuid(idem):
        return None, "meta['idempotency-key'] must be a valid UUID string when provided"
    return (idem.strip().lower() if isinstance(idem, str) else None), None


def _dispatch_ucp_tool(conn: sqlite3.Connection, base: str, cfg, name: str, args: dict) -> tuple[dict | None, tuple[int, str] | None]:
    """Execute one of the 8 UCP MCP tools. Returns (structured_result, (rpc_err_code, msg) | None)."""
    if name not in UCP_MCP_TOOL_NAMES:
        return None, (-32001, f"Unknown UCP tool: {name}")
    if not isinstance(args, dict):
        return None, (-32000, "arguments must be an object")

    need_idem = name in ("complete_checkout", "cancel_checkout")
    idem_key, meta_err = _validate_mcp_meta(args, require_idempotency=need_idem)
    if meta_err:
        return None, (-32000, meta_err)

    if name == "search_catalog":
        cat = args.get("catalog")
        if cat is not None and not isinstance(cat, dict):
            return None, (-32000, "catalog must be an object")
        return op_search_catalog(base, cfg, cat or {}), None

    if name == "lookup_catalog":
        cat = args.get("catalog")
        if not isinstance(cat, dict):
            return None, (-32000, "catalog object with ids is required")
        return op_lookup_catalog(base, cfg, cat), None

    if name == "get_product":
        cat = args.get("catalog")
        if not isinstance(cat, dict):
            return None, (-32000, "catalog object with id is required")
        return op_get_product(base, cfg, cat), None

    if name == "create_checkout":
        chk = args.get("checkout")
        if not isinstance(chk, dict):
            return None, (-32000, "checkout object is required")
        if "id" in chk:
            return None, (-32000, "checkout argument must not contain 'id'")
        return op_create_checkout(conn, base, cfg, chk), None

    if name == "get_checkout":
        cid = args.get("id")
        if not isinstance(cid, str) or not cid.strip():
            return None, (-32000, "top-level id is required")
        return op_get_checkout(conn, cid.strip()), None

    if name == "update_checkout":
        cid = args.get("id")
        chk = args.get("checkout")
        if not isinstance(cid, str) or not cid.strip():
            return None, (-32000, "top-level id is required")
        if not isinstance(chk, dict):
            return None, (-32000, "checkout object is required")
        if "id" in chk:
            return None, (-32000, "checkout argument must not contain 'id'; pass id at top level")
        return op_update_checkout(conn, base, cfg, cid.strip(), chk), None

    if name == "complete_checkout":
        cid = args.get("id")
        chk = args.get("checkout")
        if not isinstance(cid, str) or not cid.strip():
            return None, (-32000, "top-level id is required")
        if not isinstance(chk, dict):
            return None, (-32000, "checkout object is required")
        if "id" in chk:
            return None, (-32000, "checkout argument must not contain 'id'; pass id at top level")
        return op_complete_checkout(conn, base, cfg, cid.strip(), chk, idem_key), None

    if name == "cancel_checkout":
        cid = args.get("id")
        if not isinstance(cid, str) or not cid.strip():
            return None, (-32000, "top-level id is required")
        return op_cancel_checkout(conn, cid.strip(), idem_key), None

    return None, (-32001, f"Unsupported UCP tool: {name}")


# ---------------------------------------------------------------------------
# 6. Flask Blueprint Registration
# ---------------------------------------------------------------------------

def register(bp, services):
    base = services["base"]

    def _audit(action, dom="", status="ok"):
        fn = services.get("audit")
        if fn:
            fn("ucp", action, agent_audit.client_label(request.headers), dom or "", status)

    def _cors(resp, cache="public, max-age=300"):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = cache
        return resp

    @bp.get("/.well-known/ucp")
    @bp.get("/.well-known/ucp.json")
    def well_known_ucp():
        b = base().rstrip("/")
        _audit("profile", "", "ok")
        resp = jsonify(ucp_profile(b, current_app.config, services=services))
        resp.headers["Link"] = f'<{b}/.well-known/ucp>; rel="canonical"'
        return _cors(resp)

    @bp.get("/ucp/handlers/<name>.json")
    def ucp_handler_schema(name):
        schemas = payment_handler_schemas(base())
        doc = schemas.get(name)
        if not doc:
            return jsonify(error="not_found"), 404
        return _cors(jsonify(doc))

    @bp.get("/ucp/handlers/<name>")
    def ucp_handler_spec(name):
        schemas = payment_handler_schemas(base())
        doc = schemas.get(name)
        if not doc:
            return jsonify(error="not_found"), 404
        b = base().rstrip("/")
        return _cors(jsonify({
            "namespace": HANDLER_NS[name],
            "id": HANDLER_IDS[name],
            "version": UCP_VERSION,
            "title": doc["title"],
            "description": doc["description"],
            "schema": f"{b}/ucp/handlers/{name}.json",
            "profile": f"{b}/.well-known/ucp",
        }))

    # Legacy read-only catalog (kept for backward compatibility)
    @bp.get("/api/v1/ucp/catalog")
    def ucp_catalog_legacy():
        cat = (request.args.get("category") or "all").strip().lower()
        _audit("catalog_legacy", cat, "ok")
        return _cors(jsonify(catalog_payload(base(), current_app.config, category=cat)))

    # Official UCP 2026-08-25 REST Catalog Endpoints (matching rest.openapi.json)
    @bp.route("/api/v1/ucp/catalog/search", methods=["POST", "OPTIONS"])
    def ucp_rest_catalog_search():
        if request.method == "OPTIONS":
            resp = current_app.make_response(("", 204))
            resp.headers.update({"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS",
                                 "Access-Control-Allow-Headers": "Content-Type, UCP-Agent"})
            return resp
        body = request.get_json(silent=True) or {}
        out = op_search_catalog(base(), current_app.config, body)
        _audit("search_catalog", str(body.get("query") or ""), "ok")
        return _cors(jsonify(out), cache="no-store")

    @bp.route("/api/v1/ucp/catalog/lookup", methods=["POST", "OPTIONS"])
    def ucp_rest_catalog_lookup():
        if request.method == "OPTIONS":
            resp = current_app.make_response(("", 204))
            resp.headers.update({"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS",
                                 "Access-Control-Allow-Headers": "Content-Type, UCP-Agent"})
            return resp
        body = request.get_json(silent=True) or {}
        out = op_lookup_catalog(base(), current_app.config, body)
        status = 400 if out.get("ucp", {}).get("status") == "error" else 200
        _audit("lookup_catalog", ",".join(str(x) for x in (body.get("ids") or [])[:3]), "ok" if status == 200 else "error")
        resp = jsonify(out)
        resp.status_code = status
        return _cors(resp, cache="no-store")

    @bp.route("/api/v1/ucp/catalog/product", methods=["POST", "OPTIONS"])
    def ucp_rest_catalog_product():
        if request.method == "OPTIONS":
            resp = current_app.make_response(("", 204))
            resp.headers.update({"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "POST, OPTIONS",
                                 "Access-Control-Allow-Headers": "Content-Type, UCP-Agent"})
            return resp
        body = request.get_json(silent=True) or {}
        out = op_get_product(base(), current_app.config, body)
        is_err = out.get("ucp", {}).get("status") == "error"
        code = (out.get("messages") or [{}])[0].get("code") if is_err else ""
        status = 404 if code == "not_found" else (400 if is_err else 200)
        _audit("get_product", str(body.get("id") or ""), "ok" if status == 200 else "error")
        resp = jsonify(out)
        resp.status_code = status
        return _cors(resp, cache="no-store")

    # Official UCP 2026-08-25 REST Checkout Endpoints (matching rest.openapi.json)
    @bp.route("/api/v1/ucp/checkout-sessions", methods=["POST", "OPTIONS"])
    def ucp_checkout_sessions():
        if request.method == "OPTIONS":
            resp = current_app.make_response(("", 204))
            resp.headers.update({
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, UCP-Agent, Idempotency-Key",
            })
            return resp
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return _cors(jsonify(_ucp_error_response("invalid_request", "JSON object body is required")), cache="no-store"), 400
        if "id" in body:
            return _cors(jsonify(_ucp_error_response("invalid_request", "Checkout request must not contain 'id'")), cache="no-store"), 400
        # Normalize convenience {"sku": ...} into standard line_items if caller omitted line_items
        if not body.get("line_items") and body.get("sku"):
            body = dict(body, line_items=[{"item": {"id": str(body["sku"])}, "quantity": 1}])
        out = op_create_checkout(services["db"](), base(), current_app.config, body)
        is_err = out.get("ucp", {}).get("status") == "error"
        _audit("create_checkout", out.get("id", ""), "error" if is_err else "ok")
        resp = jsonify(out)
        resp.status_code = 400 if is_err else 201
        return _cors(resp, cache="no-store")

    @bp.route("/api/v1/ucp/checkout-sessions/<checkout_id>", methods=["GET", "PUT", "OPTIONS"])
    def ucp_checkout_session_item(checkout_id):
        if request.method == "OPTIONS":
            resp = current_app.make_response(("", 204))
            resp.headers.update({
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, PUT, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, UCP-Agent, Idempotency-Key",
            })
            return resp
        if request.method == "GET":
            out = op_get_checkout(services["db"](), checkout_id)
            is_err = out.get("ucp", {}).get("status") == "error"
            _audit("get_checkout", checkout_id, "error" if is_err else "ok")
            resp = jsonify(out)
            resp.status_code = 404 if is_err else 200
            return _cors(resp, cache="no-store")

        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return _cors(jsonify(_ucp_error_response("invalid_request", "JSON object body is required")), cache="no-store"), 400
        if "id" in body:
            return _cors(jsonify(_ucp_error_response("invalid_request", "Checkout body must not contain 'id'")), cache="no-store"), 400
        out = op_update_checkout(services["db"](), base(), current_app.config, checkout_id, body)
        is_err = out.get("ucp", {}).get("status") == "error"
        code = (out.get("messages") or [{}])[0].get("code") if is_err else ""
        status = 404 if code == "not_found" else (400 if is_err else 200)
        _audit("update_checkout", checkout_id, "error" if is_err else "ok")
        resp = jsonify(out)
        resp.status_code = status
        return _cors(resp, cache="no-store")

    @bp.route("/api/v1/ucp/checkout-sessions/<checkout_id>/complete", methods=["POST", "OPTIONS"])
    def ucp_checkout_session_complete(checkout_id):
        if request.method == "OPTIONS":
            resp = current_app.make_response(("", 204))
            resp.headers.update({
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, UCP-Agent, Idempotency-Key",
            })
            return resp
        idem = (request.headers.get("Idempotency-Key") or "").strip()
        if not _valid_uuid(idem):
            return _cors(jsonify(_ucp_error_response("invalid_request", "Idempotency-Key header must be a valid UUID")), cache="no-store"), 400
        body = request.get_json(silent=True) or {}
        if not isinstance(body, dict) or "id" in body:
            return _cors(jsonify(_ucp_error_response("invalid_request", "Checkout body must be an object without 'id'")), cache="no-store"), 400
        out = op_complete_checkout(services["db"](), base(), current_app.config, checkout_id, body, idem.lower())
        is_err = out.get("ucp", {}).get("status") == "error"
        code = (out.get("messages") or [{}])[0].get("code") if is_err else ""
        status = 404 if code == "not_found" else (400 if is_err else 200)
        _audit("complete_checkout", checkout_id, out.get("status", "error"))
        resp = jsonify(out)
        resp.status_code = status
        return _cors(resp, cache="no-store")

    @bp.route("/api/v1/ucp/checkout-sessions/<checkout_id>/cancel", methods=["POST", "OPTIONS"])
    def ucp_checkout_session_cancel(checkout_id):
        if request.method == "OPTIONS":
            resp = current_app.make_response(("", 204))
            resp.headers.update({
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, UCP-Agent, Idempotency-Key",
            })
            return resp
        idem = (request.headers.get("Idempotency-Key") or "").strip()
        if not _valid_uuid(idem):
            return _cors(jsonify(_ucp_error_response("invalid_request", "Idempotency-Key header must be a valid UUID")), cache="no-store"), 400
        out = op_cancel_checkout(services["db"](), checkout_id, idem.lower())
        is_err = out.get("ucp", {}).get("status") == "error"
        code = (out.get("messages") or [{}])[0].get("code") if is_err else ""
        status = 404 if code == "not_found" else (400 if is_err else 200)
        _audit("cancel_checkout", checkout_id, out.get("status", "error"))
        resp = jsonify(out)
        resp.status_code = status
        return _cors(resp, cache="no-store")

    # Official UCP 2026-08-25 Dedicated MCP Endpoint (/ucp/mcp)
    def _rpc_err(code: int, message: str, rid=None, status: int = 200):
        resp = jsonify(jsonrpc="2.0", id=rid, error={"code": code, "message": message})
        resp.status_code = status
        return _cors(resp, cache="no-store")

    @bp.route("/ucp/mcp", methods=["GET", "POST", "OPTIONS"], provide_automatic_options=False)
    def ucp_mcp_endpoint():
        if request.method == "OPTIONS":
            resp = current_app.make_response(("", 204))
            resp.headers.update({
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, MCP-Protocol-Version, UCP-Agent",
            })
            return resp
        if request.method == "GET":
            return Response(status=405, headers={"Allow": "POST"})
        if not request.is_json:
            return jsonify(error="expected_application_json"), 415
        try:
            msg = request.get_json()
        except Exception:
            return _rpc_err(-32700, "Parse error", status=400)
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
            return _rpc_err(-32600, "Invalid JSON-RPC request", status=400)
        rid = msg.get("id")
        if "id" not in msg:
            return Response(status=202)
        if isinstance(rid, (dict, list, bool)) or rid is None:
            return _rpc_err(-32600, "Request id must be a string or number", status=400)

        method = msg["method"]
        params = msg.get("params") if msg.get("params") is not None else {}
        if not isinstance(params, dict):
            return _rpc_err(-32000, "params must be an object", rid)

        if method == "initialize":
            req_ver = params.get("protocolVersion")
            ver = req_ver if req_ver in UCP_PROTOCOLS else UCP_PROTOCOLS[0]
            _audit("ucp_mcp_initialize", "", "ok")
            return _cors(jsonify(jsonrpc="2.0", id=rid, result={
                "protocolVersion": ver,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "quantum-aether-ucp", "title": "Quantum Aether UCP Shopping Server", "version": UCP_VERSION},
                "instructions": (
                    "Official UCP 2026-08-25 Shopping MCP server. Every tool call requires meta['ucp-agent'].profile; "
                    "complete_checkout and cancel_checkout also require meta['idempotency-key'] (UUID)."
                ),
            }), cache="no-store")

        if method == "ping":
            return _cors(jsonify(jsonrpc="2.0", id=rid, result={}), cache="no-store")

        if method == "tools/list":
            return _cors(jsonify(jsonrpc="2.0", id=rid, result={"tools": UCP_MCP_TOOLS}), cache="no-store")

        if method == "tools/call":
            tname = params.get("name")
            targs = params.get("arguments", {})
            if not isinstance(tname, str) or tname not in UCP_MCP_TOOL_NAMES:
                return _rpc_err(-32001, f"Unknown UCP tool: {tname}", rid)
            payload, proto_err = _dispatch_ucp_tool(services["db"](), base(), current_app.config, tname, targs)
            if proto_err is not None:
                _audit(f"mcp:{tname}", "", f"rpc_{proto_err[0]}")
                return _rpc_err(proto_err[0], proto_err[1], rid)
            _audit(f"mcp:{tname}", str(targs.get("id") or ""), payload.get("status") or payload.get("ucp", {}).get("status", "ok"))
            return _cors(jsonify(jsonrpc="2.0", id=rid, result={
                "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                "structuredContent": payload,
                "isError": False,
            }), cache="no-store")

        # Also accept direct OpenRPC method invocation for spec tooling calling method="<tool_name>"
        if method in UCP_MCP_TOOL_NAMES:
            payload, proto_err = _dispatch_ucp_tool(services["db"](), base(), current_app.config, method, params)
            if proto_err is not None:
                _audit(f"rpc:{method}", "", f"rpc_{proto_err[0]}")
                return _rpc_err(proto_err[0], proto_err[1], rid)
            _audit(f"rpc:{method}", str(params.get("id") or ""), payload.get("status") or payload.get("ucp", {}).get("status", "ok"))
            return _cors(jsonify(jsonrpc="2.0", id=rid, result=payload), cache="no-store")

        return _rpc_err(-32601, f"Method not found: {method}", rid)
