"""Arab world + Africa hosting study page: /adoption/arab-africa-hosting (ar/en), 2026-11-21.

Self-contained like dach_hosting.py. Results come from data/mea_hosting_results.json (written by
/root/qa-mea-study/mea_study.py build). Only aggregates are rendered: no customer domains on the public page.
Correction requests reuse the dach_corrections table (provider name identifies the study). Nothing here sends e-mail.
"""
import datetime as dt
import json
import os

from flask import abort, redirect, render_template, request, url_for

import dach_hosting

ENDPOINT = "site.mea_hosting"
REGIONS = ("arab", "africa", "mixed")

COUNTRY_AR = {"SA": "السعودية", "AE": "الإمارات", "QA": "قطر", "KW": "الكويت", "BH": "البحرين", "OM": "عُمان",
              "JO": "الأردن", "LB": "لبنان", "EG": "مصر", "MA": "المغرب", "DZ": "الجزائر", "TN": "تونس", "IQ": "العراق",
              "SY": "سوريا", "PS": "فلسطين", "SD": "السودان", "YE": "اليمن", "MR": "موريتانيا", "KE": "كينيا",
              "ZA": "جنوب أفريقيا", "NG": "نيجيريا", "ET": "إثيوبيا", "TZ": "تنزانيا", "RW": "رواندا", "GH": "غانا",
              "UG": "أوغندا", "SN": "السنغال", "CI": "ساحل العاج", "CM": "الكاميرون", "AO": "أنغولا", "SO": "الصومال"}

