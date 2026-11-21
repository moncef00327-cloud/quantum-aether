# exposure_web.py — صفحات سجل التعرّض الكمّي: /exposure و /exposure/<domain> وملفات البصمة وواجهة JSON وخريطة الموقع.
# وحدة مستقلة تُسجَّل على نفس الـ Blueprint (مثل dach_hosting)، فلا تتعارض مع تعديلات الصفحات الأخرى. لا تُجري أي فحص.
import os
import re

from flask import Response, abort, current_app, g, jsonify, make_response, redirect, render_template, request, send_file, url_for

import logging

import adoption
import data_access
import exposure
import terms
import quantum_vuln_scanner
import search_indexing

ENDPOINTS = ("site.exposure_page", "site.exposure_index", "site.data_license")
log = logging.getLogger("quantum_saas.exposure_web")
SITEMAP_CHUNK = 2500
ANCHOR_FILE_RE = re.compile(r"^(\d{4}-W\d{2})\.(json|manifest\.txt|manifest\.txt\.ots)$")

T = {
    "en": {
        "index_title": "Quantum Exposure Registry — when did each site stop being harvest-now-decrypt-later exposed?",
        "index_lead": "For every tracked domain we record, week by week, whether its public HTTPS endpoint negotiates post-quantum key exchange (X25519MLKEM768). The registry shows from when a domain went post-quantum and how long we observed it on classical key exchange before that — the window in which recorded traffic is exposed to harvest-now-decrypt-later. Each week's results are hashed and anchored in Bitcoin via OpenTimestamps, so nobody (including us) can rewrite the history later.",
        "title": "{domain}: quantum exposure window",
        "meta": "{domain}: first observed {first}; {status_line} Weekly post-quantum TLS timeline with tamper-evident OpenTimestamps proofs.",
        "badge": "Exposure registry · external observation",
        "first_observed": "First observed", "went_pq": "Post-quantum since", "window": "Exposure window (observed)",
        "status": "Status", "current": "Latest observation", "network": "Network", "rank": "Tranco rank",
        "never": "not yet observed", "open": "still open", "days": "{n} days",
        "st_classical": "Classical key exchange in every observation so far — traffic is harvest-now-decrypt-later exposed.",
        "st_went_pq": "Observed on classical key exchange first, then switched to post-quantum key exchange.",
        "st_pq_since_first_observation": "Already post-quantum when we first observed it; any earlier exposure is outside our record.",
        "st_no_measurement": "No conclusive measurement yet (unreachable or undetermined).",
        "regression": "Regression: post-quantum key exchange was not negotiated again in {weeks}.",
        "lower_bound": "The window is a lower bound: classical key exchange may have been in use before our first observation.",
        "timeline": "Weekly timeline", "week": "Week", "state": "Observation", "grade": "Grade", "group": "Key exchange",
        "proof": "Proof",
        "states": {"observed_pq": "post-quantum", "observed_classical": "classical", "undetermined": "undetermined", "unreachable": "no answer"},
        "anchor_pending": "anchored, Bitcoin confirmation pending", "anchor_complete": "anchored in Bitcoin block {block}", "anchor_none": "not yet anchored",
        "peers": "Same network, same week", "peers_stat": "On {net}: {pq} of {n} measured sites ({pct}%) negotiate post-quantum key exchange this week.",
        "since": "PQ since {week}",
        "verify_title": "Verify this record yourself",
        "verify_body": "Each row's fingerprint is sha256(\"quantum-aether-v1|domain|state|grade|tls|group|checked_at\"). The weekly manifest lists sha256(\"quantum-aether-domain-v1|{domain}\") with that fingerprint; the manifest's sha256 is timestamped with OpenTimestamps. Download the manifest and the .ots proof, then run: ots verify WEEK.manifest.txt.ots",
        "claim_title": "Is this your domain? Claim this page",
        "claim_body": "Publish this DNS TXT record, then press verify. A claimed page shows that the owner verified it; it does not change the measurements.",
        "claim_button": "Verify DNS record", "claimed": "Claimed by the domain owner (DNS TXT verified {date}).",
        "claim_ok": "Verified. Your page is claimed — start daily monitoring to catch the next regression within a day.",
        "claim_fail": "Record not found yet. DNS changes can take a few minutes; try again shortly.",
        "claim_wait": "Please wait 30 seconds between verification attempts.",
        "trial_title": "Keep this record clean: daily monitoring for {domain}",
        "trial_sub": "The registry checks once a week. Monitoring checks every day, including api/mail/login subdomains, and emails you when post-quantum key exchange disappears. 14-day free trial, no card.",
        "disclaimer": "External observation of the public HTTPS endpoint only (one TLS handshake per week on port 443, from one location). This is not a compliance certification, audit, or legal advice, and it says nothing about the security of the application or internal systems.",
        "anchors_title": "Weekly anchors", "rows": "rows", "download": "manifest · proof · JSON",
        "index_examples": "Examples", "index_banks": "Banks", "more": "Per-domain pages: /exposure/<domain>",
        "unknown": "We have no weekly observation of {domain} yet.",
        "terms_link": "Data licence and terms of use", "truncated": "Showing the latest {n} weeks. The full history is available with an API key (see data licence).",
        "related_site": "Current scan result", "related_registry": "Exposure registry",
    },
    "ar": {
        "index_title": "سجل التعرّض الكمّي — متى توقّف كل موقع عن التعرّض لهجوم «احصد الآن، فكّ لاحقاً»؟",
        "index_lead": "نسجّل لكل نطاق نتابعه، أسبوعاً بعد أسبوع، هل يتفاوض خادمه العام على تبادل مفاتيح ما بعد كمّي (X25519MLKEM768). يبيّن السجل متى انتقل النطاق إلى التشفير ما بعد الكمّي، وكم رأيناه يستخدم التبادل الكلاسيكي قبل ذلك، وهي المدة التي تبقى فيها حركة البيانات المسجَّلة معرّضة لهجوم «احصد الآن، فكّ لاحقاً». نحسب بصمة نتائج كل أسبوع ونرسّخها في بيتكوين عبر OpenTimestamps، فلا يستطيع أحد، ولا نحن، إعادة كتابة التاريخ لاحقاً.",
        "title": "{domain}: نافذة التعرّض الكمّي",
        "meta": "{domain}: أول رصد {first}؛ {status_line} خط زمني أسبوعي لتشفير TLS ما بعد الكمّي مع إثباتات OpenTimestamps.",
        "badge": "سجل التعرّض · رصد خارجي",
        "first_observed": "أول رصد", "went_pq": "ما بعد كمّي منذ", "window": "نافذة التعرّض (المرصودة)",
        "status": "الحالة", "current": "آخر رصد", "network": "الشبكة", "rank": "ترتيب Tranco",
        "never": "لم يُرصد بعد", "open": "ما زالت مفتوحة", "days": "{n} يوماً",
        "st_classical": "تبادل مفاتيح كلاسيكي في كل رصد حتى الآن، فحركة البيانات معرّضة لهجوم «احصد الآن، فكّ لاحقاً».",
        "st_went_pq": "رأيناه أولاً بتبادل مفاتيح كلاسيكي، ثم انتقل إلى تبادل مفاتيح ما بعد كمّي.",
        "st_pq_since_first_observation": "كان ما بعد كمّي منذ أول رصد لنا، وأي تعرّض قبل ذلك خارج سجلّنا.",
        "st_no_measurement": "لا يوجد قياس حاسم بعد (لم يُجب أو النتيجة غير محسومة).",
        "regression": "تراجع: لم يُتفاوض على تبادل المفاتيح ما بعد الكمّي مجدداً في {weeks}.",
        "lower_bound": "النافذة حدّ أدنى: ربما استُخدم التبادل الكلاسيكي قبل أول رصد لنا.",
        "timeline": "الخط الزمني الأسبوعي", "week": "الأسبوع", "state": "الرصد", "grade": "الدرجة", "group": "تبادل المفاتيح",
        "proof": "الإثبات",
        "states": {"observed_pq": "ما بعد كمّي", "observed_classical": "كلاسيكي", "undetermined": "غير محسوم", "unreachable": "لم يُجب"},
        "anchor_pending": "مُرسّخ، بانتظار تأكيد بيتكوين", "anchor_complete": "مُرسّخ في كتلة بيتكوين {block}", "anchor_none": "لم يُرسّخ بعد",
        "peers": "على الشبكة نفسها في الأسبوع نفسه", "peers_stat": "على {net}: {pq} من {n} موقعاً مقيساً ({pct}%) تتفاوض على تبادل مفاتيح ما بعد كمّي هذا الأسبوع.",
        "since": "ما بعد كمّي منذ {week}",
        "verify_title": "تحقّق من هذا السجل بنفسك",
        "verify_body": "بصمة كل صف هي sha256(\"quantum-aether-v1|domain|state|grade|tls|group|checked_at\"). يضم الملف الأسبوعي sha256(\"quantum-aether-domain-v1|{domain}\") مع تلك البصمة، وبصمة الملف كله مختومة زمنياً في OpenTimestamps. نزّل الملف وإثبات ‎.ots ثم شغّل: ots verify WEEK.manifest.txt.ots",
        "claim_title": "هل هذا نطاقك؟ طالِب بهذه الصفحة",
        "claim_body": "أضف سجل DNS TXT التالي ثم اضغط «تحقّق». تُظهر الصفحة المطالَب بها أن المالك تحقّق منها، ولا تغيّر القياسات.",
        "claim_button": "تحقّق من سجل DNS", "claimed": "طالب بها مالك النطاق (تحقّق عبر DNS TXT في {date}).",
        "claim_ok": "تم التحقق، والصفحة الآن باسمك. فعّل المراقبة اليومية لتعرف بأي تراجع خلال يوم.",
        "claim_fail": "لم نجد السجل بعد. قد يستغرق تحديث DNS بضع دقائق، فأعد المحاولة بعد قليل.",
        "claim_wait": "انتظر 30 ثانية بين محاولتين.",
        "trial_title": "حافظ على سجل نظيف: مراقبة يومية لـ {domain}",
        "trial_sub": "يفحص السجل مرة في الأسبوع. أما المراقبة فتفحص كل يوم، بما فيها النطاقات الفرعية مثل api وmail وlogin، وترسل لك بريداً إذا اختفى التبادل ما بعد الكمّي. تجربة مجانية 14 يوماً دون بطاقة.",
        "disclaimer": "رصد خارجي للخادم العام فقط (مصافحة TLS واحدة أسبوعياً على المنفذ 443 من موقع واحد). ليس شهادة امتثال ولا تدقيقاً ولا استشارة قانونية، ولا يقول شيئاً عن أمان التطبيق أو الأنظمة الداخلية.",
        "anchors_title": "البصمات الأسبوعية", "rows": "صفاً", "download": "الملف · الإثبات · JSON",
        "index_examples": "أمثلة", "index_banks": "البنوك", "more": "صفحة لكل نطاق: ‎/exposure/<domain>",
        "unknown": "لا يوجد لدينا رصد أسبوعي لـ {domain} بعد.",
        "terms_link": "ترخيص البيانات وشروط الاستخدام", "truncated": "نعرض آخر {n} أسبوعاً. التاريخ الكامل متاح بمفتاح API (راجع ترخيص البيانات).",
        "related_site": "نتيجة الفحص الحالية", "related_registry": "سجل التعرّض",
    },
    "de": {
        "index_title": "Quantum Exposure Registry — seit wann ist eine Website nicht mehr „harvest now, decrypt later“-exponiert?",
        "index_lead": "Für jede beobachtete Domain halten wir Woche für Woche fest, ob ihr öffentlicher HTTPS-Endpunkt einen Post-Quanten-Schlüsselaustausch (X25519MLKEM768) aushandelt. Das Register zeigt, seit wann eine Domain post-quanten-fähig ist und wie lange wir sie davor mit klassischem Schlüsselaustausch beobachtet haben — das Fenster, in dem mitgeschnittener Verkehr „harvest now, decrypt later“-gefährdet ist. Die Ergebnisse jeder Woche werden gehasht und per OpenTimestamps in Bitcoin verankert; niemand (auch wir nicht) kann die Historie nachträglich ändern.",
        "title": "{domain}: Quanten-Expositionsfenster",
        "meta": "{domain}: erstmals beobachtet {first}; {status_line} Wöchentliche Post-Quanten-TLS-Zeitleiste mit OpenTimestamps-Nachweisen.",
        "badge": "Expositionsregister · externe Beobachtung",
        "first_observed": "Erstmals beobachtet", "went_pq": "Post-Quanten seit", "window": "Expositionsfenster (beobachtet)",
        "status": "Status", "current": "Letzte Beobachtung", "network": "Netzwerk", "rank": "Tranco-Rang",
        "never": "noch nicht beobachtet", "open": "weiterhin offen", "days": "{n} Tage",
        "st_classical": "Bisher in jeder Beobachtung klassischer Schlüsselaustausch — der Verkehr ist „harvest now, decrypt later“-exponiert.",
        "st_went_pq": "Zuerst mit klassischem Schlüsselaustausch beobachtet, danach Umstieg auf Post-Quanten-Schlüsselaustausch.",
        "st_pq_since_first_observation": "Bereits bei unserer ersten Beobachtung post-quanten-fähig; frühere Exposition liegt außerhalb unseres Registers.",
        "st_no_measurement": "Noch keine eindeutige Messung (nicht erreichbar oder unbestimmt).",
        "regression": "Rückschritt: In {weeks} wurde kein Post-Quanten-Schlüsselaustausch mehr ausgehandelt.",
        "lower_bound": "Das Fenster ist eine Untergrenze: Vor unserer ersten Beobachtung kann bereits klassischer Schlüsselaustausch genutzt worden sein.",
        "timeline": "Wöchentliche Zeitleiste", "week": "Woche", "state": "Beobachtung", "grade": "Note", "group": "Schlüsselaustausch",
        "proof": "Nachweis",
        "states": {"observed_pq": "post-quanten", "observed_classical": "klassisch", "undetermined": "unbestimmt", "unreachable": "keine Antwort"},
        "anchor_pending": "verankert, Bitcoin-Bestätigung ausstehend", "anchor_complete": "in Bitcoin-Block {block} verankert", "anchor_none": "noch nicht verankert",
        "peers": "Gleiches Netzwerk, gleiche Woche", "peers_stat": "Bei {net}: {pq} von {n} gemessenen Websites ({pct} %) handeln diese Woche Post-Quanten-Schlüsselaustausch aus.",
        "since": "PQ seit {week}",
        "verify_title": "Diesen Eintrag selbst prüfen",
        "verify_body": "Der Fingerabdruck jeder Zeile ist sha256(\"quantum-aether-v1|domain|state|grade|tls|group|checked_at\"). Das Wochenmanifest enthält sha256(\"quantum-aether-domain-v1|{domain}\") mit diesem Fingerabdruck; der sha256 des Manifests ist per OpenTimestamps zeitgestempelt. Manifest und .ots-Nachweis herunterladen, dann: ots verify WOCHE.manifest.txt.ots",
        "claim_title": "Ist das Ihre Domain? Seite beanspruchen",
        "claim_body": "Veröffentlichen Sie diesen DNS-TXT-Eintrag und klicken Sie auf Prüfen. Eine beanspruchte Seite zeigt, dass der Inhaber sie bestätigt hat; die Messungen ändern sich nicht.",
        "claim_button": "DNS-Eintrag prüfen", "claimed": "Vom Domain-Inhaber beansprucht (DNS-TXT geprüft am {date}).",
        "claim_ok": "Bestätigt. Die Seite ist beansprucht — mit täglichem Monitoring erfahren Sie jeden Rückschritt innerhalb eines Tages.",
        "claim_fail": "Eintrag noch nicht gefunden. DNS-Änderungen brauchen einige Minuten; bitte gleich erneut versuchen.",
        "claim_wait": "Bitte 30 Sekunden zwischen zwei Prüfungen warten.",
        "trial_title": "Halten Sie den Eintrag sauber: tägliches Monitoring für {domain}",
        "trial_sub": "Das Register prüft einmal pro Woche. Das Monitoring prüft täglich, auch api-/mail-/login-Subdomains, und meldet per E-Mail, wenn der Post-Quanten-Schlüsselaustausch verschwindet. 14 Tage kostenlos, ohne Karte.",
        "disclaimer": "Nur externe Beobachtung des öffentlichen HTTPS-Endpunkts (ein TLS-Handshake pro Woche auf Port 443, von einem Standort). Keine Compliance-Zertifizierung, kein Audit und keine Rechtsberatung; keine Aussage über die Sicherheit der Anwendung oder interner Systeme.",
        "anchors_title": "Wöchentliche Verankerungen", "rows": "Zeilen", "download": "Manifest · Nachweis · JSON",
        "index_examples": "Beispiele", "index_banks": "Banken", "more": "Seite pro Domain: /exposure/<domain>",
        "unknown": "Für {domain} liegt noch keine wöchentliche Beobachtung vor.",
        "terms_link": "Datenlizenz und Nutzungsbedingungen", "truncated": "Angezeigt werden die letzten {n} Wochen. Die vollständige Historie gibt es mit API-Schlüssel (siehe Datenlizenz).",
        "related_site": "Aktuelles Scan-Ergebnis", "related_registry": "Expositionsregister",
    },
}


