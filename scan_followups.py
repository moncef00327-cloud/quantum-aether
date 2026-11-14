"""Explicit opt-in records for one-off B/C scan follow-up."""
import datetime as dt
import hashlib
import hmac
import json
import secrets
import sqlite3

CONSENT_VERSION = "scan-followup-v1"
EU_COUNTRIES = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}


def init(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS scan_followups (
        id TEXT PRIMARY KEY, scan_id TEXT NOT NULL, email TEXT NOT NULL,
        domain TEXT NOT NULL, grade TEXT NOT NULL, findings_json TEXT NOT NULL,
        country_code TEXT, recipient_type TEXT,
        consent_at TEXT NOT NULL, consent_source TEXT NOT NULL,
        consent_version TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPTED_IN',
        sent_at TEXT, unsubscribed_at TEXT,
        UNIQUE(scan_id,email))""")
    conn.execute("CREATE INDEX IF NOT EXISTS scan_followups_eligible ON scan_followups(status,sent_at)")
    conn.execute("CREATE TABLE IF NOT EXISTS scan_followup_suppressions (email TEXT PRIMARY KEY, blocked_at TEXT NOT NULL, source TEXT NOT NULL)")
    cols = {row[1] for row in conn.execute("PRAGMA table_info(scan_followups)")}
    if "country_code" not in cols:
        conn.execute("ALTER TABLE scan_followups ADD COLUMN country_code TEXT")
    if "recipient_type" not in cols:
        conn.execute("ALTER TABLE scan_followups ADD COLUMN recipient_type TEXT")
    conn.commit()


def record(conn, scan, email, country_code, recipient_type, source="scan-result"):
    result = scan["result"]
    grade = result.get("grade")
    if grade not in ("B", "C"):
        raise ValueError("grade_not_eligible")
    email = email.strip().lower()
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    rid = secrets.token_urlsafe(18)
    findings = json.dumps(result.get("findings", []), ensure_ascii=False)
    conn.execute("""INSERT INTO scan_followups
        (id,scan_id,email,domain,grade,findings_json,country_code,recipient_type,consent_at,consent_source,consent_version)
        VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(scan_id,email) DO UPDATE SET
            country_code=excluded.country_code, recipient_type=excluded.recipient_type,
            findings_json=excluded.findings_json, consent_at=excluded.consent_at,
            consent_source=excluded.consent_source, consent_version=excluded.consent_version,
            status='OPTED_IN', sent_at=NULL, unsubscribed_at=NULL""",
        (rid, scan["id"], email, result["domain"], grade, findings, country_code.upper(), recipient_type, now, source, CONSENT_VERSION))
    conn.execute("DELETE FROM scan_followup_suppressions WHERE email=?", (email,))
    conn.commit()
    return conn.execute("SELECT * FROM scan_followups WHERE scan_id=? AND email=?", (scan["id"], email)).fetchone()


def unsubscribe_token(row, salt):
    payload = f"{row['id']}|{row['email']}|{row['consent_at']}".encode()
    return hmac.new(salt.encode(), payload, hashlib.sha256).hexdigest()


def token_valid(row, salt, token):
    return bool(token) and hmac.compare_digest(unsubscribe_token(row, salt), token)


def eligible(conn):
    """Opt-ins needing review; self-reported non-EU country is a filter, not legal approval."""
    marks = ",".join("?" for _ in EU_COUNTRIES)
    return conn.execute(f"""SELECT f.* FROM scan_followups f
        LEFT JOIN scan_followup_suppressions s ON lower(s.email)=lower(f.email)
        WHERE f.status='OPTED_IN' AND f.sent_at IS NULL AND s.email IS NULL
        AND length(f.country_code)=2 AND f.recipient_type IS NOT NULL
        AND upper(f.country_code) NOT IN ({marks}) ORDER BY f.consent_at""", tuple(sorted(EU_COUNTRIES))).fetchall()


def suppress_email(conn, email, blocked_at, source="unsubscribe"):
    email = email.strip().lower()
    conn.execute("INSERT INTO scan_followup_suppressions(email,blocked_at,source) VALUES(?,?,?) "
                 "ON CONFLICT(email) DO UPDATE SET blocked_at=excluded.blocked_at,source=excluded.source",
                 (email, blocked_at, source))
    conn.execute("UPDATE scan_followups SET status='UNSUBSCRIBED',unsubscribed_at=? WHERE lower(email)=?",
                 (blocked_at, email))
    conn.commit()