T = {
"en": {
  "dir": "ltr",
  "title": "Post-quantum TLS at hosting networks in the Arab world and Africa",
  "meta": "Measurement: do websites hosted on local networks in the Arab world and Africa negotiate the hybrid post-quantum key exchange X25519MLKEM768?",
  "badge": "First measurement – will be repeated",
  "lead": "We took every Arab and African country-code domain in the Tranco list of the 100,000 most popular websites, found the network that serves each one, and measured whether sites on each local hosting network negotiate the hybrid post-quantum key exchange X25519MLKEM768 in TLS 1.3. Each sampled site was measured three times.",
  "dates": "Measurement dates", "round": "Round", "tz": "UTC", "pending": "pending",
  "overview": "Where these websites are hosted",
  "ov_cdn": "behind a global CDN or cloud (Cloudflare, Amazon, Google, Microsoft …)", "ov_local": "on a local or regional network",
  "ov_note": "Sites behind a global CDN show the CDN's TLS, not the host's, so they are counted here but not attributed to a network below.",
  "region": {"arab": "Arab world", "africa": "Africa", "mixed": "Networks serving both regions or international"},
  "col_provider": "Network (operator)", "col_countries": "Countries", "col_sample": "Sites measured", "col_result": "Result",
  "result_fmt": "{pq} of {n} sites negotiate X25519MLKEM768 ({pct}%)", "insufficient": "Insufficient data",
  "unreachable_note": "{n} unreachable or undetermined",
  "method_title": "Methodology",
  "method": [
    "Sample: all domains under Arab and African country-code TLDs in the Tranco top-100k list (list GQ38K); .ly is skipped because it is mostly used by global link shorteners. No site was hand-picked.",
    "Attribution: each domain is resolved (IPv4). The network is the autonomous system of its address(es) (iptoasn.com). Sites spread over several networks are left out; sites behind global CDNs or clouds are counted only in the overview.",
    "Probe: per address, one TLS 1.3 handshake on port 443 offering X25519MLKEM768 together with classical groups; a HelloRetryRequest is answered once, as browsers do. Nothing else is requested: no HTTP requests, no page content.",
    "Consistency: three rounds about 30 minutes apart from one vantage point. Up to 10 randomly sampled sites per network with at least 5 sites. A network is rated only if at least 5 sites gave the same, determined result in all rounds.",
    "Reading the result: a network's figure reflects how the websites on it are configured. On a shared or managed platform that is the operator's default; on rented servers it is the customer's. Samples are small; read the figures as an indication, not a ranking."],
  "correction_title": "Request a correction",
  "correction_intro": "Do you operate one of these networks and think a figure is wrong, or have you enabled post-quantum key exchange since? Send us a request and we will re-measure and update the page.",
  "f_provider": "Network", "f_name": "Your name", "f_email": "E-mail for our reply", "f_role": "Company / role (optional)",
  "f_domains": "Affected sites (optional)", "f_message": "What should we correct?", "f_rescan": "Please re-measure",
  "f_submit": "Send request", "f_privacy": "We store this request (including your name and e-mail) only to process the correction, and delete it 12 months after it is closed. See the privacy policy.",
  "sent": "Thank you – your request has been recorded. We will re-measure and reply.",
  "err": {"invalid": "Please fill in network, name, a valid e-mail and the message.", "rate_limited": "Too many requests. Please try again tomorrow."},
  "dach": "Same study for Germany, Austria and Switzerland",
},
"ar": {
  "dir": "rtl",
  "title": "TLS ما بعد الكمّي لدى شبكات الاستضافة في العالم العربي وأفريقيا",
  "meta": "قياس: هل تتفاوض المواقع المستضافة على شبكات محلية في العالم العربي وأفريقيا على تبادل المفاتيح الهجين ما بعد الكمّي X25519MLKEM768؟",
  "badge": "القياس الأول – سيُعاد",
  "lead": "أخذنا كل نطاق عربي وأفريقي (برمز الدولة) في قائمة Tranco لأكثر 100 ألف موقع زيارةً، وحدّدنا الشبكة التي تخدم كل موقع، ثم قسنا هل تتفاوض المواقع على كل شبكة استضافة محلية على تبادل المفاتيح الهجين ما بعد الكمّي X25519MLKEM768 في TLS 1.3. قيس كل موقع في العيّنة ثلاث مرات.",
  "dates": "مواعيد القياس", "round": "الجولة", "tz": "بتوقيت UTC", "pending": "قيد الانتظار",
  "overview": "أين تُستضاف هذه المواقع",
  "ov_cdn": "خلف شبكة توزيع أو سحابة عالمية (Cloudflare وAmazon وGoogle وMicrosoft …)", "ov_local": "على شبكة محلية أو إقليمية",
  "ov_note": "المواقع خلف شبكة توزيع عالمية تُظهر إعدادات تلك الشبكة لا إعدادات المستضيف، لذا تُحسب هنا فقط ولا تُنسب إلى شبكة في الجداول أدناه.",
  "region": {"arab": "العالم العربي", "africa": "أفريقيا", "mixed": "شبكات تخدم المنطقتين أو دولية"},
  "col_provider": "الشبكة (المشغّل)", "col_countries": "الدول", "col_sample": "المواقع المقيسة", "col_result": "النتيجة",
  "result_fmt": "{pq} من {n} مواقع تتفاوض على X25519MLKEM768 ({pct}%)", "insufficient": "بيانات غير كافية",
  "unreachable_note": "{n} لم تُجب أو لم تُحدَّد",
  "method_title": "المنهجية",
  "method": [
    "العيّنة: كل النطاقات تحت رموز الدول العربية والأفريقية في قائمة Tranco لأكبر 100 ألف موقع (القائمة GQ38K)؛ استُبعد ‎.ly لأن أغلب استخدامه لخدمات اختصار الروابط العالمية. لم يُنتقَ أي موقع يدوياً.",
    "النسبة إلى الشبكة: يُحَل كل نطاق (IPv4)، والشبكة هي النظام المستقل (ASN) لعناوينه (iptoasn.com). المواقع الموزعة على عدة شبكات مستبعدة؛ والمواقع خلف شبكات التوزيع والسحابات العالمية تُحسب في النظرة العامة فقط.",
    "الفحص: لكل عنوان مصافحة TLS 1.3 واحدة على المنفذ 443 تعرض X25519MLKEM768 مع المجموعات الكلاسيكية؛ ويُجاب طلب HelloRetryRequest مرة واحدة كما تفعل المتصفحات. لا شيء غير ذلك: لا طلبات HTTP ولا محتوى صفحات.",
    "الثبات: ثلاث جولات بفاصل نحو 30 دقيقة من نقطة قياس واحدة. حتى 10 مواقع عشوائية لكل شبكة فيها 5 مواقع على الأقل. لا تُقيَّم الشبكة إلا إذا أعطت 5 مواقع على الأقل النتيجة نفسها المحدَّدة في كل الجولات.",
    "قراءة النتيجة: رقم الشبكة يعكس إعداد المواقع عليها؛ في الاستضافة المشتركة أو المُدارة هو إعداد المشغّل الافتراضي، وفي الخوادم المستأجرة هو إعداد العميل. العيّنات صغيرة، فاقرأ الأرقام كمؤشر لا كترتيب."],
  "correction_title": "طلب تصحيح",
  "correction_intro": "هل تشغّل إحدى هذه الشبكات وترى أن رقماً خاطئ، أو فعّلتم تبادل المفاتيح ما بعد الكمّي منذ القياس؟ أرسل طلباً وسنعيد القياس ونحدّث الصفحة.",
  "f_provider": "الشبكة", "f_name": "اسمك", "f_email": "البريد للرد", "f_role": "الشركة / الصفة (اختياري)",
  "f_domains": "المواقع المعنية (اختياري)", "f_message": "ما الذي يجب تصحيحه؟", "f_rescan": "أعيدوا القياس من فضلكم",
  "f_submit": "إرسال الطلب", "f_privacy": "نحفظ هذا الطلب (بما فيه اسمك وبريدك) لمعالجة التصحيح فقط، ونحذفه بعد 12 شهراً من إغلاقه. راجع سياسة الخصوصية.",
  "sent": "شكراً – سُجّل طلبك. سنعيد القياس ونرد عليك.",
  "err": {"invalid": "املأ الشبكة والاسم وبريداً صحيحاً والرسالة.", "rate_limited": "طلبات كثيرة. حاول غداً."},
  "dach": "الدراسة نفسها لألمانيا والنمسا وسويسرا",
},
}


