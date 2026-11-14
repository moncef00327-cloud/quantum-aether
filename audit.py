"""Post-quantum TLS estate audit for organizations: an offer page plus an invoice request form.

No online payment: the owner reads the request, sends an invoice (bank transfer or PayPal) and delivers by hand.
The page text promises only what the scanner and the subdomain discovery actually measure.
"""
import datetime as dt

import legal

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
             "with a prioritised fix plan and dated evidence for NIS2 and DORA reviews. One-time PayPal checkout for small companies; enterprise audits by quote.",
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
        pay_line="Small-company audit: PayPal checkout, one-time. Enterprise audit from €1,500 by quote. No subscription.",
        form_title="Enterprise audit — request a quote (from €1,500)",
        name="Your name", email="Work email", org="Organization", domain="Domain (e.g. example.com)",
        message="Anything we should know (optional)",
        consent="I agree that Quantum Aether stores these details to answer my quote request.",
        privacy="Privacy",
        submit="Request enterprise quote",
        sent_title="Request received",
        sent="Thank you. We will reply to {email} within one working day with a quote and next steps.",
        err_consent="Please confirm the consent box.",
        err_email="Please enter a valid work email address.",
        err_fields="Please fill in organization and domain.",
        err_domain="Please enter a valid public domain name.",
        err_limit="Too many requests from your network today. Please write to the email in the Impressum.",
        err_unavailable="The request could not be sent right now. Please write to the email in the Impressum.",
        cta="Audit all subdomains for your organization",
        checkout=dict(title="Small-company audit", price="490 EUR · one-time payment", company="Company name",
                      street="Billing street and number", postal_code="Postal code", city="City", country="Country",
                      name="Contact name", email="Business email", domain="Primary domain",
                      company_buyer="I confirm that I am ordering on behalf of a business.",
                      agb="I accept the AGB (terms and conditions).", contact="I agree to receive emails about the delivery and performance of this audit.",
                      pay_note="PayPal verifies and captures the payment. Credit/debit card is shown only when PayPal enables it for this account and buyer.",
                      enterprise_title="Enterprise audit", enterprise_note="Larger scope and additional requirements: request a quote from €1,500.",
                      error="Payment could not be completed. Please try again or contact us.",
                      success="Payment confirmed. Invoice {invoice_number} will be delivered by email; the subdomain audit has started.",
                      email_pending="Payment is confirmed, but the invoice email could not be sent yet. Please contact us if it does not arrive."),
    ),
    "ar": dict(
        title="تدقيق TLS المقاوم للحوسبة الكمومية لنطاقك كاملاً",
        meta="نفحص كل النطاقات الفرعية العامة لمؤسستك بحثاً عن تبادل مفاتيح مقاوم للكم (X25519MLKEM768)، "
             "مع خطة إصلاح مرتّبة وتقرير مؤرَّخ لمراجعات NIS2 وDORA. دفع فوري للشركات الصغيرة، وعرض سعر للمؤسسات.",
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
        pay_line="تدقيق الشركات الصغيرة: دفع فوري عبر PayPal، مرة واحدة. تدقيق المؤسسات يبدأ من 1,500 € بعرض سعر. بلا اشتراك.",
        form_title="تدقيق المؤسسات — اطلب عرض سعر (ابتداءً من 1,500 €)",
        name="اسمك", email="بريد العمل", org="المؤسسة", domain="النطاق (مثل example.com)",
        message="أي شيء نحتاج معرفته (اختياري)",
        consent="أوافق على أن يحفظ Quantum Aether هذه البيانات للرد على طلب عرض السعر.",
        privacy="الخصوصية",
        submit="اطلب عرض سعر للمؤسسات",
        sent_title="وصل طلبك",
        sent="شكراً. سنرد على {email} خلال يوم عمل واحد بعرض السعر والخطوات التالية.",
        err_consent="يرجى تأكيد خانة الموافقة.",
        err_email="يرجى إدخال بريد عمل صحيح.",
        err_fields="يرجى إدخال اسم المؤسسة والنطاق.",
        err_domain="يرجى إدخال اسم نطاق عام صحيح.",
        err_limit="طلبات كثيرة من شبكتك اليوم. راسلنا عبر البريد في صفحة Impressum.",
        err_unavailable="تعذّر إرسال الطلب الآن. راسلنا عبر البريد في صفحة Impressum.",
        cta="دقّق كل النطاقات الفرعية لمؤسستك",
        checkout=dict(title="تدقيق الشركات الصغيرة", price="490 € · دفعة واحدة", company="اسم الشركة",
                      street="عنوان الفوترة: الشارع ورقم المبنى", postal_code="الرمز البريدي", city="المدينة", country="الدولة",
                      name="اسم المسؤول", email="بريد العمل", domain="النطاق الرئيسي",
                      company_buyer="أؤكد أنني أطلب الخدمة بصفتي شركة.",
                      agb="أوافق على الشروط العامة (AGB).", contact="أوافق على تلقي رسائل بريد تخص تنفيذ هذا التدقيق وتسليمه.",
                      pay_note="يتحقق PayPal من الدفع ويحصّله. يظهر خيار البطاقة فقط إذا أتاحه PayPal لهذا الحساب والمشتري.",
                      enterprise_title="تدقيق المؤسسات", enterprise_note="للنطاقات الأكبر والمتطلبات الإضافية: اطلب عرض سعر يبدأ من 1,500 €.",
                      error="تعذّر إتمام الدفع. حاول مرة أخرى أو تواصل معنا.",
                      success="تم تأكيد الدفع. ستصلك الفاتورة رقم {invoice_number} بالبريد، وبدأ فحص النطاقات الفرعية.",
                      email_pending="تأكد الدفع لكن تعذر إرسال الفاتورة بالبريد الآن؛ تواصل معنا إن لم تصلك لاحقاً."),
    ),
    "de": dict(
        title="Post-Quanten-TLS-Audit für Ihre gesamte Domain",
        meta="Alle öffentlichen Subdomains Ihrer Organisation auf Post-Quanten-Schlüsselaustausch (X25519MLKEM768) "
             "geprüft, mit priorisiertem Maßnahmenplan und datiertem Nachweis für NIS2- und DORA-Prüfungen. "
             "Sofortzahlung für kleine Unternehmen; Enterprise-Audits auf Anfrage.",
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
        pay_line="Audit für kleine Unternehmen: einmalige PayPal-Zahlung. Enterprise-Audit ab 1.500 € auf Anfrage. Kein Abonnement.",
        form_title="Enterprise-Audit — Angebot anfordern (ab 1.500 €)",
        name="Ihr Name", email="Geschäftliche E-Mail", org="Organisation", domain="Domain (z. B. example.com)",
        message="Was wir wissen sollten (optional)",
        consent="Ich bin einverstanden, dass Quantum Aether diese Angaben speichert, um meine Angebotsanfrage zu beantworten.",
        privacy="Datenschutz",
        submit="Enterprise-Angebot anfordern",
        sent_title="Anfrage erhalten",
        sent="Danke. Wir antworten innerhalb eines Werktags an {email} mit einem Angebot und den nächsten Schritten.",
        err_consent="Bitte bestätigen Sie die Einwilligung.",
        err_email="Bitte geben Sie eine gültige geschäftliche E-Mail-Adresse ein.",
        err_fields="Bitte Organisation und Domain angeben.",
        err_domain="Bitte geben Sie einen gültigen öffentlichen Domainnamen ein.",
        err_limit="Zu viele Anfragen aus Ihrem Netz heute. Bitte schreiben Sie an die E-Mail im Impressum.",
        err_unavailable="Die Anfrage konnte gerade nicht gesendet werden. Bitte schreiben Sie an die E-Mail "
                        "im Impressum.",
        cta="Alle Subdomains Ihrer Organisation prüfen lassen",
        checkout=dict(title="Audit für kleine Unternehmen", price="490 € · einmalig", company="Firmenname",
                      street="Rechnungsadresse: Straße und Hausnummer", postal_code="Postleitzahl", city="Ort", country="Land",
                      name="Ansprechperson", email="Geschäftliche E-Mail", domain="Hauptdomain",
                      company_buyer="Ich bestätige, dass ich im Namen eines Unternehmens bestelle.",
                      agb="Ich akzeptiere die AGB.", contact="Ich bin einverstanden, E-Mails zur Durchführung und Zustellung dieses Audits zu erhalten.",
                      pay_note="PayPal prüft und zieht die Zahlung ein. Kredit- oder Debitkarte erscheint nur, wenn PayPal sie für dieses Konto und den Käufer freigibt.",
                      enterprise_title="Enterprise-Audit", enterprise_note="Größerer Umfang oder Zusatzanforderungen: Angebot ab 1.500 € anfordern.",
                      error="Die Zahlung konnte nicht abgeschlossen werden. Bitte versuchen Sie es erneut oder kontaktieren Sie uns.",
                      success="Zahlung bestätigt. Rechnung {invoice_number} wird per E-Mail zugestellt; die Subdomain-Prüfung wurde gestartet.",
                      email_pending="Zahlung bestätigt, aber die Rechnungs-E-Mail konnte noch nicht versendet werden. Bitte kontaktieren Sie uns, falls sie nicht eintrifft."),
    ),
}


