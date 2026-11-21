"""PayPal order records, serial PDF invoices and the automatic PDF report for the one-time small-company audit.

Invoices and reports are rendered with a dependency-free PDF writer (Helvetica, WinAnsi/cp1252). Billing fields
are therefore validated as Latin script at checkout (latin_ok); nothing is silently replaced with '?'.
Test orders (owner/admin traffic or a sandbox PayPal environment) use their own TEST-YYYY-NNNN number series
and never consume the real QA-YYYY-NNNN series.
"""
import datetime as dt
import json
import os
import re
import secrets
import unicodedata
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
    paypal_env TEXT NOT NULL DEFAULT 'live',
    status TEXT NOT NULL DEFAULT 'CREATED',      -- CREATED / PENDING / COMPLETED / FAILED / REFUND_PENDING / REFUNDED
    audit_status TEXT NOT NULL DEFAULT 'NOT_STARTED',  -- NOT_STARTED / QUEUED / RUNNING / DONE / ACCESS_ISSUE
    audit_summary TEXT,                          -- JSON: counts, main-domain grade and the full host list
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
    report_path TEXT,
    report_at TEXT,
    customer_email_sent INTEGER NOT NULL DEFAULT 0,
    owner_email_sent INTEGER NOT NULL DEFAULT 0,
    report_email_sent INTEGER NOT NULL DEFAULT 0,
    access_notice_sent INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit_invoice_sequence (
    series TEXT NOT NULL,          -- 'QA' (real) or 'TEST'
    year INTEGER NOT NULL,
    next_number INTEGER NOT NULL,
    PRIMARY KEY (series, year)
);
"""

REAL_SERIES, TEST_SERIES = "QA", "TEST"
TAX_LINE = "Kleinunternehmer gemäß § 6 Abs. 1 Z 27 UStG – keine USt."
LATIN_FIELDS = ("org", "name", "street", "postal_code", "city", "country", "email")


def init(conn):
    conn.executescript(SCHEMA)


def new_id():
    return "audit_" + secrets.token_urlsafe(12)


# ------------------------------------------------------------------ validation

def latin_ok(value):
    """True if the text can be printed exactly in the invoice font (cp1252 Latin) and has no control characters."""
    value = unicodedata.normalize("NFC", str(value))
    if any(unicodedata.category(ch) in ("Cc", "Cf") for ch in value):
        return False
    try:
        value.encode("cp1252")
    except UnicodeEncodeError:
        return False
    return True


# ------------------------------------------------------------------ storage

def create(conn, *, audit_id, order_id, email, name, org, billing_address, domain, lang,
           amount, currency, agb_consent_at, contact_consent_at, client_hash, is_test, paypal_env="live"):
    with conn:
        conn.execute(
            "INSERT INTO audit_orders (id,order_id,email,name,org,billing_address,domain,lang,amount,currency,paypal_env,"
            "agb_consent_at,contact_consent_at,client_hash,company_buyer,company_confirmed_at,consent_source,is_test) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,'audit-checkout',?)",
            (audit_id, order_id, email, name, org, billing_address, domain, lang, amount, currency, paypal_env,
             agb_consent_at, contact_consent_at, client_hash, agb_consent_at, int(is_test)),
        )
    import partners; partners.attribute(conn, 'audit', audit_id)  # partner referral (2026-11-21)


def by_order(conn, order_id):
    row = conn.execute("SELECT * FROM audit_orders WHERE order_id=?", (order_id,)).fetchone()
    return dict(row) if row else None


def by_id(conn, audit_id):
    row = conn.execute("SELECT * FROM audit_orders WHERE id=?", (audit_id,)).fetchone()
    return dict(row) if row else None


def recent(conn, limit=50):
    return [dict(r) for r in conn.execute(
        "SELECT id,order_id,email,name,org,domain,amount,currency,paypal_env,status,audit_status,invoice_number,"
        "is_test,customer_email_sent,owner_email_sent,report_email_sent,report_path,refund_id,created_at,paid_at "
        "FROM audit_orders ORDER BY created_at DESC LIMIT ?", (limit,))]


def rate_limited(conn, client_hash, max_per_day=3):
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    count = conn.execute("SELECT COUNT(*) FROM audit_orders WHERE client_hash=? AND created_at>=?",
                         (client_hash, since)).fetchone()[0]
    return count >= max_per_day


def next_invoice_number(conn, is_test, year):
    """Shared serial number for every invoice the site issues (audit, agency pack): QA-YYYY-NNNN, or TEST-... .
    Call inside the caller's transaction so a retry never skips a number."""
    return _invoice_number(conn, TEST_SERIES if is_test else REAL_SERIES, year)


