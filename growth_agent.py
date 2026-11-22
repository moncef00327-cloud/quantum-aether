#!/usr/bin/env python3
"""Growth agent: runs unattended (systemd timers), owner sees a daily digest instead of approving each step.

  python3 growth_agent.py outreach [--dry-run]   send up to DAILY_CAP factual notes to new non-EU orgs
  python3 growth_agent.py digest                 email the owner yesterday's numbers
  python3 growth_agent.py status

Guard rails (owner decision 2026-11-22, «نفذ الكل»):
- Only addresses the organisation PUBLISHES in /.well-known/security.txt (Contact: mailto:). Never guessed
  addresses: guessed security@ bounced 3/7 on 2026-11-18 and pushed the bounce rate to 11.8%.
- No EU/EEA/UK/CH recipients (UWG §7 / ePrivacy), no government, universities or cyber agencies.
- Never a domain contacted before (contacted_orgs, old batch logs, suppress list), one mail per org, ever.
- Max DAILY_CAP mails a day, sent from QS_OUTREACH_FROM (separate subdomain), reply-to reply@mail.
- Auto-pause (writes PAUSE_FILE and tells the owner) on any complaint or when bounces in the last 30 sends > 5%.
- A reply containing stop/unsubscribe/إيقاف suppresses the sender's domain.
- Kill switch: touch PAUSE_FILE (deploy/growth.sh stop).
"""
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import sys
import time

import requests

DATA_DIR = os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas")
DB_PATH = os.path.join(DATA_DIR, "quantum_saas.db")
PAUSE_FILE = os.path.join(DATA_DIR, "growth.paused")
SITE = "https://ather-quantum.com"
DAILY_CAP = int(os.environ.get("QS_GROWTH_DAILY_CAP", "10"))
PER_RUN = 2  # runs hourly 06-17 UTC, so the daily cap is spread over the working day
BOUNCE_LIMIT = 0.05
UA = "Mozilla/5.0 (compatible; QuantumAether-Growth/1.0; +https://ather-quantum.com/scanning)"
HERE = os.path.dirname(os.path.abspath(__file__))
# Old logs that hold already-contacted domains (any domain-looking token in them is excluded).
HISTORY_GLOBS = [os.path.join(DATA_DIR, "growth_history.txt"), "data/outreach_*sent*.json", "data/bounced_suppress.txt", "send_arab_batch*.py",
                 "/root/outreach-*.csv", "/root/quantum-aether/data/outreach_*sent*.json",
                 "/root/quantum-aether/data/bounced_suppress.txt", "/root/quantum-aether/send_arab_batch*.py"]

TARGET_SECTORS = {"banks-mena", "banks-americas-apac", "finance-worldwide", "payments-fintech", "enterprise-saas-b2b",
                  "crypto-exchanges", "telecom", "global-insurance-healthcare", "critical-infrastructure"}
EU_TLDS = {"at", "be", "bg", "hr", "cy", "cz", "dk", "ee", "fi", "fr", "de", "gr", "hu", "ie", "it", "lv", "lt", "lu",
           "mt", "nl", "pl", "pt", "ro", "sk", "si", "es", "se", "eu", "is", "li", "no", "ch", "uk", "gb"}
ARABIC_TLDS = {"sa", "ae", "qa", "kw", "bh", "om", "eg", "jo", "lb", "ma", "dz", "tn", "iq", "ly", "ps", "sd", "ye", "sy"}
# Central banks and other state bodies count as government (owner: exclude government).
CENTRAL_BANKS = {"cbi.iq", "boj.or.jp", "bok.or.kr", "banxico.org.mx", "centralbank.ae", "cbk.gov.kw", "cbe.org.eg",
                 "sama.gov.sa", "cbb.gov.bh", "cbo.gov.om", "qcb.gov.qa", "bkam.ma", "bct.gov.tn", "cbj.gov.jo",
                 "bdl.gov.lb", "bank-of-algeria.dz", "federalreserve.gov", "ecb.europa.eu", "bis.org", "imf.org"}
