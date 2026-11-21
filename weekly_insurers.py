"""Weekly DACH insurer post-quantum tracker (/insurers/weekly): statutory health funds and private / composite
insurers in Germany, Austria and Switzerland from the weekly adoption scan (homepage host only). Built live from
adoption_results like weekly_banks, so every Monday scan publishes a new week automatically."""
import adoption
from weekly_banks import _pct, _status

SECTOR = "health-insurance-dach"
SITE = "https://ather-quantum.com"
COUNTRIES = ["DE", "AT", "CH"]
# Domains that are not on a country TLD.
COUNTRY_OVERRIDE = {"www.sbk.org": "DE", "www.munichre.com": "DE", "www.helvetia.com": "CH",
                    "www.sanitas.com": "CH", "www.swissre.com": "CH"}
# Statutory / public-law bodies (gesetzliche Krankenkassen, Sozialversicherung, gematik, KBV).
STATUTORY = {"www.aok.de", "www.barmer.de", "www.dak.de", "www.tk.de", "www.kkh.de", "www.knappschaft.de",
             "www.audi-bkk.de", "www.mhplus.de", "www.sbk.org", "www.viactiv.de", "www.bahn-bkk.de",
             "www.ikk-classic.de", "www.pronovabkk.de", "www.gematik.de", "www.kbv.de", "www.gesundheitskasse.at",
             "www.svs.at", "www.bvaeb.at", "www.pv.at", "www.sozialversicherung.at", "www.auva.at",
             "www.gesundheit.gv.at"}