def _invoice_number(conn, series, year):
    conn.execute("INSERT OR IGNORE INTO audit_invoice_sequence(series,year,next_number) VALUES (?,?,1)", (series, year))
    n = conn.execute("SELECT next_number FROM audit_invoice_sequence WHERE series=? AND year=?",
                     (series, year)).fetchone()[0]
    conn.execute("UPDATE audit_invoice_sequence SET next_number=? WHERE series=? AND year=?", (n + 1, series, year))
    return f"{series}-{year}-{n:04d}"


def complete(conn, order_id, capture_id, now=None):
    """Mark COMPLETED and allocate an invoice number once; return (row, newly_completed).
    The number is taken inside the same transaction as the status change, so retries never skip numbers."""
    now = now or dt.datetime.now(dt.timezone.utc)
    with conn:
        row = conn.execute("SELECT * FROM audit_orders WHERE order_id=?", (order_id,)).fetchone()
        if not row:
            return None, False
        if row["status"] != "CREATED" and row["status"] != "PENDING":
            return dict(row), False
        series = TEST_SERIES if row["is_test"] else REAL_SERIES
        number = _invoice_number(conn, series, now.year)
        conn.execute("UPDATE audit_orders SET status='COMPLETED',capture_id=?,invoice_number=?,paid_at=? "
                     "WHERE order_id=? AND status IN ('CREATED','PENDING')",
                     (capture_id, number, now.strftime("%Y-%m-%dT%H:%M:%SZ"), order_id))
        row = conn.execute("SELECT * FROM audit_orders WHERE order_id=?", (order_id,)).fetchone()
        return dict(row), True


def set_status(conn, order_id, status):
    with conn:
        conn.execute("UPDATE audit_orders SET status=? WHERE order_id=? AND status IN ('CREATED','PENDING')",
                     (status, order_id))


def set_invoice_path(conn, order_id, path):
    with conn:
        conn.execute("UPDATE audit_orders SET invoice_path=? WHERE order_id=? AND status='COMPLETED'",
                     (str(path), order_id))


def set_audit_result(conn, order_id, status, summary=None):
    with conn:
        conn.execute("UPDATE audit_orders SET audit_status=?,audit_summary=COALESCE(?,audit_summary) "
                     "WHERE order_id=? AND status='COMPLETED'", (status, summary, order_id))


def set_report(conn, order_id, path, when):
    with conn:
        conn.execute("UPDATE audit_orders SET report_path=?,report_at=? WHERE order_id=?", (str(path), when, order_id))


def set_refund(conn, order_id, refund_id, status):
    with conn:
        conn.execute("UPDATE audit_orders SET status=?,refund_id=? WHERE order_id=? "
                     "AND status IN ('COMPLETED','REFUND_PENDING')", (status, refund_id, order_id))


def set_delivery_state(conn, order_id, *, customer=False, owner=False, report=False, access_notice=False):
    fields = [f for f, on in (("customer_email_sent=1", customer), ("owner_email_sent=1", owner),
                              ("report_email_sent=1", report), ("access_notice_sent=1", access_notice)) if on]
    if fields:
        with conn:
            conn.execute(f"UPDATE audit_orders SET {','.join(fields)} WHERE order_id=?", (order_id,))


def summary_of(order):
    try:
        return json.loads(order.get("audit_summary") or "{}")
    except ValueError:
        return {}


# ------------------------------------------------------------------ minimal PDF writer

PAGE_W, PAGE_H, MARGIN = 595, 842, 50


def _pdf_text(value):
    raw = str(value).replace("\n", " ").encode("cp1252", "strict").decode("cp1252")
    return raw.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text, width):
    if len(text) <= width:
        return [text]
    out, current = [], ""
    for word in text.split():
        candidate = (current + " " + word).strip()
        if len(candidate) > width and current:
            out.append(current)
            current = word
        else:
            current = candidate
    if current:
        out.append(current)
    return out


