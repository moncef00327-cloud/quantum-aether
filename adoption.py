# adoption.py
# متتبّع التبنّي الأسبوعي: نعيد فحص قائمة الدراسة (Tranco top 1000) وقوائم المراقبة (DACH) كل أسبوع،
# ونحفظ نتيجة كل نطاق، ونحسب من انتقل إلى تبادل المفاتيح الهجين ومن فقده. لا يعتمد على sales_db
# (حتى لا يحدث استيراد دائري)؛ sales_db.connect يستدعي init هنا.
import concurrent.futures as cf
import csv
import datetime as dt
import io
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_STUDY_FILE = os.path.join(BASE_DIR, "data", "pq_study_top1000_raw.jsonl")
WATCHLISTS_FILE = os.path.join(BASE_DIR, "data", "adoption_watchlists.json")
TIMELINE_WEEKS = 26

SCHEMA = """
CREATE TABLE IF NOT EXISTS adoption_results (
    week        TEXT NOT NULL,          -- أسبوع ISO مثل 2026-W45
    domain      TEXT NOT NULL,
    rank        INTEGER,                -- ترتيب Tranco؛ فارغ لنطاقات قوائم المراقبة خارج الأكبر 1000
    sector      TEXT,                   -- مفتاح قائمة المراقبة إن وُجد
    ok          INTEGER NOT NULL,       -- 1 إن أجاب على HTTPS
    grade       TEXT,
    grp         TEXT,                   -- مجموعة تبادل المفاتيح المتفق عليها
    tls         TEXT,
    pq          INTEGER NOT NULL DEFAULT 0,
    scanned_at  TEXT NOT NULL,
    PRIMARY KEY (week, domain)
);
CREATE INDEX IF NOT EXISTS adoption_by_domain ON adoption_results(domain, week);
"""


def init(conn):
    conn.executescript(SCHEMA)


# ---------------------------------------------------------------- الأسابيع

def week_of(day):
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def week_monday(week):
    year, num = week.split("-W")
    return dt.date.fromisocalendar(int(year), int(num), 1)


# ---------------------------------------------------------------- القوائم

def load_watchlists(path=WATCHLISTS_FILE):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("sectors", {})
    except FileNotFoundError:
        return {}


def _raw_study_rows(path=RAW_STUDY_FILE):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_targets(raw_path=RAW_STUDY_FILE, watchlists=None):
    """كل نطاقات الدراسة (بما فيها التي لم تُجب، فقد تجيب لاحقاً) ثم نطاقات قوائم المراقبة."""
    watchlists = load_watchlists() if watchlists is None else watchlists
    sector_of = {}
    for key, sector in watchlists.items():
        for domain in sector.get("domains", []):
            sector_of.setdefault(domain.lower(), key)
    targets, seen = [], set()
    for row in _raw_study_rows(raw_path):
        domain = row["domain"].lower()
        targets.append({"domain": domain, "rank": row["rank"], "sector": sector_of.get(domain)})
        seen.add(domain)
    for domain, key in sector_of.items():
        if domain not in seen:
            targets.append({"domain": domain, "rank": None, "sector": key})
            seen.add(domain)
    return targets


# ---------------------------------------------------------------- التسجيل

def _summary_of(result):
    kx = result.get("key_exchange") or {}
    cert = result.get("certificate") or {}
    return {"ok": 1, "grade": result.get("grade"), "grp": kx.get("group"),
            "tls": kx.get("version") or cert.get("negotiated_version"), "pq": 1 if kx.get("pq") else 0}


def record(conn, week, target, result, scanned_at):
    """يحفظ نتيجة نطاق لأسبوع. result قاموس نتيجة الفحص، أو None إن لم يُجب."""
    summary = _summary_of(result) if result else {"ok": 0, "grade": None, "grp": None, "tls": None, "pq": 0}
    conn.execute(
        "INSERT OR REPLACE INTO adoption_results (week, domain, rank, sector, ok, grade, grp, tls, pq, scanned_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (week, target["domain"], target.get("rank"), target.get("sector"), summary["ok"], summary["grade"],
         summary["grp"], summary["tls"], summary["pq"], scanned_at))


def seed_from_study(conn, raw_path=RAW_STUDY_FILE):
    """أول أسبوع = بيانات الدراسة المنشورة، فتظهر أول مقارنة بعد أول فحص أسبوعي. لا يفعل شيئاً إن وُجدت بيانات."""
    if conn.execute("SELECT 1 FROM adoption_results LIMIT 1").fetchone():
        return 0
    rows = _raw_study_rows(raw_path)
    sector_of = {}
    for key, sector in load_watchlists().items():
        for domain in sector.get("domains", []):
            sector_of.setdefault(domain.lower(), key)
    count = 0
    with conn:
        for row in rows:
            scanned_at = row.get("scanned_at") or ""
            day = dt.date.fromisoformat(scanned_at[:10]) if scanned_at else None
            if day is None:  # النطاقات التي لم تُجب ليس لها وقت فحص: نأخذ يوم أول نتيجة لها تاريخ
                day = next(dt.date.fromisoformat(r["scanned_at"][:10]) for r in rows if r.get("scanned_at"))
                scanned_at = f"{day.isoformat()}T00:00:00+00:00"
            domain = row["domain"].lower()
            target = {"domain": domain, "rank": row["rank"], "sector": sector_of.get(domain)}
            record(conn, week_of(day), target, row if row.get("ok") else None, scanned_at)
            count += 1
    return count


