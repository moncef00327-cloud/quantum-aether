"""DACH hosting study page: /adoption/dach-hosting (ar/de/en) and its correction-request form.

Self-contained on purpose: all texts live here, results come from data/dach_hosting_results.json
(written by tools/dach_study.py build), correction requests go into the dach_corrections table.
Nothing here sends e-mail or contacts anyone.
"""
import datetime as dt
import json
import os
import re
from zoneinfo import ZoneInfo

from flask import abort, redirect, render_template, request, url_for

ENDPOINT = "site.dach_hosting"
CORRECTION_ENDPOINT = "site.dach_hosting_correction"
FALLBACK_EMAIL = "sajad.vip56@gmail.com"
VIENNA = ZoneInfo("Europe/Vienna")
PER_CLIENT_PER_DAY, GLOBAL_PER_DAY = 3, 100
EMAIL_RE = re.compile(r"^[^@\s<>\"']{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$")
SEGMENTS = ("managed", "vps", "unspecified")
COUNTRY = {"DE": {"en": "Germany", "de": "Deutschland", "ar": "ألمانيا"},
           "AT": {"en": "Austria", "de": "Österreich", "ar": "النمسا"},
           "CH": {"en": "Switzerland", "de": "Schweiz", "ar": "سويسرا"}}

SCHEMA = """
CREATE TABLE IF NOT EXISTS dach_corrections (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
  provider TEXT NOT NULL, name TEXT NOT NULL, email TEXT NOT NULL, company_role TEXT,
  domains TEXT, message TEXT NOT NULL, wants_rescan INTEGER NOT NULL DEFAULT 1,
  lang TEXT, client_hash TEXT, status TEXT NOT NULL DEFAULT 'new');
CREATE INDEX IF NOT EXISTS dach_corrections_client ON dach_corrections (client_hash, created_at);
"""

