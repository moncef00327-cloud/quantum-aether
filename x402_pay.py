# x402_pay.py — generic x402 v2 "exact" EIP-3009 USDC-on-Base paywall for read-only data resources (2026-11-21).
# Same facilitator and checks as the report endpoint (quantum_saas_app.x402_agent_report), which stays unchanged.
# Every settled transaction is written to x402_payments (primary key = tx hash), so one payment unlocks one response.
import base64
import datetime as dt
import json
import logging
import re
import sqlite3

import requests
from flask import current_app, jsonify, request

log = logging.getLogger(__name__)

NETWORK = "eip155:8453"
ASSET = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"  # USDC on Base
FACILITATOR = "https://facilitator.payai.network"
ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{40}")
TX_RE = re.compile(r"0x[0-9a-f]{64}")

SCHEMA = """
CREATE TABLE IF NOT EXISTS x402_payments (
    tx          TEXT PRIMARY KEY,
    resource    TEXT NOT NULL,
    amount_usd  TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
"""


def init(conn):
    with conn:
        conn.executescript(SCHEMA)


def units(price_usd):
    """'0.50' -> '500000' (USDC has 6 decimals). Exact decimal, no float."""
    whole, _, frac = str(price_usd).partition(".")
    frac = (frac + "000000")[:6]
    return str(int(whole or "0") * 1_000_000 + int(frac))


def receiver():
    addr = str(current_app.config.get("USDC_BASE_ADDR", "")).lower()
    return addr if ADDRESS_RE.fullmatch(addr) else None


def _post(path, body, timeout):
    hook = current_app.extensions.get("x402_facilitator")  # tests inject a fake
    if hook:
        return hook(path, body)
    r = requests.post(FACILITATOR + path, json=body, timeout=timeout)
    if path == "/verify":
        r.raise_for_status()
    return r.json()


def paywall(conn, price_usd, description, deliver, mime="application/json", discovery=None, resource_extra=None):
    """Return a Flask response: 402 challenge, an error, or deliver() once the payment settled.

    discovery: optional x402 v2 "bazaar" extension (specs/extensions/bazaar.md) so facilitators such as PayAI list the
    resource for agents after the first paid call; resource_extra: serviceName / tags / iconUrl for the resource object.
    deliver() -> dict must be read-only. It runs after verification and BEFORE settlement, so a failure while building
    the data never charges the buyer."""
    address = receiver()
    if not address:
        return jsonify(error="x402_unavailable"), 503
    amount = units(price_usd)
    url = current_app.config.get("PUBLIC_URL", "").rstrip("/") + request.path if current_app.config.get("PUBLIC_URL") \
        else request.base_url
    requirements = {"scheme": "exact", "network": NETWORK, "amount": amount, "asset": ASSET, "payTo": address,
                    "maxTimeoutSeconds": 60, "extra": {"assetTransferMethod": "eip3009", "name": "USD Coin", "version": "2"}}
    resource = {"url": url, "description": description, "mimeType": mime, **(resource_extra or {})}

    def payment_required(error=None):
        challenge = {"x402Version": 2, "resource": resource, "accepts": [requirements]}
        if discovery:
            challenge["extensions"] = {"bazaar": discovery}
        if error:
            challenge["error"] = error
        resp = jsonify(error="payment_required", currency="USDC", network="Base", amount_usd=str(price_usd))
        resp.status_code = 402
        resp.headers["PAYMENT-REQUIRED"] = base64.b64encode(json.dumps(challenge, separators=(",", ":")).encode()).decode()
        resp.headers["Cache-Control"] = "no-store"
        return resp

    signed = request.headers.get("PAYMENT-SIGNATURE", "")
    if not signed:
        return payment_required()
    try:
        payload = json.loads(base64.urlsafe_b64decode((signed + "=" * (-len(signed) % 4)).encode()).decode())
    except Exception:
        return payment_required("Invalid PAYMENT-SIGNATURE")
    accepted = payload.get("accepted") if isinstance(payload, dict) else None
    accepted = accepted if isinstance(accepted, dict) else {}
    signed_resource = payload.get("resource") if isinstance(payload, dict) else None
    signed_resource = signed_resource if isinstance(signed_resource, dict) else {}
    extra = accepted.get("extra") if isinstance(accepted.get("extra"), dict) else {}
    if (not isinstance(payload, dict) or payload.get("x402Version") != 2 or signed_resource.get("url") != url
            or accepted.get("network") != NETWORK or accepted.get("scheme") != "exact"
            or str(accepted.get("asset", "")).lower() != ASSET or str(accepted.get("payTo", "")).lower() != address
            or str(accepted.get("amount")) != amount or extra.get("assetTransferMethod") != "eip3009"):
        return payment_required("Payment does not match the requested amount, network, token, recipient or resource")
    body = {"x402Version": 2, "paymentPayload": payload, "paymentRequirements": requirements}
    try:
        verification = _post("/verify", body, 20)
    except (requests.RequestException, ValueError) as exc:
        log.warning("x402 verify unavailable: %s", exc)
        return jsonify(error="payment_verifier_unavailable"), 503
    if not verification.get("isValid"):
        return payment_required(verification.get("invalidReason", "Payment verification failed"))
    data = deliver()
    try:
        settlement = _post("/settle", body, 45)
    except (requests.RequestException, ValueError) as exc:
        log.warning("x402 settlement uncertain: %s", exc)
        return jsonify(error="settlement_status_unknown",
                       message="Check the same signed payment with the facilitator before retrying."), 202
    if not settlement.get("success"):
        if settlement.get("errorReason") == "settlement_pending":
            return jsonify(error="settlement_pending", transaction=settlement.get("transaction")), 202
        return payment_required(settlement.get("errorReason", "Settlement failed"))
    tx = str(settlement.get("transaction", "")).lower()
    if settlement.get("network") != NETWORK or not TX_RE.fullmatch(tx):
        log.error("x402 facilitator returned invalid settlement metadata")
        return jsonify(error="settlement_reconciliation_required"), 202
    try:
        with conn:
            conn.execute("INSERT INTO x402_payments (tx, resource, amount_usd, created_at) VALUES (?, ?, ?, ?)",
                         (tx, request.path, str(price_usd), dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
    except sqlite3.IntegrityError:  # this transaction already paid for a response
        return jsonify(error="payment_already_consumed"), 409
    except sqlite3.Error:
        # Settled on chain but not recorded: still deliver what was paid for, and leave a loud trace to reconcile.
        log.exception("x402 payment %s settled but not recorded", tx)
    resp = jsonify(data)
    resp.headers["PAYMENT-RESPONSE"] = base64.b64encode(json.dumps(settlement, separators=(",", ":")).encode()).decode()
    resp.headers["Cache-Control"] = "no-store"
    return resp
