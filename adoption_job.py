# adoption_job.py
# مهمة صفحة /adoption. أسبوعياً: أكبر 10 آلاف نطاق وقوائم المراقبة. شهرياً: أكبر 100 ألف (لجدول المزوّدين).
# التشغيل: python adoption_job.py [weekly|monthly]   (مؤقتا systemd: quantum_adoption.timer و quantum_adoption_monthly.timer)
# الفحص كفحص الزائر: اتصالان بالمنفذ 443 لكل نطاق عام، بلا محتوى ولا أي محاولة اختراق.
import datetime as dt
import logging
import os
import sys
import json
import urllib.parse
import urllib.request

import adoption
import asn
import quantum_saas_app
import quantum_vuln_scanner
import sales_db

log = logging.getLogger("quantum_saas.adoption_job")


SENT_SCHEMA = ("CREATE TABLE IF NOT EXISTS indexnow_sent (url TEXT PRIMARY KEY, lastmod TEXT, "
               "submitted_at TEXT NOT NULL)")
CATCH_UP_LIMIT = 1000  # أقصى عدد نطاقات قوائم مراقبة جديدة يفحصها التشغيل اليومي


def _indexnow_target(app):
    """(host, key, base) or None when IndexNow is not configured; the sitemap stays the discovery path then."""
    key_path = os.path.join(app.root_path, "data", "indexnow.key")
    try:
        with open(key_path, encoding="utf-8") as key_file:
            key = key_file.read().strip()
    except OSError as exc:
        log.info("IndexNow key unavailable; sitemap remains the discovery path: %s", exc)
        return None
    if not key:
        log.info("IndexNow key is empty; sitemap remains the discovery path")
        return None
    base = (app.config.get("PUBLIC_URL") or "https://ather-quantum.com").rstrip("/")
    host = urllib.parse.urlsplit(base).hostname
    if not host:
        log.warning("IndexNow skipped: PUBLIC_URL has no hostname")
        return None
    return host, key, base


def _post_indexnow(host, key, base, url_list, post=None):
    """Send URLs in batches (IndexNow accepts at most 10,000 per request). Raises on any non-2xx answer."""
    for offset in range(0, len(url_list), 10_000):
        payload = json.dumps({"host": host, "key": key,
                              "keyLocation": f"{base}/{urllib.parse.quote(key, safe='')}.txt",
                              "urlList": url_list[offset:offset + 10_000]}).encode("utf-8")
        if post is not None:
            post(payload)
            continue
        request = urllib.request.Request(
            "https://api.indexnow.org/indexnow", data=payload,
            headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "QuantumAether-IndexNow/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"IndexNow returned HTTP {response.status}")


def _remember_sent(conn, entries):
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    conn.execute(SENT_SCHEMA)
    with conn:
        conn.executemany("INSERT OR REPLACE INTO indexnow_sent (url, lastmod, submitted_at) VALUES (?, ?, ?)",
                         [(url, lastmod, stamp) for url, lastmod in entries])


def _site_urls(base, conn):
    """Indexable /site/ pages of the latest week, as {url: scan day}."""
    out = {}
    for domain, day, rank, sector in adoption.site_domains(conn):
        if quantum_saas_app.search_indexing.is_indexable(domain, rank, sector):
            out.update({f"{base}/site/{domain}?lang={lang}": day for lang in ("en", "ar")})
    return out


def notify_indexnow(app, conn, week, post=None):
    """Notify IndexNow once per weekly refresh, for only indexable URLs actually refreshed."""
    if post is None and app.config.get("TESTING"):
        log.info("IndexNow skipped: test app (pass post= to exercise the send path)")
        return 0
    conn.execute("CREATE TABLE IF NOT EXISTS crawler_submissions (period TEXT PRIMARY KEY, submitted_at TEXT NOT NULL, url_count INTEGER NOT NULL)")
    period = f"weekly:{week}"
    if conn.execute("SELECT 1 FROM crawler_submissions WHERE period = ?", (period,)).fetchone():
        log.info("IndexNow already notified for %s", week)
        return 0
    target = _indexnow_target(app)
    if target is None:
        return 0
    host, key, base = target
    urls = {f"{base}/adoption?lang={lang}" for lang in ("en", "ar", "de")}
    urls.update(f"{base}/study/top-1000-post-quantum-tls?lang={lang}" for lang in ("en", "ar", "de"))
    urls.update((f"{base}/sitemap.xml", f"{base}/sitemap-pages.xml", f"{base}/feed.xml"))
    sites = _site_urls(base, conn)
    urls.update(sites)
    url_list = sorted(urls)
    if not url_list:
        return 0
    try:
        _post_indexnow(host, key, base, url_list, post)
    except Exception as exc:
        log.warning("IndexNow notification failed for %s (%d URLs): %s", week, len(url_list), exc)
        return 0
    with conn:
        conn.execute("INSERT OR IGNORE INTO crawler_submissions (period, submitted_at, url_count) VALUES (?, ?, ?)",
                     (period, dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), len(url_list)))
    _remember_sent(conn, sites.items())  # so the daily run does not send the same /site/ pages again
    log.info("IndexNow accepted %d refreshed URLs for %s", len(url_list), week)
    return len(url_list)