COPY = {
    "de": {
        "title": "Post-Quanten-Tracker: Versicherer und Krankenkassen in DACH",
        "seo_title": "Versicherer in DACH: Post-Quanten-Tracker",
        "kicker": "Deutschland, Österreich, Schweiz · jeden Montag aktualisiert",
        "lead": "Welche Versicherer und Krankenkassen handeln auf ihrer Website bereits einen Post-Quanten-"
                "Schlüsselaustausch (X25519MLKEM768) aus? Wir prüfen jede Woche die Startseite von {total} "
                "Krankenkassen, Kranken- und Kompositversicherern.",
        "meta": "{week}: {pq} von {n} Versicherern und Krankenkassen in DACH ({pct} %) nutzen Post-Quanten-TLS "
                "auf der Startseite. Wöchentlich aktualisiert, mit Liste und Methode.",
        "changes": "Änderungen seit letzter Woche", "adopted": "Post-Quanten-Schlüsselaustausch aktiviert",
        "dropped": "Zurück zum klassischen Schlüsselaustausch",
        "no_changes": "Diese Woche hat kein Versicherer seinen Status geändert.",
        "first_week": "Erste beobachtete Woche: noch kein Vergleich.",
        "share": "{pq} von {n} ({pct} %)",
        "countries": {"DE": "Deutschland", "AT": "Österreich", "CH": "Schweiz"},
        "col_site": "Website", "col_type": "Art", "col_status": "Status", "col_since": "Post-Quanten seit",
        "statutory": "gesetzlich / öffentlich", "private": "privat",
        "pq": "Post-Quanten", "classic": "nur klassisch", "unsure": "unbestimmt", "down": "keine Antwort",
        "why_title": "Warum das für Versicherer jetzt relevant ist",
        "why": "Gesundheits- und Versicherungsdaten bleiben jahrzehntelang sensibel: genau das Ziel von "
               "„Harvest now, decrypt later“. NIST hat mit IR 8547 (final, Oktober 2026) RSA und ECC ab 2030 als "
               "veraltet und ab 2035 als unzulässig eingestuft, unabhängig von der Schlüssellänge. Die EU erwartet "
               "nationale Übergangspläne bis Ende 2026 und die Umstellung kritischer Infrastrukturen bis 2030. "
               "DORA gilt seit Januar 2025 auch für Versicherungsunternehmen und verlangt Kryptografie nach dem "
               "Stand der Technik.",
        "limits": "Grenzen: ein öffentlicher HTTPS-Host je Unternehmen (meist www), gemessen aus London. "
                  "Versichertenportale, Apps, Schnittstellen und Subdomains sind nicht erfasst. Ein klassisches "
                  "Ergebnis ist heute keine Schwachstelle; es zeigt, wo das Risiko „Harvest now, decrypt later“ "
                  "noch besteht. Häufig liegt die Lösung beim CDN oder Load Balancer, nicht beim Unternehmen selbst.",
        "cta_scan": "Eigene Domain kostenlos prüfen",
        "cta_audit": "Alle öffentlichen Subdomains prüfen lassen (DORA / NIS2)",
        "archive": "Frühere Wochen", "data": "Daten: CC BY 4.0 · JSON",
        "optout": "Sie vertreten ein gelistetes Unternehmen? Korrekturen und Fragen über das Impressum.",
    },
    "en": {
        "title": "Post-quantum tracker: DACH insurers and health funds",
        "seo_title": "DACH insurers: post-quantum TLS tracker",
        "kicker": "Germany, Austria, Switzerland · updated every Monday",
        "lead": "Which insurers and health funds already negotiate a post-quantum key exchange (X25519MLKEM768) on "
                "their website? Every week we test the homepage of {total} statutory health funds, health and "
                "composite insurers.",
        "meta": "{week}: {pq} of {n} DACH insurers and health funds ({pct}%) use post-quantum TLS on their homepage. "
                "Updated weekly, with list and method.",
        "changes": "Changes since last week", "adopted": "Enabled post-quantum key exchange",
        "dropped": "Went back to classical key exchange", "no_changes": "No insurer changed status this week.",
        "first_week": "First tracked week: no comparison yet.",
        "share": "{pq} of {n} ({pct}%)",
        "countries": {"DE": "Germany", "AT": "Austria", "CH": "Switzerland"},
        "col_site": "Website", "col_type": "Type", "col_status": "Status", "col_since": "Post-quantum since",
        "statutory": "statutory / public", "private": "private",
        "pq": "post-quantum", "classic": "classical only", "unsure": "undetermined", "down": "no answer",
        "why_title": "Why this matters for insurers now",
        "why": "Health and insurance data stays sensitive for decades, which is exactly what harvest-now-decrypt-later "
               "targets. NIST IR 8547 (final, October 2026) deprecates RSA and ECC after 2030 and disallows them "
               "after 2035 at any key size. The EU expects national transition plans by the end of 2026 and critical "
               "infrastructure migrated by 2030. DORA has applied to insurance undertakings since January 2025 and "
               "requires state-of-the-art cryptography.",
        "limits": "Limits: one public HTTPS host per organisation (usually www), tested from London. Member portals, "
                  "apps, APIs and subdomains are not covered. A classical result is not a vulnerability today; it "
                  "shows where harvest-now-decrypt-later exposure remains. The fix often sits with the CDN or load "
                  "balancer rather than the insurer itself.",
        "cta_scan": "Check your own domain for free", "cta_audit": "Audit every public subdomain (DORA / NIS2)",
        "archive": "Earlier weeks", "data": "Data: CC BY 4.0 · JSON",
        "optout": "Representing a listed organisation? Corrections and questions via the imprint.",
    },
    "ar": {
        "title": "متتبع التشفير المقاوم للكم: شركات التأمين وصناديق التأمين الصحي في ألمانيا والنمسا وسويسرا",
        "seo_title": "شركات التأمين في DACH والتشفير المقاوم للكم",
        "kicker": "ألمانيا والنمسا وسويسرا · يُحدَّث كل اثنين",
        "lead": "أيّ شركات التأمين وصناديق التأمين الصحي تتفاوض مواقعها على تبادل مفاتيح مقاوم للحوسبة الكمومية "
                "(X25519MLKEM768)؟ نفحص كل أسبوع الموقع الرئيسي لـ {total} جهة.",
        "meta": "{week}: {pq} من {n} من شركات التأمين في ألمانيا والنمسا وسويسرا ({pct}%) تستخدم TLS مقاوماً للكم.",
        "changes": "التغييرات منذ الأسبوع الماضي", "adopted": "فعّلت تبادل المفاتيح المقاوم للكم",
        "dropped": "عادت إلى التبادل التقليدي", "no_changes": "لم يتغير وضع أي جهة هذا الأسبوع.",
        "first_week": "أول أسبوع مرصود: لا مقارنة بعد.",
        "share": "{pq} من {n} ({pct}%)",
        "countries": {"DE": "ألمانيا", "AT": "النمسا", "CH": "سويسرا"},
        "col_site": "الموقع", "col_type": "النوع", "col_status": "الحالة", "col_since": "مقاوم للكم منذ",
        "statutory": "قانوني / عام", "private": "خاص",
        "pq": "مقاوم للكم", "classic": "تقليدي فقط", "unsure": "غير محدد", "down": "لا استجابة",
        "why_title": "لماذا يهم هذا شركات التأمين الآن",
        "why": "بيانات الصحة والتأمين تبقى حساسة لعقود، وهذا بالضبط ما تستهدفه هجمات «اجمع الآن وافكّ لاحقاً». "
               "صنّف NIST في IR 8547 (النهائي، أكتوبر 2026) خوارزميات RSA وECC كمتقادمة بعد 2030 وممنوعة بعد 2035 "
               "مهما كان طول المفتاح، ويطلب الاتحاد الأوروبي خططاً وطنية بنهاية 2026، وتنطبق DORA على شركات التأمين.",
        "limits": "الحدود: مضيف HTTPS عام واحد لكل جهة (غالباً www)، يُفحص من لندن. لا يشمل بوابات المؤمَّن عليهم "
                  "ولا التطبيقات ولا النطاقات الفرعية. النتيجة التقليدية ليست ثغرة اليوم.",
        "cta_scan": "افحص نطاقك مجاناً", "cta_audit": "تدقيق كل النطاقات الفرعية العامة (DORA / NIS2)",
        "archive": "الأسابيع السابقة", "data": "البيانات: CC BY 4.0 · JSON",
        "optout": "تمثّل جهة مدرجة؟ للتصحيح والأسئلة راجع صفحة البيانات القانونية.",
    },
}


