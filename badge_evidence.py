"""Bounded, read-only badge evidence with explicit expiration; never scans."""
import datetime as dt

import adoption
import sales_db
import scan_experience

MAX_AGE_DAYS = 30


def moment(value):
    try:
        value = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return (value.replace(tzinfo=dt.timezone.utc) if value.tzinfo is None else value).astimezone(dt.timezone.utc)
    except (ValueError, TypeError):
        return None


def for_domain(conn, domain, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    candidates = []
    scan = sales_db.latest_scan_for_domain(conn, domain, '0000')
    if scan:
        result = scan['result']
        candidates.append(dict(checked_at=result['scanned_at'], grade=result['grade'], source='scan',
                               observation_status=scan_experience.status(result),
                               tls=result['key_exchange'].get('version') or result['certificate'].get('negotiated_version'),
                               group=result['key_exchange'].get('group')))
    row = adoption.latest_for(conn, domain)
    if row:
        candidates.append(dict(checked_at=row['scanned_at'], grade=row['grade'], source='tracker',
                               observation_status='undetermined' if row['unsure'] else ('observed_pq' if row['pq'] else 'observed_classical'),
                               tls=row['tls'], group=row['grp']))
    candidates = [c for c in candidates if moment(c['checked_at']) is not None and moment(c['checked_at']) <= now]
    base = dict(domain=domain, state='not_scanned', grade=None, checked_at=None, expires_at=None,
                observation_status='undetermined', limitations=scan_experience.LIMITATION, cache_seconds=300)
    if not candidates:
        return base
    evidence = max(candidates, key=lambda c: moment(c['checked_at']))
    expiry = moment(evidence['checked_at']) + dt.timedelta(days=MAX_AGE_DAYS)
    state = 'stale' if expiry <= now else ('undetermined' if evidence['observation_status'] == 'undetermined' else 'fresh')
    base.update(evidence, state=state, expires_at=expiry.isoformat(),
                cache_seconds=min(300, max(0, int((expiry - now).total_seconds()))) if state != 'stale' else 300)
    if state != 'fresh':
        base['grade'] = None
    return base