GOV = re.compile(r"(^|\.)(gov|gob|gouv|govt|mil|edu|ac)(\.|$)")
DOMAIN_RE = re.compile(r"\b([a-z0-9-]+(?:\.[a-z0-9-]+)+\.[a-z]{2,}|[a-z0-9-]+\.[a-z]{2,})\b")
STOP_RE = re.compile(r"\b(stop|unsubscribe|remove me|opt[- ]?out)\b|إيقاف|الغاء|إلغاء", re.I)


def connect(path=DB_PATH):
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS growth_outreach (
        domain TEXT PRIMARY KEY, email TEXT NOT NULL, lang TEXT, reason TEXT, resend_id TEXT,
        sent_at TEXT NOT NULL, last_event TEXT, checked_at TEXT)""")
    conn.execute("CREATE TABLE IF NOT EXISTS growth_suppress (domain TEXT PRIMARY KEY, added_at TEXT, reason TEXT)")
    return conn


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def base_domain(host):
    host = host.lower().strip(".")
    return host[4:] if host.startswith("www.") else host


def tld(host):
    return host.rsplit(".", 1)[-1]


def is_eu(host):
    parts = host.split(".")
    return tld(host) in EU_TLDS or (len(parts) > 2 and parts[-2] in ("co", "com", "org") and parts[-1] in EU_TLDS)


def history_domains(paths=None):
    seen = set()
    for pattern in paths or HISTORY_GLOBS:
        for path in glob.glob(pattern if os.path.isabs(pattern) else os.path.join(HERE, pattern)):
            try:
                text = open(path, encoding="utf-8", errors="ignore").read().lower()
            except OSError:
                continue
            for d in DOMAIN_RE.findall(text):
                seen.add(base_domain(d.split("@")[-1]))
    return seen


def excluded(conn, history):
    out = set(history)
    out |= {base_domain(r[0]) for r in conn.execute("SELECT domain FROM contacted_orgs")}
    out |= {r[0] for r in conn.execute("SELECT domain FROM growth_outreach")}
    out |= {r[0] for r in conn.execute("SELECT domain FROM growth_suppress")}
    try:
        out |= {base_domain(r[0]) for r in conn.execute("SELECT domain FROM adoption_optout")}
    except sqlite3.Error:
        pass
    return out


def candidates(conn, skip):
    """Latest tracker week, target sectors, not post-quantum, not EU/gov. Regressions first, then orgs whose
    /site/ page people looked at, then the rest by Tranco rank."""
    week = conn.execute("SELECT MAX(week) FROM adoption_results WHERE sector IS NOT NULL").fetchone()[0]
    if not week:
        return []
    prev = conn.execute("SELECT MAX(week) FROM adoption_results WHERE week < ? AND sector IS NOT NULL", (week,)).fetchone()[0]
    rows = conn.execute("SELECT domain, sector, grade, grp, tls, pq, rank FROM adoption_results "
                        "WHERE week = ? AND ok = 1 AND COALESCE(unsure, 0) = 0", (week,)).fetchall()
    was_pq = {base_domain(r[0]) for r in conn.execute(
        "SELECT domain FROM adoption_results WHERE week = ? AND pq = 1", (prev,))} if prev else set()
    views = {}
    for path, n in conn.execute("SELECT path, COUNT(DISTINCT visitor) FROM pageviews WHERE is_bot = 0 AND is_test = 0 "
                                "AND path LIKE '/site/%' GROUP BY path"):
        views[base_domain(path[6:])] = n
    out = []
    for r in rows:
        d = base_domain(r["domain"])
        if (r["sector"] not in TARGET_SECTORS or r["pq"] or d in skip or is_eu(d) or GOV.search(d)
                or d in CENTRAL_BANKS):
            continue
        reason = "dropped" if d in was_pq else ("viewed" if views.get(d) else "classical")
        prio = {"dropped": 0, "viewed": 1, "classical": 2}[reason]
        out.append({"domain": d, "host": r["domain"], "sector": r["sector"], "grade": r["grade"], "group": r["grp"],
                    "tls": r["tls"], "week": week, "reason": reason, "views": views.get(d, 0),
                    "sort": (prio, -views.get(d, 0), r["rank"] or 10 ** 9)})
    return sorted(out, key=lambda c: c["sort"])


GENERIC_TLDS = {"com", "net", "org", "io", "co", "ai", "app", "dev", "tech", "cloud", "info", "biz", "xyz", "me", "global"}
KNOWN_REGION_SECTORS = {"banks-mena", "banks-americas-apac"}  # rows there are Arab, Americas or APAC institutions


def auto_send_ok(c):
    """Auto-send only where the org is known to be outside the EU: a non-EU country TLD, or a regional sector.
    A .com in a global sector can be European (commerzbank.com, spendesk.com): owner decides those (digest)."""
    return tld(c["domain"]) not in GENERIC_TLDS or c["sector"] in KNOWN_REGION_SECTORS


def parse_security_txt(text):
    """First Contact: mailto: address (RFC 9116), or None."""
    for line in text.splitlines():
        m = re.match(r"\s*contact\s*:\s*mailto:\s*([^\s?#]+@[^\s?#]+)", line, re.I)
        if m:
            return m.group(1).strip().rstrip(".").lower()
    return None


def published_contact(domain, http=None):
    http = http or requests
    for url in (f"https://{domain}/.well-known/security.txt", f"https://www.{domain}/.well-known/security.txt",
                f"https://{domain}/security.txt"):
        try:
            r = http.get(url, timeout=10, headers={"User-Agent": UA}, allow_redirects=True)
        except requests.RequestException:
            continue
        if r.status_code == 200 and "html" not in r.headers.get("content-type", "").lower():
            email = parse_security_txt(r.text[:20000])
            if email:
                return email, url
    return None, None


def message(c, lang):
    site = f"{SITE}/site/{c['domain']}?lang={lang}&utm_source=email&utm_medium=outreach&utm_campaign=growth_agent&utm_content={c['domain']}"
    group = c["group"] or "classical ECDHE"
    if lang == "ar":
        subject = f"{c['domain']}: تبادل المفاتيح في TLS ما زال تقليديًا (قياس {c['week']})"
        lines = [f"مرحبًا فريق أمن {c['domain']}،", "",
                 f"في قياسنا الأسبوعي العام ({c['week']}) تفاوض {c['host']} على {c['tls'] or 'TLS'} مع تبادل مفاتيح {group}، "
                 "من دون المجموعة الهجينة المقاومة للحوسبة الكمومية X25519MLKEM768 التي تعرضها Chrome وFirefox وSafari افتراضيًا.",
                 "هذا يعني أن الحركة المسجلة اليوم يمكن فك تشفيرها لاحقًا («احفظ الآن، فُكّ لاحقًا»).", "",
                 f"النتيجة الكاملة وطريقة الإصلاح (مجانًا، دون تسجيل): {site}", "",
                 "إن لم يكن هذا العنوان المناسب، ردّوا بكلمة «إيقاف» ولن نراسلكم مجددًا.", "",
                 "Quantum Aether — قياسات عامة لـ TLS المقاوم للكم", SITE]
    else:
        subject = f"{c['domain']}: TLS key exchange is still classical (measured {c['week']})"
        lines = [f"Hello {c['domain']} security team,", "",
                 f"In our weekly public measurement ({c['week']}), {c['host']} negotiated {c['tls'] or 'TLS'} with {group} key "
                 "exchange, without the hybrid post-quantum group X25519MLKEM768 that Chrome, Firefox and Safari offer by default.",
                 "Traffic recorded today can therefore be decrypted later (\"harvest now, decrypt later\").", "",
                 f"Full result and how to fix it (free, no sign-up): {site}", "",
                 "If this is not the right address, reply \"stop\" and we will not write again.", "",
                 "Quantum Aether — public post-quantum TLS measurements", SITE]
    if c["reason"] == "dropped":
        lines.insert(3, "Last week the same host DID offer X25519MLKEM768, so this looks like a regression."
                     if lang != "ar" else "في الأسبوع السابق كان المضيف نفسه يعرض X25519MLKEM768، فيبدو هذا تراجعًا.")
    return subject, "\n".join(lines)


def resend_send(to, subject, text, http=None):
    http = http or requests
    r = http.post("https://api.resend.com/emails", timeout=20,
                  headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}", "User-Agent": UA},
                  json={"from": os.environ["QS_OUTREACH_FROM"], "to": [to], "subject": subject, "text": text,
                        "reply_to": os.environ.get("QS_REPLY_TO") or "reply@mail.ather-quantum.com"})
    if r.status_code >= 300:
        raise RuntimeError(f"resend {r.status_code}: {r.text[:200]}")
    return r.json().get("id")


def resend_event(email_id, http=None):
    http = http or requests
    r = http.get(f"https://api.resend.com/emails/{email_id}", timeout=20,
                 headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}", "User-Agent": UA})
    return r.json().get("last_event") if r.status_code == 200 else None


def refresh_events(conn, http=None):
    """Bounce/complaint status of the last 30 sends; suppress bounced domains."""
    rows = conn.execute("SELECT domain, resend_id, last_event FROM growth_outreach WHERE resend_id IS NOT NULL "
                        "ORDER BY sent_at DESC LIMIT 30").fetchall()
    for r in rows:
        if r["last_event"] in ("bounced", "complained"):
            continue
        ev = resend_event(r["resend_id"], http)
        if ev:
            conn.execute("UPDATE growth_outreach SET last_event = ?, checked_at = ? WHERE domain = ?", (ev, now_iso(), r["domain"]))
            if ev in ("bounced", "complained"):
                conn.execute("INSERT OR IGNORE INTO growth_suppress VALUES (?, ?, ?)", (r["domain"], now_iso(), ev))
    conn.commit()
    rows = conn.execute("SELECT last_event FROM growth_outreach WHERE resend_id IS NOT NULL ORDER BY sent_at DESC LIMIT 30").fetchall()
    events = [r[0] for r in rows]
    return {"n": len(events), "bounced": events.count("bounced"), "complained": events.count("complained")}


def process_replies(conn):
    """Inbound replies: 'stop' suppresses the sender's domain; any reply from a contacted domain is a lead."""
    sent = {r[0] for r in conn.execute("SELECT domain FROM growth_outreach")}
    leads, stops = [], []
    for r in conn.execute("SELECT from_addr, subject, received_at FROM inbound_mail WHERE COALESCE(is_test,0) = 0"):
        addr = (r["from_addr"] or "").lower()
        m = re.search(r"@([a-z0-9.-]+)", addr)
        dom = base_domain(m.group(1)) if m else ""
        if STOP_RE.search(r["subject"] or ""):
            if dom:
                conn.execute("INSERT OR IGNORE INTO growth_suppress VALUES (?, ?, 'reply-stop')", (dom, now_iso()))
            stops.append(dom)
        elif any(dom == d or dom.endswith("." + d) for d in sent):
            leads.append({"from": addr, "subject": r["subject"], "at": r["received_at"]})
    conn.commit()
    return leads, stops