def register(bp, deps):
    """deps: db, lang, base, data_dir (callable), de_pages, de_endpoints, salt (callable)."""
    for e in ENDPOINTS:
        deps["de_pages"].add(e)
        deps["de_endpoints"].add(e)

    def copy():
        return T.get(deps["lang"](), T["en"])

    def current_key():
        """مفتاح API صالح من ترويسة Authorization: Bearer أو X-API-Key (مخزّن في g لكل طلب)."""
        if "qa_api_key" not in g:
            key = data_access.key_from_headers(request.headers)
            g.qa_api_key = data_access.lookup_key(deps["db"](), key) if key else None
        return g.qa_api_key

    def key_required():
        resp = jsonify(error="api_key_required",
                       message="Full multi-week history and bulk exports need an API key (Authorization: Bearer <key>). "
                               "See the data licence for terms.", terms_url=deps["base"]() + "/data-license")
        resp.status_code = 401
        resp.headers["WWW-Authenticate"] = 'Bearer realm="quantum-aether-data"'
        return resp

    def too_many(bucket, retry):
        retry = max(1, int(retry))
        if bucket == "pages":
            resp = make_response("Too many requests. Please slow down, or use the open data files (/adoption.csv) "
                                 "or an API key. Terms: /data-license\n", 429)
            resp.mimetype = "text/plain"
        else:
            resp = jsonify(error="rate_limited", retry_after_seconds=retry, terms_url=deps["base"]() + "/data-license")
            resp.status_code = 429
        resp.headers["Retry-After"] = str(retry)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Robots-Tag"] = "noindex"
        return resp

    @bp.before_app_request
    def _anti_scrape_guard():
        """حدود لكل IP على /exposure و /site و ملفات البيانات و /api/v1. الزواحف الموثّقة مستثناة، ومفاتيح API أعلى."""
        cfg = current_app.config
        if (cfg.get("TESTING") and not cfg.get("RATE_LIMIT_ENABLED")) or os.environ.get("QS_RATE_LIMIT", "on") == "off":
            return None
        bucket = data_access.bucket_for(request.path)
        if not bucket or request.method == "OPTIONS":
            return None
        try:
            data_dir = deps["data_dir"]()
            ip = request.remote_addr or ""
            info = current_key()
            if info:
                tier, ident = "key", f"key:{info['id']}"
            else:
                family = data_access.bot_family(request.headers.get("User-Agent"))
                if family and data_access.verify_bot(ip, family, data_dir):
                    return None  # verified search/AI crawler: never limited
                tier, ident = ("declared_bot" if family else "anon"), data_access.client_key(ip)
            retry = data_access.hit(data_dir, ident, bucket, data_access.LIMITS[bucket][tier])
            net = data_access.network_key(ip) if tier != "key" else None
            if net and not retry:
                retry = data_access.hit(data_dir, net, bucket, data_access.NET_LIMITS[bucket])
        except Exception:
            log.exception("rate limiter failed open")
            return None
        if retry:
            return too_many(bucket, retry)
        return None

    @bp.get("/data-license")
    def data_license():
        lang = deps["lang"]()
        return render_template("data_license.html", d=terms.TERMS.get(lang, terms.TERMS["en"]))

    @bp.get("/api/v1/registry/export.csv")
    def registry_export():
        """تصدير جماعي (بمفتاح API فقط): كل النطاقات لآخر N أسبوعاً (أو الكل)، مع كناري خاص بالمفتاح ومسجَّل."""
        info = current_key()
        if not info:
            return key_required()
        conn = deps["db"]()
        weeks = adoption.weeks(conn)
        try:
            n = int(request.args.get("weeks") or 0)
        except ValueError:
            n = 0
        if n > 0:
            weeks = weeks[-n:]
        salt = deps["salt"]()
        optout = adoption.load_optout(conn=conn)
        out_rows = []
        for week in weeks:
            rows = [r for r in adoption.rows_for(conn, week)
                    if not search_indexing.is_excluded(r["domain"]) and not adoption.opted_out(r["domain"], optout)]
            canaries = data_access.pick_canaries(conn, salt, "registry_export", week, f"key:{info['id']}")
            if canaries:
                data_access.log_canaries(conn, "registry_export", week, canaries, api_key_id=info["id"],
                                         user_agent=request.headers.get("User-Agent"))
            out_rows += data_access.watermark_rows(rows, canaries, salt, week)
        resp = Response(adoption.to_csv(out_rows), mimetype="text/csv")
        resp.headers["Content-Disposition"] = 'attachment; filename="quantum-aether-registry.csv"'
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Robots-Tag"] = "noindex"
        resp.headers["Link"] = f'<{deps["base"]()}/data-license>; rel="license"'
        return resp

    def normalize_or_404(domain):
        try:
            domain = quantum_vuln_scanner.normalize_domain(domain)
        except quantum_vuln_scanner.ScanError:
            abort(404)
        conn = deps["db"]()
        if search_indexing.is_excluded(domain) or adoption.opted_out(domain, adoption.load_optout(conn=conn)):
            abort(410)
        if data_access.is_canary(conn, domain):
            abort(404)
        return domain, conn

    @bp.get("/exposure")
    def exposure_index():
        conn = deps["db"]()
        data_dir = deps["data_dir"]()
        all_anchors = exposure.anchors(data_dir)
        weeks = adoption.weeks(conn)
        examples, banks = [], []
        if weeks:
            optout = adoption.load_optout(conn=conn)
            for r in conn.execute("SELECT domain, rank, sector, pq, grade FROM adoption_results WHERE week = ? AND ok = 1 "
                                  "AND unsure = 0 AND (rank <= 25 OR sector LIKE 'banks-%') ORDER BY rank IS NULL, rank, domain",
                                  (weeks[-1],)):
                if search_indexing.is_excluded(r["domain"]) or adoption.opted_out(r["domain"], optout):
                    continue
                (banks if (r["sector"] or "").startswith("banks-") else examples).append(dict(r))
        return render_template("exposure_index.html", x=copy(), anchors=all_anchors[::-1], examples=examples[:20],
                               banks=banks[:40])

    @bp.get("/exposure/<domain>")
    def exposure_page(domain):
        domain, conn = normalize_or_404(domain)
        data = exposure.window(conn, domain, data_dir=deps["data_dir"]())
        x = copy()
        if not data:
            resp = make_response(render_template("exposure.html", x=x, domain=domain, w=None, indexable=False, seo_noindex=True,
                                                 site_known=False), 404)
            resp.headers["X-Robots-Tag"] = "noindex, follow"
            return resp
        claimed = exposure.claim_of(conn, data["domain"])
        status_line = x["st_" + data["status"]]
        meta = x["meta"].format(domain=data["domain"], first=data["first_observed"], status_line=status_line)
        msg = {"ok": x["claim_ok"], "fail": x["claim_fail"], "wait": x["claim_wait"]}.get(request.args.get("claim", ""))
        resp = make_response(render_template(
            "exposure.html", x=x, domain=data["domain"], w=data, indexable=data["indexable"], meta=meta,
            seo_noindex=not data["indexable"],
            site_known=bool(deps["site_known"]([data["domain"]])) if deps.get("site_known") else True,
            claimed=claimed, claim_msg=msg, claim_record=f"{exposure.CLAIM_PREFIX}.{data['domain']}",
            claim_token=exposure.claim_token(data["domain"], deps["salt"]()), domain_key=exposure.domain_key(data["domain"])))
        if not data["indexable"]:
            resp.headers["X-Robots-Tag"] = "noindex, follow"
        return resp

    @bp.post("/exposure/<domain>/claim")
    def exposure_claim(domain):
        if request.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
            abort(400)
        domain, conn = normalize_or_404(domain)
        lang = request.form.get("lang") if request.form.get("lang") in T else "en"
        if not exposure.window(conn, domain, peers=False):
            abort(404)
        back = lambda state: redirect(url_for("site.exposure_page", domain=domain, lang=lang, claim=state) + "#claim", code=303)
        if not exposure.claim_allowed(conn, domain):
            return back("wait")
        res = exposure.verify_claim(domain, deps["salt"]())
        if not res["verified"]:
            return back("fail")
        exposure.record_claim(conn, domain)
        return back("ok")

    @bp.get("/exposure/anchors/<name>")
    def exposure_anchor_file(name):
        m = ANCHOR_FILE_RE.match(name)
        if not m:
            abort(404)
        path = os.path.join(deps["data_dir"](), "anchors", name)
        if not os.path.isfile(path):
            abort(404)
        mime = {"json": "application/json", "manifest.txt": "text/plain"}.get(m.group(2), "application/octet-stream")
        resp = send_file(path, mimetype=mime, as_attachment=m.group(2).endswith("ots"), download_name=name, max_age=3600)
        resp.headers["X-Robots-Tag"] = "noindex"
        resp.headers["Access-Control-Allow-Origin"] = "*"
        return resp

    @bp.get("/api/v1/exposure/<domain>")
    def exposure_api(domain):
        try:
            domain = quantum_vuln_scanner.normalize_domain(domain)
        except quantum_vuln_scanner.ScanError:
            return jsonify(error="invalid_domain"), 400
        conn = deps["db"]()
        if search_indexing.is_excluded(domain) or adoption.opted_out(domain, adoption.load_optout(conn=conn)):
            return jsonify(error="not_available", domain=domain), 410
        if data_access.is_canary(conn, domain):
            return jsonify(error="not_tracked", domain=domain), 404
        full = request.args.get("history") == "full"
        if full and not current_key():
            return key_required()
        data = window_json(conn, domain, max_weeks=None if full else exposure.PUBLIC_WEEKS)
        if not data:
            return jsonify(error="not_tracked", domain=domain,
                           message="No weekly observation of this domain in the registry yet. Not proof of anything."), 404
        resp = jsonify(data)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["X-Robots-Tag"] = "noindex"
        return resp

    def window_json(conn, domain, max_weeks=exposure.PUBLIC_WEEKS):
        data = exposure.window(conn, domain, data_dir=deps["data_dir"](), max_weeks=max_weeks)
        if not data:
            return None
        base = deps["base"]()
        data["page_url"] = f"{base}/exposure/{data['domain']}"
        for row in data["timeline"]:
            if row["anchor"]:
                row["anchor"].update({"manifest_url": f"{base}/exposure/anchors/{row['week']}.manifest.txt",
                                      "proof_url": f"{base}/exposure/anchors/{row['week']}.manifest.txt.ots",
                                      "domain_key": exposure.domain_key(data["domain"])})
        data["monitoring_trial_url"] = f"{base}/monitoring?domain={data['domain']}"
        data["terms_url"] = f"{base}/data-license"
        data["license"] = ("Quote individual entries with attribution (Source: Quantum Aether Exposure Registry + link). "
                           "Bulk copying, resale or rebuilding the registry needs a licence. See terms_url.")
        if data.get("history_truncated"):
            data["full_history"] = "Older weeks are available with an API key: GET /api/v1/exposure/<domain>?history=full"
        return data

    global _WINDOW_JSON
    _WINDOW_JSON = window_json

    @bp.get("/sitemap-exposure-<int:n>.xml")
    def sitemap_exposure(n):
        rows = exposure.sitemap_domains(deps["db"](), adoption.load_optout(conn=deps["db"]()))
        chunk = rows[(n - 1) * SITEMAP_CHUNK:n * SITEMAP_CHUNK] if n >= 1 else []
        if not chunk:
            abort(404)
        base = deps["base"]()
        parts = []
        for d, day in chunk:
            path = f"/exposure/{d}"
            alts = "".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{base}{path}?lang={l}"/>' for l in ("en", "ar", "de"))
            alts += f'<xhtml:link rel="alternate" hreflang="x-default" href="{base}{path}?lang=en"/>'
            for l in ("en", "ar", "de"):
                parts.append(f"  <url><loc>{base}{path}?lang={l}</loc><lastmod>{day}</lastmod>{alts}</url>\n")
        body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
                + "".join(parts) + "</urlset>\n")
        return Response(body, mimetype="application/xml")


