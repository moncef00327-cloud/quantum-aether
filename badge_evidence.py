"""Bounded, read-only badge evidence with explicit expiration; never scans."""
import datetime as dt
import hashlib
import json

import adoption
import sales_db
import scan_experience

MAX_AGE_DAYS = 30


def fix_snippet_for(grade, tls, group):
    if grade == 'A' or (group and 'MLKEM' in str(group).upper()):
        return 'posture OK (X25519MLKEM768 active); monitor daily to prevent silent TLS downgrades'
    if tls and tls != 'TLSv1.3':
        return 'nginx: ssl_protocols TLSv1.2 TLSv1.3; ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;'
    return 'nginx (OpenSSL 3.5+): ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1; # or enable Cloudflare proxy'


def attestation_hash(domain, state, grade, tls, group, checked_at):
    if not checked_at or state == 'not_scanned':
        return None
    canonical = f"quantum-aether-v1|{domain}|{state}|{grade or ''}|{tls or ''}|{group or ''}|{checked_at}"
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


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
    alt = domain[4:] if domain.startswith('www.') else f'www.{domain}'
    row = adoption.latest_for(conn, domain) or adoption.latest_for(conn, alt)
    if row:
        candidates.append(dict(checked_at=row['scanned_at'], grade=row['grade'], source='tracker',
                               observation_status='undetermined' if row['unsure'] else ('observed_pq' if row['pq'] else 'observed_classical'),
                               tls=row['tls'], group=row['grp']))
    try:
        mon = conn.execute(
            "SELECT d.checked_at, d.grade, d.pq, d.result_json FROM monitor_domains d "
            "JOIN monitor_accounts a ON a.id = d.account_id "
            "WHERE d.domain = ? AND a.status = 'ACTIVE' AND d.checked_at IS NOT NULL AND d.error IS NULL "
            "ORDER BY d.checked_at DESC LIMIT 1", (domain,)
        ).fetchone()
        if mon and mon['grade']:
            res = json.loads(mon['result_json']) if mon['result_json'] else {}
            kx, cert = res.get('key_exchange') or {}, res.get('certificate') or {}
            candidates.append(dict(
                checked_at=mon['checked_at'], grade=mon['grade'], source='monitor',
                observation_status='undetermined' if mon['pq'] is None else ('observed_pq' if mon['pq'] else 'observed_classical'),
                tls=kx.get('version') or cert.get('negotiated_version'),
                group=kx.get('group')
            ))
    except Exception:
        pass
    try:
        fa = conn.execute(
            "SELECT last_checked, last_grade, last_pq FROM free_alerts "
            "WHERE domain = ? AND status = 'ACTIVE' AND last_checked IS NOT NULL AND last_error IS NULL "
            "ORDER BY last_checked DESC LIMIT 1", (domain,)
        ).fetchone()
        if fa and fa['last_grade']:
            candidates.append(dict(
                checked_at=fa['last_checked'], grade=fa['last_grade'], source='free_alert',
                observation_status='undetermined' if fa['last_pq'] is None else ('observed_pq' if fa['last_pq'] else 'observed_classical'),
                tls=None, group=None
            ))
    except Exception:
        pass
    candidates = [c for c in candidates if moment(c['checked_at']) is not None and moment(c['checked_at']) <= now]
    base = dict(domain=domain, state='not_scanned', grade=None, checked_at=None, expires_at=None,
                observation_status='undetermined', limitations=scan_experience.LIMITATION, cache_seconds=300,
                attestation_sha256=None, fix_snippet=None)
    if not candidates:
        return base
    evidence = max(candidates, key=lambda c: moment(c['checked_at']))
    expiry = moment(evidence['checked_at']) + dt.timedelta(days=MAX_AGE_DAYS)
    state = 'stale' if expiry <= now else ('undetermined' if evidence['observation_status'] == 'undetermined' else 'fresh')
    base.update(evidence, state=state, expires_at=expiry.isoformat(),
                cache_seconds=min(300, max(0, int((expiry - now).total_seconds()))) if state != 'stale' else 300)
    if state != 'fresh':
        base['grade'] = None
    base['attestation_sha256'] = attestation_hash(domain, state, base['grade'], base.get('tls'), base.get('group'), base['checked_at'])
    base['fix_snippet'] = fix_snippet_for(base['grade'], base.get('tls'), base.get('group'))
    return base
