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
import config_gen
import deadlines
import quantum_vuln_scanner
import receipts
import sector_snapshot
import signed_receipts

AR_PREFIX = r"(?:^|[\s،؟?!.,:;/()-])(?:[وفبلك]?ال|[وفبلك])?"
AR_DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670]")
AR_ALEF_RE = re.compile(r"[أإآ]")


def _norm_query(text: str) -> str:
    """Normalize Arabic alef/ta-marbuta/yaa/diacritics so 'الاسعار' and 'الأسعار' match identically."""
    s = AR_DIACRITICS_RE.sub("", text or "")
    s = AR_ALEF_RE.sub("ا", s).replace("ة", "ه").replace("ى", "ي")
    return s


PROTOCOL = "0.3.0"
HOST_RE = re.compile(r"(?<![@\w.-])((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})(?![\w-])", re.I)
SCAN_WORDS = re.compile(r"\b(scan|rescan|measure|check now|fresh|live\s+scan|prüf(?:en|e)?\s+jetzt)\b|" + AR_PREFIX + r"(?:افحص|فحص\s+مباشر|فحص\s+الان)", re.I)
AFFILIATE_WORDS = re.compile(r"\b(affiliate|referral|partner\s+program|commission|ref\s*code)\b|" + AR_PREFIX + r"(?:عمول(?:ه|ات)|احال(?:ه|ات)|شراك(?:ه|ات)|شريك|مسوق)", re.I)
ATTESTATION_WORDS = re.compile(r"\b(attestation|cbom|cyclonedx|auditor\s+pdf|audit\s+pdf|sample\.pdf)\b|" + AR_PREFIX + r"(?:شهاده\s+تدقيق|ملف\s+المدقق)", re.I)
MSP_PILOT_WORDS = re.compile(r"\b(msp|pilot|it[- ]?dienstleister|white[- ]?label|ampel|50\s+hostnames?|290\s*€|290\s*eur)\b|" + AR_PREFIX + r"(?:بايلوت|تجريبي\s+للشركاء)", re.I)
QA_CONFIG_WORDS = re.compile(r"\b(nginx|apache|haproxy|caddy|cloudfront|cloudflare|node\.?js|golang|openssl|config(?:ure|uration)?|konfigur\w*)\b|" + AR_PREFIX + r"(?:اعداد(?:ات)?|تفعيل|كيف\s+افعل|اصلاح)", re.I)
QA_DEADLINE_WORDS = re.compile(r"\b(bsi|tr-?02102|nis2|dora|nist|cnsa|ncsc|sama|deadline\w*|compliance|roadmap|frist\w*|richtlinie)\b|" + AR_PREFIX + r"(?:مواعيد|موعد|امتثال|قانون|معايير|تنظيم\w*)", re.I)
QA_RECEIPT_WORDS = re.compile(r"\b(receipt\w*|jws|jwks|ed25519|offline\s+verif\w*|signatur\w*)\b|" + AR_PREFIX + r"(?:ايصال(?:ات)?|توقيع|تحقق)", re.I)
QA_MCP_WORDS = re.compile(r"\b(mcp|a2a|acp|cursor|claude|vs\s*code|vscode|api\b|openapi|llms\.txt)\b|" + AR_PREFIX + r"(?:وكيل|وكلاء|واجهه\s+برمج|برمج(?:ي|ه)|ربط)", re.I)
QA_PRICING_WORDS = re.compile(r"\b(pricing|prices?|plans?|cost|subscri\w*|billing|monitoring|trial|starter|business|audit|490|29\s*€|99\s*€|preise?|pakete?|kosten|überwachung|testphase|abo\w*)\b|" + AR_PREFIX + r"(?:سعر|اسعار|تسعير|باق(?:ه|ات)|اشتراك(?:ات)?|اشترك|مراقب(?:ه|ات)|تجرب(?:ه|ات)|تكلف(?:ه|ات)|دفع|مجان(?:ي|ا)|خط(?:ه|ط))", re.I)
QA_CONTACT_WORDS = re.compile(r"\b(contact|support|email|help\s*desk|talk\s+to\s+human|kontakt|hilfe)\b|" + AR_PREFIX + r"(?:تواصل|اتصال|دعم|مساعده|بريد|ايميل)", re.I)
QA_CONCEPT_WORDS = re.compile(r"\b(what\s+is|how\s+does|explain|hndl|harvest\s+now|ml-?kem|kyber|post[- ]?quantum|was\s+ist|wie\s+funktioniert|erklär\w*)\b|" + AR_PREFIX + r"(?:ما\s+هو|ما\s+هي|كيف\s+يعمل|ما\s+بعد\s+الكم|تشفير\s+كم\w*)", re.I)
QA_NAV_WORDS = re.compile(r"\b(study|banks?|insurers?|countries|hosting|exposure|prooflab|adoption|tracker)\b|" + AR_PREFIX + r"(?:دراس(?:ه|ات)|بنوك|مصارف|تامين|دول|استضافه|تتبع|مؤشر)", re.I)
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
GERMAN_RE = re.compile(r"\b(welche|preise?|kosten|überwachung|frist\w*|konfigur\w*|prüf\w*|hilfe|pakete?|was\s+ist|wie\s+funktioniert|beinhaltet|gibt\s+es|kontakt)\b", re.I)
VALID_SKILLS = ("tls-evidence", "tls-scan", "tls-attestation", "msp-pilot", "paid-data", "agent-affiliate", "qa-assistant")


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
            {"id": "qa-assistant", "name": "Search & Q&A inquiry assistant (AR / EN / DE)",
             "description": "Answers questions in Arabic, English, or German about post-quantum TLS (X25519MLKEM768), "
                            "server configs (nginx, Apache, Caddy, HAProxy, Go, Node.js, CloudFront, Cloudflare), "
                            "BSI TR-02102-2 / NIS2 / DORA / NIST deadlines, Ed25519 signed receipts, MCP/A2A integration, "
                            "monitoring plans, and the 290 EUR MSP Pilot — with direct links and copy-paste snippets. Free.",
             "tags": ["qa", "search", "faq", "config", "bsi", "nis2", "dora", "pricing", "mcp", "multilingual"],
             "examples": ['{"skill":"qa-assistant","lang":"en"}', "How to configure nginx for X25519MLKEM768?", "ما هي مواعيد BSI وNIS2؟"]},
        ],
    }