_WINDOW_JSON = None


def window_for(conn, domain):
    """للأداة exposure_window في MCP: نفس JSON الواجهة /api/v1/exposure/<domain>."""
    return _WINDOW_JSON(conn, domain) if _WINDOW_JSON else None


def watermark_export(conn, rows, export, week, salt, client_hash, user_agent=None):
    """للملفات المفتوحة (/adoption.csv و /adoption.json): كناريان لكل مُصدِّر/أسبوع/يوم، مسجّلان سراً."""
    try:
        import datetime as _dt
        canaries = data_access.pick_canaries(conn, salt, export, week, f"{client_hash}|{_dt.date.today().isoformat()}")
        if not canaries:
            return list(rows)
        data_access.log_canaries(conn, export, week, canaries, client_hash=client_hash, user_agent=user_agent)
        return data_access.watermark_rows(rows, canaries, salt, week)
    except Exception:
        log.exception("watermark failed; serving unmarked rows")
        return list(rows)


def sitemap_entries(conn, base, optout=None):
    """أجزاء خريطة /exposure/ لفهرس sitemap.xml (فقط النطاقات المفهرسة)."""
    rows = exposure.sitemap_domains(conn, optout)
    out = []
    for i in range(0, len(rows), SITEMAP_CHUNK):
        chunk = rows[i:i + SITEMAP_CHUNK]
        out.append((f"{base}/sitemap-exposure-{i // SITEMAP_CHUNK + 1}.xml", max(day for _, day in chunk)))
    return out
