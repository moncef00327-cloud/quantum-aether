"""Arab banks post-quantum TLS report: a frozen snapshot (data/bank_reports/<id>.json) shown at /banks/<id>.

Two measurements per bank: the main website from the weekly tracker, and every public subdomain found in
Certificate Transparency logs (counts only). Host names are never published: they stay in the paid audit.
tools/build_bank_report.py writes the snapshot; pages only read it.
"""
import json
import os

import adoption

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "bank_reports")

COUNTRIES = {
    "SA": {"ar": "السعودية", "en": "Saudi Arabia"}, "AE": {"ar": "الإمارات", "en": "UAE"},
    "QA": {"ar": "قطر", "en": "Qatar"}, "KW": {"ar": "الكويت", "en": "Kuwait"},
    "EG": {"ar": "مصر", "en": "Egypt"}, "MA": {"ar": "المغرب", "en": "Morocco"}, "JO": {"ar": "الأردن", "en": "Jordan"},
}

# domain (without www.) -> (Arabic name, English name, country, central bank?)
BANKS = {
    "adcb.com": ("بنك أبوظبي التجاري", "Abu Dhabi Commercial Bank", "AE", False),
    "alahli.com": ("البنك الأهلي السعودي", "Saudi National Bank", "SA", False),
    "alinma.com": ("مصرف الإنماء", "Alinma Bank", "SA", False),
    "alrajhibank.com.sa": ("مصرف الراجحي", "Al Rajhi Bank", "SA", False),
    "arabbank.com": ("البنك العربي", "Arab Bank", "JO", False),
    "attijariwafabank.com": ("التجاري وفا بنك", "Attijariwafa bank", "MA", False),
    "bankalbilad.com": ("بنك البلاد", "Bank Albilad", "SA", False),
    "bankfab.com": ("بنك أبوظبي الأول", "First Abu Dhabi Bank", "AE", False),
    "banquemisr.com": ("بنك مصر", "Banque Misr", "EG", False),
    "bkam.ma": ("بنك المغرب", "Bank Al-Maghrib", "MA", True),
    "cbe.org.eg": ("البنك المركزي المصري", "Central Bank of Egypt", "EG", True),
    "cbk.gov.kw": ("بنك الكويت المركزي", "Central Bank of Kuwait", "KW", True),
    "cbq.qa": ("البنك التجاري القطري", "Commercial Bank of Qatar", "QA", False),
    "centralbank.ae": ("مصرف الإمارات المركزي", "Central Bank of the UAE", "AE", True),
    "cibeg.com": ("البنك التجاري الدولي", "Commercial International Bank", "EG", False),
    "dib.ae": ("بنك دبي الإسلامي", "Dubai Islamic Bank", "AE", False),
    "kfh.com": ("بيت التمويل الكويتي", "Kuwait Finance House", "KW", False),
    "mashreq.com": ("بنك المشرق", "Mashreq", "AE", False),
    "nbk.com": ("بنك الكويت الوطني", "National Bank of Kuwait", "KW", False),
    "qib.com.qa": ("مصرف قطر الإسلامي", "Qatar Islamic Bank", "QA", False),
    "qnb.com": ("بنك قطر الوطني", "QNB", "QA", False),
    "riyadbank.com": ("بنك الرياض", "Riyad Bank", "SA", False),
    "sab.com": ("البنك السعودي الأول", "Saudi Awwal Bank", "SA", False),
    "sama.gov.sa": ("البنك المركزي السعودي", "Saudi Central Bank", "SA", True),
}

MIN_RESPONDING = 5  # fewer answering subdomains than this: too little to rank on
AWARD_MIN = 95       # "Quantum-safe bank": main site post-quantum and at least this share of subdomains


def ids():
    if not os.path.isdir(DIR):
        return []
    return sorted((f[:-5] for f in os.listdir(DIR) if f.endswith(".json")), reverse=True)


def load(report_id):
    if report_id not in ids():
        return None
    with open(os.path.join(DIR, report_id + ".json"), encoding="utf-8") as f:
        return json.load(f)