def country_of(domain):
    if domain in COUNTRY_OVERRIDE:
        return COUNTRY_OVERRIDE[domain]
    tld = domain.rsplit(".", 1)[-1].upper()
    return tld if tld in COUNTRIES else None


def weeks(conn):
    cur = conn.execute("SELECT DISTINCT week FROM adoption_results WHERE sector = ? ORDER BY week", (SECTOR,))
    return [w for (w,) in cur]


def build(conn, week=None):
    """The report for one week (default: latest). None when the week has no insurer rows."""
    all_weeks = weeks(conn)
    if not all_weeks or (week is not None and week not in all_weeks):
        return None
    week = week or all_weeks[-1]
    i = all_weeks.index(week)
    previous = all_weeks[i - 1] if i else None
    since = adoption.first_pq_weeks(conn)
    cur_rows = [r for r in adoption.rows_for(conn, week) if r["sector"] == SECTOR]
    prev_rows = [r for r in adoption.rows_for(conn, previous) if r["sector"] == SECTOR] if previous else []
    groups, total_n, total_pq = [], 0, 0
    for key in COUNTRIES:
        rows = [dict(r, status=_status(r), statutory=r["domain"] in STATUTORY,
                     pq_since=since.get(r["domain"]) if r["pq"] else None)
                for r in cur_rows if country_of(r["domain"]) == key]
        if not rows:
            continue
        rows.sort(key=lambda r: (["pq", "classic", "unsure", "down"].index(r["status"]), r["domain"]))
        n = sum(1 for r in rows if adoption.measured(r))
        pq = sum(1 for r in rows if adoption.measured(r) and r["pq"])
        groups.append({"key": key, "rows": rows, "n": n, "pq": pq, "pct": _pct(pq, n)})
        total_n, total_pq = total_n + n, total_pq + pq
    measured = [r for g in groups for r in g["rows"] if adoption.measured(r)]
    private = [r for r in measured if not r["statutory"]]
    statutory = [r for r in measured if r["statutory"]]
    diff = adoption.changes(prev_rows, cur_rows) if previous else {}
    return {"week": week, "week_start": adoption.week_monday(week).isoformat(), "previous": previous,
            "weeks": all_weeks, "groups": groups, "total": sum(len(g["rows"]) for g in groups),
            "n": total_n, "pq": total_pq, "pct": _pct(total_pq, total_n),
            "private": {"n": len(private), "pq": sum(r["pq"] for r in private),
                        "pct": _pct(sum(r["pq"] for r in private), len(private))},
            "statutory": {"n": len(statutory), "pq": sum(r["pq"] for r in statutory),
                          "pct": _pct(sum(r["pq"] for r in statutory), len(statutory))},
            "adopted": [r["domain"] for r in (diff or {}).get("adopted", [])],
            "dropped": [r["domain"] for r in (diff or {}).get("dropped", [])]}


