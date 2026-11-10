# countries.py
# ترتيب الدول: نسبة المواقع التي تتفق على X25519MLKEM768 بين نطاقات المتتبّع الأسبوعي (أكبر 10 آلاف في Tranco)
# حسب امتداد الدولة في النطاق (.de و.fr...). الامتداد تقريب لا يطابق مكان الخادم أو الشركة، ونقول ذلك في الصفحة.
# الامتدادات التي تُباع عالمياً (.io و.ai و.tv و.co و.me...) مستبعدة لأنها لا تدل على دولة.
MIN_SITES = 20   # لا ندرج دولة بأقل من 20 موقعاً مُقاساً: العيّنة أصغر من أن تُقارن

# الرمز: (en, ar, de, رمز ISO للعلم)
COUNTRIES = {
    "de": ("Germany", "ألمانيا", "Deutschland", "DE"), "at": ("Austria", "النمسا", "Österreich", "AT"),
    "ch": ("Switzerland", "سويسرا", "Schweiz", "CH"), "fr": ("France", "فرنسا", "Frankreich", "FR"),
    "it": ("Italy", "إيطاليا", "Italien", "IT"), "es": ("Spain", "إسبانيا", "Spanien", "ES"),
    "pt": ("Portugal", "البرتغال", "Portugal", "PT"), "nl": ("Netherlands", "هولندا", "Niederlande", "NL"),
    "be": ("Belgium", "بلجيكا", "Belgien", "BE"), "lu": ("Luxembourg", "لوكسمبورغ", "Luxemburg", "LU"),
    "uk": ("United Kingdom", "المملكة المتحدة", "Vereinigtes Königreich", "GB"), "ie": ("Ireland", "أيرلندا", "Irland", "IE"),
    "dk": ("Denmark", "الدنمارك", "Dänemark", "DK"), "se": ("Sweden", "السويد", "Schweden", "SE"),
    "no": ("Norway", "النرويج", "Norwegen", "NO"), "fi": ("Finland", "فنلندا", "Finnland", "FI"),
    "is": ("Iceland", "آيسلندا", "Island", "IS"), "pl": ("Poland", "بولندا", "Polen", "PL"),
    "cz": ("Czechia", "التشيك", "Tschechien", "CZ"), "sk": ("Slovakia", "سلوفاكيا", "Slowakei", "SK"),
    "hu": ("Hungary", "المجر", "Ungarn", "HU"), "ro": ("Romania", "رومانيا", "Rumänien", "RO"),
    "bg": ("Bulgaria", "بلغاريا", "Bulgarien", "BG"), "gr": ("Greece", "اليونان", "Griechenland", "GR"),
    "hr": ("Croatia", "كرواتيا", "Kroatien", "HR"), "si": ("Slovenia", "سلوفينيا", "Slowenien", "SI"),
    "rs": ("Serbia", "صربيا", "Serbien", "RS"), "ua": ("Ukraine", "أوكرانيا", "Ukraine", "UA"),
    "ru": ("Russia", "روسيا", "Russland", "RU"), "by": ("Belarus", "بيلاروسيا", "Belarus", "BY"),
    "ee": ("Estonia", "إستونيا", "Estland", "EE"), "lv": ("Latvia", "لاتفيا", "Lettland", "LV"),
    "lt": ("Lithuania", "ليتوانيا", "Litauen", "LT"), "tr": ("Türkiye", "تركيا", "Türkei", "TR"),
    "il": ("Israel", "إسرائيل", "Israel", "IL"), "ae": ("United Arab Emirates", "الإمارات", "Vereinigte Arabische Emirate", "AE"),
    "sa": ("Saudi Arabia", "السعودية", "Saudi-Arabien", "SA"), "qa": ("Qatar", "قطر", "Katar", "QA"),
    "kw": ("Kuwait", "الكويت", "Kuwait", "KW"), "eg": ("Egypt", "مصر", "Ägypten", "EG"),
    "ma": ("Morocco", "المغرب", "Marokko", "MA"), "dz": ("Algeria", "الجزائر", "Algerien", "DZ"),
    "tn": ("Tunisia", "تونس", "Tunesien", "TN"), "jo": ("Jordan", "الأردن", "Jordanien", "JO"),
    "iq": ("Iraq", "العراق", "Irak", "IQ"), "ir": ("Iran", "إيران", "Iran", "IR"),
    "pk": ("Pakistan", "باكستان", "Pakistan", "PK"), "in": ("India", "الهند", "Indien", "IN"),
    "bd": ("Bangladesh", "بنغلاديش", "Bangladesch", "BD"), "cn": ("China", "الصين", "China", "CN"),
    "hk": ("Hong Kong", "هونغ كونغ", "Hongkong", "HK"), "tw": ("Taiwan", "تايوان", "Taiwan", "TW"),
    "jp": ("Japan", "اليابان", "Japan", "JP"), "kr": ("South Korea", "كوريا الجنوبية", "Südkorea", "KR"),
    "sg": ("Singapore", "سنغافورة", "Singapur", "SG"), "my": ("Malaysia", "ماليزيا", "Malaysia", "MY"),
    "id": ("Indonesia", "إندونيسيا", "Indonesien", "ID"), "th": ("Thailand", "تايلاند", "Thailand", "TH"),
    "vn": ("Vietnam", "فيتنام", "Vietnam", "VN"), "ph": ("Philippines", "الفلبين", "Philippinen", "PH"),
    "au": ("Australia", "أستراليا", "Australien", "AU"), "nz": ("New Zealand", "نيوزيلندا", "Neuseeland", "NZ"),
    "ca": ("Canada", "كندا", "Kanada", "CA"), "us": ("United States", "الولايات المتحدة", "Vereinigte Staaten", "US"),
    "mx": ("Mexico", "المكسيك", "Mexiko", "MX"), "br": ("Brazil", "البرازيل", "Brasilien", "BR"),
    "ar": ("Argentina", "الأرجنتين", "Argentinien", "AR"), "cl": ("Chile", "تشيلي", "Chile", "CL"),
    "pe": ("Peru", "بيرو", "Peru", "PE"), "za": ("South Africa", "جنوب أفريقيا", "Südafrika", "ZA"),
    "ng": ("Nigeria", "نيجيريا", "Nigeria", "NG"), "ke": ("Kenya", "كينيا", "Kenia", "KE"),
    "kz": ("Kazakhstan", "كازاخستان", "Kasachstan", "KZ"), "uz": ("Uzbekistan", "أوزبكستان", "Usbekistan", "UZ"),
}