def build(weekly_rows, discoveries, measured_on, report_id):
    """weekly_rows: {domain: adoption row dict}; discoveries: {base: run_discovery() result}. Hosts are dropped."""
    rows = []
    for base, (name_ar, name_en, cc, central) in BANKS.items():
        w = weekly_rows.get("www." + base) or weekly_rows.get(base) or {}
        d = discoveries.get(base) or {}
        rows.append({"domain": base, "name": {"ar": name_ar, "en": name_en}, "country": cc, "central": central,
                     "www": {"ok": bool(w.get("ok")), "grade": w.get("grade"), "group": w.get("grp"),
                             "tls": w.get("tls"), "pq": bool(w.get("pq"))},
                     "subs": None if not d or d.get("error") else
                     {k: d[k] for k in ("names", "responding", "pq", "not_pq", "unknown")}})
    return {"id": report_id, "measured_on": measured_on, "rows": rows}


def share(row):
    s = row.get("subs")
    if not s or s["responding"] < MIN_RESPONDING:
        return None
    return round(100 * s["pq"] / s["responding"])


def ranked(report, optout=None):
    """Banks with enough subdomains, best protected first; the rest after, by name. Opted-out banks are removed."""
    optout = adoption.load_optout() if optout is None else optout
    rows = [r for r in report["rows"] if not adoption.opted_out(r["domain"], optout)]
    scored = sorted((r for r in rows if share(r) is not None),
                    key=lambda r: (-share(r), -r["subs"]["responding"], r["domain"]))
    rest = sorted((r for r in rows if share(r) is None), key=lambda r: r["domain"])
    return [dict(r, share=share(r)) for r in scored + rest]


def is_winner(row):
    return row.get("share") is not None and row["share"] >= AWARD_MIN and row["www"]["pq"]


def detail(rows, domain):
    """One bank with its rank, the leader and up to 4 same-country peers; None if unknown or opted out."""
    row = next((r for r in rows if r["domain"] == domain), None)
    if not row:
        return None
    ranked_rows = [r for r in rows if r["share"] is not None]
    rank = next((i for i, r in enumerate(ranked_rows, 1) if r["domain"] == domain), None)
    peers = [r for r in rows if r["country"] == row["country"] and r["domain"] != domain][:4]
    return {"row": row, "rank": rank, "of": len(ranked_rows), "leader": ranked_rows[0] if ranked_rows else None,
            "peers": peers, "winner": is_winner(row)}


def totals(rows):
    with_subs = [r for r in rows if r["share"] is not None]
    responding = sum(r["subs"]["responding"] for r in with_subs)
    pq = sum(r["subs"]["pq"] for r in with_subs)
    www_ok = [r for r in rows if r["www"]["ok"]]
    return {"banks": len(rows), "ranked": len(with_subs), "responding": responding, "pq": pq,
            "pct": round(100 * pq / responding) if responding else 0,
            "www_measured": len(www_ok), "www_pq": sum(1 for r in www_ok if r["www"]["pq"]),
            "gap": sum(1 for r in with_subs if r["www"]["pq"] and r["share"] < 50)}


