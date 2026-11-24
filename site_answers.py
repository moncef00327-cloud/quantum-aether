"""'Is <domain> quantum-safe?' answer pages (/site/<domain>, 2026-11-23).

Pattern of "is X down" sites: every page answers one question about one real host, with facts only from stored
port-443 TLS handshakes (weekly tracker or a recent live scan). Nothing here starts a scan or decides indexing;
the allow-list in search_indexing still decides which pages are indexed.
"""
import datetime as dt

CERT_MAX_AGE_DAYS = 90  # certificate facts from the last stored live handshake of this host, at most this old
RELATED_MAX = 8

TEXT = {
    "en": {
        "title": "Is {domain} quantum-safe? PQ-TLS check · Quantum Aether",
        "h1": "Is {domain} quantum-safe?",
        "verdict_yes": "",  # English uses site_verdict() from the app (quoted as-is by answer engines)
        "q_pq": "Is {domain} quantum-safe? Does it use post-quantum TLS?",
        "cert_note": " Website certificates are still classical (RSA/ECDSA) everywhere; post-quantum key exchange is what protects recorded traffic.",
        "q_tls": "Which TLS version and key exchange does {domain} use?",
        "a_tls": "In the handshake measured on {date}, {domain} negotiated {tls} with the key-exchange group {group}{cipher}.",
        "a_cipher": " and the cipher suite {cipher}",
        "q_cert": "Who issued the TLS certificate of {domain}, and when does it expire?",
        "a_cert": "The certificate observed on {date} was issued by {issuer}, uses a {key} key and is valid until {expiry}.",
        "q_peers": "How does {domain} compare with other websites?",
        "a_global": "In week {week}, {pq} of the {n} measured websites in the Tranco top {top} ({pct}%) negotiated post-quantum key exchange.",
        "a_country": " Among websites from {country} in the top 10,000: {pct}% ({pq} of {n}).",
        "a_sector": " In the {sector} watchlist: {pct}% ({pq} of {n}).",
        "a_self_yes": " {domain} is one of them.",
        "a_self_no": " {domain} is not one of them yet.",
        "q_when": "When was {domain} last checked?",
        "a_when": "The latest stored measurement of {domain} is from {date} (a TLS handshake on port 443, no other test). Anyone can run a free rescan at {url}.",
        "faq_title": "Questions about {domain}",
        "compare_title": "{domain} compared with other websites",
        "col_scope": "Group", "col_share": "Post-quantum share", "this_site": "This site",
        "scope_global": "Tranco top {top} ({week})", "scope_country": "Websites from {country}", "scope_sector": "Watchlist: {sector}",
        "pq_yes": "post-quantum", "pq_no": "classical", "pq_unsure": "undetermined",
        "plans_title": "Keep {domain} under watch",
        "plans_body": "Daily handshake checks with email alerts when post-quantum key exchange is lost or the grade changes: Starter {starter}/month (10 domains) or Business {business}/month (100 domains). 14-day free trial, no card.",
        "plans_cta": "See plans", "trial_cta": "Start the free trial",
        "explore_title": "Explore the data",
        "link_index": "PQ-TLS Index: banks, telecoms and governments",
        "link_adoption": "Weekly post-quantum adoption tracker",
        "link_countries": "Post-quantum adoption by country",
        "link_country": "{country}: post-quantum adoption",
        "related_country": "Other websites from {country}",
        "related_sector": "Same watchlist: {sector}",
    },
    "ar": {
        "title": "هل {domain} آمن من الحوسبة الكمّية؟ فحص PQ-TLS · Quantum Aether",
        "h1": "هل {domain} آمن من الحوسبة الكمّية؟",
        "verdict_yes": "نعم. بتاريخ {date} يتفق {domain} على تبادل المفاتيح الهجين المقاوم للحوسبة الكمّية {group} عبر {tls} (درجة Quantum Aether: {grade}).",
        "verdict_no": "لا. بتاريخ {date} لا يتفق {domain} على تبادل مفاتيح مقاوم للحوسبة الكمّية؛ يستخدم {group} عبر {tls} (درجة Quantum Aether: {grade})، فالحركة المسجّلة اليوم معرّضة لهجوم «اجمع الآن وفكّ لاحقاً».",
        "verdict_unsure": "بتاريخ {date} لم نتمكن من تحديد ما إذا كان {domain} يتفق على تبادل مفاتيح مقاوم للحوسبة الكمّية: رفض الخادم أو جدار الحماية مصافحتنا.",
        "classical": "تبادل مفاتيح تقليدي",
        "q_pq": "هل {domain} آمن من الحوسبة الكمّية؟ هل يستخدم TLS ما بعد الكمّي؟",
        "cert_note": " الشهادات على الويب ما زالت تقليدية (RSA/ECDSA) في كل مكان؛ تبادل المفاتيح ما بعد الكمّي هو ما يحمي الحركة المسجّلة.",
        "q_tls": "ما إصدار TLS وتبادل المفاتيح الذي يستخدمه {domain}؟",
        "a_tls": "في المصافحة المقيسة بتاريخ {date} اتفق {domain} على {tls} مع مجموعة تبادل المفاتيح {group}{cipher}.",
        "a_cipher": " ومجموعة التشفير {cipher}",
        "q_cert": "من أصدر شهادة TLS لـ {domain} ومتى تنتهي؟",
        "a_cert": "الشهادة المرصودة بتاريخ {date} صادرة عن {issuer}، بمفتاح {key}، وصالحة حتى {expiry}.",
        "q_peers": "كيف يقارن {domain} بالمواقع الأخرى؟",
        "a_global": "في الأسبوع {week} اتفق {pq} من أصل {n} موقعاً مقيساً ضمن أكبر {top} موقع في Tranco ({pct}%) على تبادل مفاتيح مقاوم للحوسبة الكمّية.",
        "a_country": " بين مواقع {country} ضمن أكبر 10,000 موقع: {pct}% ({pq} من {n}).",
        "a_sector": " في قائمة المراقبة «{sector}»: {pct}% ({pq} من {n}).",
        "a_self_yes": " و{domain} واحد منها.",
        "a_self_no": " و{domain} ليس منها بعد.",
        "q_when": "متى فُحص {domain} آخر مرة؟",
        "a_when": "آخر قياس محفوظ لـ {domain} بتاريخ {date} (مصافحة TLS على المنفذ 443 فقط، بلا أي اختبار آخر). يمكن لأي شخص إعادة الفحص مجاناً على {url}.",
        "faq_title": "أسئلة عن {domain}",
        "compare_title": "{domain} مقارنة بالمواقع الأخرى",
        "col_scope": "المجموعة", "col_share": "نسبة المقاوم للكم", "this_site": "هذا الموقع",
        "scope_global": "أكبر {top} موقع في Tranco ({week})", "scope_country": "مواقع {country}", "scope_sector": "قائمة المراقبة: {sector}",
        "pq_yes": "مقاوم للكم", "pq_no": "تقليدي", "pq_unsure": "غير محسوم",
        "plans_title": "راقب {domain} باستمرار",
        "plans_body": "فحص يومي للمصافحة مع تنبيه بالبريد إذا فُقد تبادل المفاتيح المقاوم للكم أو تغيّرت الدرجة: Starter بـ {starter} شهرياً (10 نطاقات) أو Business بـ {business} شهرياً (100 نطاق). تجربة مجانية 14 يوماً بلا بطاقة.",
        "plans_cta": "الباقات والأسعار", "trial_cta": "ابدأ التجربة المجانية",
        "explore_title": "استكشف البيانات",
        "link_index": "مؤشر PQ-TLS: البنوك والاتصالات والجهات الحكومية",
        "link_adoption": "المتتبّع الأسبوعي لاعتماد TLS ما بعد الكمّي",
        "link_countries": "الاعتماد حسب الدولة",
        "link_country": "{country}: اعتماد TLS ما بعد الكمّي",
        "related_country": "مواقع أخرى من {country}",
        "related_sector": "من قائمة المراقبة نفسها: {sector}",
    },
    "de": {
        "title": "Ist {domain} quantensicher? PQ-TLS-Check · Quantum Aether",
        "h1": "Ist {domain} quantensicher?",
        "verdict_yes": "Ja. Am {date} handelt {domain} den hybriden Post-Quanten-Schlüsselaustausch {group} über {tls} aus (Quantum-Aether-Note {grade}).",
        "verdict_no": "Nein. Am {date} handelt {domain} keinen Post-Quanten-Schlüsselaustausch aus; verwendet wird {group} über {tls} (Quantum-Aether-Note {grade}), aufgezeichneter Verkehr ist also „Harvest now, decrypt later“ ausgesetzt.",
        "verdict_unsure": "Am {date} konnten wir nicht feststellen, ob {domain} Post-Quanten-Schlüsselaustausch aushandelt: Server oder Firewall haben unseren Handshake abgelehnt.",
        "classical": "klassischer Schlüsselaustausch",
        "q_pq": "Ist {domain} quantensicher? Nutzt die Website Post-Quanten-TLS?",
        "cert_note": " Website-Zertifikate sind überall noch klassisch (RSA/ECDSA); aufgezeichneten Verkehr schützt der Post-Quanten-Schlüsselaustausch.",
        "q_tls": "Welche TLS-Version und welchen Schlüsselaustausch nutzt {domain}?",
        "a_tls": "Im Handshake vom {date} hat {domain} {tls} mit der Schlüsselaustausch-Gruppe {group}{cipher} ausgehandelt.",
        "a_cipher": " und der Cipher-Suite {cipher}",
        "q_cert": "Wer hat das TLS-Zertifikat von {domain} ausgestellt, und wann läuft es ab?",
        "a_cert": "Das am {date} beobachtete Zertifikat wurde von {issuer} ausgestellt, nutzt einen {key}-Schlüssel und ist bis {expiry} gültig.",
        "q_peers": "Wie schneidet {domain} im Vergleich ab?",
        "a_global": "In Woche {week} haben {pq} von {n} gemessenen Websites der Tranco-Top-{top} ({pct} %) Post-Quanten-Schlüsselaustausch ausgehandelt.",
        "a_country": " Unter den Websites aus {country} in den Top 10.000: {pct} % ({pq} von {n}).",
        "a_sector": " In der Beobachtungsliste {sector}: {pct} % ({pq} von {n}).",
        "a_self_yes": " {domain} gehört dazu.",
        "a_self_no": " {domain} gehört noch nicht dazu.",
        "q_when": "Wann wurde {domain} zuletzt geprüft?",
        "a_when": "Die letzte gespeicherte Messung von {domain} stammt vom {date} (TLS-Handshake auf Port 443, kein anderer Test). Jeder kann unter {url} kostenlos neu prüfen.",
        "faq_title": "Fragen zu {domain}",
        "compare_title": "{domain} im Vergleich",
        "col_scope": "Gruppe", "col_share": "Anteil Post-Quanten", "this_site": "Diese Website",
        "scope_global": "Tranco-Top-{top} ({week})", "scope_country": "Websites aus {country}", "scope_sector": "Beobachtungsliste: {sector}",
        "pq_yes": "Post-Quanten", "pq_no": "klassisch", "pq_unsure": "unbestimmt",
        "plans_title": "{domain} dauerhaft überwachen",
        "plans_body": "Tägliche Handshake-Prüfung mit E-Mail-Alarm, wenn der Post-Quanten-Schlüsselaustausch verloren geht oder sich die Note ändert: Starter {starter}/Monat (10 Domains) oder Business {business}/Monat (100 Domains). 14 Tage kostenlos testen, ohne Karte.",
        "plans_cta": "Tarife ansehen", "trial_cta": "Kostenlos testen",
        "explore_title": "Daten erkunden",
        "link_index": "PQ-TLS-Index: Banken, Telcos und Behörden",
        "link_adoption": "Wöchentlicher Post-Quanten-Tracker",
        "link_countries": "Post-Quanten-Verbreitung nach Ländern",
        "link_country": "{country}: Post-Quanten-Verbreitung",
        "related_country": "Weitere Websites aus {country}",
        "related_sector": "Gleiche Beobachtungsliste: {sector}",
    },
}