def draft_reply(lead, lang="en"):
    if lang == "ar":
        return ("شكرًا على ردكم. يسعدنا إرسال تقرير كامل لنطاقاتكم، أو تفعيل مراقبة مجانية 14 يومًا تنبهكم عند أي تغيير: "
                f"{SITE}/monitoring?lang=ar\nوإن كان لديكم سؤال عن القياس نفسه فأخبرونا.")
    return ("Thanks for getting back to us. We can send a full report for your domains, or set up a free 14-day "
            f"monitoring trial that alerts you on any change: {SITE}/monitoring?lang=en\nHappy to answer questions about the measurement.")


def check_leads(conn, http=None):
    """New replies from contacted orgs → owner alert with a DRAFT. Nothing is sent to the lead (owner decision 2026-11-22)."""
    conn.execute("CREATE TABLE IF NOT EXISTS growth_leads (key TEXT PRIMARY KEY, notified_at TEXT)")
    leads, _ = process_replies(conn)
    new = []
    for lead in leads:
        key = f"{lead['from']}|{lead['at']}"
        if conn.execute("SELECT 1 FROM growth_leads WHERE key = ?", (key,)).fetchone():
            continue
        dom = lead["from"].split("@")[-1]
        row = conn.execute("SELECT lang FROM growth_outreach WHERE ? = domain OR ? LIKE '%.' || domain", (dom, dom)).fetchone()
        text = (f"Reply from {lead['from']} ({lead['at']})\nSubject: {lead['subject']}\n\n"
                "Read the full message in your inbox (reply@mail.ather-quantum.com is forwarded to you).\n\n"
                "--- Draft answer (NOT sent; edit and send it yourself) ---\n" + draft_reply(lead, row["lang"] if row else "en"))
        notify_owner(f"[Growth] Reply from {dom} — draft inside", text, http)
        conn.execute("INSERT INTO growth_leads VALUES (?, ?)", (key, now_iso()))
        new.append(lead)
    conn.commit()
    return new