def page_urls(app):
    """Every sitemap-pages URL with its lastmod, from the same list the sitemap is built from."""
    base = (app.config.get("PUBLIC_URL") or "https://ather-quantum.com").rstrip("/")
    with app.test_request_context("/", base_url=base):
        pages = quantum_saas_app._sitemap_pages()
    out = {}
    for path, day, langs in pages:
        for lang in langs:
            out[base + "/" if (path == "/" and lang == "en") else f"{base}{path}?lang={lang}"] = day
    return out


def notify_new_urls(app, conn, post=None):
    """Daily: send pages that are new or whose lastmod changed, and /site/ pages never sent before.

    Weekly refreshes of /site/ pages stay with notify_indexnow; this run only fills the gap between Mondays
    (a new page, an edited page, a domain added to a watch list).
    """
    if post is None and app.config.get("TESTING"):
        log.info("IndexNow skipped: test app (pass post= to exercise the send path)")
        return 0
    target = _indexnow_target(app)
    if target is None:
        return 0
    host, key, base = target
    conn.execute(SENT_SCHEMA)
    sent = dict(conn.execute("SELECT url, lastmod FROM indexnow_sent"))
    due = {url: day for url, day in page_urls(app).items() if sent.get(url) != day}
    due.update({url: day for url, day in _site_urls(base, conn).items() if url not in sent})
    if not due:
        log.info("IndexNow daily: nothing new")
        return 0
    try:
        _post_indexnow(host, key, base, sorted(due), post)
    except Exception as exc:
        log.warning("IndexNow daily notification failed (%d URLs): %s", len(due), exc)
        return 0
    _remember_sent(conn, due.items())
    log.info("IndexNow daily: accepted %d new or changed URLs", len(due))
    return len(due)


def catch_up_watchlists(app, conn, scanner=None, day=None, asn_lookup="auto", limit=CATCH_UP_LIMIT):
    """Scan watch-list domains the current week does not have yet (or has under another sector).

    A domain added to data/adoption_watchlists.json then appears on /adoption and gets its /site/ page the
    next morning instead of the next Monday. Does nothing before this week's full scan has run.
    """
    week = adoption.week_of(day or dt.date.today())
    all_weeks = adoption.weeks(conn)
    if not all_weeks or all_weeks[-1] != week:
        log.info("watch-list catch-up skipped: week %s has no full scan yet", week)
        return 0
    have = dict(conn.execute("SELECT domain, sector FROM adoption_results WHERE week = ?", (week,)))
    targets = [t for t in adoption.load_targets(limit=adoption.WEEKLY_TOP)
               if t["sector"] and (t["domain"] not in have or have[t["domain"]] != t["sector"])][:limit]
    if not targets:
        log.info("watch-list catch-up: nothing new")
        return 0
    scanner = scanner or tracker_scanner(app.extensions["scanner"])
    lookup = asn_lookup_for(app) if asn_lookup == "auto" else asn_lookup
    outcome = adoption.run_week(conn, scanner, targets, day=day, workers=12, asn_lookup=lookup)
    log.info("watch-list catch-up %s: %d targets, %d answered", week, outcome["targets"], outcome["answered"])
    return outcome["targets"]