def results_path(base_dir):
    return os.environ.get("MEA_RESULTS") or os.path.join(base_dir, "data", "mea_hosting_results.json")


def load(base_dir):
    try:
        with open(results_path(base_dir), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def view(data):
    """Aggregates only."""
    rounds = {r["round"]: r for r in data.get("rounds", [])}
    by_region = {r: [] for r in REGIONS}
    for p in data["providers"]:
        c = p["counts"]
        by_region.setdefault(p["region"], []).append({
            "name": p["provider"], "asn": p["asn"], "countries": p["countries"], "measured": p["measured"],
            "graded": bool(p["graded"]), "pq": c["pq"], "determined": c["pq"] + c["classical"], "pct": p["pq_share"],
            "unreachable": c["unreachable"] + c["undetermined"] + c["mixed"] + c["variable"]})
    ov = {}
    for region, b in (data.get("buckets") or {}).items():
        cdn, local = b.get("global_cdn_cloud", 0), b.get("local_host", 0)
        ov[region] = {"cdn": cdn, "local": local, "total": cdn + local,
                      "cdn_pct": round(100 * cdn / (cdn + local)) if cdn + local else 0}
    fmt = lambda iso: dt.datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M") if iso else None
    return {"rounds": [(n, fmt(rounds[n]["started_utc"]) if n in rounds else None,
                        fmt(rounds[n]["finished_utc"])[11:] if n in rounds else None) for n in (1, 2, 3)],
            "regions": by_region, "overview": ov}


def register(bp, deps):
    """deps: base_dir, db, lang, client_hash."""

    @bp.get("/adoption/arab-africa-hosting")
    def mea_hosting():
        data = load(deps["base_dir"]) or abort(404)
        lang = deps["lang"]()
        d = T["ar"] if lang == "ar" else T["en"]
        return render_template("mea_hosting.html", d=d, v=view(data), country_ar=COUNTRY_AR, lang_code=lang,
                               provider_names=[p["provider"] for p in data["providers"]],
                               sent=request.args.get("sent") == "1", error=d["err"].get(request.args.get("error", "")))

    @bp.post("/adoption/arab-africa-hosting/correction")
    def mea_hosting_correction():
        if request.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
            abort(400)
        lang = "ar" if request.form.get("lang") == "ar" else "en"
        back = lambda **kw: redirect(url_for(ENDPOINT, lang=lang, **kw) + "#correction", code=303)
        data = load(deps["base_dir"]) or abort(404)
        if request.form.get("website"):  # honeypot
            return back(sent="1")
        f = {k: (request.form.get(k) or "").strip() for k in ("provider", "name", "email", "role", "domains", "message")}
        names = {p["provider"] for p in data["providers"]}
        if (f["provider"] not in names or not (1 <= len(f["name"]) <= 120) or not dach_hosting.EMAIL_RE.match(f["email"])
                or not (5 <= len(f["message"]) <= 4000) or len(f["role"]) > 200 or len(f["domains"]) > 1000):
            return back(error="invalid")
        conn, client = deps["db"](), deps["client_hash"]()
        dach_hosting._init(conn)
        since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        mine = conn.execute("SELECT COUNT(*) FROM dach_corrections WHERE client_hash = ? AND created_at >= ?",
                            (client, since)).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM dach_corrections WHERE created_at >= ?", (since,)).fetchone()[0]
        if mine >= dach_hosting.PER_CLIENT_PER_DAY or total >= dach_hosting.GLOBAL_PER_DAY:
            return back(error="rate_limited")
        with conn:
            conn.execute("INSERT INTO dach_corrections (provider, name, email, company_role, domains, message,"
                         " wants_rescan, lang, client_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         ("[MEA] " + f["provider"], f["name"], f["email"], f["role"] or None, f["domains"] or None,
                          f["message"], int(bool(request.form.get("rescan"))), lang, client))
        return back(sent="1")