def pause(reason):
    with open(PAUSE_FILE, "w", encoding="utf-8") as f:
        f.write(f"{now_iso()} {reason}\n")


def notify_owner(subject, text, http=None):
    owner = os.environ.get("QS_OWNER_EMAIL")
    if not owner:
        return
    http = http or requests
    http.post("https://api.resend.com/emails", timeout=20,
              headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}", "User-Agent": UA},
              json={"from": os.environ.get("QS_MAIL_FROM"), "to": [owner], "subject": subject, "text": text})


def sent_today(conn):
    day = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    return conn.execute("SELECT COUNT(*) FROM growth_outreach WHERE sent_at LIKE ?", (day + "%",)).fetchone()[0]


def outreach(conn, dry_run=False, http=None, history=None, pause_between=90, max_lookups=80):
    if os.path.exists(PAUSE_FILE):
        return {"paused": open(PAUSE_FILE, encoding="utf-8").read().strip(), "sent": []}
    health = refresh_events(conn, http) if not dry_run else {"n": 0, "bounced": 0, "complained": 0}
    if health["complained"] or (health["n"] >= 10 and health["bounced"] / health["n"] > BOUNCE_LIMIT):
        reason = f"auto-pause: {health['bounced']} bounced, {health['complained']} complaints in last {health['n']}"
        if not dry_run:
            pause(reason)
            notify_owner("[Growth agent] paused", reason + "\nResume: bash /root/quantum-aether/deploy/growth.sh start", http)
        return {"paused": reason, "sent": []}
    process_replies(conn)
    budget = max(0, min(PER_RUN, DAILY_CAP - sent_today(conn)))
    skip = excluded(conn, history_domains() if history is None else history)
    sent, looked = [], 0
    for c in candidates(conn, skip):
        if len(sent) >= budget or looked >= max_lookups:
            break
        if not auto_send_ok(c):
            continue
        looked += 1
        email, source = published_contact(c["domain"], http)
        mail_dom = base_domain(email.split("@")[1]) if email else ""
        if not email or mail_dom in skip or mail_dom.startswith("lists.") or is_eu(mail_dom):
            continue
        lang = "ar" if tld(c["domain"]) in ARABIC_TLDS or c["sector"] == "banks-mena" else "en"
        subject, text = message(c, lang)
        if dry_run:
            sent.append({"domain": c["domain"], "email": email, "reason": c["reason"], "source": source, "subject": subject})
            continue
        try:
            rid = resend_send(email, subject, text, http)
        except Exception as exc:  # one failed send never stops the run
            sent.append({"domain": c["domain"], "error": str(exc)})
            continue
        conn.execute("INSERT INTO growth_outreach (domain, email, lang, reason, resend_id, sent_at) VALUES (?,?,?,?,?,?)",
                     (c["domain"], email, lang, c["reason"], rid, now_iso()))
        conn.execute("INSERT OR IGNORE INTO contacted_orgs (domain, added_at, note) VALUES (?, ?, 'growth agent')",
                     (c["domain"], now_iso().replace("T", " ")[:19]))
        conn.commit()
        sent.append({"domain": c["domain"], "email": email, "reason": c["reason"], "id": rid})
        if pause_between:
            time.sleep(pause_between)
    return {"paused": None, "sent": sent, "looked_up": looked, "budget": budget}


