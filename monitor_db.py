# monitor_db.py
# تخزين اشتراكات المراقبة الشهرية: الحسابات والنطاقات المراقبة والتنبيهات (في ملف SQLite نفسه).
import hashlib
import json
import adoption
import secrets

SCHEMA = """
CREATE TABLE IF NOT EXISTS monitor_accounts (
    id               TEXT PRIMARY KEY,
    email            TEXT NOT NULL,
    plan             TEXT NOT NULL,
    status           TEXT NOT NULL,               -- PENDING, ACTIVE, CANCELLED, SUSPENDED, EXPIRED
    subscription_id  TEXT UNIQUE,
    token_hash       TEXT NOT NULL UNIQUE,        -- رابط لوحة التحكم السري؛ نحفظ بصمته فقط
    lang             TEXT NOT NULL DEFAULT 'en',
    last_manual_scan TEXT,
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS monitor_accounts_email ON monitor_accounts (email);

CREATE TABLE IF NOT EXISTS monitor_domains (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id   TEXT NOT NULL REFERENCES monitor_accounts (id) ON DELETE CASCADE,
    domain       TEXT NOT NULL,
    grade        TEXT,
    pq           INTEGER,
    days_left    INTEGER,
    error        TEXT,
    result_json  TEXT,
    checked_at   TEXT,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (account_id, domain)
);

CREATE TABLE IF NOT EXISTS monitor_alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id  TEXT NOT NULL REFERENCES monitor_accounts (id) ON DELETE CASCADE,
    domain      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    params_json TEXT NOT NULL,
    emailed     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS monitor_alerts_account ON monitor_alerts (account_id, created_at);
"""


def init(conn):
    conn.executescript(SCHEMA)


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_account(conn, email, plan, lang, consent_at=None):
    """ينشئ حساباً معلقاً حتى يؤكد PayPal الاشتراك. يعيد (المعرّف، الرمز السري).
    consent_at: وقت طلب المشترك الصريح لبدء الخدمة فوراً (§ 16 FAGG)."""
    account_id, token = "acc_" + secrets.token_urlsafe(12), secrets.token_urlsafe(32)
    with conn:
        conn.execute("INSERT INTO monitor_accounts (id, email, plan, status, token_hash, lang, consent_at)"
                     " VALUES (?, ?, ?, 'PENDING', ?, ?, ?)", (account_id, email, plan, hash_token(token), lang, consent_at))
    return account_id, token


def rotate_token(conn, account_id):
    token = secrets.token_urlsafe(32)
    with conn:
        conn.execute("UPDATE monitor_accounts SET token_hash = ? WHERE id = ?", (hash_token(token), account_id))
    return token


def get_account(conn, account_id):
    row = conn.execute("SELECT * FROM monitor_accounts WHERE id = ?", (account_id,)).fetchone()
    return dict(row) if row else None


def get_account_by_token(conn, token):
    row = conn.execute("SELECT * FROM monitor_accounts WHERE token_hash = ?", (hash_token(token),)).fetchone()
    return dict(row) if row else None


def active_accounts_by_email(conn, email):
    rows = conn.execute("SELECT * FROM monitor_accounts WHERE email = ? AND status = 'ACTIVE'", (email,)).fetchall()
    return [dict(r) for r in rows]


def accounts_with_subscription(conn):
    rows = conn.execute("SELECT * FROM monitor_accounts WHERE subscription_id IS NOT NULL AND status = 'ACTIVE'").fetchall()
    return [dict(r) for r in rows]


def set_status(conn, account_id, status, subscription_id=None):
    with conn:
        conn.execute("UPDATE monitor_accounts SET status = ?, subscription_id = COALESCE(?, subscription_id),"
                     " updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
                     (status, subscription_id, account_id))


def mark_manual_scan(conn, account_id, when_iso):
    with conn:
        conn.execute("UPDATE monitor_accounts SET last_manual_scan = ? WHERE id = ?", (when_iso, account_id))


