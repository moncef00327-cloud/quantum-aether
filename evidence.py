# evidence.py
# NIS2 / DORA evidence PDF for a monitoring (or trial) account, 2026-11-14.
# Built from what the account's daily monitoring recorded: monitored domains, check history, regressions/alerts and
# certificate expiry. Rendered with the invoice PDF writer (audit_checkout.render_pdf, WinAnsi / Latin only), so any
# character outside cp1252 is replaced instead of failing. Not legal advice; the PDF says so.
import datetime as dt

import audit_checkout
import monitor

HISTORY_ROWS = 200
CERT_WARN_DAYS = 30
_MAP = str.maketrans({"→": "->", "←": "<-", "≥": ">=", "≤": "<=", "✓": "OK", "✗": "x", "·": "-", "\u2009": " ", "\u202f": " "})

DISCLAIMER = [
    "Not legal advice. This document records technical measurements taken by Quantum Aether's automated monitoring. "
    "It does not by itself demonstrate compliance with NIS2 (Directive (EU) 2022/2555), DORA (Regulation (EU) 2022/2554) "
    "or any other regulation; whether and how it is used as evidence is decided by your organisation, its auditors "
    "and its legal advisers.",
    "Keine Rechtsberatung. Dieses Dokument gibt technische Messungen der automatischen Überwachung von Quantum Aether "
    "wieder. Es belegt für sich allein keine Einhaltung von NIS2, DORA oder anderen Vorschriften; ob und wie es als "
    "Nachweis dient, entscheiden Ihre Organisation, Ihre Prüfer und Ihre Rechtsberatung.",
]


def safe(value):
    text = "" if value is None else str(value).translate(_MAP)
    return text.encode("cp1252", "replace").decode("cp1252")


def _day(iso):
    return (iso or "")[:10] or "-"


def _expiry(checked_at, days_left):
    if days_left is None or not checked_at:
        return None
    try:
        base = dt.datetime.strptime(checked_at[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    return (base + dt.timedelta(days=int(days_left))).isoformat()


def _pq(value, error=None):
    if error:
        return "error"
    return {1: "yes", 0: "no"}.get(value, "undetermined")


def regressions(history):
    """Downgrades seen in the check history (oldest first): post-quantum lost, or grade got worse."""
    order = "ABCDEF"
    last, out = {}, []
    for c in sorted(history, key=lambda c: (c["checked_at"], c["id"])):
        if c["error"] or c["grade"] is None:
            continue
        prev = last.get(c["domain"])
        if prev:
            if prev["pq"] == 1 and c["pq"] == 0:
                out.append((c["checked_at"], c["domain"], f"post-quantum key exchange lost ({prev['grp']} -> {c['grp']})"))
            elif prev["grade"] in order and c["grade"] in order and order.index(c["grade"]) > order.index(prev["grade"]):
                out.append((c["checked_at"], c["domain"], f"grade dropped {prev['grade']} -> {c['grade']}"))
        last[c["domain"]] = c
    return out


def evidence_lines(account, domains, history, alerts, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    generated = now.strftime("%Y-%m-%d %H:%M UTC")
    checks = sorted(history, key=lambda c: (c["checked_at"], c["id"]))
    period = f"{_day(checks[0]['checked_at'])} to {_day(checks[-1]['checked_at'])}" if checks else "no checks recorded yet"
    status = account["status"]
    if status in ("TRIAL", "TRIAL_ENDED"):
        status = f"{status} (free trial, ends {_day(account.get('trial_ends_at'))})"
    versions = sorted({c["scanner_version"] for c in checks if c.get("scanner_version")})
    L = [("Post-quantum TLS monitoring: evidence report", "title"),
         ("Nachweis Post-Quanten-TLS-Überwachung - for NIS2 / DORA documentation", "bold"),
         (f"Generated / Erstellt: {generated}", "body"),
         (f"Account: {account['email']}   Plan: {account['plan']}   Status: {status}", "body"),
         (f"Monitoring since: {_day(account.get('created_at'))}   Period covered: {period}   Checks recorded: {len(checks)}", "body"),
         ("space", "space"), ("rule", "rule"),
         (f"1. Monitored domains ({len(domains)})", "bold")]
    if not domains:
        L.append(("No domains in this account.", "body"))
    for d in domains:
        exp = _expiry(d.get("checked_at"), d.get("days_left"))
        L.append((f"{d['domain']}   grade {d.get('grade') or '-'}   post-quantum: {_pq(d.get('pq'), d.get('error'))}"
                  f"   last check: {(d.get('checked_at') or 'not yet')[:16].replace('T', ' ')}"
                  f"   certificate expires: {exp or '-'}", "body"))
    L += [("space", "space"), ("2. Certificate expiry", "bold")]
    certs = sorted((d for d in domains if d.get("days_left") is not None), key=lambda d: d["days_left"])
    if not certs:
        L.append(("No certificate measured yet.", "body"))
    for d in certs:
        warn = "   ATTENTION: under 30 days" if d["days_left"] < CERT_WARN_DAYS else ""
        L.append((f"{d['domain']}: {d['days_left']} days left (expires {_expiry(d['checked_at'], d['days_left'])}){warn}", "body"))
    L += [("space", "space"), ("3. Regressions and alerts", "bold")]
    regs = regressions(history)
    if not regs and not alerts:
        L.append(("No regression or alert recorded in the period covered.", "body"))
    for when, domain, text in regs:
        L.append((f"{_day(when)}  {domain}: {text}", "body"))
    for a in sorted(alerts, key=lambda a: a["created_at"]):
        try:
            text = monitor.alert_text(a, "en")
        except (KeyError, IndexError, ValueError):
            text = a["kind"]
        L.append((f"{_day(a['created_at'])}  alert {a['kind']}: {text}", "body"))
    L += [("space", "space"), (f"4. Check history (most recent {min(len(checks), HISTORY_ROWS)} of {len(checks)})", "bold"),
          ("checked (UTC)     domain                         grade  PQ   group             TLS      cert", "mono")]
    for c in list(reversed(checks))[:HISTORY_ROWS]:
        when = c["checked_at"][:16].replace("T", " ")
        if c["error"]:
            L.append((f"{when}  {c['domain'][:30]:<30} error: {c['error'][:60]}", "mono"))
            continue
        L.append((f"{when}  {c['domain'][:30]:<30} {c['grade'] or '-':<6} {_pq(c['pq']):<4} {(c['grp'] or '-')[:17]:<17} "
                  f"{(c['tls'] or '-'):<8} {'-' if c['days_left'] is None else str(c['days_left']) + 'd'}", "mono"))
    if not checks:
        L.append(("No checks recorded yet. The first check runs right after a domain is added, then daily.", "body"))
    L += [("space", "space"), ("5. Method", "bold"),
          ("Each domain is checked daily: TLS 1.3 handshake offering the hybrid group X25519MLKEM768 (ML-KEM-768 + X25519), "
           "the negotiated group and the certificate are recorded. " + monitor_limitation(), "small")]
    if versions:
        L.append((f"Scanner version(s): {', '.join(versions)}", "small"))
    L += [("space", "space"), ("rule", "rule")] + [(t, "small") for t in DISCLAIMER]
    return [(safe(text), style) for text, style in L]


def monitor_limitation():
    import scan_experience
    return scan_experience.LIMITATION


def evidence_pdf(account, domains, history, alerts, now=None):
    return audit_checkout.render_pdf(evidence_lines(account, domains, history, alerts, now))
