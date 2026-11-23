#!/usr/bin/env python3
"""Outreach sender for the owner-approved template and target list (approved 2026-11-23). Prepared, not scheduled.

  python3 tools/outreach_send.py --dry-run [--limit 2]   render the mails, send nothing, write nothing
  python3 tools/outreach_send.py --send    [--limit 20]  really send (explicit flag; there is no default action)

Per target (CSV /root/outreach/targets.csv, from targets-sample.csv):
  * skip when the address/domain is suppressed (outreach_suppress, growth_suppress) or was already mailed
    (outreach_sent, growth_outreach): one mail per organisation, ever;
  * ONE TLS 1.3 ClientHello to <handshake_host>:443 (the scanner's own hello, PQ groups offered, nothing else) for
    today's group and class; no answer means skip, never a stale value;
  * fill the approved template (ar for "Arab world", en otherwise), add List-Unsubscribe + One-Click headers;
  * send via Resend from "Quantum Aether Team <sales@ather-quantum.com>", Reply-To reply@mail.ather-quantum.com,
    log to outreach_sent.
Stops when: the run limit is reached, 20 mails were sent in the last 24 h (--daily-cap), a pause file exists
(/var/lib/quantum_saas/outreach.paused or growth.paused), more than 2 bounces or any complaint among this run's
mails, or 3 send errors. Secrets come from the environment or /etc/quantum_saas.env and are never printed.
"""
import argparse
import csv
import datetime as dt
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import outreach_suppress as osup  # noqa: E402

ENV_FILE = "/etc/quantum_saas.env"
DATA_DIR = os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas")
DB_PATH = os.path.join(DATA_DIR, "quantum_saas.db")
PAUSE_FILES = [os.path.join(DATA_DIR, "outreach.paused"), os.path.join(DATA_DIR, "growth.paused")]
TARGETS = "/root/outreach/targets.csv"
SITE = "https://ather-quantum.com"
FROM = "Quantum Aether Team <sales@ather-quantum.com>"
REPLY_TO = "reply@mail.ather-quantum.com"
UA = "Mozilla/5.0 (compatible; QuantumAetherBot/1.0; +https://ather-quantum.com/bot)"
MAX_BOUNCES = 2

# ---- approved template text (template-en.md / template-ar.md, 2026-11-23). Do not edit without the owner. ----
EN = {
    "subject": "{domain}: TLS key exchange observed on {date}",
    "intro": "Hello {domain} security team,\n\nOn {date}, one public TLS handshake to {host}:443 negotiated {tls_version} with {group} key exchange.",
    "classical": "That is classical key exchange. Chrome, Firefox and Safari already offer the hybrid post-quantum group X25519MLKEM768, so enabling it is mostly a server/CDN setting.",
    "hybrid-pq": "That is the hybrid post-quantum group, so this host is already covered. Other hosts can differ, and a config or CDN change can quietly revert it.",
    "rest": ("You can check any of your hosts for free, no sign-up: https://ather-quantum.com/?domain={domain}&lang=en\n"
             "Or start a free 14-day daily monitoring trial (up to 10 domains, no card, silent-downgrade alerts): https://ather-quantum.com/monitoring?domain={domain}&lang=en#trial-form\n\n"
             "Why this email: this address is published in {domain}'s security.txt. This is a one-time commercial message from Quantum Aether; we will not write again.\n\n"
             "Unsubscribe in one click: {unsubscribe_url} (or reply \"stop\").\n\n"
             "Quantum Aether Team\n"
             "Quantum Aether, Sparkaßen 11/12, 5280 Braunau am Inn, Austria · https://ather-quantum.com/impressum"),
}
AR = {
    "subject": "{domain}: تبادل المفاتيح في TLS كما رُصد بتاريخ {date}",
    "intro": "مرحبًا فريق أمن {domain}،\n\nبتاريخ {date} أجرينا مصافحة TLS عامة واحدة مع {host} على المنفذ 443، فتم التفاوض على {tls_version} مع تبادل المفاتيح {group}.",
    "classical": "هذا تبادل مفاتيح تقليدي. متصفحات Chrome وFirefox وSafari تعرض أصلًا المجموعة الهجينة المقاومة للحوسبة الكمومية X25519MLKEM768، وتفعيلها غالبًا إعداد في الخادم أو شبكة CDN.",
    "hybrid-pq": "هذه هي المجموعة الهجينة المقاومة للحوسبة الكمومية، أي أن هذا المضيف مغطّى. قد تختلف مضيفات أخرى لديكم، وقد يُلغي تغيير في الإعدادات أو في CDN ذلك دون أن يُلاحظ.",
    "rest": ("يمكنكم فحص أي مضيف مجانًا ودون تسجيل: https://ather-quantum.com/?domain={domain}&lang=ar\n"
             "أو بدء تجربة مجانية لمدة 14 يومًا للمراقبة اليومية (حتى 10 نطاقات، بلا بطاقة، مع تنبيهات التراجع الصامت): https://ather-quantum.com/monitoring?domain={domain}&lang=ar#trial-form\n\n"
             "سبب هذه الرسالة: هذا العنوان منشور في ملف security.txt الخاص بـ {domain}. هذه رسالة تجارية لمرة واحدة من Quantum Aether، ولن نراسلكم مجددًا.\n\n"
             "لإلغاء الاشتراك بنقرة واحدة: {unsubscribe_url} (أو ردّوا بكلمة «إيقاف» أو stop).\n\n"
             "Quantum Aether Team\n"
             "Quantum Aether، Sparkaßen 11/12, 5280 Braunau am Inn, Austria · https://ather-quantum.com/impressum"),
}


