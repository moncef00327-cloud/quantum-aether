# x402_attestation.py — paid, portable, signed post-quantum TLS attestation bundle (2026-11-25).
#
# Owner decision 2026-11-25: a paid agent-native SKU. Basic scans and signed receipts stay FREE; this charges
# only for a self-contained, offline-verifiable EVIDENCE BUNDLE (fresh signed scan + verification pointers +
# explicit scope) delivered inline over x402 USDC-on-Base, so an AI agent can pay autonomously at the moment its
# user needs compliance evidence for a named domain. It is NOT a legal certification and makes no new measurement.
#
# Priced via PRICE_USD below (owner-set). Reuses x402_pay.paywall(): the buyer is charged only after the
# facilitator settles, and never if building the bundle fails. Nobody is charged without actively signing a payment.
import datetime as dt

from flask import jsonify, request

import x402_pay

PRICE_USD = "5.00"  # owner-set 2026-11-25; change only with the owner.


def register(bp, deps):
    db = deps["db"]
    public_base = deps["base"]
    perform_scan = deps["perform_scan"]
    scan_summary = deps["scan_summary"]
    issue_receipt = deps["issue_receipt"]
    normalize_domain = deps["normalize_domain"]
    ScanError = deps["scan_error"]

    @bp.get("/api/v1/attestation")
    def api_v1_attestation():
        """Paid signed PQ-TLS attestation bundle for ?domain=. Returns a 402 x402 challenge until paid;
        once paid, a fresh signed observation packaged as portable, offline-verifiable evidence."""
        try:
            domain = normalize_domain(request.args.get("domain", ""))
        except ScanError as exc:
            return jsonify(error=exc.code, message=str(exc)), 400
        conn = db()
        x402_pay.init(conn)

        def deliver():
            scan_id, result = perform_scan(domain, "pack")  # always a fresh scan
            _, _, _, signed_receipt = issue_receipt(result, scan_id)
            base = public_base()
            return {
                "type": "qa-pq-tls-attestation",
                "version": "1",
                "issued_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "domain": domain,
                "scan": scan_summary(scan_id, result),
                "signed_receipt": signed_receipt,
                "verification": {
                    "jwks": base + "/.well-known/jwks.json",
                    "policy": base + "/policies/qa-pqc-transport/1.0",
                    "how": "Verify the Ed25519 JWS in signed_receipt offline against the JWKS; no trust in this server required.",
                },
                "scope": ("Signed observation of public TLS transport (hybrid post-quantum key exchange) from one "
                          "vantage, at issued_at. Supporting compliance evidence (e.g. NIS2/DORA transport), NOT a "
                          "legal certification and NOT a full cryptographic audit."),
            }

        description = ("Signed post-quantum TLS attestation bundle for " + domain +
                       " — portable, offline-verifiable evidence (free basic scan at /api/v1/scan).")
        return x402_pay.paywall(
            conn, PRICE_USD, description, deliver, mime="application/json",
            resource_extra={
                "serviceName": "Quantum Aether — PQ-TLS attestation",
                "tags": ["tls", "post-quantum", "compliance", "nis2", "dora", "attestation", "signed-receipt"],
            },
        )
