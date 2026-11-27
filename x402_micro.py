"""x402 v2 micro-commerce endpoints for autonomous AI agents (owner-approved 2026-11-27).

Designed under autonomous agent auto-spend limits on Base USDC (eip155:8453):
  * POST/GET /api/v1/x402/batch-scan ($0.10 USDC) — up to 10 public domains in parallel with Ed25519 JWS receipts, no rate limit.
  * GET      /api/v1/x402/cbom       ($0.25 USDC) — live full scan + CycloneDX 1.6 CBOM JSON + Ed25519 JWS receipt.

All existing paid SKUs ($0.50 sector snapshot, $5.00 auditor PDF attestation, $49 full report, 29/99 EUR monitoring,
290 EUR MSP Pilot) remain completely unchanged.
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import uuid

from flask import jsonify, request

import qrisk
import quantum_vuln_scanner as qs
import x402_attestation
import x402_pay

BATCH_PRICE_USD = "0.10"
CBOM_PRICE_USD = "0.25"
MAX_BATCH_DOMAINS = 10


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_batch_domains(normalize_domain):
    raw_list = None
    if request.is_json:
        body = request.get_json(silent=True)
        if isinstance(body, dict) and "domains" in body:
            raw_list = body.get("domains")
    if raw_list is None and request.args.get("domains"):
        raw_list = [p.strip() for p in request.args.get("domains", "").split(",") if p.strip()]
    if raw_list is None:
        return None  # discovery probe without input
    if not isinstance(raw_list, list) or not (1 <= len(raw_list) <= MAX_BATCH_DOMAINS):
        raise qs.ScanError("invalid_batch", f"domains must be a list of 1 to {MAX_BATCH_DOMAINS} public domains")
    cleaned = []
    seen = set()
    for item in raw_list:
        dom = normalize_domain(str(item or ""))
        if dom not in seen:
            seen.add(dom)
            cleaned.append(dom)
    return cleaned


def register(bp, deps):
    """deps: db, base, perform_scan, scan_summary, normalize_domain, scan_error, issue_receipt."""
    db = deps["db"]
    public_base = deps["base"]
    perform_scan = deps["perform_scan"]
    scan_summary = deps["scan_summary"]
    normalize_domain = deps["normalize_domain"]
    ScanError = deps["scan_error"]
    issue_receipt = deps["issue_receipt"]
    scan_one_fn = deps.get("scan_one") or (lambda dom: qs.scan_full(dom, timeout=6.0))

    @bp.route("/api/v1/x402/batch-scan", methods=["GET", "POST"])
    def api_v1_x402_batch_scan():
        """Paid micro-SKU ($0.10 USDC on Base): scan up to 10 public domains in parallel with signed Ed25519 receipts."""
        has_sig = bool(request.headers.get("PAYMENT-SIGNATURE", ""))
        try:
            domains = _extract_batch_domains(normalize_domain)
        except ScanError as exc:
            return jsonify(error=exc.code, message=str(exc)), 400
        if domains is None:
            if has_sig:
                return jsonify(error="invalid_batch", message=f"Provide 1..{MAX_BATCH_DOMAINS} domains in JSON body or ?domains=a.com,b.com"), 400
            domains = ["example.com"]

        conn = db()
        x402_pay.init(conn)
        base = public_base()

        def deliver():
            def probe_one(dom):
                try:
                    return dom, scan_one_fn(dom), None
                except Exception as exc:  # noqa: BLE001
                    return dom, None, f"{type(exc).__name__}: {exc}"[:160]

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(domains))) as pool:
                scanned = list(pool.map(probe_one, domains))

            results = []
            for dom, raw, err in scanned:
                if err or raw is None:
                    results.append({"domain": dom, "ok": False, "error": err or "scan_failed"})
                    continue
                try:
                    _, _, _, receipt_dual = issue_receipt(raw, None)
                except Exception as exc:  # noqa: BLE001
                    results.append({"domain": dom, "ok": False, "error": f"{type(exc).__name__}: {exc}"[:160]})
                    continue
                kx = raw.get("key_exchange") or {}
                results.append({
                    "domain": dom,
                    "ok": True,
                    "grade": raw.get("grade"),
                    "tls_version": kx.get("version"),
                    "group": kx.get("group"),
                    "pq": bool(kx.get("pq")),
                    "pq_supported_not_preferred": bool(kx.get("pq_supported_not_preferred")),
                    "pq_supported_group": kx.get("pq_supported_group"),
                    "findings": raw.get("findings") or [],
                    "signed_receipt": receipt_dual,
                })

            pq_n = sum(1 for r in results if r.get("ok") and r.get("pq"))
            not_pref_n = sum(1 for r in results if r.get("ok") and r.get("pq_supported_not_preferred"))
            classical_n = sum(1 for r in results if r.get("ok") and not r.get("pq") and r.get("tls_version") == "TLSv1.3" and not r.get("pq_supported_not_preferred"))
            tls12_n = sum(1 for r in results if r.get("ok") and r.get("tls_version") == "TLSv1.2")
            failed_n = sum(1 for r in results if not r.get("ok"))

            return {
                "sku": "x402_batch_scan_v1",
                "batch_id": "qa_batch_" + uuid.uuid4().hex[:16],
                "issued_at": _now_iso(),
                "count": len(results),
                "summary": {
                    "pq_hybrid": pq_n,
                    "pq_supported_not_preferred": not_pref_n,
                    "classical_tls13": classical_n,
                    "tls12": tls12_n,
                    "failed": failed_n,
                },
                "jwks_uri": f"{base}/.well-known/jwks.json",
                "results": results,
            }

        discovery = {
            "info": {
                "input": {"type": "http", "method": "POST", "bodyType": "json",
                          "body": {"domains": ["cloudflare.com", "github.com"]}},
                "output": {"type": "json", "example": {"sku": "x402_batch_scan_v1", "count": 2, "summary": {"pq_hybrid": 1, "classical_tls13": 1}}},
            },
            "schema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "input": {
                        "type": "object",
                        "properties": {
                            "body": {
                                "type": "object",
                                "properties": {
                                    "domains": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": MAX_BATCH_DOMAINS}
                                },
                                "required": ["domains"],
                            }
                        },
                    }
                },
            },
        }
        return x402_pay.paywall(
            conn,
            BATCH_PRICE_USD,
            "Quantum Aether batch post-quantum TLS scan for up to 10 public domains with Ed25519 signed receipts and server-preference downgrade detection (no rate limit).",
            deliver,
            discovery=discovery,
            resource_extra={"serviceName": "Quantum Aether Batch PQ-TLS Scan", "tags": ["pqc", "tls", "security", "batch", "ed25519", "ml-kem"]},
        )

    @bp.get("/api/v1/x402/cbom")
    def api_v1_x402_cbom():
        """Paid micro-SKU ($0.25 USDC on Base): live full PQ-TLS scan + CycloneDX 1.6 CBOM JSON + Ed25519 signed receipt."""
        raw_dom = request.args.get("domain", "").strip()
        has_sig = bool(request.headers.get("PAYMENT-SIGNATURE", ""))
        if not raw_dom:
            if has_sig:
                return jsonify(error="invalid_domain", message="Provide ?domain=example.com"), 400
            domain = "example.com"
        else:
            try:
                domain = normalize_domain(raw_dom)
            except ScanError as exc:
                return jsonify(error=exc.code, message=str(exc)), 400

        conn = db()
        x402_pay.init(conn)
        base = public_base()

        def deliver():
            scan_id, result = perform_scan(domain, "pack")
            _, _, _, signed_receipt = issue_receipt(result, scan_id)
            return {
                "sku": "x402_cbom_v1",
                "issued_at": _now_iso(),
                "domain": domain,
                "scan": scan_summary(scan_id, result),
                "key_exchange": result.get("key_exchange"),
                "certificate": result.get("certificate"),
                "findings": result.get("findings") or [],
                "cbom": qrisk.cbom(result),
                "signed_receipt": signed_receipt,
                "methodology": x402_attestation._methodology_block(base),
                "jwks_uri": f"{base}/.well-known/jwks.json",
            }

        discovery = {
            "info": {
                "input": {"type": "http", "method": "GET", "queryParams": {"domain": "example.com"}},
                "output": {"type": "json", "example": {"sku": "x402_cbom_v1", "domain": "example.com", "cbom": {"bomFormat": "CycloneDX", "specVersion": "1.6"}}},
            },
            "schema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "input": {
                        "type": "object",
                        "properties": {"queryParams": {"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]}},
                    }
                },
            },
        }
        return x402_pay.paywall(
            conn,
            CBOM_PRICE_USD,
            "Quantum Aether live full PQ-TLS scan + CycloneDX 1.6 Cryptographic Bill of Materials (CBOM) JSON + Ed25519 signed receipt.",
            deliver,
            discovery=discovery,
            resource_extra={"serviceName": "Quantum Aether Live CycloneDX 1.6 CBOM", "tags": ["cbom", "cyclonedx", "pqc", "tls", "nis2", "dora"]},
        )
