"""Dedicated /tools/post-quantum-tls-checker landing page (copy, FAQ, JSON-LD).

The page reuses the existing port-443 TLS handshake scanner (same POST /scan form).
It does not add scan capabilities.
"""
import re

from flask import url_for

UPDATED = "2026-11-24"

# Titles stay within the 60-character SERP limit once " · Quantum Aether" is appended.
COPY = {
    "en": {
        "title": "Post-Quantum TLS Checker (X25519MLKEM768)",
        "description": "Free post-quantum TLS checker: test whether a public HTTPS site negotiates X25519MLKEM768, ML-KEM-768 or ML-KEM-1024 on port 443.",
        "h1": "Post-Quantum TLS Checker — Test ML-KEM / X25519MLKEM768 Support",
        "lead": "Run a live TLS 1.3 handshake on port 443 and see whether the server negotiates a post-quantum key exchange. Free, no account required. The check uses the same public handshake as the Quantum Aether homepage scanner — nothing else is probed.",
        "what_h": "What this checker tests",
        "what_body": """
<p>The probe opens a <strong>TLS 1.3 handshake on TCP port 443</strong> of the hostname you enter. It offers hybrid and pure ML-KEM groups the way current browsers do, answers a HelloRetryRequest once, and records the group the server finally selects.</p>
<ul>
<li><strong>Hybrid key exchange:</strong> <code>X25519MLKEM768</code> (the group Chrome and Firefox offer first), plus the RFC 10024 NIST-curve hybrids <code>SecP256r1MLKEM768</code> and <code>SecP384r1MLKEM1024</code> when the server prefers them.</li>
<li><strong>Pure ML-KEM:</strong> <code>ML-KEM-768</code> and <code>ML-KEM-1024</code>, if the server is configured to accept them.</li>
<li><strong>Classical fallback:</strong> if the server only offers X25519 or a NIST curve, the result is classical — TLS 1.3 alone is not quantum-safe.</li>
</ul>
<p>A public port-443 handshake is evidence of <em>that endpoint's posture at that moment</em>. It does not test other ports, the CDN-to-origin hop, certificates, or an organisation-wide rollout. For a named host, start here; for an estate, use monitoring or a full audit.</p>
""",
        "cta_h": "Keep watching, or collect formal evidence",
        "cta_mon": "Continuous monitoring of public HTTPS endpoints, with email alerts if hybrid key exchange disappears: <strong>Starter 29 €</strong> per month (10 domains) or <strong>Business 99 €</strong> per month (100 domains). A 14-day trial is available.",
        "cta_mon_btn": "Start monitoring (29 € / 99 €)",
        "cta_audit": "Need a dated evidence pack across an organisation's public hostnames? The <strong>PQC Audit is 490 €</strong>. It is a structured inventory and handshake record — not a BSI or government certification.",
        "cta_audit_btn": "PQC Audit (490 €)",
        "guides_h": "How to test and what the result means",
        "guides_intro": "Use these guides after the live check, or when you want to reproduce the handshake yourself.",
        "faq_h": "Frequently asked questions",
        "faq": [
            ("Is TLS 1.3 quantum safe?",
             "<p>Not by default. TLS 1.3 can still complete with classical X25519 or P-256 key exchange, which a future large quantum computer could break. A connection is post-quantum at the key-exchange layer only when a hybrid or ML-KEM group such as <code>X25519MLKEM768</code> is negotiated.</p>"),
            ("Do I need a post-quantum certificate?",
             "<p>Not for this check. A server can negotiate <code>X25519MLKEM768</code> with a classical RSA or ECDSA certificate. Post-quantum certificates (ML-DSA) are a later, separate migration. This checker reports the key-exchange group on port 443; it does not require a PQ certificate.</p>"),
            ("What is X25519MLKEM768?",
             "<p><code>X25519MLKEM768</code> is a TLS 1.3 hybrid key agreement defined in RFC 10024: it combines X25519 with ML-KEM-768 so the session remains safe if either algorithm is broken. Chrome has offered it by default since version 131. It is the group most public websites will negotiate first once they enable post-quantum TLS.</p>"),
            ("What exactly does a passing result mean?",
             "<p>It means the public hostname completed a TLS 1.3 handshake on port 443 using a post-quantum (hybrid or ML-KEM) group at the time of the test. It is not a certificate of compliance with BSI TR-02102-2, CNSA 2.0, NIS2 or DORA, and it does not speak for other IPs, subdomains, or the origin behind a CDN.</p>"),
        ],
    },
    "ar": {
        "title": "فاحص TLS المقاوم للكم (X25519MLKEM768)",
        "description": "فاحص مجاني لـ TLS المقاوم للكم: تحقق إن كان الموقع يتفاوض على X25519MLKEM768 أو ML-KEM-768 أو ML-KEM-1024 على المنفذ 443.",
        "h1": "فاحص TLS المقاوم للكم — اختبر دعم ML-KEM وX25519MLKEM768",
        "lead": "نفّذ مصافحة TLS 1.3 مباشرة على المنفذ 443 لترى إن كان الخادم يتفاوض على تبادل مفاتيح مقاوم للكم. مجاني ودون حساب. الفحص هو نفسه المستخدم في الصفحة الرئيسية، ولا يُفحص أي شيء خارج هذه المصافحة.",
        "what_h": "ماذا يفحص هذا الأداة؟",
        "what_body": """
<p>تُفتح <strong>مصافحة TLS 1.3 على المنفذ 443</strong> للاسم الذي تدخله. تُعرض المجموعات الهجينة وML-KEM كما تفعل المتصفحات الحالية، ويُجاب على HelloRetryRequest مرة واحدة، ثم تُسجَّل المجموعة التي يختارها الخادم.</p>
<ul>
<li><strong>التبادل الهجين:</strong> <code>X25519MLKEM768</code> (المجموعة التي يعرضها Chrome وFirefox أولاً)، إضافة إلى مجموعات RFC 10024 ذات منحنيات NIST إن فضّلها الخادم.</li>
<li><strong>ML-KEM الصرف:</strong> <code>ML-KEM-768</code> و<code>ML-KEM-1024</code> إذا كان الخادم يقبلها.</li>
<li><strong>التراجع التقليدي:</strong> إذا عرض الخادم X25519 أو منحنى NIST فقط فالنتيجة كلاسيكية — TLS 1.3 وحده ليس مقاوماً للكم.</li>
</ul>
<p>مصافحة المنفذ 443 دليل على <em>وضع نقطة النهاية تلك في تلك اللحظة</em> فقط. لا تفحص منافذ أخرى ولا المسار بين CDN والأصل ولا الشهادات ولا انتشار المؤسسة بالكامل.</p>
""",
        "cta_h": "واصل المراقبة، أو اجمع دليلاً رسمياً",
        "cta_mon": "مراقبة مستمرة لنقاط HTTPS العامة، مع تنبيه بالبريد إذا اختفى التبادل الهجين: <strong>Starter بـ 29 €</strong> شهرياً (10 نطاقات) أو <strong>Business بـ 99 €</strong> شهرياً (100 نطاق). تتوفر تجربة 14 يوماً.",
        "cta_mon_btn": "ابدأ المراقبة (29 € / 99 €)",
        "cta_audit": "تحتاج حزمة أدلة مؤرخة لكل الأسماء العامة؟ <strong>تدقيق PQC بسعر 490 €</strong>. هذا جرد منظم وسجل مصافحات، وليس شهادة BSI أو اعتماداً حكومياً.",
        "cta_audit_btn": "تدقيق PQC (490 €)",
        "guides_h": "كيف تختبر وماذا تعني النتيجة",
        "guides_intro": "استخدم هذه الأدلة بعد الفحص المباشر، أو إذا أردت إعادة المصافحة بنفسك من سطر الأوامر.",
        "faq_h": "أسئلة شائعة",
        "faq": [
            ("هل TLS 1.3 مقاوم للكم؟",
             "<p>ليس افتراضياً. يمكن لـ TLS 1.3 أن يكتمل بتبادل تقليدي X25519 أو P-256. يصبح التبادل مقاوماً للكم فقط عند التفاوض على مجموعة هجينة أو ML-KEM مثل <code>X25519MLKEM768</code>.</p>"),
            ("هل أحتاج شهادة مقاومة للكم؟",
             "<p>لا لهذا الفحص. يمكن للخادم التفاوض على <code>X25519MLKEM768</code> بشهادة RSA أو ECDSA تقليدية. شهادات ML-DSA مرحلة لاحقة منفصلة. هذا الفاحص يبلّغ عن مجموعة تبادل المفاتيح على المنفذ 443 فقط.</p>"),
            ("ما هي X25519MLKEM768؟",
             "<p>مجموعة اتفاق مفاتيح هجينة في TLS 1.3 حسب RFC 10024: تجمع X25519 مع ML-KEM-768. يعرضها Chrome افتراضياً منذ الإصدار 131، وهي عادة أول مجموعة تتفاوض عليها المواقع العامة بعد تفعيل TLS المقاوم للكم.</p>"),
            ("ماذا تعني النتيجة الناجحة بالضبط؟",
             "<p>تعني أن الاسم العام أكمل مصافحة TLS 1.3 على المنفذ 443 بمجموعة هجينة أو ML-KEM وقت الفحص. ليست شهادة امتثال لـ BSI TR-02102-2 أو CNSA 2.0 أو NIS2 أو DORA، ولا تمثّل عناوين IP أو نطاقاً فرعياً أو الأصل خلف CDN.</p>"),
        ],
    },
    "de": {
        "title": "Post-Quanten-TLS-Checker (X25519MLKEM768)",
        "description": "Kostenloser Post-Quanten-TLS-Checker: Prüfen Sie, ob eine öffentliche HTTPS-Site X25519MLKEM768, ML-KEM-768 oder ML-KEM-1024 auf Port 443 aushandelt.",
        "h1": "Post-Quanten-TLS-Checker — ML-KEM / X25519MLKEM768 prüfen",
        "lead": "Führen Sie einen Live-TLS-1.3-Handshake auf Port 443 aus und sehen Sie, ob der Server einen Post-Quanten-Schlüsselaustausch aushandelt. Kostenlos, ohne Konto. Es ist derselbe öffentliche Handshake wie auf der Startseite — es wird nichts anderes geprüft.",
        "what_h": "Was dieser Checker prüft",
        "what_body": """
<p>Die Sonde öffnet einen <strong>TLS-1.3-Handshake auf TCP-Port 443</strong> des eingegebenen Hostnamens. Sie bietet hybride und reine ML-KEM-Gruppen wie aktuelle Browser, beantwortet einmal ein HelloRetryRequest und hält die vom Server gewählte Gruppe fest.</p>
<ul>
<li><strong>Hybrider Schlüsselaustausch:</strong> <code>X25519MLKEM768</code> (die Gruppe, die Chrome und Firefox zuerst anbieten), plus die NIST-Kurven-Hybride aus RFC 10024, wenn der Server sie bevorzugt.</li>
<li><strong>Reines ML-KEM:</strong> <code>ML-KEM-768</code> und <code>ML-KEM-1024</code>, sofern der Server sie akzeptiert.</li>
<li><strong>Klassischer Rückfall:</strong> bietet der Server nur X25519 oder eine NIST-Kurve an, ist das Ergebnis klassisch — TLS 1.3 allein ist nicht quantensicher.</li>
</ul>
<p>Ein öffentlicher Handshake auf Port 443 belegt die <em>Haltung genau dieses Endpunkts zu diesem Zeitpunkt</em>. Andere Ports, der Weg vom CDN zum Origin, Zertifikate und eine organisationsweite Einführung werden nicht geprüft.</p>
""",
        "cta_h": "Weiter beobachten oder formelle Nachweise sammeln",
        "cta_mon": "Kontinuierliche Überwachung öffentlicher HTTPS-Endpunkte mit E-Mail-Alarm, wenn der hybride Schlüsselaustausch verschwindet: <strong>Starter 29 €</strong> pro Monat (10 Domains) oder <strong>Business 99 €</strong> pro Monat (100 Domains). Eine 14-tägige Testphase ist möglich.",
        "cta_mon_btn": "Monitoring starten (29 € / 99 €)",
        "cta_audit": "Sie brauchen ein datiertes Evidence Pack über die öffentlichen Hostnamen einer Organisation? Das <strong>PQC-Audit kostet 490 €</strong>. Es ist ein strukturiertes Inventar und Handshake-Protokoll — keine BSI- oder behördliche Zertifizierung.",
        "cta_audit_btn": "PQC-Audit (490 €)",
        "guides_h": "So testen Sie und was das Ergebnis bedeutet",
        "guides_intro": "Nutzen Sie diese Leitfäden nach dem Live-Check oder wenn Sie den Handshake selbst nachstellen wollen.",
        "faq_h": "Häufige Fragen",
        "faq": [
            ("Ist TLS 1.3 quantensicher?",
             "<p>Nicht standardmäßig. TLS 1.3 kann weiterhin mit klassischem X25519- oder P-256-Schlüsselaustausch abgeschlossen werden. Quantensicher ist der Schlüsselaustausch erst, wenn eine hybride oder ML-KEM-Gruppe wie <code>X25519MLKEM768</code> ausgehandelt wird.</p>"),
            ("Brauche ich ein Post-Quanten-Zertifikat?",
             "<p>Nicht für diese Prüfung. Ein Server kann <code>X25519MLKEM768</code> mit einem klassischen RSA- oder ECDSA-Zertifikat aushandeln. Post-Quanten-Zertifikate (ML-DSA) sind eine spätere, getrennte Migration. Dieser Checker berichtet die Schlüsselaustauschgruppe auf Port 443.</p>"),
            ("Was ist X25519MLKEM768?",
             "<p><code>X25519MLKEM768</code> ist eine hybride TLS-1.3-Schlüsselvereinbarung nach RFC 10024: sie kombiniert X25519 mit ML-KEM-768. Chrome bietet sie seit Version 131 standardmäßig an. Das ist typischerweise die erste Gruppe, die öffentliche Websites aushandeln, sobald Post-Quanten-TLS aktiv ist.</p>"),
            ("Was bedeutet ein positives Ergebnis genau?",
             "<p>Der öffentliche Hostname hat zum Testzeitpunkt einen TLS-1.3-Handshake auf Port 443 mit einer Post-Quanten-Gruppe (hybrid oder ML-KEM) abgeschlossen. Das ist keine Konformitätsbescheinigung nach BSI TR-02102-2, CNSA 2.0, NIS2 oder DORA und gilt nicht automatisch für andere IPs, Subdomains oder den Origin hinter einem CDN.</p>"),
        ],
    },
}


def page(lang):
    return COPY.get(lang) or COPY["en"]


def jsonld(lang, base, org):
    p = page(lang)
    url = base + url_for("site.pq_tls_checker_page", lang=lang)
    faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "inLanguage": lang,
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", a)}}
            for q, a in p["faq"]
        ],
    }
    app = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": p["h1"] if lang != "en" else "Post-Quantum TLS Checker",
        "applicationCategory": "SecurityApplication",
        "operatingSystem": "Web",
        "description": p["description"],
        "url": url,
        "inLanguage": lang,
        "publisher": org,
        "offers": [
            {"@type": "Offer", "price": "0", "priceCurrency": "EUR", "name": p["title"]},
            {"@type": "Offer", "price": "29.00", "priceCurrency": "EUR", "name": "Starter monitoring"},
            {"@type": "Offer", "price": "99.00", "priceCurrency": "EUR", "name": "Business monitoring"},
            {"@type": "Offer", "price": "490", "priceCurrency": "EUR", "name": "PQC Audit"},
        ],
    }
    return [app, faq]