def render_pdf(lines):
    """lines: list of (text, style) with style in body/bold/title/mono/small/rule/space. Returns PDF bytes.
    Text that is not cp1252 raises UnicodeEncodeError instead of printing '?'."""
    fonts = {"body": ("F1", 10, 14, 95), "bold": ("F2", 11, 16, 85), "title": ("F2", 16, 24, 55),
             "mono": ("F3", 8.5, 12, 100), "small": ("F1", 8, 11, 120)}
    pages, current, y = [], [], PAGE_H - MARGIN
    for text, style in lines:
        if style == "space":
            y -= 8
            continue
        if style == "rule":
            if y < MARGIN + 20:
                pages.append(current); current, y = [], PAGE_H - MARGIN
            current.append(f"0.6 w {MARGIN} {y + 4} m {PAGE_W - MARGIN} {y + 4} l S")
            y -= 8
            continue
        font, size, leading, width = fonts[style]
        for part in _wrap(text, width):
            if y < MARGIN + leading:
                pages.append(current); current, y = [], PAGE_H - MARGIN
            current.append(f"BT /{font} {size} Tf {MARGIN} {y} Td ({_pdf_text(part)}) Tj ET")
            y -= leading
    pages.append(current)
    total = len(pages)
    objects = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
               3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
               4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
               5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"}
    kids, next_obj = [], 6
    for number, ops in enumerate(pages, 1):
        if total > 1:
            ops = ops + [f"BT /F1 8 Tf {PAGE_W - MARGIN - 40} 25 Td ({number} / {total}) Tj ET"]
        stream = "\n".join(ops).encode("cp1252")
        page_obj, content_obj = next_obj, next_obj + 1
        next_obj += 2
        kids.append(page_obj)
        objects[page_obj] = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
                             f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
                             f"/Contents {content_obj} 0 R >>").encode()
        objects[content_obj] = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
    objects[2] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {total} >>".encode()
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for i in sorted(objects):
        offsets[i] = len(out)
        out.extend(f"{i} 0 obj\n".encode()); out.extend(objects[i]); out.extend(b"\nendobj\n")
    xref = len(out)
    size = max(objects) + 1
    out.extend(f"xref\n0 {size}\n0000000000 65535 f \n".encode())
    for i in range(1, size):
        out.extend(f"{offsets[i]:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(out)


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(data)
    os.replace(temp, path)


def _safe(name):
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


# ------------------------------------------------------------------ invoice

def invoice_path(data_dir, order):
    return Path(data_dir) / "invoices" / f"{_safe(order['invoice_number'] or order['id'])}.pdf"


def invoice_pdf(order, seller):
    issued = (order.get("paid_at") or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))[:10]
    test = bool(order.get("is_test"))
    L = [("Rechnung / Invoice", "title")]
    if test:
        L += [("TESTRECHNUNG (PayPal-Sandbox) – keine gültige Rechnung, keine echte Zahlung", "bold")]
    L += [(f"Rechnungsnummer: {order['invoice_number']}", "body"), (f"Rechnungsdatum: {issued}", "body"),
          (f"Leistungsdatum: {issued}", "body"), ("space", "space"),
          ("Leistungserbringer", "bold"), (seller["name"], "body"), (seller["address"], "body"),
          (seller["email"], "body"), ("space", "space"),
          ("Rechnungsempfänger", "bold"), (order["org"], "body"), (f"z. Hd. {order['name']}", "body")]
    L += [(line, "body") for line in order["billing_address"].split("\n")]
    L += [(order["email"], "body"), ("space", "space"), ("rule", "rule"),
          ("Leistung", "bold"),
          (order.get("service") or f"Post-Quanten-TLS-Subdomain-Audit für {order['domain']} (bis zu 200 Hosts), einmalig",
           "body"),
          (f"Menge: 1   Einzelpreis: {order['amount']} {order['currency']}", "body"), ("rule", "rule"),
          (f"Gesamtbetrag: {order['amount']} {order['currency']}", "bold"),
          (TAX_LINE, "body"), ("space", "space"),
          (f"Zahlungsart: {order.get('payment_method') or 'PayPal'} - bezahlt am {issued}", "body"),
          (f"PayPal-Bestellung: {order['order_id']}", "small")]
    if order.get("capture_id"):
        L.append((f"PayPal-Transaktion: {order['capture_id']}", "small"))
    return render_pdf(L)


