"""Weekly bank post-quantum tracker (/banks/weekly): Gulf & MENA, DACH and European banks from the weekly
adoption scan (homepage = www host only). Built live from adoption_results, so every Monday scan publishes a
new week automatically. Also writes ready-to-post LinkedIn texts that go into the Monday scorecard email."""
import adoption

# Order = order on the page. Keys are sectors in data/adoption_watchlists.json.
REGIONS = ["banks-mena", "banks-dach", "banks-europe"]
SITE = "https://ather-quantum.com"

COPY = {
    "en": {
        "title": "Weekly bank post-quantum tracker",
        "kicker": "Gulf, DACH and European banks · updated every Monday",
        "lead": "Which banks' public websites negotiate a post-quantum key exchange (X25519MLKEM768)? "
                "We test the homepage host of {banks} banks and central banks every week.",
        "meta": "{week}: {pq} of {n} tracked banks ({pct}%) use post-quantum TLS on their homepage. "
                "Gulf, DACH and European banks, updated weekly.",
        "changes": "Changes since last week", "adopted": "Enabled post-quantum key exchange",
        "dropped": "Went back to classical key exchange", "no_changes": "No bank changed status this week.",
        "first_week": "First tracked week: no comparison yet.",
        "share": "{pq} of {n} ({pct}%)", "delta": "{d:+.1f} points vs last week",
        "col_bank": "Website", "col_status": "Status", "col_since": "Post-quantum since",
        "pq": "post-quantum", "classic": "classical only", "unsure": "undetermined", "down": "no answer",
        "why_title": "Why compliance and security teams track this",
        "why": "NIS2 (Art. 21) and DORA (RTS 2024/1774) require cryptography policies that follow the state of the art, "
               "and SAMA circular 482021280 asks Saudi financial institutions for a cryptographic inventory by "
               "31 December 2026. A public homepage is only one host: most banks run dozens of public subdomains.",
        "limits": "Limits: one public HTTPS host per bank (usually www), tested from London. Internal systems, apps "
                  "and subdomains are not covered. A classical result is not a vulnerability today; it shows where "
                  "harvest-now-decrypt-later exposure exists.",
        "cta_scan": "Check your own domain for free", "cta_audit": "Audit every public subdomain (NIS2 / DORA / SAMA)",
        "archive": "Earlier weeks", "data": "Data: CC BY 4.0 · JSON",
    },
    "ar": {
        "title": "المتتبع الأسبوعي لتشفير البنوك المقاوم للحوسبة الكمومية",
        "kicker": "بنوك الخليج والشرق الأوسط وأوروبا · يُحدَّث كل اثنين",
        "lead": "أيّ البنوك تتفاوض مواقعها العامة على تبادل مفاتيح مقاوم للحوسبة الكمومية (X25519MLKEM768)؟ "
                "نفحص كل أسبوع الموقع الرئيسي لـ {banks} من البنوك والبنوك المركزية.",
        "meta": "{week}: {pq} من {n} بنكاً ({pct}%) تستخدم TLS مقاوماً للحوسبة الكمومية في موقعها الرئيسي. "
                "بنوك الخليج وأوروبا، تحديث أسبوعي.",
        "changes": "التغييرات منذ الأسبوع الماضي", "adopted": "فعّلت تبادل المفاتيح المقاوم للكم",
        "dropped": "عادت إلى التبادل التقليدي", "no_changes": "لم يتغير وضع أي بنك هذا الأسبوع.",
        "first_week": "أول أسبوع مرصود: لا مقارنة بعد.",
        "share": "{pq} من {n} ({pct}%)", "delta": "{d:+.1f} نقطة عن الأسبوع الماضي",
        "col_bank": "الموقع", "col_status": "الحالة", "col_since": "مقاوم للكم منذ",
        "pq": "مقاوم للكم", "classic": "تقليدي فقط", "unsure": "غير محدد", "down": "لا استجابة",
        "why_title": "لماذا يتابع مسؤولو الامتثال والأمن هذا المؤشر",
        "why": "يطلب تعميم ساما رقم 482021280 من المؤسسات المالية السعودية حصر أصول التشفير بنهاية 31 ديسمبر 2026، "
               "وتشترط NIS2 وDORA في أوروبا سياسات تشفير تواكب أحدث المعايير. والموقع الرئيسي مضيف واحد فقط: "
               "لدى معظم البنوك عشرات النطاقات الفرعية العامة.",
        "limits": "الحدود: مضيف HTTPS عام واحد لكل بنك (غالباً www)، يُفحص من لندن. لا يشمل الأنظمة الداخلية "
                  "ولا التطبيقات ولا النطاقات الفرعية. النتيجة التقليدية ليست ثغرة اليوم، لكنها تكشف التعرض لهجمات "
                  "«اجمع الآن وافكّ لاحقاً».",
        "cta_scan": "افحص نطاقك مجاناً", "cta_audit": "تدقيق كل النطاقات الفرعية العامة (ساما / NIS2 / DORA)",
        "archive": "الأسابيع السابقة", "data": "البيانات: CC BY 4.0 · JSON",
    },
    "de": {
        "title": "Wöchentlicher Post-Quanten-Tracker für Banken",
        "kicker": "Banken am Golf, in DACH und Europa · jeden Montag aktualisiert",
        "lead": "Welche Banken handeln auf ihrer Website einen Post-Quanten-Schlüsselaustausch (X25519MLKEM768) aus? "
                "Wir prüfen jede Woche die Startseite von {banks} Banken und Zentralbanken.",
        "meta": "{week}: {pq} von {n} beobachteten Banken ({pct} %) nutzen Post-Quanten-TLS auf der Startseite. "
                "Banken am Golf, in DACH und Europa, wöchentlich aktualisiert.",
        "changes": "Änderungen seit letzter Woche", "adopted": "Post-Quanten-Schlüsselaustausch aktiviert",
        "dropped": "Zurück zum klassischen Schlüsselaustausch", "no_changes": "Diese Woche hat keine Bank ihren Status geändert.",
        "first_week": "Erste beobachtete Woche: noch kein Vergleich.",
        "share": "{pq} von {n} ({pct} %)", "delta": "{d:+.1f} Prozentpunkte zur Vorwoche",
        "col_bank": "Website", "col_status": "Status", "col_since": "Post-Quanten seit",
        "pq": "Post-Quanten", "classic": "nur klassisch", "unsure": "unbestimmt", "down": "keine Antwort",
        "why_title": "Warum Compliance- und Security-Teams das verfolgen",
        "why": "NIS2 (Art. 21) und DORA (RTS 2024/1774) verlangen Kryptografie-Richtlinien nach dem Stand der Technik; "
               "SAMA-Rundschreiben 482021280 verlangt von saudischen Finanzinstituten ein Krypto-Inventar bis "
               "31. Dezember 2026. Die Startseite ist nur ein Host: Die meisten Banken betreiben Dutzende öffentliche Subdomains.",
        "limits": "Grenzen: ein öffentlicher HTTPS-Host je Bank (meist www), gemessen aus London. Interne Systeme, Apps "
                  "und Subdomains sind nicht erfasst. Ein klassisches Ergebnis ist heute keine Schwachstelle, zeigt aber "
                  "das Risiko „Harvest now, decrypt later“.",
        "cta_scan": "Eigene Domain kostenlos prüfen", "cta_audit": "Alle öffentlichen Subdomains prüfen lassen (NIS2 / DORA / SAMA)",
        "archive": "Frühere Wochen", "data": "Daten: CC BY 4.0 · JSON",
    },
}


