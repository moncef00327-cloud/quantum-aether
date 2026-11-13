# assets.py
# جرد أصول المشترك: نطاقات أساسية (بذور) يثبت ملكيتها، كشف أسبوعي لأسمائها الحية من سجلات شفافية الشهادات،
# إضافتها للمراقبة تلقائياً مع تنبيه «أصل جديد»، وتنبيه عند تجاوز حد الخطة، وسحب الأصل المكتشف الذي اختفى مع سبب مكتوب.
# الأسماء المضافة يدوياً لا تُسحب أبداً.
import datetime as dt
import logging
import secrets
import subprocess
import threading

import discovery
import monitor
import monitor_db

log = logging.getLogger("quantum_saas.assets")

SEED_LIMITS = {"TRIAL": 1, "starter": 3, "business": 20}
DISCOVERY_INTERVAL_DAYS = 7      # كشف تلقائي أسبوعي لكل بذرة موثّقة
MANUAL_DISCOVER_HOURS = 6        # زر «اكشف الآن»: مرة كل 6 ساعات لكل بذرة
RETIRE_AFTER_FAILURES = 7        # أصل مكتشف لا يرد 7 فحوص متتالية ولم يعد يظهر في الكشف: يُسحب
TXT_PREFIX = "_quantum-aether"

SCHEMA = """
CREATE TABLE IF NOT EXISTS monitor_seeds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id      TEXT NOT NULL,
    base            TEXT NOT NULL,
    verify_code     TEXT NOT NULL,
    verified_at     TEXT,
    verified_by     TEXT,              -- email | dns
    last_run_at     TEXT,
    last_status     TEXT,              -- RUNNING | DONE | FAILED
    last_names      INTEGER,
    last_responding INTEGER,
    last_error      TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (account_id, base)
);
"""

_threads = []


def _now(delta=None):
    return (dt.datetime.now(dt.timezone.utc) + (delta or dt.timedelta())).strftime("%Y-%m-%dT%H:%M:%SZ")


def init(conn):
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(monitor_domains)")}
    with conn:
        if "source" not in cols:
            conn.execute("ALTER TABLE monitor_domains ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")
        if "fail_streak" not in cols:
            conn.execute("ALTER TABLE monitor_domains ADD COLUMN fail_streak INTEGER NOT NULL DEFAULT 0")


def seed_limit(account):
    if account["status"] in ("TRIAL", "TRIAL_ENDED"):
        return SEED_LIMITS["TRIAL"]
    return SEED_LIMITS.get(account["plan"], 1)


def seeds(conn, account_id):
    return [dict(r) for r in conn.execute("SELECT * FROM monitor_seeds WHERE account_id = ? ORDER BY base", (account_id,))]


def get_seed(conn, account_id, seed_id):
    row = conn.execute("SELECT * FROM monitor_seeds WHERE account_id = ? AND id = ?", (account_id, seed_id)).fetchone()
    return dict(row) if row else None


def add_seed(conn, account, raw):
    """يعيد 'added' أو 'exists' أو 'limit' أو 'invalid'. بريد الحساب على النطاق نفسه يثبت الملكية فوراً."""
    try:
        base = discovery.base_domain(monitor.normalize(raw))
    except Exception:  # noqa: BLE001
        return "invalid"
    current = seeds(conn, account["id"])
    if any(s["base"] == base for s in current):
        return "exists"
    if len(current) >= seed_limit(account):
        return "limit"
    by_email = discovery.email_matches(account["email"], base)
    with conn:
        conn.execute("INSERT INTO monitor_seeds (account_id, base, verify_code, verified_at, verified_by) VALUES (?, ?, ?, ?, ?)",
                     (account["id"], base, secrets.token_hex(8), _now() if by_email else None, "email" if by_email else None))
    return "added"


def remove_seed(conn, account_id, seed_id):
    """حذف البذرة لا يحذف النطاقات المراقبة (قد يريد العميل إبقاءها)."""
    with conn:
        conn.execute("DELETE FROM monitor_seeds WHERE account_id = ? AND id = ?", (account_id, seed_id))


def txt_records(name):
    """سجلات TXT عبر dig (لا مكتبة DNS على الخادم). الاسم مُتحقق منه مسبقاً؛ يعيد [] عند أي فشل."""
    try:
        out = subprocess.run(["dig", "+short", "+time=4", "+tries=2", "TXT", name],
                             capture_output=True, text=True, timeout=12).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    # كل سطر سجل واحد، وقد يُقسَّم السجل الطويل إلى "جزء" "جزء"
    return ["".join(part for part in line.strip().split('"') if part.strip()) for line in out.splitlines() if line.strip()]


def verify_seed(conn, seed):
    expected = f"qa-verify={seed['verify_code']}"
    if expected in txt_records(f"{TXT_PREFIX}.{seed['base']}"):
        with conn:
            conn.execute("UPDATE monitor_seeds SET verified_at = ?, verified_by = 'dns' WHERE id = ?", (_now(), seed["id"]))
        return True
    return False


def _under(domain, base):
    return domain == base or domain.endswith("." + base)