def save_invoice(data_dir, order, seller):
    path = invoice_path(data_dir, order)
    data = invoice_pdf(order, seller)
    _atomic_write(path, data)
    return path, data


# ------------------------------------------------------------------ audit report

STATUS_LABEL = {"pq": "post-quantum", "not_pq": "CLASSICAL", "unknown": "undetermined"}


def report_path(data_dir, order):
    return Path(data_dir) / "audit_reports" / f"{_safe(order['invoice_number'] or order['id'])}-report.pdf"


def report_pdf(order, summary, seller, generated_at):
    hosts = summary.get("hosts") or []
    main = summary.get("main") or {}
    L = [("Post-Quantum TLS Audit Report", "title"),
         (f"Domain: {order['domain']}", "bold"),
         (f"Organisation: {order['org']}", "body"),
         (f"Report date (UTC): {generated_at}", "body"),
         (f"Reference: {order['invoice_number']}", "body")]
    if order.get("is_test"):
        L.append(("TEST REPORT - generated from a sandbox / test order", "bold"))
    L += [("space", "space"), ("Summary", "bold"),
          (f"Names found in Certificate Transparency logs: {summary.get('names', 0)} (source: {summary.get('source') or '-'})", "body"),
          (f"Checked (max. 200): {summary.get('checked', len(hosts))}   Responding on port 443: {summary.get('responding', 0)}", "body"),
          (f"Post-quantum key exchange: {summary.get('pq', 0)}   Classical only: {summary.get('not_pq', 0)}   "
           f"Undetermined: {summary.get('unknown', 0)}", "body")]
    if main.get("grade"):
        L.append((f"Primary domain {order['domain']}: grade {main['grade']}, {main.get('version') or '-'}, "
                  f"key exchange {main.get('group') or '-'}"
                  + (f", {main['endpoints_pq']}/{main['endpoints_total']} IP addresses post-quantum"
                     if main.get("endpoints_total") else ""), "body"))
    elif main.get("error"):
        L.append((f"Primary domain {order['domain']}: full check not possible ({main['error']})", "body"))
    L += [("space", "space"), ("Results per host (classical first)", "bold"),
          (f"{'Host':<52} {'Result':<13} {'TLS':<8} Key exchange", "mono"), ("rule", "rule")]
    for h in hosts:
        host = h.get("host") or "-"
        if len(host) > 52:
            host = host[:49] + "..."
        L.append((f"{host:<52} {STATUS_LABEL.get(h.get('status'), h.get('status') or '-'):<13} "
                  f"{(h.get('version') or '-'):<8} {h.get('group') or '-'}", "mono"))
    if not hosts:
        L.append(("No discovered host answered on port 443.", "body"))
    L += [("space", "space"), ("What to do", "bold"),
          ("Hosts marked CLASSICAL negotiate only classical key exchange. Enable the hybrid group X25519MLKEM768 "
           "on the TLS terminator (web server, load balancer or CDN): OpenSSL 3.5+, BoringSSL/AWS-LC based "
           "proxies, nginx/Apache built against OpenSSL 3.5+, Caddy 2.10+, Cloudflare and other CDNs that "
           "support ML-KEM. Keep X25519 as fallback for older clients.", "body"),
          ("Hosts marked undetermined answered but the key exchange could not be classified; re-check them "
           "manually.", "body"),
          ("space", "space"), ("Regulatory context", "bold"),
          ("NIS2 Art. 21(2)(h) requires policies on cryptography and, where appropriate, encryption. DORA "
           "(Regulation (EU) 2022/2554) requires ICT risk management including cryptographic controls. This "
           "report documents the state of public TLS key exchange on the date above.", "body"),
          ("space", "space"), ("Method and limits", "bold"),
          ("Subdomains are taken from public Certificate Transparency logs (crt.sh, Cert Spotter), up to 200 "
           "hosts. Each host is checked once on port 443 from a single vantage point. This is not a penetration "
           "test and does not assess application security.", "small"),
          ("space", "space"), (f"{seller['name']} - {seller['address']} - {seller['email']}", "small")]
    return render_pdf(L)


def save_report(data_dir, order, summary, seller, generated_at):
    path = report_path(data_dir, order)
    data = report_pdf(order, summary, seller, generated_at)
    _atomic_write(path, data)
    return path, data
