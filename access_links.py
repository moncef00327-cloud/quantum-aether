"""Short-lived, one-use recovery links; requesting one never revokes existing access."""
import hashlib
import secrets
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS access_links (
    token_hash TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('monitor', 'pack')),
    target_id TEXT NOT NULL,
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS access_links_target ON access_links (kind, target_id);
CREATE TABLE IF NOT EXISTS access_attempts (
    client_hash TEXT NOT NULL,
    email_hash TEXT NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS access_attempts_time ON access_attempts (created_at);
"""


def init(conn):
    conn.executescript(SCHEMA)


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def allow_request(conn, client_hash, email_hash, now=None):
    now = int(time.time() if now is None else now)
    if conn.in_transaction:
        conn.commit()
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM access_attempts WHERE created_at < ?", (now - 3600,))
        clients, emails = conn.execute(
            "SELECT COALESCE(SUM(client_hash = ?), 0), COALESCE(SUM(email_hash = ?), 0) "
            "FROM access_attempts", (client_hash, email_hash)).fetchone()
        if clients >= 5 or emails >= 3:
            return False
        conn.execute("INSERT INTO access_attempts VALUES (?, ?, ?)", (client_hash, email_hash, now))
    return True


def issue(conn, kind, target_id, now=None):
    now = int(time.time() if now is None else now)
    token = secrets.token_urlsafe(32)
    with conn:
        conn.execute("DELETE FROM access_links WHERE expires_at <= ?", (now,))
        conn.execute("INSERT INTO access_links VALUES (?, ?, ?, ?)",
                     (digest(token), kind, target_id, now + 900))
    return token


def revoke(conn, token):
    with conn:
        conn.execute("DELETE FROM access_links WHERE token_hash = ?", (digest(token),))


def lookup(conn, token, now=None):
    row = conn.execute("SELECT * FROM access_links WHERE token_hash = ? AND expires_at > ?",
                       (digest(token), int(time.time() if now is None else now))).fetchone()
    return dict(row) if row else None


def consume(conn, token, now=None):
    """Consume and rotate the target in one transaction, only after an explicit POST."""
    if conn.in_transaction:
        conn.commit()
    with conn:
        conn.execute("BEGIN IMMEDIATE")
        link = lookup(conn, token, now)
        if link is None:
            return None
        table = "monitor_accounts" if link["kind"] == "monitor" else "packs"
        # Same accounts that may request a link (monitor_db.accounts_for_login); a cancelled or expired account
        # is never reactivated by an old recovery link.
        statuses = ("ACTIVE", "TRIAL", "TRIAL_ENDED") if link["kind"] == "monitor" else ("COMPLETED",)
        new_token = secrets.token_urlsafe(32)
        updated = conn.execute(
            f"UPDATE {table} SET token_hash = ? WHERE id = ? AND status IN ({','.join('?' * len(statuses))})",
            (digest(new_token), link["target_id"], *statuses)).rowcount
        conn.execute("DELETE FROM access_links WHERE kind = ? AND target_id = ?",
                     (link["kind"], link["target_id"]))
        if not updated:
            return None
        return link["kind"], new_token