def load_env(path=ENV_FILE):
    """Fill missing variables from the service env file (values are never printed)."""
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def handshake(host, timeout=8.0):
    """One ClientHello (PQ + classical groups offered) to host:443 -> {'tls_version','group','kex_class'} or None."""
    import quantum_vuln_scanner as qs
    try:
        ip = qs.resolve_public_ip(host)
        hello = qs._hello_attempt(ip, host, True, timeout)
    except Exception as exc:  # noqa: BLE001  any failure: skip this target
        return {"error": f"{type(exc).__name__}: {exc}"[:160]}
    group = hello.get("group")
    if group is None or hello.get("hrr"):
        return {"error": "no negotiated group observed"}
    name = qs.GROUP_NAMES.get(group, hex(group))
    name = {"x25519": "X25519", "x448": "X448"}.get(name.lower(), name)  # template spelling
    return {"tls_version": qs.TLS_VERSIONS.get(hello["version"], hex(hello["version"])),
            "group": name, "kex_class": "hybrid-pq" if group in qs.PQ_GROUPS else "classical"}


def render(target, obs, secret, date=None):
    lang = "ar" if target["region"].strip().lower() == "arab world" else "en"
    t = AR if lang == "ar" else EN
    slots = {"domain": target["domain"], "host": target["handshake_host"], "date": date or dt.date.today().isoformat(),
             "tls_version": obs["tls_version"], "group": obs["group"],
             "unsubscribe_url": osup.unsubscribe_url(SITE, target["contact_email"], secret)}
    body = "\n\n".join([t["intro"], t[obs["kex_class"]], t["rest"]]).format(**slots)
    return {"lang": lang, "subject": t["subject"].format(**slots), "text": body,
            "headers": osup.list_unsubscribe_headers(SITE, target["contact_email"], secret, mailto=REPLY_TO)}


def already_sent(conn, email, domain):
    if conn.execute("SELECT 1 FROM outreach_sent WHERE email = ? OR domain = ?", (email, domain)).fetchone():
        return True
    try:
        return bool(conn.execute("SELECT 1 FROM growth_outreach WHERE domain = ? OR email = ?", (domain, email)).fetchone())
    except sqlite3.Error:
        return False


def sent_last_24h(conn):
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return conn.execute("SELECT COUNT(*) FROM outreach_sent WHERE sent_at >= ?", (since,)).fetchone()[0]


def resend_send(to, mail, http):
    r = http.post("https://api.resend.com/emails", timeout=20,
                  headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}", "User-Agent": UA},
                  json={"from": FROM, "to": [to], "subject": mail["subject"], "text": mail["text"],
                        "reply_to": REPLY_TO, "headers": mail["headers"]})
    if r.status_code >= 300:
        raise RuntimeError(f"resend HTTP {r.status_code}")
    return r.json().get("id")


def resend_event(email_id, http):
    r = http.get(f"https://api.resend.com/emails/{email_id}", timeout=20,
                 headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}", "User-Agent": UA})
    return r.json().get("last_event") if r.status_code == 200 else None


def run_events(conn, ids, http):
    """Refresh this run's mails; returns (bounced, complained)."""
    bounced = complained = 0
    for rid in ids:
        ev = resend_event(rid, http)
        if ev:
            conn.execute("UPDATE outreach_sent SET last_event = ?, checked_at = ? WHERE resend_id = ?", (ev, now_iso(), rid))
        if ev == "bounced":
            bounced += 1
            row = conn.execute("SELECT email FROM outreach_sent WHERE resend_id = ?", (rid,)).fetchone()
            if row:
                osup.suppress(conn, row[0], "bounced")
        elif ev == "complained":
            complained += 1
            row = conn.execute("SELECT email FROM outreach_sent WHERE resend_id = ?", (rid,)).fetchone()
            if row:
                osup.suppress(conn, row[0], "complained")
    conn.commit()
    return bounced, complained


