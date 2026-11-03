# sales_db.py
# تخزين الفحوصات والطلبات في SQLite (بدل CSV): آمن مع عدة عمّال gunicorn بفضل WAL والمعاملات.
import datetime as dt
import json
import sqlite3
from decimal import Decimal

import adoption
import analytics_db
import monitor_db

SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id            TEXT PRIMARY KEY,
    report_token  TEXT NOT NULL UNIQUE,
    domain        TEXT NOT NULL,
    grade         TEXT NOT NULL,
    result_json   TEXT NOT NULL,
    client_hash   TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS scans_client_time ON scans (client_hash, created_at);

CREATE TABLE IF NOT EXISTS orders (
    order_id    TEXT PRIMARY KEY,
    scan_id     TEXT NOT NULL REFERENCES scans (id),
    status      TEXT NOT NULL,
    amount      TEXT NOT NULL,
    currency    TEXT NOT NULL,
    capture_id  TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS orders_scan ON orders (scan_id);

CREATE TABLE IF NOT EXISTS scan_attempts (
    client_hash  TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS attempts_client_time ON scan_attempts (client_hash, created_at);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    monitor_db.init(conn)
    analytics_db.init(conn)
    adoption.init(conn)
    _migrate(conn)
    return conn


def _migrate(conn):
    """ترحيلات صغيرة للقواعد الموجودة: أعمدة أضيفت بعد الإطلاق."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(scans)")}
    if "is_test" not in cols:
        with conn:
            conn.execute("ALTER TABLE scans ADD COLUMN is_test INTEGER NOT NULL DEFAULT 0")
            conn.execute("UPDATE scans SET is_test = 1")  # كل ما سبق الإطلاق اختبارات
    cols = {r[1] for r in conn.execute("PRAGMA table_info(orders)")}
    if "email" not in cols:
        with conn:
            conn.execute("ALTER TABLE orders ADD COLUMN email TEXT")
    if "consent_at" not in cols:
        with conn:
            conn.execute("ALTER TABLE orders ADD COLUMN consent_at TEXT")
    if "is_test" not in cols:
        with conn:
            conn.execute("ALTER TABLE orders ADD COLUMN is_test INTEGER NOT NULL DEFAULT 0")
            conn.execute("UPDATE orders SET is_test = 1")  # كل الطلبات السابقة اختبارات
    cols = {r[1] for r in conn.execute("PRAGMA table_info(monitor_accounts)")}
    if "consent_at" not in cols:
        with conn:
            conn.execute("ALTER TABLE monitor_accounts ADD COLUMN consent_at TEXT")
    # معاملة العملات الرقمية الواحدة لا تفتح أكثر من طلب واحد
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS orders_crypto_tx ON orders (capture_id)"
                 " WHERE currency IN ('USDT', 'USDC') AND capture_id IS NOT NULL")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(pageviews)")}
    if "is_test" not in cols:
        with conn:
            conn.execute("ALTER TABLE pageviews ADD COLUMN is_test INTEGER NOT NULL DEFAULT 0")
            conn.execute("UPDATE pageviews SET is_test = 1")


def create_scan(conn, scan_id, report_token, result, client_hash, is_test=False):
    with conn:
        conn.execute(
            "INSERT INTO scans (id, report_token, domain, grade, result_json, client_hash, is_test) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (scan_id, report_token, result["domain"], result["grade"], json.dumps(result, ensure_ascii=False), client_hash,
             int(is_test)),
        )


def _scan_from_row(row):
    if row is None:
        return None
    scan = dict(row)
    scan["result"] = json.loads(scan.pop("result_json"))
    return scan


def get_scan(conn, scan_id):
    return _scan_from_row(conn.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone())


def get_scan_by_report_token(conn, token):
    return _scan_from_row(conn.execute("SELECT * FROM scans WHERE report_token = ?", (token,)).fetchone())


def latest_scan_for_domain(conn, domain, since_iso):
    """آخر فحص لنطاق منذ تاريخ معيّن (للشارة)، أو None."""
    row = conn.execute("SELECT * FROM scans WHERE domain = ? AND created_at >= ? ORDER BY created_at DESC LIMIT 1",
                       (domain, since_iso)).fetchone()
    return _scan_from_row(row)


def record_attempt(conn, client_hash):
    """كل محاولة فحص تُحسب، حتى الفاشلة، كي لا يُستعمل الخادم لإجراء اتصالات بلا حد."""
    with conn:
        conn.execute("INSERT INTO scan_attempts (client_hash) VALUES (?)", (client_hash,))
        conn.execute("DELETE FROM scan_attempts WHERE created_at < strftime('%Y-%m-%dT%H:%M:%SZ', 'now', '-1 day')")


def count_attempts_since(conn, since_iso, client_hash=None):
    if client_hash is None:
        row = conn.execute("SELECT COUNT(*) FROM scan_attempts WHERE created_at >= ?", (since_iso,)).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM scan_attempts WHERE client_hash = ? AND created_at >= ?",
                           (client_hash, since_iso)).fetchone()
    return row[0]


def create_order(conn, order_id, scan_id, amount, currency, consent_at=None, is_test=False, email=None):
    """consent_at: وقت موافقة المشتري الصريحة على التسليم الفوري وفقدان حق التراجع (§ 18 FAGG)."""
    with conn:
        conn.execute("INSERT INTO orders (order_id, scan_id, status, amount, currency, consent_at, is_test, email)"
                     " VALUES (?, ?, 'CREATED', ?, ?, ?, ?, ?)",
                     (order_id, scan_id, amount, currency, consent_at, int(is_test), email))


def get_order(conn, order_id):
    row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    return dict(row) if row else None


def update_order(conn, order_id, status, capture_id=None):
    with conn:
        conn.execute(
            "UPDATE orders SET status = ?, capture_id = COALESCE(?, capture_id),"
            " updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE order_id = ?",
            (status, capture_id, order_id),
        )


def open_amounts(conn, currency, days=7):
    """مبالغ طلبات العملات الرقمية المفتوحة حديثاً، حتى لا يتكرر المبلغ الفريد."""
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = conn.execute("SELECT amount FROM orders WHERE currency = ? AND status = 'CREATED' AND created_at >= ?",
                        (currency, since)).fetchall()
    return {r["amount"] for r in rows}


def order_by_capture(conn, capture_id):
    row = conn.execute("SELECT * FROM orders WHERE capture_id = ?", (capture_id,)).fetchone()
    return dict(row) if row else None


def is_scan_paid(conn, scan_id):
    row = conn.execute("SELECT 1 FROM orders WHERE scan_id = ? AND status = 'COMPLETED' LIMIT 1", (scan_id,)).fetchone()
    return row is not None


def stats(conn):
    scans = conn.execute("SELECT COUNT(*) FROM scans WHERE is_test = 0").fetchone()[0]
    paid = conn.execute("SELECT amount, currency FROM orders WHERE status = 'COMPLETED' AND is_test = 0").fetchall()
    incomplete = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'CREATED' AND is_test = 0 AND created_at < ?",
                              (_hours_ago(INCOMPLETE_AFTER_HOURS),)).fetchone()[0]
    revenue = {}
    for row in paid:
        revenue[row["currency"]] = revenue.get(row["currency"], Decimal("0")) + Decimal(row["amount"])
    return {"scans": scans, "paid_orders": len(paid), "incomplete_orders": incomplete,
            "revenue": {k: f"{v:.2f}" for k, v in revenue.items()}}


INCOMPLETE_AFTER_HOURS = 3


def _hours_ago(hours):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def recent_orders(conn, limit=50):
    """الطلبات الأخيرة. الطلب الذي بقي CREATED أكثر من 3 ساعات يُعرض كـ INCOMPLETE (لم يكتمل)."""
    rows = conn.execute(
        "SELECT o.*, s.domain FROM orders o JOIN scans s ON s.id = o.scan_id ORDER BY o.created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    cutoff = _hours_ago(INCOMPLETE_AFTER_HOURS)
    out = []
    for r in rows:
        order = dict(r)
        order["display_status"] = ("INCOMPLETE" if order["status"] == "CREATED" and order["created_at"] < cutoff
                                   else order["status"])
        out.append(order)
    return out


def scans_per_day(conn, since_day):
    rows = conn.execute("SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n FROM scans"
                        " WHERE created_at >= ? AND is_test = 0 GROUP BY day ORDER BY day DESC", (since_day,)).fetchall()
    return {r["day"]: r["n"] for r in rows}


def recent_scans(conn, limit=50):
    rows = conn.execute("SELECT id, domain, grade, created_at, is_test FROM scans ORDER BY created_at DESC LIMIT ?",
                        (limit,)).fetchall()
    return [dict(r) for r in rows]
