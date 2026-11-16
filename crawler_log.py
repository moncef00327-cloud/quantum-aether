# crawler_log.py — عدّاد زيارات زواحف البحث والذكاء الاصطناعي، لقياس أثر IndexNow و llms.txt.
#
# الخصوصية: لا نحفظ IP ولا User-Agent ولا الرابط الكامل. لكل يوم: عائلة الزاحف (google, bing...)،
# هل تحقّقنا أنه حقيقي (نطاقات IP المنشورة أو DNS عكسي ثم أمامي، عبر data_access.verify_bot)،
# قسم الصفحة (/site/, /guides/...)، رمز الاستجابة، والعدد.
# قاعدة منفصلة (crawler_hits.db) حتى لا تزاحم قاعدة الموقع، وأي خطأ هنا لا يمسّ الطلب.
import datetime as dt
import logging
import os
import sqlite3

import data_access

log = logging.getLogger("quantum_saas.crawler_log")

SCHEMA = """
CREATE TABLE IF NOT EXISTS crawler_hits (
    day      TEXT NOT NULL,
    family   TEXT NOT NULL,
    verified INTEGER NOT NULL,
    section  TEXT NOT NULL,
    status   INTEGER NOT NULL,
    hits     INTEGER NOT NULL,
    PRIMARY KEY (day, family, verified, section, status)
);
"""
FILES = {"/robots.txt", "/sitemap.xml", "/llms.txt", "/llms-full.txt", "/feed.xml"}


def db_path(data_dir):
    return os.path.join(data_dir, "crawler_hits.db")


def _connect(data_dir):
    conn = sqlite3.connect(db_path(data_dir), timeout=1)
    conn.executescript(SCHEMA)
    return conn


def section_of(path):
    """قسم عام للصفحة، لا الرابط نفسه (لا نطاقات زُوّار ولا رموز وصول في القاعدة)."""
    path = path or "/"
    if path in FILES or path.startswith("/sitemap"):
        return "sitemap*" if path.startswith("/sitemap") else path
    first = path.strip("/").split("/", 1)[0]
    if not first:
        return "/"
    if "/" in path.strip("/"):
        return f"/{first}/"
    return f"/{first}"


def record(data_dir, family, verified, path, status, day=None):
    day = day or dt.datetime.now(dt.timezone.utc).date().isoformat()
    try:
        conn = _connect(data_dir)
        try:
            with conn:
                conn.execute("INSERT INTO crawler_hits VALUES (?, ?, ?, ?, ?, 1) ON CONFLICT "
                             "(day, family, verified, section, status) DO UPDATE SET hits = hits + 1",
                             (day, family, 1 if verified else 0, section_of(path), int(status)))
        finally:
            conn.close()
    except Exception:  # العدّاد لا يُسقط طلباً أبداً
        log.warning("crawler hit not recorded", exc_info=True)


def register(app, data_dir_fn, verify=None):
    """after_request: يعدّ فقط الطلبات التي يعلن User-Agent فيها زاحفاً معروفاً (data_access.BOTS)."""
    from flask import request

    @app.after_request
    def _count_crawler(response):
        family = data_access.bot_family(request.headers.get("User-Agent"))
        if family and request.method in ("GET", "HEAD"):
            try:
                data_dir = data_dir_fn()
                ok = (verify or data_access.verify_bot)(request.remote_addr or "", family, data_dir)
                record(data_dir, family, ok, request.path, response.status_code)
            except Exception:
                log.warning("crawler counting failed", exc_info=True)
        return response
    return _count_crawler


def summary(data_dir, days=7, today=None):
    """آخر `days` يوماً مقابل الفترة التي قبلها، لكل عائلة (الموثّق فقط) ولأكثر الأقسام زيارة."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    start, prev = today - dt.timedelta(days=days - 1), today - dt.timedelta(days=2 * days - 1)
    if not os.path.exists(db_path(data_dir)):
        return {"days": days, "since": start.isoformat(), "families": [], "sections": [], "unverified": 0, "errors": 0}
    conn = _connect(data_dir)
    try:
        q = lambda sql, *a: conn.execute(sql, a).fetchall()
        cur = dict(q("SELECT family, SUM(hits) FROM crawler_hits WHERE verified = 1 AND day >= ? GROUP BY family",
                     start.isoformat()))
        old = dict(q("SELECT family, SUM(hits) FROM crawler_hits WHERE verified = 1 AND day >= ? AND day < ? "
                     "GROUP BY family", prev.isoformat(), start.isoformat()))
        families = sorted(({"family": f, "hits": cur.get(f, 0), "previous": old.get(f, 0)} for f in set(cur) | set(old)),
                          key=lambda r: -r["hits"])
        sections = [{"section": s, "hits": n} for s, n in q(
            "SELECT section, SUM(hits) FROM crawler_hits WHERE verified = 1 AND day >= ? GROUP BY section "
            "ORDER BY 2 DESC LIMIT 8", start.isoformat())]
        unverified = q("SELECT COALESCE(SUM(hits), 0) FROM crawler_hits WHERE verified = 0 AND day >= ?",
                       start.isoformat())[0][0]
        errors = q("SELECT COALESCE(SUM(hits), 0) FROM crawler_hits WHERE verified = 1 AND status >= 400 AND day >= ?",
                   start.isoformat())[0][0]
    finally:
        conn.close()
    return {"days": days, "since": start.isoformat(), "families": families, "sections": sections,
            "unverified": unverified, "errors": errors}


def as_text(s):
    lines = [f"Crawler visits, last {s['days']} days (since {s['since']}), verified crawlers only:"]
    if not s["families"]:
        lines.append("  no verified crawler visits recorded yet")
    for r in s["families"]:
        change = r["hits"] - r["previous"]
        lines.append(f"  {r['family']:<11} {r['hits']:>6}  (previous {s['days']} days: {r['previous']}, "
                     f"{'+' if change >= 0 else ''}{change})")
    if s["sections"]:
        lines.append("  most visited: " + ", ".join(f"{r['section']} {r['hits']}" for r in s["sections"]))
    lines.append(f"  answered 4xx/5xx to verified crawlers: {s['errors']}")
    lines.append(f"  claimed crawler user-agents that failed verification (or cannot be verified): {s['unverified']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    print(as_text(summary(os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas"),
                          days=int(sys.argv[1]) if len(sys.argv) > 1 else 7)))
