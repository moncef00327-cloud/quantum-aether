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
TRACKED_PREFIXES = ("/", "/monitoring", "/guides", "/study", "/research", "/scan/")


def init(conn):
    conn.executescript(SCHEMA)


def normalize_path(path):
    """يجمع صفحات النتائج في مسار واحد ولا يتتبع الصفحات الخاصة."""
    if path.startswith(("/report/", "/monitor/", "/admin", "/api/", "/static/", "/badge/")):
        return None
    if path.startswith("/scan/"):
        return "/scan/*"
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


def record(conn, day, path, referrer, visitor, is_bot):
    with conn:
        conn.execute("INSERT INTO pageviews (day, path, referrer, visitor, is_bot) VALUES (?, ?, ?, ?, ?)",
                     (day, path, referrer, visitor, int(is_bot)))


def summary(conn, since_day):
    q = lambda sql, *a: [dict(r) for r in conn.execute(sql, (since_day, *a)).fetchall()]
    humans = "is_bot = 0 AND day >= ?"
    return {
        "daily": q(f"SELECT day, COUNT(*) AS views, COUNT(DISTINCT visitor) AS visitors FROM pageviews"
                   f" WHERE {humans} GROUP BY day ORDER BY day DESC"),
        "referrers": q(f"SELECT referrer, COUNT(DISTINCT visitor || day) AS visitors FROM pageviews"
                       f" WHERE {humans} AND referrer != '(internal)' GROUP BY referrer ORDER BY visitors DESC LIMIT 15"),
        "pages": q(f"SELECT path, COUNT(*) AS views FROM pageviews WHERE {humans} GROUP BY path ORDER BY views DESC LIMIT 15"),
        "bots": conn.execute("SELECT COUNT(*) FROM pageviews WHERE is_bot = 1 AND day >= ?", (since_day,)).fetchone()[0],
        "funnel": {
            "visitors": conn.execute(f"SELECT COUNT(DISTINCT visitor || day) FROM pageviews WHERE {humans}", (since_day,)).fetchone()[0],
            "scan_pages": conn.execute(f"SELECT COUNT(DISTINCT visitor || day) FROM pageviews WHERE {humans} AND path = '/scan/*'", (since_day,)).fetchone()[0],
            "monitoring_page": conn.execute(f"SELECT COUNT(DISTINCT visitor || day) FROM pageviews WHERE {humans} AND path = '/monitoring'", (since_day,)).fetchone()[0],
        },
    }


def prune(conn, before_day):
    with conn:
        conn.execute("DELETE FROM pageviews WHERE day < ?", (before_day,))