def texts(lang):
    return TEXT.get(lang) or TEXT["en"]


def h1_parts(lang):
    """The H1 question split around the domain, so the template can wrap the host in <bdi> (Arabic stays readable)."""
    before, _, after = texts(lang)["h1"].partition("{domain}")
    return before, after


def title(domain, lang):
    return texts(lang)["title"].format(domain=domain)


def _tls(value):
    return (value or "TLS").replace("TLSv", "TLS ")


def verdict(domain, summary, lang, english_verdict):
    """One quotable sentence. English keeps the app's existing site_verdict(); ar/de say the same facts."""
    if lang not in ("ar", "de"):
        return english_verdict
    t = texts(lang)
    day = str(summary.get("scanned_at", ""))[:10]
    if summary.get("unsure"):
        return t["verdict_unsure"].format(domain=domain, date=day)
    key = "verdict_yes" if summary.get("pq") else "verdict_no"
    group = summary.get("group") or ("X25519MLKEM768" if summary.get("pq") else t["classical"])
    return t[key].format(domain=domain, date=day, group=group, tls=_tls(summary.get("tls") or ("TLSv1.3" if summary.get("pq") else None)),
                         grade=summary.get("grade"))


def cert_facts(result, today=None):
    """Certificate and cipher facts from one stored scan result (the same port-443 handshake), or None."""
    if not result:
        return None
    cert = result.get("certificate") or {}
    kx = result.get("key_exchange") or {}
    today = today or dt.datetime.now(dt.timezone.utc).date()
    expiry, days_left = None, None
    if cert.get("not_after"):
        try:
            expiry = dt.datetime.fromisoformat(str(cert["not_after"]).replace("Z", "+00:00")).date()
            days_left = (expiry - today).days
        except ValueError:
            expiry = None
    alg, bits = cert.get("key_algorithm"), cert.get("key_bits")
    key = None
    if alg and alg != "unknown":
        key = f"{alg}-{bits}" if bits else alg
        if cert.get("curve"):
            key += f" ({cert['curve']})"
    facts = {"issuer": cert.get("issuer"), "key": key, "signature": cert.get("signature_algorithm"),
             "expiry": expiry.isoformat() if expiry else None, "days_left": days_left,
             "verified": cert.get("verified"), "cipher": kx.get("cipher"),
             "scanned_at": str(result.get("scanned_at") or "")[:10]}
    return facts if any(facts[k] for k in ("issuer", "key", "expiry", "cipher")) else None