def _pct(pq, n):
    return round(100.0 * pq / n, 1) if n else 0.0


def _status(row):
    if not row["ok"]:
        return "down"
    if row.get("unsure"):
        return "unsure"
    return "pq" if row["pq"] else "classic"


def weeks(conn):
    """Weeks that contain at least one tracked bank row (oldest first)."""
    marks = ",".join("?" * len(REGIONS))
    cur = conn.execute(f"SELECT DISTINCT week FROM adoption_results WHERE sector IN ({marks}) ORDER BY week", REGIONS)
    return [w for (w,) in cur]


def build(conn, week=None, watchlists=None):
    """The report for one week (default: latest). None when the week has no bank rows."""
    all_weeks = weeks(conn)
    if not all_weeks or (week is not None and week not in all_weeks):
        return None
    week = week or all_weeks[-1]
    i = all_weeks.index(week)
    previous = all_weeks[i - 1] if i else None
    watchlists = adoption.load_watchlists() if watchlists is None else watchlists
    since = adoption.first_pq_weeks(conn)
    cur_rows = [r for r in adoption.rows_for(conn, week) if r["sector"] in REGIONS]
    prev_rows = [r for r in adoption.rows_for(conn, previous) if r["sector"] in REGIONS] if previous else []
    regions, total_n, total_pq, prev_n, prev_pq = [], 0, 0, 0, 0
    for key in REGIONS:
        rows = [dict(r, status=_status(r), pq_since=since.get(r["domain"]) if r["pq"] else None)
                for r in cur_rows if r["sector"] == key]
        rows.sort(key=lambda r: (["pq", "classic", "unsure", "down"].index(r["status"]), r["domain"]))
        n = sum(1 for r in rows if adoption.measured(r))
        pq = sum(1 for r in rows if adoption.measured(r) and r["pq"])
        before = [r for r in prev_rows if r["sector"] == key and adoption.measured(r)]
        b_pq = sum(1 for r in before if r["pq"])
        diff = adoption.changes([r for r in prev_rows if r["sector"] == key], rows) if previous else None
        regions.append({"key": key, "labels": watchlists.get(key, {}).get("labels", {}), "rows": rows, "n": n, "pq": pq,
                        "pct": _pct(pq, n), "delta": round(_pct(pq, n) - _pct(b_pq, len(before)), 1) if before else None,
                        "adopted": [r["domain"] for r in (diff or {}).get("adopted", [])],
                        "dropped": [r["domain"] for r in (diff or {}).get("dropped", [])]})
        total_n, total_pq, prev_n, prev_pq = total_n + n, total_pq + pq, prev_n + len(before), prev_pq + b_pq
    return {"week": week, "week_start": adoption.week_monday(week).isoformat(), "previous": previous,
            "weeks": all_weeks, "regions": regions, "banks": sum(len(r["rows"]) for r in regions),
            "n": total_n, "pq": total_pq, "pct": _pct(total_pq, total_n),
            "delta": round(_pct(total_pq, total_n) - _pct(prev_pq, prev_n), 1) if prev_n else None,
            "adopted": [d for r in regions for d in r["adopted"]], "dropped": [d for r in regions for d in r["dropped"]]}