def paid_receipt_email(order, base_url):
    lang = order.get("lang") if order.get("lang") in ("en", "ar", "de") else "en"
    subject = {
        "en": "Your Quantum Aether audit payment and invoice {invoice}",
        "ar": "دفعتك وفاتورتك لتدقيق الأثير الكمومي {invoice}",
        "de": "Zahlung und Rechnung für Ihr Quantum-Aether-Audit {invoice}",
    }[lang].format(invoice=order["invoice_number"])
    bodies = {
        "en": ("Hello {name},\n\nYour payment for the post-quantum TLS subdomain audit of {domain} was "
               "verified by our server. Invoice {invoice} for {amount} {currency} is attached.\n\n"
               "We have started discovery and TLS checks of public HTTPS endpoints. Delivery is within "
               "three business days.\n\n{owner}\n{base}"),
        "ar": ("مرحباً {name}،\n\nتحقق خادمنا من دفعتك مقابل تدقيق TLS للنطاقات الفرعية لـ {domain}. "
               "أرفقنا الفاتورة رقم {invoice} بمبلغ {amount} {currency}.\n\n"
               "بدأنا اكتشاف وفحص نقاط HTTPS العامة. يُسلَّم التقرير خلال ثلاثة أيام عمل.\n\n{owner}\n{base}"),
        "de": ("Guten Tag {name},\n\nIhre Zahlung für das Post-Quanten-TLS-Subdomain-Audit von {domain} "
               "wurde serverseitig bestätigt. Die Rechnung {invoice} über {amount} {currency} ist beigefügt.\n\n"
               "Die Entdeckung und Prüfung öffentlicher HTTPS-Endpunkte wurde gestartet. Die Zustellung erfolgt "
               "innerhalb von drei Werktagen.\n\n{owner}\n{base}"),
    }[lang]
    return subject, bodies.format(name=order["name"], domain=order["domain"], invoice=order["invoice_number"],
                                  amount=order["amount"], currency=order["currency"], owner=legal.OWNER, base=base_url)