def asn_lookup_for(app):
    """قاعدة IP→ASN في مجلد البيانات؛ تُنزَّل أو تُحدَّث عند الحاجة. فشلها لا يوقف الفحص."""
    path = os.path.join(app.config["DATA_DIR"], "ip2asn-v4.tsv.gz")
    try:
        asn.ensure_database(path)
        return asn.AsnLookup(path).lookup
    except Exception as exc:
        log.warning("ASN database unavailable, providers will be skipped this run: %s", exc)
        return None


def run_indexnow(app):
    """Retry the latest weekly discovery notification without repeating TLS scans."""
    conn = sales_db.connect(os.path.join(app.config["DATA_DIR"], "quantum_saas.db"))
    try:
        weeks = adoption.weeks(conn)
        if not weeks:
            log.info("IndexNow retry skipped: no weekly dataset is available")
            return 0
        return notify_indexnow(app, conn, weeks[-1])
    finally:
        conn.close()


def run_daily(app):
    """Daily 07:00 UTC: retry the weekly notification, scan new watch-list domains, send new or changed URLs."""
    run_indexnow(app)
    conn = sales_db.connect(os.path.join(app.config["DATA_DIR"], "quantum_saas.db"))
    try:
        catch_up_watchlists(app, conn)
        return notify_new_urls(app, conn)
    finally:
        conn.close()


def tracker_scanner(scanner):
    """المتتبّع (10 آلاف أسبوعياً، 100 ألف شهرياً) يفحص عنواناً واحداً لكل نطاق كما في المنهجية المنشورة."""
    return quantum_vuln_scanner.scan if scanner is quantum_vuln_scanner.scan_full else scanner


def run(app, mode="weekly", day=None, workers=None, asn_lookup="auto"):
    conn = sales_db.connect(os.path.join(app.config["DATA_DIR"], "quantum_saas.db"))
    try:
        lookup = asn_lookup_for(app) if asn_lookup == "auto" else asn_lookup
        if mode == "monthly":
            targets = adoption.load_targets(limit=adoption.MONTHLY_TOP, watchlists={})
            outcome = adoption.run_month(conn, tracker_scanner(app.extensions["scanner"]), targets, day=day or dt.date.today(),
                                         workers=workers or 32, asn_lookup=lookup)
            log.info("adoption month %s: %d targets, %d answered", outcome["month"], outcome["targets"], outcome["answered"])
        else:
            seeded = adoption.seed_from_study(conn)
            if seeded:
                log.info("seeded %d rows from the published study", seeded)
            targets = adoption.load_targets(limit=adoption.WEEKLY_TOP)
            outcome = adoption.run_week(conn, tracker_scanner(app.extensions["scanner"]), targets, day=day or dt.date.today(),
                                        workers=workers or 24, asn_lookup=lookup)
            log.info("adoption week %s: %d targets, %d answered", outcome["week"], outcome["targets"], outcome["answered"])
        pruned = adoption.prune(conn)
        log.info("adoption history retention: mode=%s, week rows moved=%d, month rows moved=%d", pruned["mode"], pruned["weeks"], pruned["months"])
        if mode != "monthly":
            outcome["indexnow_urls"] = notify_indexnow(app, conn, outcome["week"])
        return outcome
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    app = quantum_saas_app.create_app()
    if len(sys.argv) > 1 and sys.argv[1] == "indexnow":
        run_daily(app)
    else:
        run(app, mode=sys.argv[1] if len(sys.argv) > 1 else "weekly")
