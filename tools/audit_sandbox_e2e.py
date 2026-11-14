"""End-to-end check of the audit checkout against the PayPal SANDBOX, run from the work copy (never the live site).

Reads QS_AUDIT_PAYPAL_CLIENT_ID / QS_AUDIT_PAYPAL_SECRET from the environment (never printed). Payment approval is
done headlessly with a sandbox test card (Advanced Card Processing: confirm-payment-source). Emails are NOT sent:
a recording mailer stores them under the output directory. Discovery and checks run for real against the domain
given (default: ather-quantum.com, the owner's own site).
"""
import json
import secrets
import os
import sys
import tempfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import audit_checkout  # noqa: E402
import quantum_saas_app  # noqa: E402
from paypal_client import PayPalClient  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

ADMIN_PW = secrets.token_urlsafe(16)  # throwaway admin password for the temporary test app, new on every run

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts-sandbox").resolve()
DOMAIN = sys.argv[2] if len(sys.argv) > 2 else "ather-quantum.com"
OWNER = "sajad.vip56@gmail.com"
OUT.mkdir(parents=True, exist_ok=True)
CARD = {"number": "4032039317984658", "expiry": "2030-12", "security_code": "123", "name": "Test Buyer",
        "billing_address": {"address_line_1": "Sparkassen 11", "admin_area_2": "Braunau", "postal_code": "5280",
                            "country_code": "AT"}}


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


def step(name, ok, detail=""):
    print(f"[{'OK' if ok else 'FAIL'}] {name}{': ' + detail if detail else ''}", flush=True)
    if not ok:
        raise SystemExit(1)


def confirm_card(client, order_id):
    token = client._access_token()
    r = requests.post(f"{client.base}/v2/checkout/orders/{order_id}/confirm-payment-source",
                      json={"payment_source": {"card": CARD}},
                      headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, timeout=30)
    return r.status_code, (r.json() if r.content else {}).get("status")


