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
    ),
}