def run_seed(conn, account_id, seed, discover, now_iso=None):
    """يكشف الأسماء الحية تحت البذرة ويحدّث المخزون. discover(base) يعيد نتيجة discovery.run_discovery."""
    now_iso = now_iso or _now()
    account = monitor_db.get_account(conn, account_id)
    try:
        result = discover(seed["base"])
    except Exception as exc:  # noqa: BLE001 — فشل المصدر لا يمس المخزون
        with conn:
            conn.execute("UPDATE monitor_seeds SET last_run_at = ?, last_status = 'FAILED', last_error = ? WHERE id = ?",
                         (now_iso, str(exc)[:200], seed["id"]))
        log.warning("asset discovery failed for %s: %s", seed["base"], exc)
        return {"added": 0, "skipped": 0, "retired": 0, "error": str(exc)}
    live = {h["host"]: h for h in result["hosts"]}
    current = {d["domain"]: d for d in monitor_db.list_domains(conn, account_id)}
    limit = monitor.domain_limit(account)
    added = skipped = retired = 0
    for host in sorted(live):
        if host in current:
            continue
        if len(current) + added >= limit:
            skipped += 1
            continue
        monitor_db.add_domain(conn, account_id, host, source="discovered")
        h = live[host]
        monitor_db.add_alert(conn, account_id, host, "NEW_ASSET",
                             {"base": seed["base"], "status": h["status"], "group": h.get("group") or "?"})
        added += 1
    if skipped:
        monitor_db.add_alert(conn, account_id, seed["base"], "ASSETS_OVER_LIMIT", {"count": skipped, "limit": limit})
    # كشف بلا أي اسم حي (مصدر مثقل أو عطل شبكة) غير حاسم: لا نسحب شيئاً بناءً عليه
    for d in (current.values() if live else ()):
        if (d.get("source") == "discovered" and _under(d["domain"], seed["base"]) and d["domain"] not in live
                and (d.get("fail_streak") or 0) >= RETIRE_AFTER_FAILURES):
            monitor_db.remove_domain(conn, account_id, d["id"])
            monitor_db.add_alert(conn, account_id, d["domain"], "ASSET_RETIRED",
                                 {"base": seed["base"], "days": RETIRE_AFTER_FAILURES})
            retired += 1
    with conn:
        conn.execute("UPDATE monitor_seeds SET last_run_at = ?, last_status = 'DONE', last_names = ?, last_responding = ?,"
                     " last_error = NULL WHERE id = ?", (now_iso, result["names"], result["responding"], seed["id"]))
    log.info("assets %s: +%d new, %d over limit, %d retired", seed["base"], added, skipped, retired)
    return {"added": added, "skipped": skipped, "retired": retired, "error": None}


def due_seeds(conn, now=None):
    """بذور موثّقة لحسابات فعّالة أو في التجربة، لم تُكشف منذ أسبوع."""
    now = now or dt.datetime.now(dt.timezone.utc)
    cutoff = (now - dt.timedelta(days=DISCOVERY_INTERVAL_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = conn.execute("SELECT s.* FROM monitor_seeds s JOIN monitor_accounts a ON a.id = s.account_id"
                        " WHERE s.verified_at IS NOT NULL AND a.status IN ('ACTIVE', 'TRIAL')"
                        " AND (s.last_run_at IS NULL OR s.last_run_at < ?)", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def manual_wait(seed, now=None):
    """True إن كان آخر كشف أحدث من MANUAL_DISCOVER_HOURS."""
    if not seed.get("last_run_at"):
        return False
    now = now or dt.datetime.now(dt.timezone.utc)
    last = dt.datetime.strptime(seed["last_run_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    return now - last < dt.timedelta(hours=MANUAL_DISCOVER_HOURS)


def start_background(connect, account_id, seed, discover):
    """زر «اكشف الآن»: يحجز التشغيل (يُحسب في حد الست ساعات) ثم يكشف في خيط بلا حجز طلب HTTP."""
    conn = connect()
    try:
        with conn:
            conn.execute("UPDATE monitor_seeds SET last_run_at = ?, last_status = 'RUNNING' WHERE id = ?", (_now(), seed["id"]))
    finally:
        conn.close()

    def work():
        with discovery._running:  # نفس حد التشغيل المتزامن لكشف النطاقات العام
            c = connect()
            try:
                run_seed(c, account_id, seed, discover)
            finally:
                c.close()

    t = threading.Thread(target=work, name=f"assets-{seed['base']}", daemon=True)
    _threads.append(t)
    t.start()
    return t


def wait_background(timeout=30):
    """للاختبارات: انتظر انتهاء خيوط الكشف."""
    while _threads:
        _threads.pop().join(timeout)


def summary_for(conn, account_id):
    """ما تعرضه اللوحة: البذور مع حالتها وعدد الأصول المكتشفة تحت كل منها."""
    doms = monitor_db.list_domains(conn, account_id)
    out = []
    for s in seeds(conn, account_id):
        s["discovered"] = sum(1 for d in doms if d.get("source") == "discovered" and _under(d["domain"], s["base"]))
        s["txt_name"] = f"{TXT_PREFIX}.{s['base']}"
        s["txt_value"] = f"qa-verify={s['verify_code']}"
        out.append(s)
    return out