def keep_db_owner(db):
    """Run as root, SQLite may create -wal/-shm files owned by root, and the web service (user quantum) could then no
    longer write the database. Give them back to the database file's owner."""
    if not hasattr(os, "geteuid") or os.geteuid() != 0 or not os.path.exists(db):
        return
    st = os.stat(db)
    for suffix in ("-wal", "-shm", "-journal"):
        p = db + suffix
        try:
            if os.path.exists(p) and (os.stat(p).st_uid, os.stat(p).st_gid) != (st.st_uid, st.st_gid):
                os.chown(p, st.st_uid, st.st_gid)
        except OSError:
            pass


def read_targets(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("contact_email") and r.get("domain")]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="print rendered mails; no send, no DB writes")
    mode.add_argument("--send", action="store_true", help="really send via Resend")
    ap.add_argument("--limit", type=int, default=20, help="max mails this run (default 20)")
    ap.add_argument("--daily-cap", type=int, default=20, help="max mails in any 24 h (default 20)")
    ap.add_argument("--targets", default=TARGETS)
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--pause", type=float, default=60.0, help="seconds between sends (default 60)")
    a = ap.parse_args(argv)

    load_env()
    secret = os.environ.get("QS_HASH_SALT", "")
    if not secret:
        sys.exit("QS_HASH_SALT missing: cannot mint unsubscribe links")
    if a.send and not os.environ.get("RESEND_API_KEY"):
        sys.exit("RESEND_API_KEY missing")
    if a.send:
        for p in PAUSE_FILES:
            if os.path.exists(p):
                sys.exit(f"paused: {p} exists")

    if a.dry_run:  # read-only: never create tables or rows in a dry run
        conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
        try:
            conn.execute("SELECT 1 FROM outreach_sent LIMIT 1")
        except sqlite3.Error:
            conn.close()
            conn = sqlite3.connect(":memory:")
            osup.init(conn)
    else:
        conn = sqlite3.connect(a.db, timeout=30)
        osup.init(conn)

    keep_db_owner(a.db)
    try:
        return _run(a, conn, secret)
    finally:
        conn.close()
        keep_db_owner(a.db)


def _run(a, conn, secret):
    import requests
    http = requests.Session()
    budget = min(a.limit, max(0, a.daily_cap - sent_last_24h(conn)))
    print(f"mode={'dry-run' if a.dry_run else 'SEND'} budget={budget} targets={a.targets}")
    done, ids, errors = 0, [], 0
    for t in read_targets(a.targets):
        if done >= budget:
            break
        email, domain = osup.normalize(t["contact_email"]), t["domain"].strip().lower()
        if not email:
            print(f"skip {domain}: invalid address")
            continue
        if osup.is_suppressed(conn, email, domain):
            print(f"skip {domain}: suppressed")
            continue
        if already_sent(conn, email, domain):
            print(f"skip {domain}: already contacted")
            continue
        obs = handshake(t["handshake_host"])
        if obs.get("error"):
            print(f"skip {domain}: handshake {obs['error']}")
            continue
        mail = render(t, obs, secret)
        if a.dry_run:
            print("=" * 72)
            print(f"To: {email}\nFrom: {FROM}\nReply-To: {REPLY_TO}")
            for k, v in mail["headers"].items():
                print(f"{k}: {v}")
            print(f"Subject: {mail['subject']}\n\n{mail['text']}")
            done += 1
            continue
        try:
            rid = resend_send(email, mail, http)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"error {domain}: {exc}")
            if errors >= 3:
                print("stop: 3 send errors")
                break
            continue
        with conn:
            conn.execute("INSERT INTO outreach_sent (email, domain, org, lang, kex_group, kex_class, subject, resend_id, sent_at)"
                         " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (email, domain, t.get("organization", ""), mail["lang"], obs["group"], obs["kex_class"],
                          mail["subject"], rid, now_iso()))
        keep_db_owner(a.db)
        ids.append(rid)
        done += 1
        print(f"sent {domain} -> {email} ({obs['kex_class']}, {mail['lang']}) id={rid}")
        time.sleep(a.pause)
        bounced, complained = run_events(conn, ids, http)
        if bounced > MAX_BOUNCES or complained:
            open(PAUSE_FILES[0], "w").write(f"{now_iso()} bounced={bounced} complained={complained}\n")
            print(f"stop: bounced={bounced} complained={complained}; wrote {PAUSE_FILES[0]}")
            break
    print(f"done: {done} {'rendered' if a.dry_run else 'sent'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
