#!/usr/bin/env python3
"""Partner programme admin (run on the server with the env loaded):

  partners_admin.py list                 applications, partners and MSP pilot leads
  partners_admin.py approve ID [CODE]    activate, assign a code, e-mail the partner their link (needs RESEND env)
  partners_admin.py reject ID
  partners_admin.py end ID               revoke/end an active partner (stops further click/referral attribution)
  partners_admin.py report               clicks, referrals and commission due / pending per partner
  partners_admin.py pilot                list MSP pilot leads (/partners/pilot)
  partners_admin.py pilot ID STATUS      set a pilot lead status: NEW / CONTACTED / WON / LOST
"""
import json
import os
import re
import sqlite3
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mailer import with_team_from  # noqa: E402
import partners  # noqa: E402

DB = os.environ.get("QS_DB", "/var/lib/quantum_saas/quantum_saas.db")
BASE = "https://ather-quantum.com"

MAIL = {
    "en": ("Your Quantum Aether partner link & live dashboard", "Hello {name},\n\nwelcome to the Quantum Aether partner programme.\n\nYour code: {code}\nYour referral link: {base}/?ref={code}\nIt works on every page, e.g. {base}/monitoring?ref={code} or {base}/guides/post-quantum-vendor-security-questionnaire?ref={code}\nYour private live stats dashboard (clicks, visits & referrals): {live_stats_url}\n\nTerms: 30% of monitoring payments for 12 months, 20% of reports, packs and audits; monthly payout ({payout}) for payments older than 30 days, from USD 50. Full terms: {base}/partners?lang=en\nPlease: no spam or cold e-mail without consent, no ads on our brand name, no misleading security claims.\n\nReply to this e-mail with questions.\nQuantum Aether Team"),
    "de": ("Ihr Quantum-Aether-Partnerlink & Live-Dashboard", "Hallo {name},\n\nwillkommen im Partnerprogramm von Quantum Aether.\n\nIhr Code: {code}\nIhr Empfehlungslink: {base}/?ref={code}\nEr funktioniert auf jeder Seite, z. B. {base}/monitoring?ref={code}&lang=de\nIhr privates Live-Statistik-Dashboard (Klicks & Vermittlungen): {live_stats_url}\n\nBedingungen: 30 % der Überwachungszahlungen für 12 Monate, 20 % von Berichten, Paketen und Audits; monatliche Auszahlung ({payout}) für Zahlungen älter als 30 Tage, ab 50 USD. Alle Bedingungen: {base}/partners?lang=de\nBitte: kein Spam, keine unverlangten E-Mails, keine Anzeigen auf unseren Markennamen, keine irreführenden Sicherheitsversprechen.\n\nBei Fragen einfach antworten.\nQuantum Aether Team"),
    "ar": ("رابط الشريك ولوحة الإحصائيات المباشرة — Quantum Aether", "مرحباً {name}،\n\nأهلاً بك في برنامج شركاء Quantum Aether.\n\nرمزك: {code}\nرابط الإحالة الخاص بك: {base}/?ref={code}&lang=ar\nيعمل على أي صفحة، مثل {base}/monitoring?ref={code}&lang=ar\nلوحة الإحصائيات المباشرة الخاصة بك (النقرات والزيارات والتحويلات لحظياً): {live_stats_url}\n\nالشروط: 30% من مدفوعات المراقبة لمدة 12 شهراً، و20% من التقارير والباقات والتدقيقات؛ الدفع شهرياً ({payout}) للمدفوعات التي مضى عليها 30 يوماً، بحد أدنى 50 دولاراً. الشروط كاملة: {base}/partners?lang=ar\nرجاءً: لا رسائل مزعجة ولا إيميل بارد بلا موافقة، ولا إعلانات على اسم علامتنا، ولا وعود أمنية مضلِّلة.\n\nللأسئلة ردّ على هذا البريد.\nQuantum Aether Team"),
}


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    partners.init(c)
    return c


