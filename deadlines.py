# deadlines.py
# صفحة /deadlines: المواعيد الرسمية للانتقال إلى التشفير ما بعد الكمومي، مع مصدر لكل سطر.
# قاعدة: لا نكتب تاريخاً بلا مصدر رسمي، ولا نبالغ (لا يوجد اليوم قانون يُلزم موقعاً خاصاً بـ PQ TLS).
UPDATED = "2026-11-04"

# (التاريخ، المفتاح، الرابط) — النص لكل لغة في TEXT[lang]["items"][key]
TIMELINE = [
    ("2022-09", "cnsa2", "https://media.defense.gov/2022/Sep/07/2003071836/-1/-1/0/CSI_CNSA_2.0_FAQ_.PDF"),
    ("2024-08", "fips", "https://csrc.nist.gov/pubs/fips/203/final"),
    ("2024-11", "chrome", "https://security.googleblog.com/2024/09/a-new-path-for-kyber-on-web.html"),
    ("2024-11", "nistir", "https://csrc.nist.gov/pubs/ir/8547/ipd"),
    ("2025-03", "ncsc", "https://www.ncsc.gov.uk/guidance/pqc-migration-timelines"),
    ("2025-04", "openssl", "https://github.com/openssl/openssl/releases/tag/openssl-3.5.0"),
    ("2025-06", "eu", "https://digital-strategy.ec.europa.eu/en/library/coordinated-implementation-roadmap-transition-post-quantum-cryptography"),
]

# المعالم القادمة (السنة، المفتاح)
MILESTONES = [("2026", "m2026"), ("2028", "m2028"), ("2030", "m2030"), ("2031", "m2031"), ("2033", "m2033"), ("2035", "m2035")]