def digest_text(conn, day=None):
    day = day or (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    q = lambda sql, *a: conn.execute(sql, a).fetchone()[0]
    visitors = q("SELECT COUNT(DISTINCT visitor) FROM pageviews WHERE day = ? AND is_bot = 0 AND is_test = 0", day)
    email_visits = q("SELECT COUNT(DISTINCT visitor) FROM pageviews WHERE day = ? AND is_bot = 0 AND is_test = 0 "
                     "AND referrer LIKE 'utm:email%'", day)
    scans = q("SELECT COUNT(*) FROM scans WHERE created_at LIKE ? AND is_test = 0", day + "%")
    trials = q("SELECT COUNT(*) FROM monitor_accounts WHERE created_at LIKE ? AND status != 'PENDING'", day + "%")
    sent = conn.execute("SELECT domain, email, reason, last_event FROM growth_outreach WHERE sent_at LIKE ?", (day + "%",)).fetchall()
    leads, stops = process_replies(conn)
    total = q("SELECT COUNT(*) FROM growth_outreach")
    lines = [f"Growth agent — {day}", "",
             f"Real visitors: {visitors} (from outreach email: {email_visits})",
             f"Real scans: {scans} · New trials: {trials}",
             f"Outreach sent: {len(sent)} (total since start: {total})"]
    lines += [f"  - {r['domain']} → {r['email']} [{r['reason']}] {r['last_event'] or ''}" for r in sent]
    lines += ["", f"Replies from contacted orgs (all time): {len(leads)}"]
    lines += [f"  - {l['at']} {l['from']}: {l['subject']}" for l in leads[-5:]]
    if stops:
        lines.append(f"Stop requests honoured: {', '.join(s for s in stops if s)}")
    manual = [c["domain"] for c in candidates(conn, excluded(conn, history_domains())) if not auto_send_ok(c)][:8]
    if manual:
        lines += ["", "Not auto-sent (global .com, may be EU; tell Claude which to contact): " + ", ".join(manual)]
    lines += ["", "PAUSED: " + open(PAUSE_FILE, encoding="utf-8").read().strip() if os.path.exists(PAUSE_FILE) else "Status: running",
              "Stop all: bash /root/quantum-aether/deploy/growth.sh stop"]
    return f"[Growth] {day}: {visitors} visitors, {len(sent)} sent, {trials} trials", "\n".join(lines)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    conn = connect()
    if cmd == "outreach":
        print(json.dumps(outreach(conn, dry_run="--dry-run" in argv), ensure_ascii=False, indent=1))
    elif cmd == "leads":
        print(json.dumps(check_leads(conn), ensure_ascii=False))
    elif cmd == "digest":
        subject, text = digest_text(conn)
        print(text)
        if "--print" not in argv:
            notify_owner(subject, text)
    else:
        print("paused" if os.path.exists(PAUSE_FILE) else "running", "· sent today", sent_today(conn), "/", DAILY_CAP,
              "· total", conn.execute("SELECT COUNT(*) FROM growth_outreach").fetchone()[0])


if __name__ == "__main__":
    main(sys.argv)
