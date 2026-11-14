"""Privacy-preserving, aggregate public statistics for the transparency page."""
from datetime import date, datetime, timedelta, timezone

import analytics_db


MIN_PUBLIC_CELL = 5
WINDOW_DAYS = 30


def _public_count(value):
    """Hide small counts that could expose a visitor or a single customer."""
    value = int(value or 0)
    if 0 < value < MIN_PUBLIC_CELL:
        return {"value": None, "display": f"<{MIN_PUBLIC_CELL}", "suppressed": True}
    return {"value": value, "display": str(value), "suppressed": False}


def _day_bounds():
    today = date.today()
    start = today - timedelta(days=WINDOW_DAYS - 1)
    return start.isoformat(), (today + timedelta(days=1)).isoformat()


def build(conn):
    """Return aggregates only; never return domains, emails, IDs, or visitor hashes."""
    since, until = _day_bounds()
    window = (since, until)

    pv = conn.execute(
        "SELECT COUNT(*) AS views, "
        "COUNT(DISTINCT visitor || day) AS visitor_days "
        "FROM pageviews WHERE is_bot=0 AND is_test=0 AND day>=? AND day<?", window
    ).fetchone()
    bots = conn.execute(
        "SELECT COUNT(*) FROM pageviews WHERE is_bot=1 AND is_test=0 AND day>=? AND day<?", window
    ).fetchone()[0]
    tests = conn.execute(
        "SELECT COUNT(*) FROM pageviews WHERE is_test=1 AND day>=? AND day<?", window
    ).fetchone()[0]
    scans = conn.execute(
        "SELECT COUNT(*) FROM scans WHERE is_test=0 AND created_at>=? AND created_at<?",
        (since + "T00:00:00", until + "T00:00:00"),
    ).fetchone()[0]
    grades = conn.execute(
        "SELECT grade,COUNT(*) FROM scans WHERE is_test=0 AND created_at>=? AND created_at<? "
        "GROUP BY grade ORDER BY grade",
        (since + "T00:00:00", until + "T00:00:00"),
    ).fetchall()
    trials = conn.execute(
        "SELECT COUNT(*) FROM monitor_accounts WHERE trial_ends_at IS NOT NULL AND created_at>=? AND created_at<?",
        (since + "T00:00:00", until + "T00:00:00"),
    ).fetchone()[0]
    events = conn.execute(
        "SELECT name,COUNT(DISTINCT visitor || day) FROM events "
        "WHERE is_bot=0 AND is_test=0 AND day>=? AND day<? GROUP BY name", window
    ).fetchall()

    daily_rows = conn.execute(
        "SELECT day,COUNT(*) AS views,COUNT(DISTINCT visitor) AS visitors "
        "FROM pageviews WHERE is_bot=0 AND is_test=0 AND day>=? AND day<? GROUP BY day ORDER BY day",
        window,
    ).fetchall()
    daily = [{"day": row[0], "views": row[1], "visitor_days": row[2]}
             for row in daily_rows if row[2] >= MIN_PUBLIC_CELL]

    source_rows = analytics_db.grouped_referrers(
        conn, "is_bot=0 AND is_test=0 AND day>=? AND day<? AND referrer!='(internal)'", window, limit=100
    )
    sources = []
    small_sources = 0
    for row in source_rows:
        if row["visitors"] >= MIN_PUBLIC_CELL:
            sources.append({"source": row["referrer"], "visitor_days": row["visitors"]})
        else:
            small_sources += row["visitors"]
    if small_sources >= MIN_PUBLIC_CELL:
        sources.append({"source": "Other", "visitor_days": small_sources})

    event_counts = {row[0]: _public_count(row[1]) for row in events}
    return {
        "period": {"start": since, "end": (date.fromisoformat(until) - timedelta(days=1)).isoformat(),
                   "days": WINDOW_DAYS},
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "privacy": {
            "visitors": "Daily pseudonymous visitor estimates from browser page views; not people across the full period.",
            "filters": "Known bots and test records are excluded from public activity; admin visits are excluded at collection.",
            "small_counts": f"Nonzero counts below {MIN_PUBLIC_CELL} are suppressed.",
            "individual_records": "Domains, email addresses, visitor identifiers and individual scan records are never included.",
        },
        "traffic": {
            "page_views": int(pv["views"]),
            "visitor_days": int(pv["visitor_days"]),
            "bot_page_views_excluded": int(bots),
            "test_page_views_excluded": int(tests),
            "daily": daily,
            "sources": sources,
        },
        "scans": {
            "completed": int(scans),
            "grades": [{"grade": row[0], **_public_count(row[1])} for row in grades],
        },
        "funnel": {
            "events": event_counts,
            "trial_accounts_created": _public_count(trials),
        },
    }