def main():
    cid, secret = os.environ["QS_AUDIT_PAYPAL_CLIENT_ID"], os.environ["QS_AUDIT_PAYPAL_SECRET"]
    sandbox = PayPalClient(cid, secret, "sandbox")
    data_dir = tempfile.mkdtemp(prefix="qa-e2e-")
    mailer = RecordingMailer()
    app = quantum_saas_app.create_app(
        {"TESTING": True, "DATA_DIR": data_dir, "PUBLIC_URL": "https://ather-quantum.com", "HASH_SALT": "e2e",
         "OWNER_EMAIL": OWNER, "AUDIT_PAYPAL_ENV": "sandbox", "AUDIT_PAYPAL_CLIENT_ID": cid,
         "PAYPAL_CLIENT_ID": cid, "ADMIN_PASSWORD_HASH": generate_password_hash(ADMIN_PW)},
        paypal=sandbox, mailer=mailer, audit_paypal=sandbox)
    c = app.test_client()
    log = {}

    page = c.get("/audit?lang=ar")
    html = page.get_data(as_text=True)
    step("1 page /audit?lang=ar", page.status_code == 200 and 'id="audit-paypal-buttons" hidden' in html
         and "currency=EUR" in html and "enable-funding=card" in html and 'id="enterprise-quote"' in html)

    form = {"name": "Omer Alsaloum", "email": OWNER, "org": "Quantum Aether Testkunde", "street": "Sparkaßen 11/12",
            "postal_code": "5280", "city": "Braunau am Inn", "country": "Österreich", "domain": DOMAIN,
            "company_buyer": True, "agb_consent": True, "contact_consent": True, "lang": "de"}
    bad = c.post("/api/paypal/audit", json=dict(form, agb_consent=False))
    step("2a server rejects missing AGB box", bad.status_code == 400, bad.get_json()["error"])
    bad = c.post("/api/paypal/audit", json=dict(form, org="شركة"))
    step("2b server rejects non-Latin billing data", bad.status_code == 400, bad.get_json()["error"])
    r = c.post("/api/paypal/audit", json=form)
    created = r.get_json()
    step("2c sandbox order created", r.status_code == 201, f"{created.get('id')} {created.get('amount')} {created.get('currency')}")
    order_id = created["id"]
    log["order_id"] = order_id

    status, st = confirm_card(sandbox, order_id)
    step("3 sandbox card approval (confirm-payment-source)", status in (200, 201), f"HTTP {status}, order {st}")

    r = c.post(f"/api/paypal/audit/{order_id}/capture")
    cap = r.get_json()
    step("4 server capture + verification", r.status_code == 200 and cap["status"] == "COMPLETED", json.dumps(cap))
    with app.app_context():
        row = audit_checkout.by_order(quantum_saas_app.db(), order_id)
    step("5 order stored COMPLETED", row["status"] == "COMPLETED" and row["is_test"] == 1,
         f"capture {row['capture_id']}, invoice {row['invoice_number']}")
    pdf = Path(row["invoice_path"]).read_bytes()
    step("6 invoice PDF", "Kleinunternehmer gemäß § 6 Abs. 1 Z 27 UStG – keine USt.".encode("cp1252") in pdf,
         row["invoice_number"])
    (OUT / f"{row['invoice_number']}.pdf").write_bytes(pdf)
    to_customer = [m for m in mailer.sent if m["to"] == OWNER and "Audit paid" not in m["subject"]]
    step("7 emails (recorded, not sent)", row["customer_email_sent"] == 1 and row["owner_email_sent"] == 1,
         "; ".join(f"{m['to']} | {m['subject']} | {m['attachments']}" for m in mailer.sent))
    summary = json.loads(row["audit_summary"] or "{}")
    step("8 discovery + scan finished", row["audit_status"] == "DONE",
         f"names {summary.get('names')}, responding {summary.get('responding')}, pq {summary.get('pq')}, "
         f"classical {summary.get('not_pq')}, main grade {summary.get('main', {}).get('grade')}")
    report = Path(row["report_path"]).read_bytes()
    (OUT / f"{row['invoice_number']}-report.pdf").write_bytes(report)
    step("9 report PDF emailed", row["report_email_sent"] == 1, f"{len(summary.get('hosts', []))} hosts listed")

    # Refund path: a second paid order whose domain does not answer (discovery/scanner stubbed as unreachable).
    app.extensions["audit_discover"] = lambda d: {"source": "stub", "names": 0, "hosts": []}
    app.extensions["discovery_probe"] = lambda h: None
    real_scanner = app.extensions["scanner"]
    app.extensions["scanner"] = lambda d: (_ for _ in ()).throw(RuntimeError("unreachable (stub)"))
    r = c.post("/api/paypal/audit", json=dict(form, domain="unreachable-test.example.com"))
    oid2 = r.get_json()["id"]
    confirm_card(sandbox, oid2)
    cap2 = c.post(f"/api/paypal/audit/{oid2}/capture").get_json()
    with app.app_context():
        row2 = audit_checkout.by_order(quantum_saas_app.db(), oid2)
    step("10 unreachable domain -> ACCESS_ISSUE, no report", row2["audit_status"] == "ACCESS_ISSUE"
         and not row2["report_path"], f"{oid2} {cap2.get('invoice_number')}")
    step("10b admin login", c.get("/admin", auth=("admin", ADMIN_PW)).status_code == 200)
    admin_html = c.get("/admin", auth=("admin", ADMIN_PW)).get_data(as_text=True)
    step("10c refund button shown only for it", admin_html.count("via PayPal</button>") == 1)
    r = c.post(f"/admin/audit/{row2['id']}/refund", data={"confirm": "yes"})
    with app.app_context():
        row2 = audit_checkout.by_order(quantum_saas_app.db(), oid2)
    step("11 full sandbox refund", row2["status"] == "REFUNDED", f"{r.headers.get('Location')} refund {row2['refund_id']}")
    app.extensions["scanner"] = real_scanner

    # Agency pack still works (same sandbox client stands in for the live one here).
    r = c.post("/api/paypal/packs", json=form)
    pid = r.get_json().get("id")
    confirm_card(sandbox, pid)
    cap3 = c.post(f"/api/paypal/packs/{pid}/capture").get_json()
    step("12 agency pack create+capture unchanged", cap3.get("status") == "COMPLETED", f"{pid} {cap3.get('status')} {cap3.get('invoice_number')}")
    step("13 monitoring/subscription page renders", c.get("/monitoring?lang=en").status_code == 200)
    print("artifacts:", OUT)


if __name__ == "__main__":
    main()
