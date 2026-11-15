# analytics_db.py
# إحصاءات زيارات بسيطة تحترم الخصوصية: لا عناوين IP ولا ملفات تعريف (كوكيز).
# الزائر الفريد يُحسب ببصمة يومية (IP + المتصفح + ملح + التاريخ) لا يمكن ربطها بين الأيام.
import re

SCHEMA = """
CREATE TABLE IF NOT EXISTS pageviews (
    day       TEXT NOT NULL,
    path      TEXT NOT NULL,
    referrer  TEXT NOT NULL,
    visitor   TEXT NOT NULL,
    is_bot    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS pageviews_day ON pageviews (day);
"""

BOT_RE = re.compile(r"bot|crawl|spider|slurp|curl|wget|python|httpclient|go-http|java/|headless|scan|censys|"
                    r"preview|monitor|verification|facebookexternalhit|embedly|whatsapp|telegram", re.I)
TRACKED_PREFIXES = ("/", "/monitoring", "/guides", "/study", "/research", "/scan/", "/deadlines", "/site/", "/adoption", "/compare",
                    "/pricing", "/business", "/agency", "/sample-report", "/audit")


def init(conn):
    conn.executescript(SCHEMA)


def normalize_path(path):
    """يجمع صفحات النتائج في مسار واحد ولا يتتبع الصفحات الخاصة."""
    if path.startswith(("/report/", "/monitor/", "/admin", "/api/", "/static/", "/badge/")):
        return None
    if path.startswith("/scan/"):
        return "/scan/*"
    if path == "/scan":  # the result of a failed scan form (POST /scan) is rendered here
        return "/scan"
    if path == "/" or path.startswith(TRACKED_PREFIXES[1:]):
        return path
    return None


def referrer_host(referrer, own_host):
    if not referrer:
        return "(direct)"
    m = re.match(r"^https?://([^/:?#]+)", referrer)
    if not m:
        return "(other)"
    host = m.group(1).lower().removeprefix("www.")
    if host == own_host.removeprefix("www."):
        return "(internal)"
    # تجميع روابط الشبكات الاجتماعية المختصرة
    return {"t.co": "x.com", "old.reddit.com": "reddit.com", "out.reddit.com": "reddit.com",
            "lnkd.in": "linkedin.com", "l.facebook.com": "facebook.com", "m.facebook.com": "facebook.com"}.get(host, host)


def utm_source(value):
    """قيمة utm_source منظَّفة (حروف وأرقام و . _ - فقط، 40 حرفاً)، تُسجَّل كمصدر «utm:القيمة»."""
    if not value:
        return None
    clean = re.sub(r"[^a-z0-9._-]", "", value.strip().lower())[:40]
    return f"utm:{clean}" if clean else None


# مصادر تُعرض كسطر واحد في لوحة الإدارة (بيانات الجدول الخام لا تتغير).
# الزائر نفسه لا يُحسب مرتين لو جاء من أكثر من صيغة للمصدر نفسه في اليوم نفسه.
SOURCE_GROUPS = (
    ("LinkedIn", re.compile(r"^(utm:(linked|lnkd|li$)|linkedin\.com$|lnkd\.in$)")),
    ("Facebook", re.compile(r"^(utm:(facebook|fb$|meta$)|facebook\.com$|fb\.com$)")),
    ("X", re.compile(r"^(utm:(twitter|x$)|x\.com$|twitter\.com$)")),
    ("Reddit", re.compile(r"^(utm:reddit|reddit\.com$)")),
)


def source_group(source):
    for name, rx in SOURCE_GROUPS:
        if rx.match(source):
            return name
    return source


def grouped_referrers(conn, where, args, limit=15):
    seen = {}
    for src, key in conn.execute(f"SELECT referrer, visitor || day FROM pageviews WHERE {where} AND referrer != '(internal)'", args):
        seen.setdefault(source_group(src), set()).add(key)
    rows = sorted(({"referrer": k, "visitors": len(v)} for k, v in seen.items()), key=lambda r: (-r["visitors"], r["referrer"]))
    return rows[:limit]