def _pct(pq, n):
    return round(100.0 * pq / n, 1) if n else 0.0


def comparison(snapshot, country, sector_key, lang):
    """Rows for the comparison table: all tracked sites, the domain's country (ccTLD), its watchlist sector."""
    t = texts(lang)
    rows = []
    tier = (snapshot or {}).get("top10k") or (
        {"top": 1000, "reachable": snapshot["reachable"], "pq": snapshot["pq"], "pct": snapshot["pct"]}
        if snapshot and snapshot.get("reachable") else None)
    if tier and tier.get("reachable"):
        top = f"{tier['top']:,}".replace(",", "." if lang == "de" else ",")
        rows.append({"kind": "global", "label": t["scope_global"].format(week=snapshot["week"], top=top), "top": top,
                     "pct": tier["pct"], "pq": tier["pq"], "n": tier["reachable"], "week": snapshot["week"]})
    if country and country.get("measured"):
        rows.append({"kind": "country", "label": t["scope_country"].format(country=country["name"]),
                     "pct": country["pct"], "pq": country["pq"], "n": country["measured"], "name": country["name"],
                     "code": country["code"]})
    if snapshot and sector_key:
        sector = next((s for s in snapshot.get("sectors", ()) if s["key"] == sector_key), None)
        if sector and sector.get("reachable"):
            labels = sector.get("labels") or {}
            name = labels.get(lang) or labels.get("en") or sector_key
            rows.append({"kind": "sector", "key": sector_key, "label": t["scope_sector"].format(sector=name), "name": name,
                         "pct": _pct(sector["pq"], sector["reachable"]), "pq": sector["pq"], "n": sector["reachable"]})
    return rows


