"""Company billing data for the agency pack and the monitoring subscriptions (same form as the audit checkout).

One row per pack purchase (kind='pack', ref_id=pack id) or per subscription account (kind='subscription',
ref_id=monitor account id). Validation is shared with the audit checkout (_audit_order_fields in the app):
every field, Latin billing data for the invoice font, 'ordering as a business', AGB and contact consent.
Agency pack invoices use the same serial number sequence as the audit invoices (QA-YYYY-NNNN, TEST-... for tests).
"""
import datetime as dt
import secrets
from pathlib import Path

import audit_checkout

SCHEMA = """
CREATE TABLE IF NOT EXISTS billing_records (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,                 -- 'pack' or 'subscription'
    ref_id TEXT NOT NULL,               -- packs.id or monitor_accounts.id
    org TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    billing_address TEXT NOT NULL,
    domain TEXT NOT NULL,
    plan TEXT,                          -- subscriptions: starter / business
    plan_id TEXT,                       -- subscriptions: PayPal plan id offered at signup
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    paypal_env TEXT NOT NULL DEFAULT 'live',
    company_buyer INTEGER NOT NULL DEFAULT 1,
    company_confirmed_at TEXT NOT NULL,
    agb_consent_at TEXT NOT NULL,
    contact_consent_at TEXT NOT NULL,
    client_hash TEXT,
    is_test INTEGER NOT NULL DEFAULT 0,
    invoice_number TEXT UNIQUE,
    invoice_path TEXT,
    order_id TEXT,
    capture_id TEXT,
    paid_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE (kind, ref_id)
);
"""


def init(conn):
    conn.executescript(SCHEMA)


def create(conn, *, kind, ref_id, fields, amount, currency, consent_at, client_hash, is_test, paypal_env,
           plan=None, plan_id=None, order_id=None):
    """Insert or replace the billing data for one pack / subscription account (a new signup overwrites it)."""
    with conn:
        conn.execute(
            "INSERT INTO billing_records (id,kind,ref_id,org,name,email,billing_address,domain,plan,plan_id,amount,"
            "currency,paypal_env,company_confirmed_at,agb_consent_at,contact_consent_at,client_hash,is_test,order_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(kind, ref_id) DO UPDATE SET org=excluded.org,name=excluded.name,email=excluded.email,"
            "billing_address=excluded.billing_address,domain=excluded.domain,plan=excluded.plan,"
            "plan_id=excluded.plan_id,amount=excluded.amount,currency=excluded.currency,"
            "paypal_env=excluded.paypal_env,company_confirmed_at=excluded.company_confirmed_at,"
            "agb_consent_at=excluded.agb_consent_at,contact_consent_at=excluded.contact_consent_at,"
            "client_hash=excluded.client_hash,is_test=excluded.is_test,order_id=excluded.order_id "
            "WHERE billing_records.invoice_number IS NULL",
            ("bill_" + secrets.token_urlsafe(9), kind, ref_id, fields["org"], fields["name"], fields["email"],
             fields["billing_address"], fields["domain"], plan, plan_id, amount, currency, paypal_env,
             consent_at, consent_at, consent_at, client_hash, int(bool(is_test)), order_id))


def get(conn, kind, ref_id):
    row = conn.execute("SELECT * FROM billing_records WHERE kind=? AND ref_id=?", (kind, ref_id)).fetchone()
    return dict(row) if row else None


def recent(conn, limit=50):
    return [dict(r) for r in conn.execute(
        "SELECT id,kind,ref_id,org,name,email,domain,plan,plan_id,amount,currency,paypal_env,is_test,invoice_number,"
        "invoice_path,paid_at,created_at "
        "FROM billing_records ORDER BY created_at DESC LIMIT ?", (limit,))]


def mark_paid(conn, kind, ref_id, order_id, capture_id, now=None):
    """Allocate the invoice number once (same transaction as the paid mark). Returns the row, or None."""
    now = now or dt.datetime.now(dt.timezone.utc)
    with conn:
        row = conn.execute("SELECT * FROM billing_records WHERE kind=? AND ref_id=?", (kind, ref_id)).fetchone()
        if not row:
            return None
        if not row["invoice_number"]:
            number = audit_checkout.next_invoice_number(conn, row["is_test"], now.year)
            conn.execute("UPDATE billing_records SET invoice_number=?,order_id=?,capture_id=?,paid_at=? "
                         "WHERE id=? AND invoice_number IS NULL",
                         (number, order_id, capture_id, now.strftime("%Y-%m-%dT%H:%M:%SZ"), row["id"]))
        row = conn.execute("SELECT * FROM billing_records WHERE id=?", (row["id"],)).fetchone()
        return dict(row)


def pack_invoice(conn, data_dir, record, seller, credits):
    """PDF invoice for a paid agency pack, saved once under DATA_DIR/invoices. Returns (path, bytes)."""
    order = dict(record, service=f"Agenturpaket: {credits} vollständige Post-Quanten-TLS-Berichte, einmalig, "
                                 f"ohne Ablaufdatum", order_id=record.get("order_id") or "-")
    path = audit_checkout.invoice_path(data_dir, order)
    if path.is_file():
        return path, path.read_bytes()
    data = audit_checkout.invoice_pdf(order, seller)
    audit_checkout._atomic_write(Path(path), data)
    with conn:
        conn.execute("UPDATE billing_records SET invoice_path=? WHERE id=?", (str(path), record["id"]))
    return path, data
