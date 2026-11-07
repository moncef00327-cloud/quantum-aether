"""Read-only public demand dashboard built from existing radar evidence."""
import datetime as dt

from flask import render_template, request

import gravity


def register(bp, get_db):
    @bp.get('/gravity')
    def gravity_dashboard():
        since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat()
        conn = get_db()
        available = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='radar_seen'").fetchone()
        items = []
        if available:
            rows = conn.execute(
                "SELECT url, source, title, found_at FROM radar_seen WHERE julianday(found_at) >= julianday(?) ORDER BY julianday(found_at) DESC LIMIT 500",
                (since,)).fetchall()
            items = [dict(url=r[0], source=r[1], title=r[2], text='', created='', found_at=r[3]) for r in rows]
        ranked = gravity.opportunities(items)
        return render_template('gravity.html', opportunities=ranked,
                               evidence_count=sum(r['discussion_count'] for r in ranked),
                               collected_count=len(items),
                               source_count=len({e['source'] for r in ranked for e in r['evidence']}),
                               last_seen=max((r['found_at'] for r in items), default=None),
                               ar=request.args.get('lang') == 'ar')