def record(conn, day, path, referrer, visitor, is_bot):
    with conn:
        conn.execute("INSERT INTO pageviews (day, path, referrer, visitor, is_bot) VALUES (?, ?, ?, ?, ?)",
                     (day, path, referrer, visitor, int(is_bot)))


def summary(conn, since_day):
    q = lambda sql, *a: [dict(r) for r in conn.execute(sql, (since_day, *a)).fetchall()]
    humans = "is_bot = 0 AND is_test = 0 AND day >= ?"
    return {
        "daily": q(f"SELECT day, COUNT(*) AS views, COUNT(DISTINCT visitor) AS visitors FROM pageviews"
                   f" WHERE {humans} GROUP BY day ORDER BY day DESC"),
        "referrers": grouped_referrers(conn, humans, (since_day,)),
        "pages": q(f"SELECT path, COUNT(*) AS views FROM pageviews WHERE {humans} GROUP BY path ORDER BY views DESC LIMIT 15"),
        "bots": conn.execute("SELECT COUNT(*) FROM pageviews WHERE is_bot = 1 AND is_test = 0 AND day >= ?", (since_day,)).fetchone()[0],
        "funnel": {
            "visitors": conn.execute(f"SELECT COUNT(DISTINCT visitor || day) FROM pageviews WHERE {humans}", (since_day,)).fetchone()[0],
            "scan_pages": conn.execute(f"SELECT COUNT(DISTINCT visitor || day) FROM pageviews WHERE {humans} AND path = '/scan/*'", (since_day,)).fetchone()[0],
            "monitoring_page": conn.execute(f"SELECT COUNT(DISTINCT visitor || day) FROM pageviews WHERE {humans} AND path = '/monitoring'", (since_day,)).fetchone()[0],
        },
    }


def prune(conn, before_day):
    with conn:
        conn.execute("DELETE FROM pageviews WHERE day < ?", (before_day,))


# ---------------------------------------------------------------- أحداث داخل الصفحة (بلا كوكيز)
# نعرف بها هل يحاول الزائر الفحص أصلاً: لمس الخانة، الكتابة، مثال، إرسال، ظهور النتيجة...
EVENT_NAMES = ("focus", "type", "example", "submit", "result", "lang", "monitoring_cta", "buy_click",
               "share", "badge_copy", "sample_report", "error", "scan_cta", "alert_signup", "agency_cta",
               # command UI (2026-11-09): tab switches and outbound links
               "tab_scanner", "tab_tracker", "tab_monitor", "tab_guides", "tab_business", "tab_llm",
               "business_cta", "agents_cta", "explore",
               "disc_start", "disc_email", "cfg_copy",
               "trial_start", "page_view", "scan_started", "scan_completed", "offer_impression",
               "trial_cta_clicked", "signup_completed", "monitoring_activated", "checkout_started",
               "subscription_completed",  # مسار التحويل وقياس تجربة العرض
               "trial_created", "subscription_start", "subscription_active",
               "checkout_start", "purchase_complete",  # أحداث الخادم بعد إنشاء الطلب أو تأكيد الدفع
               "agency_start", "agency_paid",  # تحويلات باقة تقارير العملاء لمقدمي الخدمات
               "history_csv", "evidence_pdf", "fix_copy",  # تنزيل سجل الفحوص من لوحة المراقبة
               "seed_add",  # إضافة نطاق أساسي لجرد الأصول
               # 2026-11-14: names already sent by pages/server but dropped until now, and the trial-first CTA
               "trial_cta", "audit_cta", "exec_brief", "audit_checkout_start",
               # 2026-11-14: trial funnel detail: passed browser checks / blocked in the browser / rejected by the server
               "trial_submit", "trial_invalid", "trial_failed",
               # 2026-11-14: ProofLab waitlist page view and accepted signup (server-side)
               "prooflab_view", "prooflab_submit")
EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    day      TEXT NOT NULL,
    name     TEXT NOT NULL,
    page     TEXT NOT NULL,
    lang     TEXT NOT NULL,
    visitor  TEXT NOT NULL,
    is_bot   INTEGER NOT NULL,
    is_test  INTEGER NOT NULL DEFAULT 0,
    detail   TEXT NOT NULL DEFAULT '',
    variant  TEXT
);
CREATE INDEX IF NOT EXISTS events_day ON events (day, name);
"""


def init_events(conn):
    conn.executescript(EVENTS_SCHEMA)
    # 2026-11-14: "detail" carries a machine code (e.g. "dns_failure:example.com" for a scan error), never PII.
    if "detail" not in {row[1] for row in conn.execute("PRAGMA table_info(events)")}:
        with conn:
            conn.execute("ALTER TABLE events ADD COLUMN detail TEXT NOT NULL DEFAULT ''")
    if "variant" not in {row[1] for row in conn.execute("PRAGMA table_info(events)")}:
        with conn:
            conn.execute("ALTER TABLE events ADD COLUMN variant TEXT")


DETAIL_RE = re.compile(r"[^a-z0-9_.:\-]")


def clean_detail(value):
    """Lower-case code/domain text only (letters, digits, _ . : -), at most 120 characters."""
    return DETAIL_RE.sub("", str(value or "").lower())[:120]


def record_event(conn, day, name, page, lang, visitor, is_bot, is_test=False, detail="", variant=None):
    """حدث واحد لكل (زائر، يوم، اسم، صفحة، تفصيل): التكرار لا يضخّم الأرقام."""
    if name not in EVENT_NAMES:
        return False
    detail = clean_detail(detail)
    if variant not in ("control", "treatment"):
        variant = None
    with conn:
        exists = conn.execute("SELECT 1 FROM events WHERE day = ? AND name = ? AND page = ? AND visitor = ? "
                              "AND (detail = ? OR ? = '') LIMIT 1", (day, name, page, visitor, detail, detail)).fetchone()
        if not exists:
            conn.execute("INSERT INTO events (day, name, page, lang, visitor, is_bot, is_test, detail, variant) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (day, name, page, lang, visitor, int(is_bot), int(is_test), detail, variant))
    return True


def error_details(conn, since_day, limit=50):
    """Most frequent scan error codes and domains (humans only), for the admin page."""
    return conn.execute("SELECT detail, COUNT(*) AS n, MAX(day) AS last_day FROM events WHERE name = 'error' AND detail != '' "
                        "AND is_bot = 0 AND is_test = 0 AND day >= ? GROUP BY detail ORDER BY n DESC, last_day DESC LIMIT ?",
                        (since_day, limit)).fetchall()


def event_funnel(conn, since_day, until_day="9999-12-31"):
    """عدد الزوار (زائر-يوم) الفريدين لكل حدث، بلا روبوتات ولا اختبارات."""
    rows = conn.execute("SELECT name, COUNT(DISTINCT visitor || day) FROM events WHERE is_bot = 0 AND is_test = 0 "
                        "AND day >= ? AND day < ? GROUP BY name", (since_day, until_day)).fetchall()
    counts = {name: 0 for name in EVENT_NAMES}
    counts.update({name: n for name, n in rows})
    return counts


def conversion_funnel_by_variant(conn, since_day, until_day="9999-12-31"):
    names = ("page_view", "offer_impression", "trial_cta_clicked", "signup_completed",
             "monitoring_activated", "checkout_started", "subscription_completed", "scan_started", "scan_completed")
    out = {arm: {name: 0 for name in names} for arm in ("control", "treatment")}
    rows = conn.execute("SELECT variant, name, COUNT(DISTINCT visitor || day) FROM events "
                        "WHERE is_bot = 0 AND is_test = 0 AND variant IN ('control','treatment') "
                        "AND day >= ? AND day < ? GROUP BY variant, name", (since_day, until_day)).fetchall()
    for arm, name, count in rows:
        if arm in out and name in out[arm]:
            out[arm][name] = count
    return out