def faq(domain, summary, lang, verdict_text, cert=None, compare_rows=(), rescan_url=""):
    """Visible Q&A; the FAQPage JSON-LD uses exactly this list. Every answer is a stored fact or omitted."""
    t = texts(lang)
    day = str(summary.get("scanned_at", ""))[:10]
    items = [(t["q_pq"].format(domain=domain), verdict_text + t["cert_note"])]
    if summary.get("tls") and summary.get("group"):
        cipher = t["a_cipher"].format(cipher=cert["cipher"]) if cert and cert.get("cipher") else ""
        items.append((t["q_tls"].format(domain=domain),
                      t["a_tls"].format(date=day, domain=domain, tls=_tls(summary["tls"]), group=summary["group"], cipher=cipher)))
    if cert and cert.get("issuer") and cert.get("key") and cert.get("expiry"):
        items.append((t["q_cert"].format(domain=domain),
                      t["a_cert"].format(date=cert["scanned_at"], issuer=cert["issuer"], key=cert["key"], expiry=cert["expiry"])))
    by_kind = {r["kind"]: r for r in compare_rows}
    if "global" in by_kind:
        g = by_kind["global"]
        answer = t["a_global"].format(week=g["week"], pct=g["pct"], n=g["n"], pq=g["pq"], top=g["top"])
        if "country" in by_kind:
            c = by_kind["country"]
            answer += t["a_country"].format(country=c["name"], pct=c["pct"], pq=c["pq"], n=c["n"])
        if "sector" in by_kind:
            s = by_kind["sector"]
            answer += t["a_sector"].format(sector=s["name"], pct=s["pct"], pq=s["pq"], n=s["n"])
        if not summary.get("unsure"):
            answer += t["a_self_yes" if summary.get("pq") else "a_self_no"].format(domain=domain)
        items.append((t["q_peers"].format(domain=domain), answer))
    items.append((t["q_when"].format(domain=domain), t["a_when"].format(domain=domain, date=day, url=rescan_url)))
    return [{"q": q, "a": a} for q, a in items]