COPY = {
    "ar": dict(
        title="البنوك العربية والتشفير ما بعد الكمومي",
        kicker="تقرير Quantum Aether",
        meta="قياس {banks} بنكاً عربياً: {pct}% فقط من {responding} نطاقاً فرعياً عاماً يستخدم تبادل مفاتيح مقاوماً "
             "للحوسبة الكمومية. ترتيب البنوك بالأرقام.",
        lead="قسنا الموقع الرئيسي وكل النطاقات الفرعية العامة لـ{banks} بنكاً في الخليج ومصر والمغرب والأردن، "
             "في {date}.",
        findings="أهم النتائج",
        f_overall="{pq} فقط من {responding} نطاقاً فرعياً يستجيب ({pct}%) تستخدم تبادل مفاتيح مقاوماً للحوسبة الكمومية.",
        f_www="{www_pq} من {www_measured} موقعاً رئيسياً محمي، لكن الموقع الرئيسي لا يمثّل البنك كله.",
        f_gap="{gap} بنوك موقعها الرئيسي محمي بينما أقل من نصف نطاقاتها الفرعية محمية.",
        why_title="لماذا يهم هذا",
        why="الاتصالات المشفّرة بالطريقة التقليدية يمكن تسجيلها اليوم وفك تشفيرها لاحقاً عندما يتوفر حاسوب كمومي "
            "كبير (احصد الآن وفك التشفير لاحقاً). المتصفحات الحالية تدعم التبادل الهجين X25519MLKEM768، فالحماية "
            "متاحة اليوم إذا فعّلها الخادم.",
        table_title="الترتيب",
        th=["#", "البنك", "الدولة", "النطاقات الفرعية المحمية", "الموقع الرئيسي"],
        central="بنك مركزي",
        few="أقل من {n} نطاقات تستجيب",
        www_yes="محمي ({grade})", www_no="غير محمي ({grade})", www_na="لم يستجب",
        cta_title="بنكك في القائمة؟",
        cta="نرسل لفريق الأمن القائمة الكاملة بأسماء النطاقات غير المحمية، مرتّبة حسب الأولوية، مع طريقة الإصلاح "
            "لكل خادم، في تقرير مؤرَّخ.",
        cta_button="اطلب تقرير بنكك",
        method_title="طريقة القياس وحدودها",
        method=["الموقع الرئيسي: من متتبّعنا الأسبوعي، اتصال TLS 1.3 واحد يعرض X25519MLKEM768.",
                "النطاقات الفرعية: كل الأسماء تحت نطاق البنك في سجلات شفافية الشهادات العامة (crt.sh أو Cert Spotter)، "
                "حتى 200 اسم لكل بنك، ونعدّ فقط ما يستجيب على المنفذ 443.",
                "ننشر الأعداد فقط، ولا ننشر أسماء النطاقات.",
                "القياس يخص تبادل المفاتيح في نقاط HTTPS العامة فقط، ولا يقيّم أمان التطبيقات أو الأنظمة الداخلية.",
                "أعداد الأسماء تختلف قليلاً بين مصادر السجلات ومن قياس لآخر."],
        optout="لإزالة بنك من التقرير، راسلنا من بريد على نطاق البنك عبر صفحة Impressum.",
        data="البيانات بصيغة JSON (CC BY 4.0)",
        award_title="جائزة «بنك آمن كمومياً 2026»",
        award_rule="تُمنح لكل بنك موقعه الرئيسي محمي و{n}% على الأقل من نطاقاته الفرعية محمية. تُعاد القياسات دورياً، "
                   "ويُضاف كل بنك يحقق الشرط.",
        award_winners="الحاصلون عليها:",
        award_none="لم يحققها أي بنك بعد.",
        award_badge="شارة الجائزة للبنك الفائز",
        award_badge_note="البنك الفائز يمكنه وضع هذه الشارة على موقعه:",
        d_rank="المرتبة {rank} من {of}",
        d_unranked="غير مرتّب: {few}",
        d_subs="{pq} من {responding} نطاقاً فرعياً يستجيب محمي",
        d_vs_leader="المتصدر {leader}: {share}%",
        d_peers="بنوك أخرى في {country}",
        d_winner="حاصل على جائزة «بنك آمن كمومياً 2026»",
        d_gap="لتحصل على الجائزة: {need} نطاقاً فرعياً إضافياً يجب حمايته{www}.",
        d_gap_www=" وتفعيل الحماية على الموقع الرئيسي",
        d_staff_title="تعمل في {name}؟",
        d_staff="أرسل هذه الصفحة لفريق أمن المعلومات. نعدّ لهم القائمة الكاملة بأسماء النطاقات غير المحمية وطريقة إصلاح كل منها.",
        d_staff_button="اطلب قائمة {name}",
        share="شارك",
        share_text="{name}: {share}% من نطاقاته الفرعية محمية بتشفير مقاوم للحوسبة الكمومية. الترتيب الكامل للبنوك العربية:",
        back="الترتيب الكامل",
        detail_meta="{name}: {pq} من {responding} نطاقاً فرعياً عاماً يستخدم تبادل مفاتيح مقاوماً للحوسبة الكمومية. المرتبة {rank} بين البنوك العربية.",
    ),
    "en": dict(
        title="Arab banks and post-quantum TLS",
        kicker="Quantum Aether report",
        meta="{banks} Arab banks measured: only {pct}% of {responding} public subdomains use post-quantum key exchange. "
             "Bank ranking with numbers.",
        lead="We measured the main website and every public subdomain of {banks} banks in the Gulf, Egypt, Morocco "
             "and Jordan on {date}.",
        findings="Key findings",
        f_overall="Only {pq} of {responding} responding subdomains ({pct}%) use post-quantum key exchange.",
        f_www="{www_pq} of {www_measured} main websites are protected, but the main website is not the whole bank.",
        f_gap="{gap} banks protect their main website while fewer than half of their subdomains are protected.",
        why_title="Why it matters",
        why="Traffic encrypted with classical key exchange can be recorded today and decrypted once a large quantum "
            "computer exists (harvest now, decrypt later). Current browsers already support the hybrid "
            "X25519MLKEM768, so protection is available as soon as the server enables it.",
        table_title="Ranking",
        th=["#", "Bank", "Country", "Protected subdomains", "Main website"],
        central="central bank",
        few="fewer than {n} subdomains answered",
        www_yes="protected ({grade})", www_no="not protected ({grade})", www_na="no answer",
        cta_title="Is your bank on the list?",
        cta="We send your security team the full list of unprotected subdomains, ranked by priority, with the fix for "
            "each server, as a dated report.",
        cta_button="Request your bank's report",
        method_title="Method and limits",
        method=["Main website: from our weekly tracker, one TLS 1.3 handshake offering X25519MLKEM768.",
                "Subdomains: every name under the bank's domain in public Certificate Transparency logs (crt.sh or "
                "Cert Spotter), up to 200 names per bank; only names answering on port 443 count.",
                "We publish counts only, never host names.",
                "This covers the key exchange of public HTTPS endpoints only. It does not assess application security "
                "or internal systems.",
                "Name counts vary slightly between log sources and between runs."],
        optout="To remove a bank from this report, write to us from an address on the bank's domain (see Impressum).",
        data="Data as JSON (CC BY 4.0)",
        award_title="\"Quantum-safe bank 2026\" award",
        award_rule="Awarded to every bank whose main website is protected and at least {n}% of whose subdomains are "
                   "protected. We re-measure regularly and add every bank that qualifies.",
        award_winners="Awarded to:",
        award_none="No bank has qualified yet.",
        award_badge="Award badge for the winning bank",
        award_badge_note="A winning bank can show this badge on its website:",
        d_rank="Rank {rank} of {of}",
        d_unranked="Not ranked: {few}",
        d_subs="{pq} of {responding} responding subdomains protected",
        d_vs_leader="Leader {leader}: {share}%",
        d_peers="Other banks in {country}",
        d_winner="Winner of the \"Quantum-safe bank 2026\" award",
        d_gap="To win the award: protect {need} more subdomains{www}.",
        d_gap_www=" and enable protection on the main website",
        d_staff_title="Do you work at {name}?",
        d_staff="Send this page to your security team. We prepare the full list of unprotected subdomains with the fix for each one.",
        d_staff_button="Request the {name} list",
        share="Share",
        share_text="{name}: {share}% of its subdomains use post-quantum key exchange. Full ranking of Arab banks:",
        back="Full ranking",
        detail_meta="{name}: {pq} of {responding} public subdomains use post-quantum key exchange. Rank {rank} among Arab banks.",
    ),
}