T = {
"en": {
  "dir": "ltr",
  "title": "Post-quantum TLS at DACH hosting providers",
  "meta": "Preliminary measurement: do customer websites of 22 hosting providers in Germany, Austria and Switzerland negotiate the hybrid post-quantum key exchange X25519MLKEM768?",
  "badge": "Preliminary measurement – continuously updated",
  "lead": "We checked whether websites that hosting providers in Germany, Austria and Switzerland list as their own customer references negotiate the hybrid post-quantum key exchange X25519MLKEM768 in TLS 1.3. Each site was verified to be served from the provider's own network and measured three times.",
  "dates": "Measurement dates", "round": "Round", "tz": "Vienna time (CET, UTC+1)", "pending": "pending",
  "providers": "Providers", "col_provider": "Provider", "col_country": "Country", "col_sample": "Verified sites",
  "col_result": "Result", "result_fmt": "{pq} of {n} sites negotiate X25519MLKEM768 ({pct}%)",
  "insufficient": "Insufficient data",
  "reason": {"no_published_references": "no published customer references found",
             "fewer_than_5_verified": "fewer than 5 verified sites", "rounds_incomplete": "measurement rounds not complete yet",
             "rounds_differ": "results differed between rounds"},
  "unreachable_note": "{n} unreachable",
  "segments_title": "Managed hosting and VPS, shown separately",
  "segments_intro": "Sites are assigned to a segment only from what the provider's reference itself says. On a VPS or cloud server the customer usually runs and configures the TLS stack; on managed hosting the provider does. VPS results therefore say more about the customers than about the provider.",
  "seg": {"managed": "Managed hosting", "vps": "VPS / cloud servers", "unspecified": "Segment not stated in the reference"},
  "seg_col": "Sites (post-quantum / total)",
  "sample_title": "Sample size per provider",
  "method_title": "Methodology",
  "method": [
    "Sample: up to 10 customer websites per provider, taken only from the provider's own published references (customer showcases, case studies, reference lists). The source page is recorded for every site.",
    "Verification: every site is resolved in DNS (A, AAAA, CNAME). It is included only if every address belongs to the provider's own network (autonomous system, iptoasn.com; for World4You, which operates inside the IONOS network, the RIPE registration name). Sites behind a CDN (e.g. Cloudflare, Akamai, Fastly, Amazon CloudFront, Google) are excluded, because they show the CDN, not the host.",
    "Probe: per address, one TLS 1.3 handshake on port 443 offering X25519MLKEM768 together with classical groups; a HelloRetryRequest is answered once, as browsers do. Nothing else is requested: no HTTP requests, no other ports, no page content.",
    "Consistency: three rounds on the same day, at least two hours apart, from one vantage point. A provider is rated only if it has at least 5 verified sites and every site gave the same result in all three rounds; otherwise the page shows “Insufficient data”.",
    "Result: share of reachable verified sites that negotiated X25519MLKEM768. Customer sites reflect the provider's defaults only in part, and a sample of 5–10 sites is small; read the figures as an indication, not a ranking."],
  "correction_title": "Request a correction",
  "correction_intro": "Are you a provider in this table and think a figure is wrong, a site is mis-assigned, or your platform has changed? Send us a request and we will rescan and correct the page. Requests are stored for processing only.",
  "f_provider": "Provider", "f_name": "Your name", "f_email": "E-mail for our reply", "f_role": "Company / role (optional)",
  "f_domains": "Affected sites (optional)", "f_message": "What should we correct?", "f_rescan": "Please rescan our sites",
  "f_submit": "Send request", "f_privacy": "We store this request (including your name and e-mail) only to process the correction, and delete it 12 months after it is closed. See the privacy policy.",
  "f_alt": "Alternatively, by e-mail:", "sent": "Thank you – your request has been recorded. We will rescan and reply.",
  "err": {"invalid": "Please fill in provider, name, a valid e-mail and the message.", "rate_limited": "Too many requests. Please try again tomorrow or write to us by e-mail."},
  "back": "Hosting networks worldwide",
},
"de": {
  "dir": "ltr",
  "title": "Post-Quanten-TLS bei Hostern in Deutschland, Österreich und der Schweiz",
  "meta": "Erste Messung: Handeln Kundenwebsites von 22 Hostern in Deutschland, Österreich und der Schweiz den hybriden Post-Quanten-Schlüsselaustausch X25519MLKEM768 aus?",
  "badge": "Erste Messung – wird laufend aktualisiert",
  "lead": "Wir haben geprüft, ob Websites, die Hoster in Deutschland, Österreich und der Schweiz selbst als Kundenreferenzen nennen, in TLS 1.3 den hybriden Post-Quanten-Schlüsselaustausch X25519MLKEM768 aushandeln. Für jede Website wurde geprüft, dass sie aus dem eigenen Netz des Hosters ausgeliefert wird; gemessen wurde dreimal.",
  "dates": "Messzeitpunkte", "round": "Runde", "tz": "Wiener Zeit (MEZ, UTC+1)", "pending": "ausstehend",
  "providers": "Anbieter", "col_provider": "Anbieter", "col_country": "Land", "col_sample": "Verifizierte Websites",
  "col_result": "Ergebnis", "result_fmt": "{pq} von {n} Websites handeln X25519MLKEM768 aus ({pct} %)",
  "insufficient": "Unzureichende Daten",
  "reason": {"no_published_references": "keine veröffentlichten Kundenreferenzen gefunden",
             "fewer_than_5_verified": "weniger als 5 verifizierte Websites", "rounds_incomplete": "Messrunden noch nicht abgeschlossen",
             "rounds_differ": "Ergebnisse unterschieden sich zwischen den Runden"},
  "unreachable_note": "{n} nicht erreichbar",
  "segments_title": "Managed Hosting und VPS getrennt",
  "segments_intro": "Einem Segment wird eine Website nur zugeordnet, wenn die Referenz des Hosters es selbst angibt. Auf einem VPS oder Cloud-Server betreibt und konfiguriert meist der Kunde den TLS-Stack, beim Managed Hosting der Hoster. VPS-Ergebnisse sagen daher mehr über die Kunden als über den Hoster.",
  "seg": {"managed": "Managed Hosting", "vps": "VPS / Cloud-Server", "unspecified": "Segment in der Referenz nicht angegeben"},
  "seg_col": "Websites (Post-Quanten / gesamt)",
  "sample_title": "Stichprobengröße je Anbieter",
  "method_title": "Methodik",
  "method": [
    "Stichprobe: bis zu 10 Kundenwebsites je Anbieter, ausschließlich aus den eigenen veröffentlichten Referenzen des Anbieters (Kundenbeispiele, Fallstudien, Referenzlisten). Für jede Website ist die Quellseite dokumentiert.",
    "Verifikation: Jede Website wird per DNS aufgelöst (A, AAAA, CNAME). Aufgenommen wird sie nur, wenn jede Adresse zum eigenen Netz des Anbieters gehört (autonomes System, iptoasn.com; bei World4You, das im IONOS-Netz betrieben wird, der RIPE-Registrierungsname). Websites hinter einem CDN (z. B. Cloudflare, Akamai, Fastly, Amazon CloudFront, Google) werden ausgeschlossen, da sie das CDN zeigen und nicht den Hoster.",
    "Messung: je Adresse ein TLS-1.3-Handshake auf Port 443, der X25519MLKEM768 zusammen mit klassischen Gruppen anbietet; ein HelloRetryRequest wird wie im Browser einmal beantwortet. Sonst wird nichts abgefragt: keine HTTP-Anfragen, keine anderen Ports, keine Seiteninhalte.",
    "Konsistenz: drei Runden am selben Tag im Abstand von mindestens zwei Stunden, von einem Messpunkt aus. Bewertet wird ein Anbieter nur mit mindestens 5 verifizierten Websites und identischem Ergebnis jeder Website in allen drei Runden; sonst steht hier „Unzureichende Daten“.",
    "Ergebnis: Anteil der erreichbaren verifizierten Websites, die X25519MLKEM768 ausgehandelt haben. Kundenwebsites spiegeln die Voreinstellungen des Hosters nur teilweise wider, und 5–10 Websites sind eine kleine Stichprobe; die Zahlen sind ein Hinweis, keine Rangliste."],
  "correction_title": "Korrektur anfordern",
  "correction_intro": "Sie sind ein Anbieter in dieser Tabelle und halten eine Angabe für falsch, eine Website für falsch zugeordnet, oder Ihre Plattform hat sich geändert? Senden Sie uns eine Anfrage – wir messen erneut und korrigieren die Seite. Anfragen werden nur zur Bearbeitung gespeichert.",
  "f_provider": "Anbieter", "f_name": "Ihr Name", "f_email": "E-Mail für unsere Antwort", "f_role": "Unternehmen / Funktion (optional)",
  "f_domains": "Betroffene Websites (optional)", "f_message": "Was sollen wir korrigieren?", "f_rescan": "Bitte unsere Websites erneut messen",
  "f_submit": "Anfrage senden", "f_privacy": "Wir speichern diese Anfrage (einschließlich Name und E-Mail) nur zur Bearbeitung der Korrektur und löschen sie 12 Monate nach Abschluss. Siehe Datenschutzerklärung.",
  "f_alt": "Alternativ per E-Mail:", "sent": "Vielen Dank – Ihre Anfrage ist erfasst. Wir messen erneut und melden uns.",
  "err": {"invalid": "Bitte Anbieter, Name, eine gültige E-Mail und die Nachricht angeben.", "rate_limited": "Zu viele Anfragen. Bitte morgen erneut versuchen oder per E-Mail schreiben."},
  "back": "Hosting-Netze weltweit",
},
"ar": {
  "dir": "rtl",
  "title": "التشفير المقاوم للكم لدى مزوّدي الاستضافة في ألمانيا والنمسا وسويسرا",
  "meta": "قياس أولي: هل تتفاوض مواقع عملاء 22 مزوّد استضافة في ألمانيا والنمسا وسويسرا على تبادل المفاتيح الهجين المقاوم للكم X25519MLKEM768؟",
  "badge": "قياس أولي – يُحدَّث باستمرار",
  "lead": "فحصنا هل تتفاوض المواقع التي يعرضها مزوّدو الاستضافة في ألمانيا والنمسا وسويسرا بأنفسهم بوصفها مراجع لعملائهم على تبادل المفاتيح الهجين المقاوم للكم X25519MLKEM768 في TLS 1.3. تحققنا من أن كل موقع يُخدَّم من شبكة المزوّد نفسه، وقسناه ثلاث مرات.",
  "dates": "مواعيد القياس", "round": "الجولة", "tz": "بتوقيت فيينا (UTC+1)", "pending": "لم تُنفَّذ بعد",
  "providers": "المزوّدون", "col_provider": "المزوّد", "col_country": "البلد", "col_sample": "مواقع متحقَّق منها",
  "col_result": "النتيجة", "result_fmt": "{pq} من {n} مواقع تتفاوض على X25519MLKEM768 ({pct}%)",
  "insufficient": "بيانات غير كافية",
  "reason": {"no_published_references": "لم نجد مراجع عملاء منشورة",
             "fewer_than_5_verified": "أقل من 5 مواقع متحقَّق منها", "rounds_incomplete": "جولات القياس لم تكتمل بعد",
             "rounds_differ": "اختلفت النتائج بين الجولات"},
  "unreachable_note": "{n} تعذّر الوصول إليه",
  "segments_title": "الاستضافة المُدارة والخوادم الافتراضية كلٌّ على حدة",
  "segments_intro": "لا يُنسب الموقع إلى فئة إلا إذا ذكرها مرجع المزوّد نفسه. على الخادم الافتراضي (VPS) أو السحابي يشغّل العميل غالبًا إعدادات TLS بنفسه، أما في الاستضافة المُدارة فيتولاها المزوّد؛ لذلك تعبّر نتائج VPS عن العملاء أكثر مما تعبّر عن المزوّد.",
  "seg": {"managed": "استضافة مُدارة", "vps": "خوادم افتراضية / سحابية (VPS)", "unspecified": "الفئة غير مذكورة في المرجع"},
  "seg_col": "المواقع (مقاوم للكم / الإجمالي)",
  "sample_title": "حجم العينة لكل مزوّد",
  "method_title": "المنهجية",
  "method": [
    "العينة: حتى 10 مواقع عملاء لكل مزوّد، مأخوذة حصرًا من المراجع التي نشرها المزوّد نفسه (معارض العملاء، دراسات الحالة، قوائم المراجع). صفحة المصدر موثّقة لكل موقع.",
    "التحقق: يُحلّ كل موقع في DNS (A وAAAA وCNAME)، ولا يدخل العينة إلا إذا كان كل عنوان من عناوينه ضمن شبكة المزوّد نفسه (النظام المستقل ASN وفق iptoasn.com؛ ولـ World4You التي تعمل داخل شبكة IONOS اسمُ التسجيل لدى RIPE). تُستبعد المواقع التي خلف شبكة توزيع محتوى (مثل Cloudflare وAkamai وFastly وAmazon CloudFront وGoogle) لأنها تُظهر الشبكة لا المستضيف.",
    "القياس: لكل عنوان مصافحة TLS 1.3 واحدة على المنفذ 443 تعرض X25519MLKEM768 مع المجموعات التقليدية، ويُجاب طلب HelloRetryRequest مرة واحدة كما تفعل المتصفحات. لا شيء غير ذلك: لا طلبات HTTP، ولا منافذ أخرى، ولا محتوى صفحات.",
    "الثبات: ثلاث جولات في اليوم نفسه، بين كل جولتين ساعتان على الأقل، من نقطة قياس واحدة. لا يُقيَّم مزوّد إلا إذا كان لديه 5 مواقع متحقَّق منها على الأقل وأعطى كل موقع النتيجة نفسها في الجولات الثلاث؛ وإلا تظهر «بيانات غير كافية».",
    "النتيجة: نسبة المواقع المتحقَّق منها والممكن الوصول إليها التي تفاوضت على X25519MLKEM768. مواقع العملاء لا تعكس الإعدادات الافتراضية للمزوّد إلا جزئيًا، وعينة من 5 إلى 10 مواقع صغيرة؛ فالأرقام مؤشر لا ترتيب."],
  "correction_title": "طلب تصحيح",
  "correction_intro": "هل أنت مزوّد مذكور في الجدول وترى أن رقمًا خاطئ، أو أن موقعًا نُسب خطأً، أو أن منصتك تغيّرت؟ أرسل إلينا طلبًا وسنعيد القياس ونصحّح الصفحة. تُحفظ الطلبات لمعالجتها فقط.",
  "f_provider": "المزوّد", "f_name": "اسمك", "f_email": "البريد الإلكتروني للرد", "f_role": "الشركة / الصفة (اختياري)",
  "f_domains": "المواقع المعنية (اختياري)", "f_message": "ما الذي ينبغي تصحيحه؟", "f_rescan": "يُرجى إعادة قياس مواقعنا",
  "f_submit": "إرسال الطلب", "f_privacy": "نحفظ هذا الطلب (بما فيه الاسم والبريد) لمعالجة التصحيح فقط، ونحذفه بعد 12 شهرًا من إغلاقه. راجع سياسة الخصوصية.",
  "f_alt": "أو عبر البريد الإلكتروني:", "sent": "شكرًا لك – سُجّل طلبك. سنعيد القياس ونرد عليك.",
  "err": {"invalid": "يُرجى تعبئة المزوّد والاسم وبريد صالح والرسالة.", "rate_limited": "طلبات كثيرة. حاول غدًا أو راسلنا بالبريد."},
  "back": "شبكات الاستضافة حول العالم",
},
}