def as_text(rep):
    """Section appended to the Monday scorecard email: numbers, changes, ready-to-post texts.
    Private insurers still classical are listed for LinkedIn mentions only — never for cold email (UWG/TKG)."""
    if not rep:
        return "Weekly DACH insurer tracker: no data yet."
    classic = [r["domain"] for g in rep["groups"] for r in g["rows"] if r["status"] == "classic" and not r["statutory"]]
    head = (f"WEEKLY DACH INSURER TRACKER {rep['week']}: {rep['pq']}/{rep['n']} ({rep['pct']}%) · "
            f"private {rep['private']['pct']}% · statutory {rep['statutory']['pct']}% · "
            f"new: {', '.join(rep['adopted']) or 'none'} · lost: {', '.join(rep['dropped']) or 'none'}\n"
            f"Page: {SITE}/insurers/weekly/{rep['week']}?lang=de\n"
            f"Private insurers still classical ({len(classic)}; for LinkedIn mentions, NOT email): "
            f"{', '.join(classic) or 'none'}\n")
    p = posts(rep)
    return head + "".join(f"\n--- LinkedIn post ({lang}) ---\n{p[lang]}\n" for lang in ("de", "en"))


def posts(rep):
    """Ready-to-post LinkedIn texts in German and English (owner posts them by hand). Numbers only."""
    url = f"{SITE}/insurers/weekly/{rep['week']}"
    by = {g["key"]: g for g in rep["groups"]}
    line = lambda k, label, fmt: f"• {label}: {by[k]['pq']} {fmt} {by[k]['n']}" if k in by else ""
    de_pct = lambda v: f"{v}".replace(".", ",")
    if not rep["previous"]:
        news_de, news_en = "Erste Messung, ab jetzt jeden Montag.", "First measurement; updated every Monday from now on."
    else:
        news_de = (f"Neu diese Woche: {', '.join(rep['adopted'])}." if rep["adopted"]
                   else "Diese Woche keine Statusänderung.")
        news_en = (f"New this week: {', '.join(rep['adopted'])}." if rep["adopted"] else "No status change this week.")
    return {
        "de": f"""Post-Quanten-Check: Versicherer und Krankenkassen in DACH ({rep['week']})

{rep['pq']} von {rep['n']} Startseiten ({de_pct(rep['pct'])} %) handeln X25519MLKEM768 aus.
{line('DE', 'Deutschland', 'von')}
{line('AT', 'Österreich', 'von')}
{line('CH', 'Schweiz', 'von')}
• Private Versicherer: {de_pct(rep['private']['pct'])} % · gesetzliche Kassen: {de_pct(rep['statutory']['pct'])} %

{news_de}

Gesundheitsdaten bleiben jahrzehntelang sensibel. NIST IR 8547 (final) stuft RSA/ECC ab 2030 als veraltet ein, die EU erwartet die Umstellung kritischer Infrastrukturen bis 2030.

Liste + Methode: {url}?lang=de&utm_source=linkedin&utm_campaign=insurers_{rep['week']}

#Versicherung #Krankenkasse #DORA #PostQuanten #Informationssicherheit""",
        "en": f"""Post-quantum check: DACH insurers and health funds ({rep['week']})

{rep['pq']} of {rep['n']} homepages ({rep['pct']}%) negotiate X25519MLKEM768.
{line('DE', 'Germany', 'of')}
{line('AT', 'Austria', 'of')}
{line('CH', 'Switzerland', 'of')}
• Private insurers: {rep['private']['pct']}% · statutory funds: {rep['statutory']['pct']}%

{news_en}

Health data stays sensitive for decades. NIST IR 8547 (final) deprecates RSA/ECC after 2030; the EU expects critical infrastructure migrated by 2030.

List + method: {url}?lang=en&utm_source=linkedin&utm_campaign=insurers_{rep['week']}

#Insurance #DORA #PostQuantum #CISO""",
    }