def code_of(domain):
    tld = domain.rsplit(".", 1)[-1].lower()
    return tld if tld in COUNTRIES else None


def name(code, lang):
    en, ar, de, _ = COUNTRIES[code]
    return {"ar": ar, "de": de}.get(lang, en)


def flag(code):
    """علم الدولة كرمز يونيكود (حرفان إقليميان)."""
    iso = COUNTRIES[code][3]
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso)


def _stats(rows):
    """{code: {"measured", "pq", "pct"}} من صفوف أسبوع واحد."""
    counts = {}
    for row in rows:
        code = code_of(row["domain"])
        if not code or not row["ok"] or row.get("unsure"):
            continue
        entry = counts.setdefault(code, {"measured": 0, "pq": 0})
        entry["measured"] += 1
        entry["pq"] += 1 if row["pq"] else 0
    for entry in counts.values():
        entry["pct"] = round(100 * entry["pq"] / entry["measured"], 1)
    return counts


def _ranked(stats):
    eligible = [(code, s) for code, s in stats.items() if s["measured"] >= MIN_SITES]
    eligible.sort(key=lambda item: (-item[1]["pct"], -item[1]["measured"], item[0]))
    return {code: i + 1 for i, (code, _) in enumerate(eligible)}, eligible


def leaderboard(conn):
    """ترتيب آخر أسبوع مع التغيّر عن الأسبوع السابق (نقاط مئوية ومراتب). None إن لم تكن بيانات."""
    weeks = [r[0] for r in conn.execute("SELECT DISTINCT week FROM adoption_results ORDER BY week")]
    if not weeks:
        return None

    def rows_of(week):
        # Tranco-ranked sites only: watch-list sectors (banks, government) would skew a country comparison.
        cur = conn.execute("SELECT domain, ok, pq, unsure FROM adoption_results WHERE week = ? AND rank IS NOT NULL", (week,))
        return [dict(r) for r in cur]

    current = _stats(rows_of(weeks[-1]))
    ranks, eligible = _ranked(current)
    prev_stats, prev_ranks = ({}, {})
    if len(weeks) > 1:
        prev_stats = _stats(rows_of(weeks[-2]))
        prev_ranks, _ = _ranked(prev_stats)
    entries = []
    for code, s in eligible:
        before = prev_stats.get(code)
        entries.append({
            "code": code, "iso": COUNTRIES[code][3], "flag": flag(code), "rank": ranks[code],
            "measured": s["measured"], "pq": s["pq"], "pct": s["pct"],
            "delta_pp": round(s["pct"] - before["pct"], 1) if before and before["measured"] >= MIN_SITES else None,
            "rank_change": (prev_ranks[code] - ranks[code]) if code in prev_ranks else None,
        })
    total = sum(e["measured"] for e in entries)
    return {"week": weeks[-1], "previous_week": weeks[-2] if len(weeks) > 1 else None, "entries": entries,
            "countries": len(entries), "sites": total, "min_sites": MIN_SITES}


def country_sites(conn, code, week):
    """مواقع دولة واحدة في أسبوع: الجاهزة ثم غير الجاهزة، كلٌّ حسب ترتيب Tranco."""
    cur = conn.execute("SELECT domain, rank, grade, grp, pq, unsure, as_name FROM adoption_results "
                       "WHERE week = ? AND ok = 1 AND rank IS NOT NULL AND domain LIKE ? ORDER BY rank", (week, f"%.{code}"))
    rows = [dict(r) for r in cur if code_of(r["domain"]) == code]
    return {"ready": [r for r in rows if r["pq"] and not r["unsure"]],
            "not_ready": [r for r in rows if not r["pq"] and not r["unsure"]],
            "unsure": [r for r in rows if r["unsure"]]}
