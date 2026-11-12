"""Post-quantum TLS estate audit for organizations: an offer page plus an invoice request form.

No online payment: the owner reads the request, sends an invoice (bank transfer or PayPal) and delivers by hand.
The page text promises only what the scanner and the subdomain discovery actually measure.
"""
import datetime as dt

REQUESTS_PER_CLIENT_PER_DAY = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT NOT NULL,
    name        TEXT,
    org         TEXT NOT NULL,
    domain      TEXT NOT NULL,
    message     TEXT,
    lang        TEXT NOT NULL DEFAULT 'en',
    client_hash TEXT,
    is_test     INTEGER NOT NULL DEFAULT 0,
    consent_at  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""


def init(conn):
    conn.executescript(SCHEMA)


def _now(delta=None):
    moment = dt.datetime.now(dt.timezone.utc) + (delta or dt.timedelta())
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def rate_limited(conn, client_hash):
    since = _now(dt.timedelta(days=-1))
    n = conn.execute("SELECT COUNT(*) FROM audit_requests WHERE client_hash = ? AND created_at >= ?",
                     (client_hash, since)).fetchone()[0]
    return n >= REQUESTS_PER_CLIENT_PER_DAY


def create(conn, *, email, name, org, domain, message, lang, client_hash, is_test):
    with conn:
        cur = conn.execute(
            "INSERT INTO audit_requests (email,name,org,domain,message,lang,client_hash,is_test,consent_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (email, name, org, domain, message, lang, client_hash, 1 if is_test else 0, _now()))
    return cur.lastrowid


def owner_email(req_id, req, discovery_summary, base_url):
    """Plain-text lead mail for the owner, with whatever we already measured for that domain."""
    lines = [f"Audit request #{req_id}",
             f"Organization: {req['org']}",
             f"Name: {req['name'] or '-'}",
             f"Email: {req['email']}",
             f"Domain: {req['domain']}",
             f"Language: {req['lang']}",
             "", "Message:", req["message"] or "-", ""]
    d = discovery_summary or {}
    if d.get("status") == "DONE":
        lines.append(f"Existing discovery: {d['names']} names, {d['responding']} responding, "
                     f"{d['not_pq']} not PQ, {d['pq']} PQ, {d['unknown']} undetermined.")
    else:
        lines.append("No subdomain discovery on file yet: run one from a scan page before replying.")
    lines.append(f"Public page: {base_url}/site/{req['domain']}")
    return f"[Quantum Aether] Audit request: {req['org']} ({req['domain']})", "\n".join(lines)


COPY = {
    "en": dict(
        title="Post-quantum TLS audit for your whole domain",
        meta="Every public subdomain of your organization checked for post-quantum key exchange (X25519MLKEM768), "
             "with a prioritised fix plan and dated evidence for NIS2 and DORA reviews. Paid by invoice.",
        eyebrow="For security and compliance teams",
        lead="Your main website can pass while dozens of subdomains still use classical key exchange. "
             "We check them all and tell you which to fix first.",
        example="Example from our measurements: a German bank whose www site gets grade A still had 39 of 124 "
                "responding subdomains without post-quantum key exchange.",
        included_title="What you get",
        included=["Every subdomain we find in public Certificate Transparency logs (up to 200 hosts), "
                  "checked for TLS version and key-exchange group",
                  "A list of hosts without post-quantum key exchange, sorted by priority, with the fix "
                  "for the server or CDN each one runs on",
                  "A dated PDF report you can hand to your auditor, with references to NIS2 Art. 21(2)(h) "
                  "and DORA ICT risk requirements",
                  "A free re-check 30 days later to confirm the fixes",
                  "Delivery within 3 working days"],
        limits="This audit covers the key exchange of public HTTPS endpoints only. It is not a penetration test "
               "and does not assess application security.",
        price_title="Price",
        price_line="{price} {currency} per organization (one registrable domain), one-time.",
        pay_line="Paid by invoice: bank transfer or PayPal. No subscription.",
        form_title="Request an audit and invoice",
        name="Your name", email="Work email", org="Organization", domain="Domain (e.g. example.com)",
        message="Anything we should know (optional)",
        consent="I agree that Quantum Aether stores these details to answer my request and send an invoice.",
        privacy="Privacy",
        submit="Request audit",
        sent_title="Request received",
        sent="Thank you. We will reply to {email} within one working day with the invoice and next steps.",
        err_consent="Please confirm the consent box.",
        err_email="Please enter a valid work email address.",
        err_fields="Please fill in organization and domain.",
        err_domain="Please enter a valid public domain name.",
        err_limit="Too many requests from your network today. Please write to the email in the Impressum.",
        err_unavailable="The request could not be sent right now. Please write to the email in the Impressum.",
        cta="Audit all subdomains for your organization",
    ),
    "ar": dict(
        title="تدقيق TLS المقاوم للحوسبة الكمومية لنطاقك كاملاً",
        meta="نفحص كل النطاقات الفرعية العامة لمؤسستك بحثاً عن تبادل مفاتيح مقاوم للكم (X25519MLKEM768)، "
             "مع خطة إصلاح مرتّبة وتقرير مؤرَّخ لمراجعات NIS2 وDORA. الدفع بفاتورة.",
        eyebrow="لفرق الأمن والامتثال",
        lead="قد ينجح موقعك الرئيسي بينما تبقى عشرات النطاقات الفرعية على تبادل المفاتيح التقليدي. "
             "نفحصها كلها ونخبرك بما تبدأ بإصلاحه.",
        example="مثال من قياساتنا: بنك ألماني موقعه www بدرجة A، لكن 39 من 124 نطاقاً فرعياً يستجيب كانت بلا "
                "تبادل مفاتيح مقاوم للكم.",
        included_title="ما تحصل عليه",
        included=["كل نطاق فرعي نجده في سجلات شفافية الشهادات العامة (حتى 200 مضيف)، مع إصدار TLS ومجموعة "
                  "تبادل المفاتيح لكل واحد",
                  "قائمة بالمضيفات غير المقاومة للكم مرتّبة حسب الأولوية، مع طريقة الإصلاح للخادم أو شبكة CDN "
                  "التي يعمل عليها كل منها",
                  "تقرير PDF مؤرَّخ تقدّمه للمدقق، مع الإحالة إلى المادة 21(2)(h) من NIS2 ومتطلبات مخاطر "
                  "تقنية المعلومات في DORA",
                  "إعادة فحص مجانية بعد 30 يوماً للتأكد من الإصلاح",
                  "التسليم خلال 3 أيام عمل"],
        limits="يغطي هذا التدقيق تبادل المفاتيح في نقاط HTTPS العامة فقط. ليس اختبار اختراق ولا يقيّم أمان "
               "التطبيقات.",
        price_title="السعر",
        price_line="{price} {currency} لكل مؤسسة (نطاق رئيسي واحد)، دفعة واحدة.",
        pay_line="الدفع بفاتورة: تحويل بنكي أو PayPal. بلا اشتراك.",
        form_title="اطلب التدقيق والفاتورة",
        name="اسمك", email="بريد العمل", org="المؤسسة", domain="النطاق (مثل example.com)",
        message="أي شيء نحتاج معرفته (اختياري)",
        consent="أوافق على أن يحفظ Quantum Aether هذه البيانات للرد على طلبي وإرسال الفاتورة.",
        privacy="الخصوصية",
        submit="اطلب التدقيق",
        sent_title="وصل طلبك",
        sent="شكراً. سنرد على {email} خلال يوم عمل واحد بالفاتورة والخطوات التالية.",
        err_consent="يرجى تأكيد خانة الموافقة.",
        err_email="يرجى إدخال بريد عمل صحيح.",
        err_fields="يرجى إدخال اسم المؤسسة والنطاق.",
        err_domain="يرجى إدخال اسم نطاق عام صحيح.",
        err_limit="طلبات كثيرة من شبكتك اليوم. راسلنا عبر البريد في صفحة Impressum.",
        err_unavailable="تعذّر إرسال الطلب الآن. راسلنا عبر البريد في صفحة Impressum.",
        cta="دقّق كل النطاقات الفرعية لمؤسستك",
    ),
    "de": dict(
        title="Post-Quanten-TLS-Audit für Ihre gesamte Domain",
        meta="Alle öffentlichen Subdomains Ihrer Organisation auf Post-Quanten-Schlüsselaustausch (X25519MLKEM768) "
             "geprüft, mit priorisiertem Maßnahmenplan und datiertem Nachweis für NIS2- und DORA-Prüfungen. "
             "Zahlung auf Rechnung.",
        eyebrow="Für Security- und Compliance-Teams",
        lead="Ihre Hauptwebsite kann bestehen, während Dutzende Subdomains noch klassischen Schlüsselaustausch "
             "nutzen. Wir prüfen alle und sagen Ihnen, was Sie zuerst beheben sollten.",
        example="Beispiel aus unseren Messungen: Eine deutsche Bank mit Note A auf www hatte bei 39 von 124 "
                "erreichbaren Subdomains keinen Post-Quanten-Schlüsselaustausch.",
        included_title="Leistungsumfang",
        included=["Alle Subdomains aus öffentlichen Certificate-Transparency-Logs (bis 200 Hosts), geprüft auf "
                  "TLS-Version und Schlüsselaustausch-Gruppe",
                  "Liste der Hosts ohne Post-Quanten-Schlüsselaustausch, nach Priorität sortiert, mit der "
                  "Lösung für den jeweiligen Server oder CDN",
                  "Datierter PDF-Bericht für Ihre Prüfer, mit Bezug auf NIS2 Art. 21 Abs. 2 lit. h und die "
                  "IKT-Risikoanforderungen der DORA",
                  "Kostenlose Nachprüfung nach 30 Tagen",
                  "Lieferung innerhalb von 3 Werktagen"],
        limits="Das Audit umfasst nur den Schlüsselaustausch öffentlicher HTTPS-Endpunkte. Es ist kein "
               "Penetrationstest und bewertet keine Anwendungssicherheit.",
        price_title="Preis",
        price_line="{price} {currency} pro Organisation (eine registrierbare Domain), einmalig.",
        pay_line="Zahlung auf Rechnung: Überweisung oder PayPal. Kein Abonnement.",
        form_title="Audit und Rechnung anfordern",
        name="Ihr Name", email="Geschäftliche E-Mail", org="Organisation", domain="Domain (z. B. example.com)",
        message="Was wir wissen sollten (optional)",
        consent="Ich bin einverstanden, dass Quantum Aether diese Angaben speichert, um meine Anfrage zu "
                "beantworten und eine Rechnung zu senden.",
        privacy="Datenschutz",
        submit="Audit anfordern",
        sent_title="Anfrage erhalten",
        sent="Danke. Wir antworten innerhalb eines Werktags an {email} mit Rechnung und nächsten Schritten.",
        err_consent="Bitte bestätigen Sie die Einwilligung.",
        err_email="Bitte geben Sie eine gültige geschäftliche E-Mail-Adresse ein.",
        err_fields="Bitte Organisation und Domain angeben.",
        err_domain="Bitte geben Sie einen gültigen öffentlichen Domainnamen ein.",
        err_limit="Zu viele Anfragen aus Ihrem Netz heute. Bitte schreiben Sie an die E-Mail im Impressum.",
        err_unavailable="Die Anfrage konnte gerade nicht gesendet werden. Bitte schreiben Sie an die E-Mail "
                        "im Impressum.",
        cta="Alle Subdomains Ihrer Organisation prüfen lassen",
    ),
}
