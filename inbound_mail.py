"""Replies to our mail: Resend receives everything sent to *@mail.ather-quantum.com (MX on that subdomain only;
the apex ather-quantum.com has no MX) and posts an "email.received" webhook here.

POST /hooks/resend/inbound
  * signature checked (Svix scheme Resend uses: svix-id, svix-timestamp, svix-signature; secret QS_RESEND_WEBHOOK_SECRET),
  * stores sender, recipient, subject and Resend's email id (the body stays in Resend: dashboard -> Emails -> Receiving),
  * emails the owner a short notice. A QA message ("[qa-test]" in the subject, sent from one of our own domains)
    is stored as a test and does not notify anyone.
Nothing here replies to the sender. (2026-11-21)
"""
import base64
import hashlib
import hmac
import json
import logging
import time

from flask import request

log = logging.getLogger("quantum_saas.inbound")

SCHEMA = """
CREATE TABLE IF NOT EXISTS inbound_mail (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  webhook_id TEXT UNIQUE, email_id TEXT, received_at TEXT,
  from_addr TEXT NOT NULL DEFAULT '', to_addr TEXT NOT NULL DEFAULT '', subject TEXT NOT NULL DEFAULT '',
  is_test INTEGER NOT NULL DEFAULT 0, notified INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS inbound_mail_created ON inbound_mail (created_at);
"""
TOLERANCE_SECONDS = 300
OWN_DOMAINS = ("ather-quantum.com", "mail.ather-quantum.com", "ather-quatum.cloud")
TEST_MARK = "[qa-test]"


def init(conn):
    conn.executescript(SCHEMA)


def verify(secret, msg_id, timestamp, signature_header, body, now=None):
    """True when one of the v1 signatures matches HMAC-SHA256(secret, "id.timestamp.body") and the time is fresh."""
    if not (secret and msg_id and timestamp and signature_header):
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs((now if now is not None else time.time()) - ts) > TOLERANCE_SECONDS:
        return False
    raw = secret.split("_", 1)[1] if secret.startswith("whsec_") else secret
    try:
        key = base64.b64decode(raw)
    except (ValueError, TypeError):
        return False
    if isinstance(body, str):
        body = body.encode()
    expected = base64.b64encode(hmac.new(key, f"{msg_id}.{timestamp}.".encode() + body, hashlib.sha256).digest()).decode()
    for part in signature_header.split():
        version, _, sig = part.partition(",")
        if version == "v1" and hmac.compare_digest(sig, expected):
            return True
    return False


def sign(secret, msg_id, timestamp, body):
    """Test helper: the header value Resend would send."""
    raw = secret.split("_", 1)[1] if secret.startswith("whsec_") else secret
    if isinstance(body, str):
        body = body.encode()
    digest = hmac.new(base64.b64decode(raw), f"{msg_id}.{timestamp}.".encode() + body, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def _addr(value):
    if isinstance(value, list):
        return ", ".join(_addr(v) for v in value)[:500]
    if isinstance(value, dict):
        return str(value.get("email") or value.get("address") or "")[:254]
    return str(value or "")[:254]


def is_test_mail(from_addr, subject):
    sender = from_addr.rsplit("<", 1)[-1].rstrip(">").strip().lower()
    return TEST_MARK in (subject or "").lower() and sender.rpartition("@")[2] in OWN_DOMAINS


def store(conn, webhook_id, data):
    """Insert once per webhook delivery id; returns the row dict, or None if it was already stored."""
    row = {"webhook_id": webhook_id, "email_id": str(data.get("email_id") or data.get("id") or "")[:80],
           "received_at": str(data.get("created_at") or "")[:40], "from_addr": _addr(data.get("from")),
           "to_addr": _addr(data.get("to")), "subject": str(data.get("subject") or "")[:300]}
    row["is_test"] = int(is_test_mail(row["from_addr"], row["subject"]))
    with conn:
        cur = conn.execute("INSERT OR IGNORE INTO inbound_mail (webhook_id, email_id, received_at, from_addr, to_addr,"
                           " subject, is_test) VALUES (:webhook_id, :email_id, :received_at, :from_addr, :to_addr,"
                           " :subject, :is_test)", row)
    if not cur.rowcount:
        return None
    row["id"] = cur.lastrowid
    return row


def owner_notice(row):
    subject = f"New reply: {row['subject'][:120] or '(no subject)'}"
    text = (f"A reply arrived at {row['to_addr']}.\n\nFrom: {row['from_addr']}\nSubject: {row['subject']}\n"
            f"Received: {row['received_at']} (UTC)\nResend email id: {row['email_id']}\n\n"
            "Read the full message in the Resend dashboard: Emails > Receiving.\n"
            "Nothing was answered automatically.\n\nQuantum Aether Team")
    return subject, text


def recent(conn, limit=20):
    try:
        return conn.execute("SELECT received_at, from_addr, to_addr, subject FROM inbound_mail WHERE is_test = 0 "
                            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    except Exception:  # table missing on an old database: admin page still renders
        return []


def register(bp, deps):
    """deps: db, mailer (callable), owner (callable), secret (callable)."""

    @bp.post("/hooks/resend/inbound")
    def resend_inbound():
        secret = deps["secret"]()
        if not secret:
            return {"error": "not_configured"}, 503
        body = request.get_data(cache=False)
        h = request.headers
        if not verify(secret, h.get("svix-id", ""), h.get("svix-timestamp", ""), h.get("svix-signature", ""), body):
            log.warning("inbound webhook: bad signature")
            return {"error": "bad_signature"}, 401
        try:
            event = json.loads(body or b"{}")
        except ValueError:
            return {"error": "bad_json"}, 400
        if not isinstance(event, dict) or event.get("type") != "email.received":
            return {"ok": True, "ignored": True}
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        conn = deps["db"]()
        init(conn)
        row = store(conn, h.get("svix-id", "")[:100], data)
        if row is None:
            return {"ok": True, "duplicate": True}
        log.info("inbound mail stored: id=%s test=%s", row["id"], row["is_test"])
        owner = deps["owner"]()
        if not row["is_test"] and owner:
            subject, text = owner_notice(row)
            if deps["mailer"]().send(owner, subject, text):
                with conn:
                    conn.execute("UPDATE inbound_mail SET notified = 1 WHERE id = ?", (row["id"],))
        return {"ok": True}