def need_for_award(row):
    """Subdomains still to protect so that pq / responding >= AWARD_MIN."""
    s = row.get("subs") or {}
    r, pq = s.get("responding", 0), s.get("pq", 0)
    import math
    return max(0, math.ceil(AWARD_MIN * r / 100) - pq)


def badge_svg(name_en, year):
    """Award badge (SVG, Latin text) for a winning bank."""
    from html import escape
    n = escape(name_en)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="72" viewBox="0 0 300 72" role="img" '
            f'aria-label="Quantum-safe bank {year}: {n}">'
            f'<rect width="300" height="72" rx="10" fill="#0f172a"/><rect x="1" y="1" width="298" height="70" rx="9" '
            f'fill="none" stroke="#4ade80" stroke-width="2"/>'
            f'<circle cx="36" cy="36" r="18" fill="none" stroke="#4ade80" stroke-width="3"/>'
            f'<path d="M27 36l6 6 12-13" fill="none" stroke="#4ade80" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<text x="66" y="30" font-family="Verdana,DejaVu Sans,sans-serif" font-size="15" font-weight="bold" fill="#f8fafc">'
            f'Quantum-safe bank {year}</text>'
            f'<text x="66" y="52" font-family="Verdana,DejaVu Sans,sans-serif" font-size="12" fill="#94a3b8">'
            f'{n} · Quantum Aether</text></svg>')