def results_path(base_dir):
    return os.environ.get("DACH_RESULTS") or os.path.join(base_dir, "data", "dach_hosting_results.json")


def load(base_dir):
    try:
        with open(results_path(base_dir), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def vienna(iso):
    if not iso:
        return None
    return dt.datetime.fromisoformat(iso).astimezone(VIENNA).strftime("%Y-%m-%d %H:%M")


def updated(base_dir):
    data = load(base_dir)
    return (data or {}).get("generated_utc", "")[:10] or dt.date.today().isoformat()


def view(data):
    """Only aggregates leave this function: no customer domains are rendered on the public page."""
    rounds = {m["round"]: m for m in data.get("rounds", [])}
    providers = []
    for p in data["providers"]:
        c = p["counts"]
        determined = c["pq"] + c["classical"] + c["mixed"]
        providers.append({
            "name": p["provider"], "country": p["country"], "verified": p["verified"],
            "graded": bool(p["graded"]), "reason": p["insufficient_reason"], "pq": c["pq"], "determined": determined,
            "pct": p["pq_share"], "unreachable": c["unreachable"] + c["undetermined"],
            "segments": p["segments"]})
    segments = {s: [] for s in SEGMENTS}
    for p in providers:
        for s, v in p["segments"].items():
            segments.setdefault(s, []).append({"name": p["name"], "country": p["country"], "graded": p["graded"],
                                               "reason": p["reason"], "sites": v["sites"], "pq": v["pq"]})
    return {"rounds": [(n, vienna(rounds[n]["started_utc"]) if n in rounds else None,
                        vienna(rounds[n]["finished_utc"])[11:] if n in rounds else None) for n in (1, 2, 3)],
            "providers": providers, "segments": segments, "min_sites": data.get("min_sites", 5),
            "max_sites": data.get("max_sites", 10), "total": sum(p["verified"] for p in providers)}


def _init(conn):
    conn.executescript(SCHEMA)


def register(bp, deps):
    """deps: base_dir, db, lang, client_hash, de_pages, de_endpoints."""
    deps["de_pages"].add(ENDPOINT)
    deps["de_endpoints"].add(ENDPOINT)

    @bp.get("/adoption/dach-hosting")
    def dach_hosting():
        data = load(deps["base_dir"]) or abort(404)
        lang = deps["lang"]()
        d = T.get(lang, T["en"])
        names = [p["provider"] for p in data["providers"]]
        status = request.args.get("sent")
        return render_template("dach_hosting.html", d=d, v=view(data), country=COUNTRY, lang_code=lang,
                               provider_names=names, fallback_email=FALLBACK_EMAIL,
                               sent=status == "1", error=d["err"].get(request.args.get("error", "")))

    @bp.post("/adoption/dach-hosting/correction")
    def dach_hosting_correction():
        if request.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
            abort(400)
        lang = request.form.get("lang") if request.form.get("lang") in T else "en"
        back = lambda **kw: redirect(url_for(ENDPOINT, lang=lang, **kw) + "#correction", code=303)
        data = load(deps["base_dir"]) or abort(404)
        if request.form.get("website"):  # honeypot field, hidden from people
            return back(sent="1")
        f = {k: (request.form.get(k) or "").strip() for k in ("provider", "name", "email", "role", "domains", "message")}
        names = {p["provider"] for p in data["providers"]}
        if (f["provider"] not in names or not (1 <= len(f["name"]) <= 120) or not EMAIL_RE.match(f["email"])
                or not (5 <= len(f["message"]) <= 4000) or len(f["role"]) > 200 or len(f["domains"]) > 1000):
            return back(error="invalid")
        conn, client = deps["db"](), deps["client_hash"]()
        _init(conn)
        since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        mine = conn.execute("SELECT COUNT(*) FROM dach_corrections WHERE client_hash = ? AND created_at >= ?",
                            (client, since)).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM dach_corrections WHERE created_at >= ?", (since,)).fetchone()[0]
        if mine >= PER_CLIENT_PER_DAY or total >= GLOBAL_PER_DAY:
            return back(error="rate_limited")
        with conn:
            conn.execute("INSERT INTO dach_corrections (provider, name, email, company_role, domains, message,"
                         " wants_rescan, lang, client_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (f["provider"], f["name"], f["email"], f["role"] or None, f["domains"] or None, f["message"],
                          int(bool(request.form.get("rescan"))), lang, client))
        return back(sent="1")
