#!/usr/bin/env python3
"""Partner programme admin (run on the server with the env loaded):

  partners_admin.py list                 applications and partners
  partners_admin.py approve ID [CODE]    activate, assign a code, e-mail the partner their link (needs RESEND env)
  partners_admin.py reject ID
  partners_admin.py end ID               revoke/end an active partner (stops further click/referral attribution)
  partners_admin.py report               clicks, referrals and commission due / pending per partner
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
    "en": ("Your Quantum Aether partner link", "Hello {name},\n\nwelcome to the Quantum Aether partner programme.\n\nYour code: {code}\nYour link: {base}/?ref={code}\nIt works on every page, e.g. {base}/monitoring?ref={code} or {base}/guides/post-quantum-vendor-security-questionnaire?ref={code}\n\nTerms: 30% of monitoring payments for 12 months, 20% of reports, packs and audits; monthly payout ({payout}) for payments older than 30 days, from USD 50. Full terms: {base}/partners?lang=en\nPlease: no spam or cold e-mail without consent, no ads on our brand name, no misleading security claims.\n\nReply to this e-mail with questions.\nQuantum Aether"),
    "de": ("Ihr Quantum-Aether-Partnerlink", "Hallo {name},\n\nwillkommen im Partnerprogramm von Quantum Aether.\n\nIhr Code: {code}\nIhr Link: {base}/?ref={code}\nEr funktioniert auf jeder Seite, z. B. {base}/monitoring?ref={code}&lang=de\n\nBedingungen: 30 % der Überwachungszahlungen für 12 Monate, 20 % von Berichten, Paketen und Audits; monatliche Auszahlung ({payout}) für Zahlungen älter als 30 Tage, ab 50 USD. Alle Bedingungen: {base}/partners?lang=de\nBitte: kein Spam, keine unverlangten E-Mails, keine Anzeigen auf unseren Markennamen, keine irreführenden Sicherheitsversprechen.\n\nBei Fragen einfach antworten.\nQuantum Aether"),
    "ar": ("رابط الشريك الخاص بك في Quantum Aether", "مرحباً {name}،\n\nأهلاً بك في برنامج شركاء Quantum Aether.\n\nرمزك: {code}\nرابطك: {base}/?ref={code}&lang=ar\nيعمل على أي صفحة، مثل {base}/monitoring?ref={code}&lang=ar\n\nالشروط: 30% من مدفوعات المراقبة لمدة 12 شهراً، و20% من التقارير والباقات والتدقيقات؛ الدفع شهرياً ({payout}) للمدفوعات التي مضى عليها 30 يوماً، بحد أدنى 50 دولاراً. الشروط كاملة: {base}/partners?lang=ar\nرجاءً: لا رسائل مزعجة ولا إيميل بارد بلا موافقة، ولا إعلانات على اسم علامتنا، ولا وعود أمنية مضلِّلة.\n\nللأسئلة ردّ على هذا البريد.\nQuantum Aether"),
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
    if not argv or argv[0] not in ("list", "approve", "reject", "end", "report"):
        print(__doc__)
        return 2
    c = conn()
    cmd = argv[0]
    if cmd == "list":
        for r in c.execute("SELECT id, status, code, name, email, payout, lang, created_at, channel, website FROM partners ORDER BY id"):
            print(f"#{r['id']} [{r['status']}] {r['code'] or '-'} · {r['name']} · {r['email']} · {r['payout']} · {r['lang']} · {r['created_at']}")
            print(f"    {r['website'] or ''} | {r['channel'][:200]}")
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
        print(f"ACTIVE {code}: {BASE}/?ref={code}")
        subject, text = MAIL.get(row["lang"], MAIL["en"])
        send(row["email"], subject, text.format(name=row["name"], code=code, base=BASE,
                                                payout="PayPal" if row["payout"] == "paypal" else "USDC"))
        return 0
    clicks = {r[0]: r[1] for r in c.execute("SELECT code, SUM(n) FROM partner_clicks GROUP BY code")}
    refs = {r[0]: r[1] for r in c.execute("SELECT code, COUNT(*) FROM referrals GROUP BY code")}
    com = partners.commissions(c)
    for r in c.execute("SELECT code, name, payout FROM partners WHERE status = 'ACTIVE' ORDER BY code"):
        k = r["code"]
        d = com.get(k, {"items": [], "due": 0.0, "pending": 0.0})
        flag = "PAY NOW" if d["due"] >= partners.MIN_PAYOUT else "below minimum"
        print(f"{k} ({r['name']}, {r['payout']}): clicks {clicks.get(k, 0)} · conversions {refs.get(k, 0)} · "
              f"due {d['due']:.2f} · pending {d['pending']:.2f} → {flag}")
        for it in d["items"]:
            print("    ", it)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