def _detect_lang(joined: str, data: dict) -> str:
    explicit = str(data.get("lang") or "").strip().lower()
    if ARABIC_RE.search(joined):
        return "ar"
    if explicit in ("ar", "en", "de"):
        return explicit
    if GERMAN_RE.search(joined):
        return "de"
    return "en"


def _match_server_key(joined: str) -> str | None:
    low = joined.lower()
    mapping = [
        ("nginx", "nginx"),
        ("apache", "apache"),
        ("haproxy", "haproxy"),
        ("caddy", "caddy"),
        ("cloudfront", "cloudfront"),
        ("cloudflare", "cloudflare"),
        ("node", "node"),
        ("golang", "go"),
        (" go ", "go"),
    ]
    padded = f" {low} "
    for needle, key in mapping:
        if needle in padded and key in config_gen.SERVERS:
            return key
    return None


def _qa_answer(joined: str, base: str, lang: str, offer: dict, domain: str | None = None):
    """Deterministic trilingual Q&A & site-search responder backed by real site modules."""
    b = base.rstrip("/")
    l = lang if lang in ("ar", "en", "de") else "en"
    lq = f"?lang={l}"
    en_or_l = l if l != "de" else "en"
    norm = _norm_query(joined)

    # 1) Server / CDN configuration generator
    srv = _match_server_key(norm)
    integration = re.search(r"\b(?:mcp|a2a|acp|cursor|claude|vscode|vs\s+code)\b", norm, re.I)
    if not integration and (srv or QA_CONFIG_WORDS.search(norm)):
        srv_key = srv or "nginx"
        spec = config_gen.SERVERS[srv_key]
        chosen_key, var = config_gen.variant(srv_key, "")
        code_blocks = [st["code"] for st in var["steps"] if st.get("code") and st["kind"] in (config_gen.S_CONFIG, config_gen.S_RELOAD)]
        note = next((st["note"][l] for st in var["steps"] if st.get("note")), "")
        code = "\n\n".join(code_blocks) if code_blocks else config_gen.VERIFY
        text = {
            "ar": f"لتفعيل تبادل المفاتيح الهجين X25519MLKEM768 على {spec['name']} ({var['label']['ar']}): {note or 'طبّق الإعداد أدناه ثم أعد التحميل وتحقق بالفحص.'}",
            "de": f"So aktivieren Sie den hybriden Schlüsselaustausch X25519MLKEM768 auf {spec['name']} ({var['label']['de']}): {note or 'Konfiguration anwenden, neu laden und per Check verifizieren.'}",
            "en": f"To enable hybrid X25519MLKEM768 on {spec['name']} ({var['label']['en']}): {note or 'Apply the configuration below, reload, and verify with a live scan.'}",
        }[l]
        actions = [
            {"label": {"ar": f"مولّد إعدادات {spec['name']} الكامل ↗", "de": f"{spec['name']}-Konfigurator öffnen ↗", "en": f"Open {spec['name']} config generator ↗"}[l],
             "url": f"{b}/tools/pq-tls-config/{srv_key}{lq}"},
            {"label": {"ar": "دليل التنفيذ الكامل ↗", "de": "Vollständige Anleitung ↗", "en": "Full step-by-step guide ↗"}[l],
             "url": f"{b}/guides/{spec['guide']}?lang={en_or_l}"},
        ]
        if domain:
            actions.insert(0, {"label": {"ar": f"افحص {domain} الآن", "de": f"{domain} jetzt prüfen", "en": f"Scan {domain} now"}[l], "scan_domain": domain})
        return text, {
            "topic": "config", "lang": l, "server": srv_key, "variant": chosen_key,
            "code_label": f"{spec['name']} · X25519MLKEM768", "code": code,
            "actions": actions, "services": offer,
        }

    # 2) Deadlines & compliance (BSI / NIS2 / DORA / NIST / CNSA 2.0 / NCSC)
    if QA_DEADLINE_WORDS.search(norm):
        dtxt = deadlines.TEXT[l] if l in deadlines.TEXT else deadlines.TEXT["en"]
        pts = list(dtxt["short"][:3]) + [
            f"{y}: {dtxt['milestones'][k]}" for y, k in deadlines.MILESTONES if y in ("2026", "2030", "2035")
        ]
        text = {
            "ar": "المواعيد الرسمية للانتقال إلى التشفير ما بعد الكم (BSI TR-02102-2 وNIS2 وDORA وNIST وEU): لا يوجد قانون اليوم يُلزم موقعاً خاصاً، لكن الاتحاد الأوروبي يبدأ الانتقال في 2026، والأنظمة عالية الأهمية حتى 2030–2031، والإلغاء الكامل للتشفير التقليدي في 2035. تبادل المفاتيح (X25519MLKEM768) يمكن تفعيله اليوم فوراً.",
            "de": "Offizielle Post-Quantum-Fristen (BSI TR-02102-2, NIS2, DORA, EU-Roadmap, NIST): Kein Gesetz erzwingt PQ-TLS heute für private Websites, aber die EU startet 2026, hochkritische Systeme folgen bis 2030–2031, und klassische Verfahren laufen bis 2035 aus. Den Schlüsselaustausch (X25519MLKEM768) können Sie bereits heute aktivieren.",
            "en": "Official PQC timelines (BSI TR-02102-2, NIS2, DORA, EU roadmap, NIST IR 8547): no law forces private sites today, but EU member states start transitions in 2026, high-risk systems migrate by 2030–2031, and classical algorithms phase out by 2035. Key exchange (X25519MLKEM768) is fixable today.",
        }[l]
        return text, {
            "topic": "deadlines", "lang": l, "points": pts,
            "actions": [
                {"label": {"ar": "صفحة المواعيد الرسمية والمصادر ↗", "de": "Offizielle Fristen & Quellen ↗", "en": "Official deadlines & sources ↗"}[l], "url": f"{b}/deadlines{lq}"},
                {"label": {"ar": "عرض MSP Pilot (290 €) ↗", "de": "MSP Pilot (290 €) ansehen ↗", "en": "MSP Partner Pilot (290 €) ↗"}[l], "url": f"{b}/partners{lq}#msp-pilot"},
                {"label": {"ar": "عينة تقرير PDF للمدقق ↗", "de": "Kostenlose Auditor-PDF-Probe ↗", "en": "Free sample Auditor PDF ↗"}[l], "url": f"{b}/api/v1/attestation/sample.pdf"},
            ],
            "services": offer,
        }

    # 3) Signed receipts & offline verification
    if QA_RECEIPT_WORDS.search(norm):
        text = {
            "ar": "كل فحص عبر الموقع أو API أو MCP أو A2A يُصدر إيصالاً موقّعاً رقمياً v1 بصيغة Ed25519 JWS (صالح 24 ساعة وفق سياسة qa-pqc-transport 1.0) قابل للتحقق محلياً دون اتصال عبر /.well-known/jwks.json أو أداة tools/qa_verify.py في خطوط CI/CD.",
            "de": "Jeder Scan über Web, API, MCP oder A2A erzeugt eine 24h gültige, offline verifizierbare Ed25519-JWS-Quittung (v1, Policy qa-pqc-transport 1.0), prüfbar gegen /.well-known/jwks.json und tools/qa_verify.py in CI/CD.",
            "en": "Every scan via Web, API, MCP, or A2A issues a 24h offline-verifiable Ed25519 compact JWS receipt (v1, policy qa-pqc-transport 1.0), verifiable against /.well-known/jwks.json or tools/qa_verify.py in CI/CD.",
        }[l]
        return text, {
            "topic": "signed-receipts", "lang": l,
            "code_label": "Offline CI verification (Ed25519 JWS)",
            "code": f"curl -sS -X POST {b}/api/v1/scan -H 'Content-Type: application/json' -d '{{\"host\":\"cloudflare.com\",\"port\":443}}' | python3 tools/qa_verify.py --host cloudflare.com --port 443",
            "actions": [
                {"label": "JWKS (/.well-known/jwks.json) ↗", "url": f"{b}/.well-known/jwks.json"},
                {"label": "Policy v1.0 ↗", "url": f"{b}{receipts.POLICY_PATH}"},
                {"label": {"ar": "توثيق الوكلاء وAPI ↗", "de": "API & Agenten-Doku ↗", "en": "API & Agents docs ↗"}[l], "url": f"{b}/agents?lang={en_or_l}"},
            ],
            "services": offer,
        }

    # 4) MCP / A2A / API / Developer tools
    if QA_MCP_WORDS.search(norm):
        text = {
            "ar": "يدعم Quantum Aether بروتوكولات MCP (13 أداة + 5 موارد + 4 قوالب جاهزة على /mcp) وA2A 0.3.0 الموقّع (على /a2a) وACP وHTTP REST بدون مفتاح API للبحث والفحص المجاني.",
            "de": "Quantum Aether unterstützt Remote-MCP (13 Tools, 5 Resources, 4 Prompts unter /mcp), signiertes A2A 0.3.0 (/a2a), ACP sowie HTTP REST — kostenlos und ohne API-Key für Basis-Checks.",
            "en": "Quantum Aether exposes remote Streamable HTTP MCP (13 tools, 5 resources, 4 prompts at /mcp), signed A2A 0.3.0 (/a2a), ACP, and HTTP REST — no API key required for free lookups and scans.",
        }[l]
        return text, {
            "topic": "mcp-a2a", "lang": l,
            "code_label": "Claude Code (1-line MCP install)",
            "code": f"claude mcp add --transport http quantum-aether {b}/mcp",
            "actions": [
                {"label": {"ar": "صفحة MCP والربط بضغطة واحدة ↗", "de": "MCP & 1-Klick-Installation ↗", "en": "MCP 1-click install & docs ↗"}[l], "url": f"{b}/agents?lang={en_or_l}#mcp"},
                {"label": "A2A Agent Card ↗", "url": f"{b}/.well-known/agent-card.json"},
                {"label": "OpenAPI ↗", "url": f"{b}/openapi.yaml"},
            ],
            "services": offer,
        }

    # 5) Pricing, Monitoring, Subscriptions & Plans (checked BEFORE generic 'ما هي / what is' concept matcher!)
    if QA_PRICING_WORDS.search(norm):
        pts = {
            "ar": [
                "الفحص الفوري + الإيصال الموقّع Ed25519: مجاني (0 €).",
                "المراقبة اليومية الآلية: تجربة مجانية 14 يوماً (حتى 10 نطاقات، بدون بطاقة)، ثم Starter بـ 29 €/شهر أو Business بـ 99 €/شهر (حتى 100 نطاق).",
                "MSP Pilot لمزودي خدمات IT: حتى 50 نطاقاً مع تقرير PDF Ampel ألماني وإيصالات موقّعة بـ 290 € مرة واحدة.",
                "التقرير الكامل: 49 $ · حزمة المدقّق (PDF + CycloneDX CBOM عبر x402): 5.00 USDC · تدقيق المؤسسة الكامل: 490 €.",
            ],
            "de": [
                "Sofort-Check + signierte Ed25519-Quittung: kostenlos (0 €).",
                "Tägliches Monitoring: 14 Tage kostenlos testen (bis 10 Domains, ohne Karte), danach Starter 29 €/Monat oder Business 99 €/Monat (bis 100 Domains).",
                "IT-Dienstleister / MSP Pilot: bis 50 Hostnamen, deutsches Ampel-PDF + signierte Quittungen + optionales Logo für 290 € einmalig.",
                "Vollbericht: 49 $ · Auditor-PDF + CycloneDX CBOM (x402): 5,00 USDC · Organisations-Audit: 490 €.",
            ],
            "en": [
                "Instant TLS check + Ed25519 signed receipt: free ($0).",
                "Daily PQ-TLS monitoring: 14-day free trial (up to 10 domains, no card), then Starter 29 €/mo or Business 99 €/mo (up to 100 domains).",
                "IT-Dienstleister / MSP Pilot: up to 50 hostnames, German Ampel PDF + signed receipts + optional logo for 290 € one-time.",
                "Full remediation report: $49 · Auditor PDF + CycloneDX CBOM (x402): 5.00 USDC · Organization audit: 490 €.",
            ],
        }[l]
        text = {
            "ar": "ملخص الاشتراكات والأسعار المتوفرة حالياً في Quantum Aether (تبدأ بتجربة مجانية 14 يوماً بدون بطاقة):",
            "de": "Übersicht der aktuellen Quantum-Aether-Tarife und Abos (Start mit 14 Tagen kostenloser Testphase):",
            "en": "Here is the current Quantum Aether pricing and subscription overview (starts with a 14-day free trial, no card):",
        }[l]
        return text, {
            "topic": "pricing", "lang": l, "points": pts,
            "actions": [
                {"label": {"ar": "ابدأ تجربة الاشتراك 14 يوماً مجاناً ↗", "de": "14 Tage kostenlos testen ↗", "en": "Start 14-day free trial ↗"}[l], "url": f"{b}/monitoring{lq}#trial-form"},
                {"label": {"ar": "عرض MSP Pilot (290 €) ↗", "de": "MSP Pilot (290 €) ↗", "en": "MSP Pilot (290 €) ↗"}[l], "url": f"{b}/partners{lq}#msp-pilot"},
                {"label": {"ar": "صفحة الأسعار الكاملة ↗", "de": "Alle Preise ansehen ↗", "en": "Full pricing page ↗"}[l], "url": f"{b}/pricing{lq}"},
            ],
            "services": offer,
        }

    # 6) Contact & direct support
    if QA_CONTACT_WORDS.search(norm):
        text = {
            "ar": "يسعدنا مساعدتك مباشرةً — يمكنك مراسلة فريق Quantum Aether عبر البريد الإلكتروني أو طلب عرض MSP Pilot (حتى 50 نطاقاً بـ 290 €) بدون دفع مسبق.",
            "de": "Wir helfen Ihnen gerne direkt weiter — schreiben Sie dem Quantum-Aether-Team per E-Mail oder fragen Sie unverbindlich den MSP Pilot (bis 50 Hostnamen, 290 €) an.",
            "en": "We are happy to help directly — email the Quantum Aether team below or request the fixed-scope MSP Pilot (up to 50 hostnames, 290 EUR) with no upfront payment.",
        }[l]
        return text, {
            "topic": "contact", "lang": l, "allow_contact": True,
            "actions": [
                {"label": {"ar": "طلب عرض MSP Pilot (290 €) ↗", "de": "MSP Pilot anfragen ↗", "en": "Request MSP Pilot ↗"}[l], "url": f"{b}/partners{lq}#msp-pilot"},
                {"label": {"ar": "صفحة الشركات ↗", "de": "Für Unternehmen ↗", "en": "For business ↗"}[l], "url": f"{b}/business{lq}"},
            ],
            "services": offer,
        }

    # 7) Concept / What is PQ-TLS & HNDL
    if QA_CONCEPT_WORDS.search(norm):
        text = {
            "ar": "تشفير TLS لما بعد الكم (مثل X25519MLKEM768 وفق معيار NIST FIPS 203) يحمي حركة HTTPS اليوم ضد خطر «اجمع الآن وفكّ التشفير لاحقاً» (Harvest Now, Decrypt Later). متصفحات Chrome وFirefox وEdge تدعمه افتراضياً؛ تحتاج فقط لتفعيله على الخادم أو الـ CDN.",
            "de": "Post-Quantum-TLS (hybrid X25519MLKEM768 nach NIST FIPS 203) schützt heutigen HTTPS-Datenverkehr gegen «Harvest Now, Decrypt Later». Chrome, Firefox und Edge unterstützen es standardmäßig — es muss nur am Server oder CDN aktiviert werden.",
            "en": "Post-quantum TLS (hybrid X25519MLKEM768, NIST FIPS 203) protects today's HTTPS traffic against 'Harvest Now, Decrypt Later'. Chrome, Firefox, and Edge already use it by default; you only need to enable it on your server or CDN.",
        }[l]
        return text, {
            "topic": "concept", "lang": l,
            "actions": [
                {"label": {"ar": "دراسة أكبر 1,000 موقع ↗", "de": "Top-1.000-Studie ↗", "en": "Top 1,000 websites study ↗"}[l], "url": f"{b}/study/top-1000-post-quantum-tls{lq}"},
                {"label": {"ar": "أدلة التنفيذ العملية ↗", "de": "Praxisanleitungen ↗", "en": "Practical guides ↗"}[l], "url": f"{b}/guides?lang={en_or_l}"},
                {"label": {"ar": "فحص cloudflare.com كمثال", "de": "cloudflare.com als Beispiel prüfen", "en": "Check cloudflare.com example"}[l], "prompt": "Is cloudflare.com post-quantum ready?"},
            ],
            "services": offer,
        }

    # 8) Site search / observatory datasets
    if QA_NAV_WORDS.search(norm):
        text = {
            "ar": "روابط سريعة لأقسام الرصد والبيانات المفتوحة في Quantum Aether:",
            "de": "Direktzugriff auf die Messdaten und Tracker von Quantum Aether:",
            "en": "Quick links to Quantum Aether observatory datasets and trackers:",
        }[l]
        return text, {
            "topic": "search", "lang": l,
            "actions": [
                {"label": {"ar": "متتبّع التبنّي الأسبوعي ↗", "de": "Wöchentlicher Tracker ↗", "en": "Weekly adoption tracker ↗"}[l], "url": f"{b}/adoption{lq}"},
                {"label": {"ar": "البنوك الأسبوعية ↗", "de": "Banken-Tracker ↗", "en": "Weekly banks tracker ↗"}[l], "url": f"{b}/banks/weekly{lq}"},
                {"label": {"ar": "الدول والاستضافة ↗", "de": "Länder & Hosting ↗", "en": "Countries & hosting ↗"}[l], "url": f"{b}/adoption/countries{lq}"},
                {"label": {"ar": "سجل نافذة التعرّض ↗", "de": "Exposure Registry ↗", "en": "Exposure Registry ↗"}[l], "url": f"{b}/exposure?lang={en_or_l}"},
            ],
            "services": offer,
        }

    # 9) General inquiry fallback (preserves 'hostname' in English for A2A callers + contact option for humans)
    text = {
        "ar": "يمكنني فحص أي نطاق عام (اكتب مثلاً: cloudflare.com أو «افحص example.com»)، أو الإجابة فوراً عن الأسعار والاشتراكات، عرض MSP Pilot (290 €)، إعدادات Nginx/Cloudflare، ومواعيد BSI/NIS2/DORA. إذا كان لديك استفسار مخصص، تواصل مع فريقنا مباشرة من الزر أدناه.",
        "de": "Ich kann jede öffentliche Domain prüfen (z. B. «cloudflare.com» oder «scan example.com») oder sofort Fragen zu Preisen, dem 290-€-MSP-Piloten, nginx/Cloudflare-Konfiguration sowie BSI/NIS2/DORA-Fristen beantworten. Für individuelle Anfragen schreiben Sie direkt unserem Team.",
        "en": "Send a public hostname, e.g. 'Is example.com post-quantum ready?' or {\"skill\":\"tls-scan\",\"domain\":\"example.com\"}, or ask about pricing, the 290 EUR MSP Pilot, nginx/Cloudflare config, BSI/NIS2 deadlines, Ed25519 receipts, or MCP/A2A integration.",
    }[l]
    return text, {
        "topic": "help", "lang": l, "allow_contact": True,
        "skills": list(VALID_SKILLS),
        "actions": [
            {"label": {"ar": "عرض MSP Pilot (290 €) ↗", "de": "MSP Pilot (290 €) ↗", "en": "MSP Pilot (290 €) ↗"}[l], "url": f"{b}/partners{lq}#msp-pilot"},
            {"label": {"ar": "الأسعار والمراقبة ↗", "de": "Preise & Monitoring ↗", "en": "Pricing & monitoring ↗"}[l], "url": f"{b}/pricing{lq}"},
            {"label": {"ar": "مولّد إعدادات الخوادم ↗", "de": "TLS-Konfigurator ↗", "en": "PQ-TLS config generator ↗"}[l], "url": f"{b}/tools/pq-tls-config{lq}"},
        ],
        "services": offer,
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
    """-> (skill, domain, joined_text, data_dict) from text and/or data parts."""
    text, data = [], {}
    for p in message.get("parts") or []:
        if not isinstance(p, dict):
            continue
        if p.get("kind") == "text" and isinstance(p.get("text"), str):
            text.append(p["text"][:2000])
        elif p.get("kind") == "data" and isinstance(p.get("data"), dict):
            data.update(p["data"])
    joined = " ".join(text)
    norm = _norm_query(joined)
    skill = data.get("skill") if data.get("skill") in VALID_SKILLS else None
    domain = data.get("domain") if isinstance(data.get("domain"), str) else None
    if not domain:
        m = HOST_RE.search(joined)
        if m and m.group(1).lower() not in ("node.js", "llms.txt", "sample.pdf"):
            domain = m.group(1)
    if not skill:
        if MSP_PILOT_WORDS.search(norm):
            skill = "msp-pilot"
        elif ATTESTATION_WORDS.search(norm):
            skill = "tls-attestation"
        elif AFFILIATE_WORDS.search(norm) and not domain:
            skill = "agent-affiliate"
        elif re.search(r"\b(buy|pay|report|x402|sector|snapshot)\b|" + AR_PREFIX + r"(?:شراء|تقرير)", norm, re.I) and not domain and not QA_PRICING_WORDS.search(norm):
            skill = "paid-data"
        elif (QA_CONFIG_WORDS.search(norm) or QA_DEADLINE_WORDS.search(norm)
              or QA_RECEIPT_WORDS.search(norm) or QA_MCP_WORDS.search(norm)
              or QA_PRICING_WORDS.search(norm) or QA_CONTACT_WORDS.search(norm)
              or QA_CONCEPT_WORDS.search(norm) or QA_NAV_WORDS.search(norm)) and not domain:
            skill = "qa-assistant"
        elif domain and re.search(r"\b(config(?:ure|uration)?|konfigur\w*|nginx|apache|haproxy|caddy|openssl)\b|" + AR_PREFIX + r"(?:اعداد(?:ات)?|تفعيل|كيف\s+افعل)", norm, re.I) and not SCAN_WORDS.search(norm):
            skill = "qa-assistant"
        elif SCAN_WORDS.search(norm):
            skill = "tls-scan"
        elif domain:
            skill = "tls-evidence"
        else:
            skill = "qa-assistant"
    return skill, domain, joined, data


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
        skill, domain, joined, req_data = _read_request(message)
        lang = _detect_lang(joined, req_data)
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
            actions = [
                {"label": {"ar": "احجز / اطلب تفاصيل MSP Pilot ↗", "de": "MSP Pilot (290 €) anfragen ↗", "en": "Request MSP Pilot (290 €) ↗"}[lang],
                 "url": f"{b}/partners?lang={lang}#msp-pilot"},
                {"label": {"ar": "معاينة عينة PDF للمدقق مجاناً ↗", "de": "Kostenlose PDF-Probe ansehen ↗", "en": "Preview free sample PDF ↗"}[lang],
                 "url": offer["msp_pilot"]["sample_pdf"]},
            ]
            pilot = dict(offer["msp_pilot"], mcp=b + "/mcp", lang=lang, actions=actions, services=offer)
            _audit("msp-pilot", domain or "", "ok")
            if lang == "ar":
                txt = (
                    "عرض MSP / IT-Dienstleister Pilot (290 € لمرة واحدة · 3 مقاعد للشركاء): "
                    "فحص حتى 50 نطاقاً لعملائك وفق X25519MLKEM768 وBSI TR-02102-2 وNIS2، مع تقرير PDF بنظام الإشارات (Ampel) "
                    "وإيصالات Ed25519 موقّعة قابلة للتحقق دون اتصال + شعار شريكك اختيارياً. لا يوجد دفع مسبق."
                )
            elif lang == "de":
                txt = (
                    "IT-Dienstleister / MSP Partner-Pilot (290 € einmalig · 3 Partner-Plätze): "
                    "Prüfung von bis zu 50 Kunden-Hostnamen auf X25519MLKEM768 / BSI TR-02102-2 / NIS2 als deutsches "
                    "Ampel-PDF (optional mit Partner-Logo) plus offline prüfbare Ed25519-Quittungen. Keine Vorauszahlung."
                )
            else:
                txt = (
                    "IT-Dienstleister / MSP Partner Pilot (290 EUR one-time, 3 partner slots): up to 50 client hostnames "
                    "measured for post-quantum TLS (X25519MLKEM768 / BSI TR-02102-2 / NIS2), delivered as a German Ampel "
                    "PDF report (optional partner white-label logo) + offline-verifiable Ed25519 JWS signed receipts. "
                    f"Book or request details (no upfront payment): {pilot['url']} (DE) / {pilot['url_en']} (EN). "
                    f"Free archived single-host sample PDF: {pilot['sample_pdf']}."
                )
            return _reply(txt, pilot)
        if skill == "tls-attestation":
            offer = services_offer(b, domain=domain, price_usd=price_usd, sector_price_usd=sector_price_usd)
            att = dict(offer["tls_attestation"], example_request={"domain": domain or "example.com"},
                       mcp=b + "/mcp", actions=[
                           {"label": {"ar": "عينة Auditor PDF المجانية ↗", "de": "Kostenlose Auditor-PDF-Probe ↗", "en": "Free sample Auditor PDF ↗"}[lang], "url": offer["tls_attestation"]["sample_pdf"]},
                           {"label": {"ar": "توثيق Attestation API ↗", "de": "Attestation-API-Doku ↗", "en": "Attestation API docs ↗"}[lang], "url": f"{b}/agents?lang={'ar' if lang == 'ar' else 'en'}#attestation"},
                       ], services=offer)
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
            data = dict(offer["partner_affiliate"], mcp=b + "/mcp", actions=[
                {"label": {"ar": "صفحة برنامج الشركاء 30% ↗", "de": "Partnerprogramm (30 %) ↗", "en": "Partner programme (30%) ↗"}[lang], "url": f"{b}/partners?lang={lang}"},
            ], services=offer)
            _audit("agent-affiliate", domain or "", "ok")
            return _reply(
                "AI Agent Affiliate Programme: call MCP tool register_agent_affiliate or POST "
                f"{b}/api/v1/agent/affiliate/register with name, contact_email, payout_method (usdc|paypal), "
                "payout_destination, and consent_terms=true to receive an instant ?ref=CODE link. Earns 30% of "
                "monitoring payments for 12 months and 20% of one-time reports/audits; paid monthly manually by "
                f"the owner after a 30-day hold (min $50). Terms: {b}/partners?lang=en", data)
        if skill == "paid-data":
            offer = services_offer(b, domain=domain, price_usd=price_usd, sector_price_usd=sector_price_usd)
            data = dict(offer, mcp=b + "/mcp", actions=[
                {"label": {"ar": "الأسعار والباقات ↗", "de": "Preise ansehen ↗", "en": "View pricing ↗"}[lang], "url": f"{b}/pricing?lang={lang}"},
                {"label": {"ar": "عينة PDF المجانية ↗", "de": "Kostenlose PDF-Probe ↗", "en": "Free sample PDF ↗"}[lang], "url": offer["tls_attestation"]["sample_pdf"]},
            ])
            _audit("paid-data", domain or "", "ok")
            return _reply(
                "Paid data is bought per call with x402 (USDC on Base) over HTTP or MCP (unpaid calls return the price "
                "challenge and never charge): Auditor-Ready PDF + CycloneDX CBOM attestation (5.00 USDC; free sample "
                f"PDF at {offer['tls_attestation']['sample_pdf']}), full report, or weekly sector snapshot. Also "
                f"available: 14-day free daily monitoring trial (Starter 29 EUR/mo, Business 99 EUR/mo at "
                f"{offer['monitoring']['trial_url']}), MSP Partner Pilot (290 EUR at {offer['msp_pilot']['url']}), and "
                f"organization compliance audit (490 EUR at {offer['organization_audit']['url']}).", data)
        if skill == "qa-assistant" or not domain:
            offer = services_offer(b, domain=domain, price_usd=price_usd, sector_price_usd=sector_price_usd)
            qa_text, qa_data = _qa_answer(joined, b, lang, offer, domain=domain)
            _audit("qa-assistant", domain or "", qa_data.get("topic", "ok"))
            return _reply(qa_text, qa_data)
        try:
            domain = quantum_vuln_scanner.normalize_domain(domain)
            if skill == "tls-scan":
                scan_id, raw = services["scan"](domain, "a2a")
                offer = services_offer(b, domain=domain, scan_id=scan_id, price_usd=price_usd, sector_price_usd=sector_price_usd)
                data = dict(services["summary"](scan_id, raw), services=offer, actions=[
                    {"label": {"ar": "فتح صفحة نتيجة الفحص والإيصال ↗", "de": "Prüfergebnis & Quittung öffnen ↗", "en": "Open scan report & receipt ↗"}[lang],
                     "url": f"{b}/scan/{scan_id}?lang={lang}"},
                    {"label": {"ar": "مراقبة يومية مجانية 14 يوماً ↗", "de": "14 Tage kostenlos überwachen ↗", "en": "14-day free monitoring ↗"}[lang],
                     "url": offer["monitoring"]["trial_url"]},
                ])
                _attach_receipt(data, "tls-scan")
                _, _, _, dual = receipts.issue_and_store_receipt(services, raw, scan_id=scan_id, endpoint_type="a2a")
                data.update(dual)
                pq = data.get("post_quantum_key_exchange")
                if lang == "ar":
                    text = (f"نتيجة فحص {domain}: الدرجة {data.get('grade')}، تبادل المفاتيح {data.get('key_exchange_group') or 'غير محدد'}"
                            f"{' (مقاوم للكم ✓)' if pq else ' (تقليدي فقط)'}. تم إصدار إيصال Ed25519 موقّع v1.")
                elif lang == "de":
                    text = (f"Scan-Ergebnis für {domain}: Note {data.get('grade')}, Schlüsselaustausch {data.get('key_exchange_group') or 'unbekannt'}"
                            f"{' (Post-Quantum ✓)' if pq else ' (nur klassisch)'}. Signierte Ed25519-Quittung v1 erstellt.")
                else:
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
                    data["actions"] = [
                        {"label": {"ar": f"افحص {domain} مباشرة الآن", "de": f"{domain} jetzt live prüfen", "en": f"Run live scan on {domain}"}[lang], "scan_domain": domain},
                    ]
                    text = {
                        "ar": f"لا يوجد قياس مخزّن لـ {domain} بعد (وهذا ليس دليلاً على أي خلل). اضغط الزر أدناه لإجراء فحص مباشر فوري.",
                        "de": f"Für {domain} liegt noch kein gespeicherter Messwert vor. Klicken Sie unten für eine Live-Prüfung.",
                        "en": f"No stored evidence for {domain} yet (not proof of anything). Ask to 'scan {domain}' for a measurement.",
                    }[lang]
                else:
                    data["actions"] = [
                        {"label": {"ar": f"فحص جديد لـ {domain}", "de": f"{domain} neu prüfen", "en": f"Re-scan {domain} now"}[lang], "scan_domain": domain},
                        {"label": {"ar": "صفحة التحقق والأدلة ↗", "de": "Verifizierungsseite ↗", "en": "Verification page ↗"}[lang], "url": b + "/verify/" + domain},
                        {"label": {"ar": "تجربة مراقبة 14 يوماً ↗", "de": "14 Tage kostenlos überwachen ↗", "en": "14-day free monitoring ↗"}[lang], "url": offer["monitoring"]["trial_url"]},
                    ]
                    if lang == "ar":
                        obs = {"observed_pq": "يدعم تبادل المفاتيح لما بعد الكم ✓", "observed_classical": "تبادل مفاتيح تقليدي فقط",
                               "undetermined": "غير محسوم"}.get(data.get("observation_status"), "انظر التفاصيل")
                        text = f"{domain}: {obs} (المجموعة: {data.get('group') or 'غير محددة'}، الدرجة: {data.get('grade')})، آخر قياس: {data.get('checked_at')}."
                    elif lang == "de":
                        obs = {"observed_pq": "handelt Post-Quantum-Schlüsselaustausch aus ✓", "observed_classical": "nur klassischer Schlüsselaustausch",
                               "undetermined": "nicht eindeutig"}.get(data.get("observation_status"), "siehe Daten")
                        text = f"{domain}: {obs} (Gruppe {data.get('group') or 'unbekannt'}, Note {data.get('grade')}), geprüft {data.get('checked_at')}."
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