def run_week(conn, scanner, targets, day=None, workers=16, now=None):
    """يفحص كل الأهداف ويحفظها تحت أسبوع اليوم. الفحص في خيوط، والكتابة في الخيط الرئيسي."""
    day = day or dt.date.today()
    week = week_of(day)

    def one(target):
        try:
            return target, scanner(target["domain"])
        except Exception:  # أي فشل (لا عنوان، لا HTTPS، مهلة) = لم يُجب هذا الأسبوع
            return target, None

    answered = 0
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        for target, result in pool.map(one, targets):
            stamp = (now or dt.datetime.now(dt.timezone.utc)).isoformat(timespec="seconds")
            with conn:
                record(conn, week, target, result, stamp)
            answered += 1 if result else 0
    return {"week": week, "targets": len(targets), "answered": answered}


# ---------------------------------------------------------------- القراءة

def weeks(conn):
    return [r[0] for r in conn.execute("SELECT DISTINCT week FROM adoption_results ORDER BY week")]


def rows_for(conn, week):
    cur = conn.execute("SELECT * FROM adoption_results WHERE week = ? ORDER BY rank IS NULL, rank, domain", (week,))
    return [dict(r) for r in cur]


def timeline(conn, limit=TIMELINE_WEEKS):
    """نسبة التبنّي أسبوعياً على قائمة الأكبر 1000 وحدها، حتى تبقى الأرقام قابلة للمقارنة."""
    cur = conn.execute(
        "SELECT week, SUM(ok) AS reachable, SUM(CASE WHEN ok = 1 AND pq = 1 THEN 1 ELSE 0 END) AS pq "
        "FROM adoption_results WHERE rank IS NOT NULL GROUP BY week ORDER BY week")
    points = []
    for r in cur:
        reachable, pq = r["reachable"] or 0, r["pq"] or 0
        points.append({"week": r["week"], "date": week_monday(r["week"]).isoformat(), "reachable": reachable,
                       "pq": pq, "pct": round(100 * pq / reachable, 1) if reachable else 0.0})
    return points[-limit:]


def first_pq_weeks(conn):
    cur = conn.execute("SELECT domain, MIN(week) FROM adoption_results WHERE ok = 1 AND pq = 1 GROUP BY domain")
    return {domain: week for domain, week in cur}


def changes(previous, current):
    """يقارن أسبوعين. لا يُحسب «فقد» لنطاق لم يُجب هذا الأسبوع: الغياب ليس تراجعاً."""
    prev = {r["domain"]: r for r in previous}
    adopted, dropped, regraded = [], [], []
    for row in current:
        before = prev.get(row["domain"])
        if not before or not before["ok"] or not row["ok"]:
            continue
        if row["pq"] and not before["pq"]:
            adopted.append(dict(row, grade_before=before["grade"], grp_before=before["grp"]))
        elif before["pq"] and not row["pq"]:
            dropped.append(dict(row, grade_before=before["grade"], grp_before=before["grp"]))
        elif row["grade"] != before["grade"]:
            regraded.append(dict(row, grade_before=before["grade"], grp_before=before["grp"]))
    return {"adopted": adopted, "dropped": dropped, "regraded": regraded}


def snapshot(conn, watchlists=None):
    """كل ما تحتاجه الصفحة وملفات JSON/CSV. يعيد None إن لم تكن هناك بيانات بعد."""
    all_weeks = weeks(conn)
    if not all_weeks:
        return None
    week = all_weeks[-1]
    previous_week = all_weeks[-2] if len(all_weeks) > 1 else None
    current = rows_for(conn, week)
    diff = changes(rows_for(conn, previous_week), current) if previous_week else None
    points = timeline(conn)
    now_point = points[-1] if points else {"reachable": 0, "pq": 0, "pct": 0.0}
    prev_point = points[-2] if len(points) > 1 else None
    since = first_pq_weeks(conn)
    watchlists = load_watchlists() if watchlists is None else watchlists
    sectors = []
    for key, sector in watchlists.items():
        members = [dict(r, pq_since=since.get(r["domain"]) if r["pq"] else None)
                   for r in current if r["sector"] == key]
        members.sort(key=lambda r: (not r["ok"], not r["pq"], r["domain"]))
        sectors.append({"key": key, "labels": sector.get("labels", {}), "rows": members,
                        "reachable": sum(1 for r in members if r["ok"]),
                        "pq": sum(1 for r in members if r["ok"] and r["pq"])})
    return {
        "week": week, "week_start": week_monday(week).isoformat(), "previous_week": previous_week,
        "scanned_at": max((r["scanned_at"] for r in current), default=""),
        "reachable": now_point["reachable"], "pq": now_point["pq"], "pct": now_point["pct"],
        "delta_pp": round(now_point["pct"] - prev_point["pct"], 1) if prev_point else None,
        "timeline": points, "changes": diff, "sectors": sectors, "rows": current,
    }


EXPORT_FIELDS = ["week", "domain", "rank", "sector", "ok", "grade", "grp", "tls", "pq", "scanned_at"]


def to_csv(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=EXPORT_FIELDS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k) for k in EXPORT_FIELDS})
    return out.getvalue()