TEXT = {
    "en": {
        "title": "Post-quantum deadlines: NIST, CNSA 2.0, EU and UK",
        "description": "Official dates for moving to post-quantum cryptography (NIST FIPS 203, NIST IR 8547, NSA CNSA 2.0, the EU roadmap, UK NCSC) and what they mean for a website's TLS today.",
        "lead": "Governments have set dates for retiring RSA and elliptic-curve cryptography. Here is every official date that matters for a website, with its source, and what to do about it now.",
        "short_title": "In short",
        "short": [
            "No law today forces a private website to use post-quantum TLS.",
            "Every major government roadmap ends in 2035: by then quantum-vulnerable key exchange and signatures are meant to be gone.",
            "The EU and the UK expect high-priority systems to be migrated around 2030–2031.",
            "Key exchange is the part you can fix today (a configuration change); certificates come later, when browsers accept ML-DSA.",
        ],
        "timeline_title": "What has already happened",
        "items": {
            "cnsa2": "NSA publishes CNSA 2.0 for US national security systems: web browsers, servers and cloud services should support and prefer the new algorithms by 2025 and use them exclusively by 2033. CNSA 2.0 requires ML-KEM-1024; the hybrid X25519MLKEM768 that browsers use is a step in that direction, not CNSA 2.0 compliance.",
            "fips": "NIST publishes the first post-quantum standards: FIPS 203 (ML-KEM, key exchange), FIPS 204 (ML-DSA, signatures) and FIPS 205 (SLH-DSA, signatures).",
            "chrome": "Chrome 131 switches its default post-quantum key exchange to the standardised X25519MLKEM768; Firefox and Edge follow. From now on, any server that supports it is protected for most visitors automatically.",
            "nistir": "NIST draft IR 8547 proposes deprecating quantum-vulnerable algorithms (RSA, ECDH, ECDSA) at the 112-bit level after 2030 and disallowing them entirely after 2035.",
            "ncsc": "The UK NCSC sets three milestones: discovery and a migration plan by 2028, high-priority migrations by 2031, migration complete by 2035.",
            "openssl": "OpenSSL 3.5 (long-term support) ships ML-KEM and offers X25519MLKEM768 by default, so nginx, Apache and HAProxy can enable it with a library upgrade.",
            "eu": "The EU Coordinated Implementation Roadmap: every member state starts its transition by the end of 2026, high-risk use cases are migrated by the end of 2030, and as many systems as feasible by 2035.",
        },
        "upcoming_title": "What is coming",
        "milestones": {
            "m2026": "EU member states should have started their post-quantum transition and inventories.",
            "m2028": "UK: discovery and migration plan complete (NCSC).",
            "m2030": "EU: high-risk use cases migrated. NIST draft: 112-bit RSA/ECC deprecated.",
            "m2031": "UK: high-priority migrations complete (NCSC).",
            "m2033": "US national security systems: browsers, servers and cloud services use CNSA 2.0 algorithms exclusively.",
            "m2035": "NIST draft: quantum-vulnerable algorithms disallowed. UK and EU: migration complete.",
        },
        "means_title": "What this means for your website",
        "means": [
            ("Key exchange: act now.", "Traffic recorded today can be decrypted once a large quantum computer exists (harvest now, decrypt later). Enabling X25519MLKEM768 is a configuration change on a current TLS library, and browsers already use it."),
            ("Certificates: wait.", "Browsers do not accept ML-DSA certificates yet, so every site still uses RSA or ECDSA certificates. That is expected, not a misconfiguration."),
            ("Regulated sectors (EU NIS2, DORA):", "these laws do not name post-quantum cryptography, but they require appropriate, state-of-the-art security. Expect auditors to ask for a cryptographic inventory and a migration plan; the first line of that inventory is which of your hosts already negotiate post-quantum key exchange."),
        ],
        "cta_scan": "Check your site's key exchange now",
        "cta_monitor": "Track all your domains daily",
        "sources_note": "Status as of {date}. Dates come from the linked official documents; drafts can change, so check the source before relying on a date.",
        "source": "source",
    },
    "ar": {
        "title": "مواعيد الانتقال إلى التشفير ما بعد الكمومي: NIST وCNSA 2.0 والاتحاد الأوروبي وبريطانيا",
        "description": "المواعيد الرسمية للانتقال إلى التشفير المقاوم للحوسبة الكمومية (NIST FIPS 203 وNIST IR 8547 وCNSA 2.0 وخارطة الاتحاد الأوروبي وNCSC البريطاني) وما تعنيه لـ TLS في موقعك اليوم.",
        "lead": "حددت الحكومات مواعيد للتخلي عن RSA وتشفير المنحنيات الإهليلجية. هذه كل المواعيد الرسمية التي تهم موقعاً على الإنترنت، مع مصدر كل منها، وما يمكنك فعله الآن.",
        "short_title": "باختصار",
        "short": [
            "لا يوجد اليوم قانون يُلزم موقعاً خاصاً باستخدام TLS ما بعد الكمومي.",
            "كل خرائط الطريق الحكومية الكبرى تنتهي في 2035: بحلولها يُفترض أن يختفي تبادل المفاتيح والتواقيع المعرّضة للحوسبة الكمومية.",
            "يتوقع الاتحاد الأوروبي وبريطانيا نقل الأنظمة ذات الأولوية العالية بين 2030 و2031.",
            "تبادل المفاتيح هو ما يمكنك إصلاحه اليوم (تغيير في الإعدادات)؛ أما الشهادات فلاحقاً، حين تقبل المتصفحات ML-DSA.",
        ],
        "timeline_title": "ما حدث فعلاً",
        "items": {
            "cnsa2": "وكالة الأمن القومي الأمريكية تنشر CNSA 2.0 لأنظمة الأمن القومي: على المتصفحات والخوادم والخدمات السحابية دعم الخوارزميات الجديدة وتفضيلها بحلول 2025 واستخدامها حصراً بحلول 2033. يشترط CNSA 2.0 خوارزمية ML-KEM-1024؛ أما X25519MLKEM768 الهجين الذي تستخدمه المتصفحات فخطوة في الاتجاه نفسه، لا امتثال لـ CNSA 2.0.",
            "fips": "NIST ينشر أول معايير ما بعد الكم: FIPS 203 (ML-KEM لتبادل المفاتيح) وFIPS 204 (ML-DSA للتواقيع) وFIPS 205 (SLH-DSA للتواقيع).",
            "chrome": "كروم 131 يعتمد X25519MLKEM768 القياسي افتراضياً، ويتبعه فايرفوكس وإيدج. منذ ذلك الحين، أي خادم يدعمه يحمي أغلب زواره تلقائياً.",
            "nistir": "مسودة NIST IR 8547 تقترح إيقاف الخوارزميات المعرّضة للحوسبة الكمومية (RSA وECDH وECDSA) بمستوى 112 بت بعد 2030، ومنعها كلياً بعد 2035.",
            "ncsc": "المركز الوطني البريطاني للأمن السيبراني يحدد ثلاث مراحل: الحصر وخطة الانتقال بحلول 2028، والأنظمة ذات الأولوية بحلول 2031، واكتمال الانتقال بحلول 2035.",
            "openssl": "OpenSSL 3.5 (دعم طويل الأمد) يتضمن ML-KEM ويعرض X25519MLKEM768 افتراضياً، فيمكن تفعيله في nginx وApache وHAProxy بتحديث المكتبة.",
            "eu": "خارطة الطريق المنسقة للاتحاد الأوروبي: تبدأ كل دولة عضو انتقالها بنهاية 2026، وتُنقل الاستخدامات عالية الخطورة بنهاية 2030، وأكبر عدد ممكن من الأنظمة بحلول 2035.",
        },
        "upcoming_title": "ما هو قادم",
        "milestones": {
            "m2026": "الاتحاد الأوروبي: يُفترض أن تكون الدول الأعضاء قد بدأت الانتقال وحصر أنظمتها.",
            "m2028": "بريطانيا: اكتمال الحصر وخطة الانتقال (NCSC).",
            "m2030": "الاتحاد الأوروبي: نقل الاستخدامات عالية الخطورة. مسودة NIST: إيقاف RSA/ECC بمستوى 112 بت.",
            "m2031": "بريطانيا: اكتمال نقل الأنظمة ذات الأولوية (NCSC).",
            "m2033": "أنظمة الأمن القومي الأمريكية: المتصفحات والخوادم والسحابة تستخدم خوارزميات CNSA 2.0 حصراً.",
            "m2035": "مسودة NIST: منع الخوارزميات المعرّضة للحوسبة الكمومية. بريطانيا والاتحاد الأوروبي: اكتمال الانتقال.",
        },
        "means_title": "ماذا يعني هذا لموقعك؟",
        "means": [
            ("تبادل المفاتيح: الآن.", "حركة المرور المسجّلة اليوم يمكن فك تشفيرها حين يوجد حاسوب كمومي كبير («اجمع الآن، فُكّ لاحقاً»). تفعيل X25519MLKEM768 تغيير في إعدادات مكتبة TLS حديثة، والمتصفحات تستخدمه أصلاً."),
            ("الشهادات: انتظر.", "المتصفحات لا تقبل شهادات ML-DSA بعد، لذلك ما زالت كل المواقع تستخدم شهادات RSA أو ECDSA. هذا متوقع وليس خطأً في الإعداد."),
            ("القطاعات المنظَّمة (NIS2 وDORA في الاتحاد الأوروبي):", "هذه القوانين لا تذكر التشفير ما بعد الكمومي بالاسم، لكنها تشترط أماناً مناسباً ومواكباً لأحدث التقنيات. توقّع أن يطلب المدققون حصراً لأنظمة التشفير وخطة انتقال؛ وأول سطر في هذا الحصر: أيٌّ من خوادمك يتفق فعلاً على تبادل مفاتيح ما بعد كمومي."),
        ],
        "cta_scan": "افحص تبادل المفاتيح في موقعك الآن",
        "cta_monitor": "راقب كل نطاقاتك يومياً",
        "sources_note": "الوضع بتاريخ {date}. المواعيد مأخوذة من الوثائق الرسمية المرتبطة؛ المسودات قد تتغير، فراجع المصدر قبل الاعتماد على أي تاريخ.",
        "source": "المصدر",
    },
    "de": {
        "title": "Post-Quanten-Fristen: NIST, CNSA 2.0, EU und Großbritannien",
        "description": "Offizielle Termine für den Umstieg auf Post-Quanten-Kryptografie (NIST FIPS 203, NIST IR 8547, NSA CNSA 2.0, EU-Roadmap, UK NCSC) und was sie heute für das TLS Ihrer Website bedeuten.",
        "lead": "Regierungen haben Termine für das Ende von RSA und Elliptische-Kurven-Kryptografie festgelegt. Hier sind alle offiziellen Termine, die für eine Website zählen, mit Quelle, und was Sie jetzt tun können.",
        "short_title": "Kurz gesagt",
        "short": [
            "Kein Gesetz verpflichtet heute eine private Website zu Post-Quanten-TLS.",
            "Alle großen staatlichen Roadmaps enden 2035: Bis dahin sollen quantenanfälliger Schlüsselaustausch und Signaturen verschwunden sein.",
            "EU und Großbritannien erwarten die Migration wichtiger Systeme um 2030–2031.",
            "Den Schlüsselaustausch können Sie heute beheben (eine Konfigurationsänderung); Zertifikate folgen später, wenn Browser ML-DSA akzeptieren.",
        ],
        "timeline_title": "Was bereits geschehen ist",
        "items": {
            "cnsa2": "Die NSA veröffentlicht CNSA 2.0 für US-Systeme der nationalen Sicherheit: Browser, Server und Cloud-Dienste sollen die neuen Algorithmen bis 2025 unterstützen und bevorzugen und sie bis 2033 ausschließlich verwenden. CNSA 2.0 verlangt ML-KEM-1024; das hybride X25519MLKEM768 der Browser ist ein Schritt in diese Richtung, aber keine CNSA-2.0-Konformität.",
            "fips": "NIST veröffentlicht die ersten Post-Quanten-Standards: FIPS 203 (ML-KEM, Schlüsselaustausch), FIPS 204 (ML-DSA, Signaturen) und FIPS 205 (SLH-DSA, Signaturen).",
            "chrome": "Chrome 131 nutzt standardmäßig das standardisierte X25519MLKEM768; Firefox und Edge folgen. Seitdem schützt jeder Server, der es unterstützt, die meisten Besucher automatisch.",
            "nistir": "Der NIST-Entwurf IR 8547 schlägt vor, quantenanfällige Algorithmen (RSA, ECDH, ECDSA) mit 112 Bit Sicherheit nach 2030 abzukündigen und nach 2035 ganz zu verbieten.",
            "ncsc": "Das britische NCSC setzt drei Meilensteine: Bestandsaufnahme und Migrationsplan bis 2028, Migration wichtiger Systeme bis 2031, Abschluss bis 2035.",
            "openssl": "OpenSSL 3.5 (Langzeitsupport) enthält ML-KEM und bietet X25519MLKEM768 standardmäßig an; nginx, Apache und HAProxy können es per Bibliotheks-Update aktivieren.",
            "eu": "Die koordinierte EU-Roadmap: Jeder Mitgliedstaat beginnt bis Ende 2026, Hochrisiko-Anwendungen werden bis Ende 2030 migriert, so viele Systeme wie möglich bis 2035.",
        },
        "upcoming_title": "Was kommt",
        "milestones": {
            "m2026": "EU: Die Mitgliedstaaten sollen mit Umstieg und Bestandsaufnahme begonnen haben.",
            "m2028": "Großbritannien: Bestandsaufnahme und Migrationsplan abgeschlossen (NCSC).",
            "m2030": "EU: Hochrisiko-Anwendungen migriert. NIST-Entwurf: RSA/ECC mit 112 Bit abgekündigt.",
            "m2031": "Großbritannien: Migration wichtiger Systeme abgeschlossen (NCSC).",
            "m2033": "US-Systeme der nationalen Sicherheit: Browser, Server und Cloud nutzen ausschließlich CNSA-2.0-Algorithmen.",
            "m2035": "NIST-Entwurf: quantenanfällige Algorithmen verboten. Großbritannien und EU: Migration abgeschlossen.",
        },
        "means_title": "Was das für Ihre Website bedeutet",
        "means": [
            ("Schlüsselaustausch: jetzt handeln.", "Heute aufgezeichneter Datenverkehr kann entschlüsselt werden, sobald es einen großen Quantencomputer gibt (Harvest now, decrypt later). X25519MLKEM768 zu aktivieren ist eine Konfigurationsänderung mit einer aktuellen TLS-Bibliothek, und Browser nutzen es bereits."),
            ("Zertifikate: abwarten.", "Browser akzeptieren noch keine ML-DSA-Zertifikate, daher nutzen alle Websites weiterhin RSA- oder ECDSA-Zertifikate. Das ist erwartet und kein Konfigurationsfehler."),
            ("Regulierte Branchen (EU NIS2, DORA):", "Diese Gesetze nennen Post-Quanten-Kryptografie nicht ausdrücklich, verlangen aber angemessene Sicherheit nach dem Stand der Technik. Rechnen Sie damit, dass Prüfer ein Kryptografie-Inventar und einen Migrationsplan sehen wollen; die erste Zeile dieses Inventars: Welche Ihrer Hosts handeln bereits Post-Quanten-Schlüsselaustausch aus?"),
        ],
        "cta_scan": "Schlüsselaustausch Ihrer Website jetzt prüfen",
        "cta_monitor": "Alle Domains täglich überwachen",
        "sources_note": "Stand: {date}. Die Termine stammen aus den verlinkten offiziellen Dokumenten; Entwürfe können sich ändern, prüfen Sie die Quelle, bevor Sie sich auf ein Datum verlassen.",
        "source": "Quelle",
    },
}