def faq_jsonld(items):
    return {"@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": i["q"], "acceptedAnswer": {"@type": "Answer", "text": i["a"]}}
                           for i in items]}


def country_peers(conn, domain, code, week, limit=40):
    """Top-ranked sites with the same country-code TLD in the same week (candidates; the app filters indexability)."""
    if not (code and week):
        return []
    cur = conn.execute("SELECT domain, rank, sector, grade, pq, unsure FROM adoption_results WHERE week = ? AND ok = 1 "
                       "AND rank IS NOT NULL AND domain LIKE ? AND domain <> ? ORDER BY rank LIMIT ?",
                       (week, "%." + code, domain, limit))
    return [dict(r) for r in cur if r["domain"].rsplit(".", 1)[-1].lower() == code]


def sector_peers(conn, domain, sector, week, limit=40):
    if not (sector and week):
        return []
    cur = conn.execute("SELECT domain, rank, sector, grade, pq, unsure FROM adoption_results WHERE week = ? AND ok = 1 "
                       "AND sector = ? AND domain <> ? ORDER BY rank IS NULL, rank, domain LIMIT ?",
                       (week, sector, domain, limit))
    return [dict(r) for r in cur]


def money(amount, currency):
    value = float(amount)
    shown = str(int(value)) if value.is_integer() else f"{value:.2f}"
    return f"{shown} €" if currency == "EUR" else f"{shown} {currency}"
