"""End-to-end check of the EUR agency pack and EUR monitoring subscriptions against the PayPal SANDBOX.

Runs the app from the work copy in-process (never the live site, never the live database). Reads the sandbox app
credentials QS_AUDIT_PAYPAL_CLIENT_ID / QS_AUDIT_PAYPAL_SECRET from the environment (never printed) and the sandbox
plan ids PAYPAL_PLAN_*_EUR and PAYPAL_PLAN_* (legacy USD) from the environment. Emails are NOT sent: a recording
mailer writes them under the output directory. Order approval is headless with a sandbox test card
(confirm-payment-source); subscriptions need a buyer approval in a browser, so they are created and verified up to
APPROVAL_PENDING. EPS: a sandbox EUR order with payment_source.eps shows whether the merchant account may take eps.
Usage: python tools/eur_sandbox_e2e.py OUT_DIR
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import company_billing  # noqa: E402
import quantum_saas_app  # noqa: E402
from paypal_client import PayPalClient  # noqa: E402

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts-eur-sandbox").resolve()
OUT.mkdir(parents=True, exist_ok=True)
OWNER = "sajad.vip56@gmail.com"
CARD = {"number": "4032039317984658", "expiry": "2030-12", "security_code": "123", "name": "Test Buyer",
        "billing_address": {"address_line_1": "Ringstrasse 1", "admin_area_2": "Wien", "postal_code": "1010",
                            "country_code": "AT"}}
FORM = {"name": "Eva Muster", "email": OWNER, "org": "Quantum Aether Testkunde GmbH", "street": "Ringstraße 1",
        "postal_code": "1010", "city": "Wien", "country": "Austria", "domain": "ather-quantum.com",
        "company_buyer": True, "agb_consent": True, "contact_consent": True, "lang": "de"}
RESULTS = []


class RecordingMailer:
    enabled = True

    def __init__(self):
        self.sent = []

    def send(self, to, subject, text, html=None, attachments=None):
        n = len(self.sent) + 1
        self.sent.append({"to": to, "subject": subject, "attachments": [a["filename"] for a in attachments or []]})
        (OUT / f"mail-{n:02d}.txt").write_text(f"To: {to}\nSubject: {subject}\nAttachments: "
                                               f"{[a['filename'] for a in attachments or []]}\n\n{text}\n")
        return True


def step(name, ok, detail="", fatal=True):
    line = f"[{'OK' if ok else 'FAIL'}] {name}{': ' + detail if detail else ''}"
    print(line, flush=True)
    RESULTS.append(line)
    if not ok and fatal:
        (OUT / "results.txt").write_text("\n".join(RESULTS) + "\n")
        raise SystemExit(1)


def api(client, method, path, body=None):
    import uuid
    token = client._access_token()
    r = requests.request(method, f"{client.base}{path}", json=body, timeout=30,
                         headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                  "Prefer": "return=representation", "PayPal-Request-Id": str(uuid.uuid4())})
    return r.status_code, (r.json() if r.content else {})


def main():
    cid, secret = os.environ["QS_AUDIT_PAYPAL_CLIENT_ID"], os.environ["QS_AUDIT_PAYPAL_SECRET"]
    plans = {k: os.environ[k] for k in ("PAYPAL_PLAN_STARTER", "PAYPAL_PLAN_BUSINESS", "PAYPAL_PLAN_STARTER_EUR",
                                         "PAYPAL_PLAN_BUSINESS_EUR")}
    sandbox = PayPalClient(cid, secret, "sandbox")
    data_dir = tempfile.mkdtemp(prefix="qa-eur-e2e-")
    mailer = RecordingMailer()
    app = quantum_saas_app.create_app(
        {"TESTING": True, "DATA_DIR": data_dir, "PUBLIC_URL": "https://ather-quantum.com", "HASH_SALT": "e2e",
         "OWNER_EMAIL": OWNER, "PAYPAL_ENV": "sandbox", "PAYPAL_CLIENT_ID": cid, "AUDIT_PAYPAL_ENV": "sandbox",
         "AUDIT_PAYPAL_CLIENT_ID": cid, **plans},
        paypal=sandbox, mailer=mailer, audit_paypal=sandbox)
    c = app.test_client()

    # ---------------------------------------------------------------- agency pack
    html = c.get("/agency?lang=ar").get_data(as_text=True)
    step("A1 /agency?lang=ar: EUR, company form, buttons hidden, eps enabled",
         "currency=EUR" in html and "enable-funding=card,eps" in html and 'id="paypal-button-container" hidden' in html
         and 'name="company_buyer"' in html and "199.00 EUR" in html)
    bad = c.post("/api/paypal/packs", json=dict(FORM, contact_consent=False))
    step("A2 server rejects missing contact box", bad.status_code == 400, bad.get_json()["error"])
    r = c.post("/api/paypal/packs", json=FORM)
    created = r.get_json()
    step("A3 sandbox EUR order created", r.status_code == 201 and created.get("currency") == "EUR",
         f"{created.get('id')} {created.get('amount')} {created.get('currency')}")
    oid = created["id"]
    status, body = api(sandbox, "POST", f"/v2/checkout/orders/{oid}/confirm-payment-source", {"payment_source": {"card": CARD}})
    step("A4 sandbox card approval", status in (200, 201), f"HTTP {status}, order {body.get('status')}")
    r = c.post(f"/api/paypal/packs/{oid}/capture")
    cap = r.get_json()
    step("A5 server capture + verification", r.status_code == 200 and cap.get("pack_url"),
         f"invoice {cap.get('invoice_number')}")
    with app.app_context():
        conn = quantum_saas_app.db()
        rec = company_billing.get(conn, "pack", conn.execute("SELECT id FROM packs WHERE order_id=?", (oid,)).fetchone()[0])
        pack = dict(conn.execute("SELECT status, amount, currency, is_test, capture_id FROM packs WHERE order_id=?", (oid,)).fetchone())
    step("A6 pack COMPLETED in EUR, test flag", pack["status"] == "COMPLETED" and pack["currency"] == "EUR"
         and pack["is_test"] == 1, json.dumps(pack))
    pdf = Path(rec["invoice_path"]).read_bytes()
    step("A7 invoice PDF with Kleinunternehmer line", "Kleinunternehmer gemäß § 6 Abs. 1 Z 27 UStG – keine USt."
         .encode("cp1252") in pdf and b"199.00 EUR" in pdf, rec["invoice_number"])
    (OUT / f"pack-{rec['invoice_number']}.pdf").write_bytes(pdf)
    step("A8 emails recorded (not sent)", any(m["attachments"] for m in mailer.sent),
         "; ".join(f"{m['to']} | {m['subject']} | {m['attachments']}" for m in mailer.sent))
    token = cap["pack_url"].split("/pack/")[1].split("?")[0]
    step("A9 pack page opens", c.get(f"/pack/{token}?lang=en").status_code == 200)

    # ---------------------------------------------------------------- eps eligibility (sandbox merchant)
    status, body = api(sandbox, "POST", "/v2/checkout/orders", {
        "intent": "CAPTURE", "purchase_units": [{"reference_id": "eps-probe", "amount": {"currency_code": "EUR", "value": "199.00"}}],
        "payment_source": {"eps": {"country_code": "AT", "name": "Eva Muster", "experience_context": {
            "return_url": "https://ather-quantum.com/agency", "cancel_url": "https://ather-quantum.com/agency",
            "locale": "de-AT"}}}})
    approve = [l["href"] for l in body.get("links", []) if l.get("rel") == "payer-action"]
    eps_detail = (f"HTTP {status}, status {body.get('status')}, payer-action link {'yes' if approve else 'no'}"
                  if status < 400 else f"HTTP {status}, {body.get('name')}: {(body.get('details') or [{}])[0].get('issue')}")
    step("E1 sandbox EUR order with eps payment source", status in (200, 201) and bool(approve), eps_detail, fatal=False)
    (OUT / "eps-probe.json").write_text(json.dumps({"status": status, "body": {k: body.get(k) for k in ("id", "status", "name", "details")}}, indent=2))

    # ---------------------------------------------------------------- subscriptions
    html = c.get("/monitoring?lang=ar").get_data(as_text=True)
    step("S1 /monitoring?lang=ar: EUR plans, company form, buttons hidden", "currency=EUR" in html
         and "29.00 EUR" in html and "99.00 EUR" in html and 'data-plan="starter" hidden' in html
         and 'name="agb_consent"' in html and "enable-funding=eps" not in html)
    r = c.post("/api/monitor/signup", json=dict(FORM, plan="starter"))
    d = r.get_json()
    step("S2 signup returns sandbox EUR plan", r.status_code == 201 and d["plan_id"] == plans["PAYPAL_PLAN_STARTER_EUR"],
         d.get("plan_id"))
    status, sub = api(sandbox, "POST", "/v1/billing/subscriptions", {
        "plan_id": d["plan_id"], "custom_id": d["account_id"],
        "application_context": {"brand_name": "Quantum Aether", "shipping_preference": "NO_SHIPPING",
                                "user_action": "SUBSCRIBE_NOW", "return_url": "https://ather-quantum.com/monitoring",
                                "cancel_url": "https://ather-quantum.com/monitoring"}})
    step("S3 sandbox EUR subscription created", status in (200, 201) and sub.get("status") == "APPROVAL_PENDING",
         f"{sub.get('id')} {sub.get('status')}")
    status, got = api(sandbox, "GET", f"/v1/billing/subscriptions/{sub['id']}")
    step("S4 PayPal reports the EUR price", got.get("plan_id") == d["plan_id"],
         f"plan {got.get('plan_id')}, custom_id matches: {got.get('custom_id') == d['account_id']}")
    status, plan = api(sandbox, "GET", f"/v1/billing/plans/{d['plan_id']}")
    price = plan["billing_cycles"][0]["pricing_scheme"]["fixed_price"]
    step("S5 sandbox plan price", price == {"currency_code": "EUR", "value": "29.0"} or
         (price["currency_code"] == "EUR" and float(price["value"]) == 29.0), json.dumps(price))
    r = c.post("/api/monitor/activate", json={"account_id": d["account_id"], "subscription_id": sub["id"]})
    step("S6 activation refuses until the buyer approved", r.status_code == 402
         and r.get_json().get("status") == "APPROVAL_PENDING", json.dumps(r.get_json()))
    with app.app_context():
        rec = company_billing.get(quantum_saas_app.db(), "subscription", d["account_id"])
    step("S7 billing data stored with the subscription account", rec["org"] == FORM["org"] and rec["currency"] == "EUR"
         and rec["billing_address"].startswith("Ringstraße 1"), f"{rec['plan']} {rec['amount']} {rec['currency']}")
    # A USD subscription must not activate an account that was offered the EUR plan.
    status, usd = api(sandbox, "POST", "/v1/billing/subscriptions", {"plan_id": plans["PAYPAL_PLAN_STARTER"], "custom_id": d["account_id"]})
    r = c.post("/api/monitor/activate", json={"account_id": d["account_id"], "subscription_id": usd["id"]})
    step("S8 wrong-currency plan rejected", r.status_code == 402 and r.get_json().get("status") == "MISMATCH")
    approve = [l["href"] for l in sub.get("links", []) if l.get("rel") == "approve"]
    (OUT / "subscription-approve-url.txt").write_text((approve or [""])[0] + "\n")
    print("artifacts:", OUT)
    (OUT / "results.txt").write_text("\n".join(RESULTS) + "\n")


if __name__ == "__main__":
    main()