def _region(rep, key):
    return next(r for r in rep["regions"] if r["key"] == key)


def posts(rep):
    """Ready-to-post LinkedIn texts (owner posts them by hand). Plain numbers only, no claims beyond the data."""
    url = f"{SITE}/banks/weekly/{rep['week']}"
    g, d, e = (_region(rep, k) for k in REGIONS)
    news_en = (f"New this week: {', '.join(rep['adopted'])} enabled post-quantum key exchange."
               if rep["adopted"] else "No bank changed status this week.")
    news_ar = (f"الجديد هذا الأسبوع: {', '.join(rep['adopted'])} فعّل تبادل المفاتيح المقاوم للكم."
               if rep["adopted"] else "لم يتغير وضع أي بنك هذا الأسبوع.")
    news_de = (f"Neu diese Woche: {', '.join(rep['adopted'])} hat Post-Quanten-Schlüsselaustausch aktiviert."
               if rep["adopted"] else "Diese Woche hat keine Bank ihren Status geändert.")
    gulf_classic = [r["domain"] for r in g["rows"] if r["status"] == "classic"]
    return {
        "ar": f"""مؤشر البنوك الأسبوعي للتشفير المقاوم للحوسبة الكمومية ({rep['week']})

• بنوك الخليج والشرق الأوسط: {g['pq']} من {g['n']} موقعاً رئيسياً يستخدم X25519MLKEM768
• بنوك أوروبا: {e['pq']} من {e['n']}
• بنوك ألمانيا والنمسا وسويسرا: {d['pq']} من {d['n']}

{news_ar}

تعميم ساما 482021280 يطلب حصر أصول التشفير بنهاية 31 ديسمبر 2026. الموقع الرئيسي مضيف واحد فقط؛ النطاقات الفرعية العامة هي الجزء الأكبر من الحصر.

القائمة الكاملة والمنهجية: {url}?lang=ar&utm_source=linkedin
افحص نطاقك مجاناً: {SITE}/?lang=ar&utm_source=linkedin

#ساما #الأمن_السيبراني #البنوك #التشفير_ما_بعد_الكمي""",
        "en": f"""Weekly bank post-quantum TLS tracker ({rep['week']})

• European banks: {e['pq']} of {e['n']} homepages negotiate X25519MLKEM768
• DACH banks: {d['pq']} of {d['n']}
• Gulf & MENA banks: {g['pq']} of {g['n']}

{news_en}

NIS2 Art. 21 and DORA (RTS 2024/1774) expect state-of-the-art cryptography and crypto-agility. A homepage is one host; most banks expose dozens of public subdomains.

Full list + method: {url}?lang=en&utm_source=linkedin
Free check for your domain: {SITE}/?lang=en&utm_source=linkedin

#NIS2 #DORA #PostQuantum #CISO #Banking""",
        "de": f"""Wöchentlicher Post-Quanten-TLS-Tracker für Banken ({rep['week']})

• Banken in DACH: {d['pq']} von {d['n']} Startseiten nutzen X25519MLKEM768
• Banken in Europa: {e['pq']} von {e['n']}
• Banken am Golf / MENA: {g['pq']} von {g['n']}

{news_de}

NIS2 (Art. 21) und DORA verlangen Kryptografie nach dem Stand der Technik und Krypto-Agilität. Die Startseite ist nur ein Host; die meisten Banken betreiben Dutzende öffentliche Subdomains.

Vollständige Liste + Methode: {url}?lang=de&utm_source=linkedin
Eigene Domain kostenlos prüfen: {SITE}/?lang=de&utm_source=linkedin

#NIS2 #DORA #PostQuanten #Informationssicherheit""",
        "gulf_classic": gulf_classic,
    }


def as_text(rep):
    """Section appended to the Monday scorecard email."""
    if not rep:
        return "Weekly bank tracker: no data yet."
    p = posts(rep)
    head = (f"WEEKLY BANK TRACKER {rep['week']}: {rep['pq']}/{rep['n']} ({rep['pct']}%) · "
            f"new: {', '.join(rep['adopted']) or 'none'} · lost: {', '.join(rep['dropped']) or 'none'}\n"
            f"Page: {SITE}/banks/weekly/{rep['week']}\n")
    return head + "".join(f"\n--- LinkedIn post ({lang}) ---\n{p[lang]}\n" for lang in ("ar", "en", "de"))
