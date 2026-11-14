"""PayPal order records and serial PDF invoices for the one-time organization audit."""
import datetime as dt
import os
import re
import secrets
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_orders (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL UNIQUE,
    capture_id TEXT UNIQUE,
    refund_id TEXT UNIQUE,
    invoice_number TEXT UNIQUE,
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    org TEXT NOT NULL,
    billing_address TEXT NOT NULL,
    domain TEXT NOT NULL,
    lang TEXT NOT NULL DEFAULT 'en',
    amount TEXT NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CREATED',
    audit_status TEXT NOT NULL DEFAULT 'NOT_STARTED',
    audit_summary TEXT,
    agb_consent_at TEXT NOT NULL,
    contact_consent_at TEXT NOT NULL,
    client_hash TEXT NOT NULL,
    company_buyer INTEGER NOT NULL DEFAULT 0,
    company_confirmed_at TEXT NOT NULL,
    consent_source TEXT NOT NULL DEFAULT 'audit-checkout',
    is_test INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    paid_at TEXT,
    invoice_path TEXT,
    customer_email_sent INTEGER NOT NULL DEFAULT 0,
    owner_email_sent INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit_invoice_sequence (
    year INTEGER PRIMARY KEY,
    next_number INTEGER NOT NULL
);
"""


def init(conn):
    conn.executescript(SCHEMA)


def new_id():
    return "audit_" + secrets.token_urlsafe(12)


def create(conn, *, audit_id, order_id, email, name, org, billing_address, domain, lang,
           amount, currency, agb_consent_at, contact_consent_at, client_hash, is_test):
    with conn:
        conn.execute(
            "INSERT INTO audit_orders (id,order_id,email,name,org,billing_address,domain,lang,amount,currency,"
            "agb_consent_at,contact_consent_at,client_hash,company_buyer,company_confirmed_at,consent_source,is_test) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,'audit-checkout',?)",
            (audit_id, order_id, email, name, org, billing_address, domain, lang, amount, currency,
             agb_consent_at, contact_consent_at, client_hash, agb_consent_at, int(is_test)),
        )


def by_order(conn, order_id):
    row = conn.execute("SELECT * FROM audit_orders WHERE order_id=?", (order_id,)).fetchone()
    return dict(row) if row else None


def by_id(conn, audit_id):
    row = conn.execute("SELECT * FROM audit_orders WHERE id=?", (audit_id,)).fetchone()
    return dict(row) if row else None


def recent(conn, limit=50):
    return [dict(r) for r in conn.execute(
        "SELECT id,order_id,email,name,org,domain,amount,currency,status,audit_status,invoice_number,"
        "is_test,customer_email_sent,owner_email_sent,created_at,paid_at "
        "FROM audit_orders ORDER BY created_at DESC LIMIT ?", (limit,))]


def rate_limited(conn, client_hash, max_per_day=3):
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    count = conn.execute("SELECT COUNT(*) FROM audit_orders WHERE client_hash=? AND created_at>=?",
                         (client_hash, since)).fetchone()[0]
    return count >= max_per_day


def _invoice_number(conn, year):
    conn.execute("INSERT OR IGNORE INTO audit_invoice_sequence(year,next_number) VALUES (?,1)", (year,))
    n = conn.execute("SELECT next_number FROM audit_invoice_sequence WHERE year=?", (year,)).fetchone()[0]
    conn.execute("UPDATE audit_invoice_sequence SET next_number=? WHERE year=?", (n + 1, year))
    return f"QA-{year}-{n:06d}"


def complete(conn, order_id, capture_id, now=None):
    """Make COMPLETED and allocate an invoice number once; return (row, newly_completed)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    with conn:
        row = conn.execute("SELECT * FROM audit_orders WHERE order_id=?", (order_id,)).fetchone()
        if not row:
            return None, False
        if row["status"] == "COMPLETED":
            return dict(row), False
        number = _invoice_number(conn, now.year)
        updated = conn.execute("UPDATE audit_orders SET status='COMPLETED',capture_id=?,invoice_number=?,paid_at=? "
                               "WHERE order_id=? AND status IN ('CREATED','PENDING')",
                               (capture_id, number, now.strftime("%Y-%m-%dT%H:%M:%SZ"), order_id)).rowcount
        row = conn.execute("SELECT * FROM audit_orders WHERE order_id=?", (order_id,)).fetchone()
        return dict(row), bool(updated)


def set_status(conn, order_id, status):
    with conn:
        conn.execute("UPDATE audit_orders SET status=? WHERE order_id=?", (status, order_id))


def set_invoice_path(conn, order_id, path):
    with conn:
        conn.execute("UPDATE audit_orders SET invoice_path=? WHERE order_id=? AND status='COMPLETED'",
                     (str(path), order_id))


def set_audit_result(conn, order_id, status, summary=None):
    with conn:
        conn.execute("UPDATE audit_orders SET audit_status=?,audit_summary=? WHERE order_id=? AND status='COMPLETED'",
                     (status, summary, order_id))


def set_refunded(conn, order_id, refund_id):
    with conn:
        conn.execute("UPDATE audit_orders SET status='REFUNDED',refund_id=? WHERE order_id=? AND status='COMPLETED'",
                     (refund_id, order_id))


def set_delivery_state(conn, order_id, *, customer=False, owner=False):
    fields = []
    if customer:
        fields.append("customer_email_sent=1")
    if owner:
        fields.append("owner_email_sent=1")
    if fields:
        with conn:
            conn.execute(f"UPDATE audit_orders SET {','.join(fields)} WHERE order_id=?", (order_id,))


def invoice_path(data_dir, order):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", order["invoice_number"] or order["id"])
    return Path(data_dir) / "invoices" / f"{safe}.pdf"


def _pdf_text(value):
    raw = str(value).replace("\n", " ").encode("cp1252", "replace").decode("cp1252")
    return raw.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def invoice_pdf(order, seller):
    """Create a dependency-free, one-page WinAnsi PDF invoice."""
    issued = (order.get("paid_at") or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))[:10]
    lines = [
        ("Quantum Aether", True), ("Rechnung / Invoice", True),
        (f"Rechnungsnummer: {order['invoice_number']}", False), (f"Ausstellungsdatum: {issued}", False),
        ("", False), ("Leistungserbringer", True), (seller["name"], False), (seller["address"], False),
        (seller["email"], False), ("", False), ("Rechnungsempfänger", True), (order["org"], False),
        (order["name"], False), (order["billing_address"], False), (order["email"], False),
        ("", False), ("Leistungsbeschreibung", True),
        (f"Post-Quantum-TLS-Subdomain-Audit fuer {order['domain']} (bis zu 200 Hosts)", False),
        ("Einmalige Leistung gemaess Audit-Angebot.", False), ("", False),
        (f"Gesamtbetrag: {order['amount']} {order['currency']}", True),
        ("Kleinunternehmer gemäß § 6 Abs. 1 Z 27 UStG – keine USt", False),
        ("Zahlungsart: PayPal · bezahlt", False), (f"PayPal-Referenz: {order['order_id']}", False),
        ("", False), (seller["name"], True), (seller["address"], False), (seller["email"], False),
    ]
    # Wrap to fit A4 using a conservative character width for Helvetica.
    wrapped = []
    for line, bold in lines:
        if len(line) <= 88:
            wrapped.append((line, bold))
            continue
        words, current = line.split(), ""
        for word in words:
            candidate = (current + " " + word).strip()
            if len(candidate) > 88:
                wrapped.append((current, bold)); current = word
            else:
                current = candidate
        if current:
            wrapped.append((current, bold))
    commands = ["BT", "50 790 Td"]
    for i, (line, bold) in enumerate(wrapped[:38]):
        if i:
            commands.append("0 -19 Td")
        commands.append(f"/{'F2' if bold else 'F1'} {15 if bold else 11} Tf")
        commands.append(f"({_pdf_text(line)}) Tj")
    commands.append("ET")
    stream = "\n".join(commands).encode("cp1252", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, body in enumerate(objects, 1):
        offsets.append(len(out)); out.extend(f"{i} 0 obj\n".encode()); out.extend(body); out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(out)


def save_invoice(data_dir, order, seller):
    path = invoice_path(data_dir, order)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = invoice_pdf(order, seller)
    temp = path.with_suffix(".pdf.tmp")
    temp.write_bytes(data)
    os.replace(temp, path)
    return path, data