def send(to, subject, text):
    api = os.environ.get("RESEND_API_KEY", "").strip()
    raw = os.environ.get("QS_MAIL_FROM", "").strip()
    if not api or not raw:
        print("  (no RESEND env: e-mail not sent; send the link manually)")
        return
    sender = with_team_from(raw)
    m = re.search(r"<([^>]+)>", raw)
    body = {"from": sender, "to": [to], "subject": subject, "text": text,
            "reply_to": os.environ.get("QS_REPLY_TO") or (m.group(1) if m else raw)}
    req = urllib.request.Request("https://api.resend.com/emails", data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {api}", "Content-Type": "application/json", "User-Agent": "QuantumAether-mailer/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        print("  e-mail sent", json.loads(r.read().decode()).get("id"))


def main(argv):
    if not argv or argv[0] not in ("list", "approve", "reject", "end", "report", "pilot"):
        print(__doc__)
        return 2
    c = conn()
    cmd = argv[0]

    def print_pilot(rows):
        for r in rows:
            print(f"#{r['id']} [{r['status']}] {r['name']} · {r['email']} · {r['company'] or '-'} · "
                  f"client={r['client_domain'] or '-'} hosts={r['hostnames'] or '-'} logo={r['white_label'] or '-'} · "
                  f"{r['lang']} · {r['created_at']}")
            if r["note"]:
                print(f"    {r['note'][:300]}")

    if cmd == "pilot":
        if len(argv) >= 3:
            pid, new_st = int(argv[1]), argv[2].upper()
            if new_st not in ("NEW", "CONTACTED", "WON", "LOST"):
                print("status must be NEW / CONTACTED / WON / LOST")
                return 1
            with c:
                n = c.execute("UPDATE pilot_leads SET status = ? WHERE id = ?", (new_st, pid)).rowcount
            print(f"{new_st.lower()} ({n} row)" if n else "no such pilot lead")
            return 0 if n else 1
        print_pilot(c.execute("SELECT * FROM pilot_leads ORDER BY id DESC"))
        return 0

    data_dir = os.environ.get("QS_DATA_DIR") or os.path.dirname(os.path.abspath(DB))

    if cmd == "list":
        for r in c.execute("SELECT id, status, code, name, email, payout, lang, created_at, channel, website FROM partners ORDER BY id"):
            print(f"#{r['id']} [{r['status']}] {r['code'] or '-'} · {r['name']} · {r['email']} · {r['payout']} · {r['lang']} · {r['created_at']}")
            if r["status"] == "ACTIVE" and r["code"]:
                lurl = partners.live_stats_url(r["code"], BASE, data_dir=data_dir)
                print(f"    ref: {BASE}/?ref={r['code']} | live: {lurl}")
            print(f"    {r['website'] or ''} | {r['channel'][:200]}")
        pilots = list(c.execute("SELECT * FROM pilot_leads ORDER BY id DESC"))
        if pilots:
            print(f"\n-- MSP pilot leads ({len(pilots)}) --")
            print_pilot(pilots)
        return 0
    if cmd in ("approve", "reject", "end"):
        pid = int(argv[1])
        row = c.execute("SELECT * FROM partners WHERE id = ?", (pid,)).fetchone()
        if not row:
            print("no such application")
            return 1
        if cmd in ("reject", "end"):
            new_st = "REJECTED" if cmd == "reject" else "ENDED"
            with c:
                c.execute("UPDATE partners SET status = ? WHERE id = ?", (new_st, pid))
            print(new_st.lower())
            return 0
        code = (argv[2].upper() if len(argv) > 2 else None) or row["code"] or partners.new_code(c, row["name"])
        if not partners.CODE_RE.match(code):
            print("code must be 3-20 letters/digits")
            return 1
        with c:
            c.execute("UPDATE partners SET status = 'ACTIVE', code = ?, approved_at = strftime('%Y-%m-%dT%H:%M:%SZ','now') "
                      "WHERE id = ?", (code, pid))
        live_url = partners.live_stats_url(code, BASE, data_dir=data_dir)
        print(f"ACTIVE {code}: {BASE}/?ref={code}")
        print(f"LIVE STATS: {live_url}")
        subject, text = MAIL.get(row["lang"], MAIL["en"])
        send(row["email"], subject, text.format(name=row["name"], code=code, base=BASE,
                                                live_stats_url=live_url,
                                                payout="PayPal" if row["payout"] == "paypal" else "USDC"))
        return 0
    clicks = {r[0]: r[1] for r in c.execute("SELECT code, SUM(n) FROM partner_clicks GROUP BY code")}
    refs = {r[0]: r[1] for r in c.execute("SELECT code, COUNT(*) FROM referrals GROUP BY code")}
    com = partners.commissions(c)
    for r in c.execute("SELECT code, name, payout FROM partners WHERE status = 'ACTIVE' ORDER BY code"):
        k = r["code"]
        d = com.get(k, {"items": [], "due": 0.0, "pending": 0.0})
        flag = "PAY NOW" if d["due"] >= partners.MIN_PAYOUT else "below minimum"
        live_url = partners.live_stats_url(k, BASE, data_dir=data_dir)
        print(f"{k} ({r['name']}, {r['payout']}): clicks {clicks.get(k, 0)} · conversions {refs.get(k, 0)} · "
              f"due {d['due']:.2f} · pending {d['pending']:.2f} → {flag}")
        print(f"    live: {live_url}")
        for it in d["items"]:
            print("    ", it)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