def list_domains(conn, account_id):
    rows = conn.execute("SELECT * FROM monitor_domains WHERE account_id = ? ORDER BY domain", (account_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["result"] = json.loads(d.pop("result_json")) if d["result_json"] else None
        out.append(d)
    return out


def count_domains(conn, account_id):
    return conn.execute("SELECT COUNT(*) FROM monitor_domains WHERE account_id = ?", (account_id,)).fetchone()[0]


def add_domain(conn, account_id, domain):
    """يعيد True إن أُضيف، وFalse إن كان موجوداً."""
    with conn:
        cur = conn.execute("INSERT OR IGNORE INTO monitor_domains (account_id, domain) VALUES (?, ?)", (account_id, domain))
    return cur.rowcount == 1


def remove_domain(conn, account_id, domain_id):
    with conn:
        conn.execute("DELETE FROM monitor_domains WHERE account_id = ? AND id = ?", (account_id, domain_id))


def save_check(conn, domain_id, result=None, error=None):
    with conn:
        if result is not None:
            kx = result['key_exchange']
            pq = None if adoption.is_unsure(kx, kx.get('version') or result['certificate'].get('negotiated_version')) else int(bool(kx.get('pq')))
            conn.execute(
                "UPDATE monitor_domains SET grade = ?, pq = ?, days_left = ?, error = NULL, result_json = ?,"
                " checked_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
                (result["grade"], pq, result["certificate"].get("days_left"),
                 json.dumps(result, ensure_ascii=False), domain_id))
        else:
            conn.execute("UPDATE monitor_domains SET error = ?, checked_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
                         (error, domain_id))


def add_alert(conn, account_id, domain, kind, params):
    with conn:
        conn.execute("INSERT INTO monitor_alerts (account_id, domain, kind, params_json) VALUES (?, ?, ?, ?)",
                     (account_id, domain, kind, json.dumps(params)))


def recent_alerts(conn, account_id, limit=50):
    rows = conn.execute("SELECT * FROM monitor_alerts WHERE account_id = ? ORDER BY id DESC LIMIT ?",
                        (account_id, limit)).fetchall()
    return [dict(r, params=json.loads(r["params_json"])) for r in rows]


def unsent_alerts(conn, account_id):
    rows = conn.execute("SELECT * FROM monitor_alerts WHERE account_id = ? AND emailed = 0 ORDER BY id",
                        (account_id,)).fetchall()
    return [dict(r, params=json.loads(r["params_json"])) for r in rows]


def mark_alerts_sent(conn, alert_ids):
    if not alert_ids:
        return
    with conn:
        conn.executemany("UPDATE monitor_alerts SET emailed = 1 WHERE id = ?", [(i,) for i in alert_ids])


def stats(conn, plans):
    """عدد المشتركين الفعّالين لكل خطة والدخل الشهري المتكرر المتوقع (MRR)."""
    rows = conn.execute("SELECT plan, COUNT(*) AS n FROM monitor_accounts WHERE status = 'ACTIVE' GROUP BY plan").fetchall()
    active = {r["plan"]: r["n"] for r in rows}
    mrr = sum(float(plans[p]["price"]) * n for p, n in active.items() if p in plans)
    cancelled = conn.execute("SELECT COUNT(*) FROM monitor_accounts WHERE status IN ('CANCELLED', 'SUSPENDED', 'EXPIRED')").fetchone()[0]
    return {"active": active, "active_total": sum(active.values()), "mrr": f"{mrr:.2f}", "churned": cancelled}


def recent_accounts(conn, limit=50):
    rows = conn.execute(
        "SELECT a.id, a.email, a.plan, a.status, a.created_at, a.updated_at,"
        " (SELECT COUNT(*) FROM monitor_domains d WHERE d.account_id = a.id) AS domains"
        " FROM monitor_accounts a WHERE a.status != 'PENDING' ORDER BY a.created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]
