# i18n.py
# نصوص الموقع والتقرير بالعربية والإنجليزية.

TEXTS = {
    "ar": {
        "dir": "rtl",
        "brand": "الأثير الكمومي",
        "nav_scan": "الفحص",
        "nav_research": "الأبحاث",
        "nav_api": "API",
        "other_lang": "English",
        "hero_title": "هل موقعك جاهز لعصر الحواسيب الكمومية؟",
        "hero_sub": "فحص حقيقي لاتصال HTTPS: هل يتفق خادمك مع المتصفحات على المفاتيح عبر X25519MLKEM768 "
                    "(المعيار ML-KEM / FIPS 203) الذي تستخدمه Chrome وFirefox اليوم؟ وما حال شهادتك أمام خوارزمية Shor؟",
        "domain_label": "اسم النطاق",
        "scan_button": "افحص مجاناً",
        "scanning": "جارٍ الفحص… قد يستغرق حتى 20 ثانية",
        "checks_title": "ماذا نفحص",
        "checks": [
            "إصدار TLS وهل يدعم الخادم TLS 1.3",
            "تبادل المفاتيح: هجين مقاوم للكم أم تقليدي معرّض لهجوم «احفظ الآن، فُكّ لاحقاً»",
            "توافق الخادم مع رسائل ClientHello الكبيرة التي ترسلها المتصفحات الحديثة",
            "خوارزمية الشهادة وطول المفتاح وصلاحيتها وتاريخ انتهائها",
        ],
        "how_title": "كيف يعمل الفحص",
        "how_body": "نجري اتصالين عاديين بالمنفذ 443 كما يفعل أي متصفح، ونقرأ ما يختاره الخادم ثم نغلق الاتصال. "
                    "لا نرسل بيانات ولا نجرّب أي ثغرة. نفحص فقط النطاقات العامة على الإنترنت.",
        "pricing_title": "الأسعار",
        "free_title": "الملخص المجاني",
        "free_items": ["الدرجة (A / B / C / F)", "حالة تبادل المفاتيح المقاوم للكم", "إصدار TLS وخوارزمية الشهادة"],
        "paid_title": "التقرير الكامل",
        "paid_items": [
            "كل النتائج مع شرح كل خطر وأولويته",
            "خطوات الإصلاح لـ nginx وApache وCaddy وCloudflare",
            "تفاصيل الشهادة والمصافحة",
            "السياق الزمني: معايير NIST وتقديرات كسر RSA المنشورة",
            "نسخة من التقرير مرمّزة في DNA رقمي مع تصحيح أخطاء Reed-Solomon",
        ],
        "privacy": "نحفظ اسم النطاق ونتيجة الفحص فقط. لا نحفظ عنوان IP الخاص بك، بل بصمة مشفّرة منه للحد من الاستخدام المفرط.",
        "result_title": "نتيجة الفحص",
        "grade": "الدرجة",
        "scanned_at": "وقت الفحص",
        "summary_title": "الملخص",
        "tls_version": "إصدار TLS",
        "key_exchange": "تبادل المفاتيح",
        "pq_yes": "هجين مقاوم للكم",
        "pq_no": "تقليدي",
        "certificate": "الشهادة",
        "findings_count": "عدد النتائج في التقرير الكامل",
        "buy_title": "التقرير الكامل",
        "buy_sub": "ادفع عبر PayPal أو بالبطاقة. يظهر رابط التقرير فور تأكيد الدفع من خادمنا مع PayPal.",
        "save_link": "احفظ رابط التقرير؛ هو مفتاح الوصول إليه.",
        "payments_off": "الدفع غير متاح حالياً. الملخص المجاني أعلاه كامل وصحيح.",
        "already_paid": "تم شراء تقرير هذا الفحص. استخدم الرابط الذي ظهر بعد الدفع.",
        "pay_error": "تعذّر إتمام الدفع. لم يُخصم أي مبلغ إن لم تصلك رسالة تأكيد من PayPal. حاول مجدداً.",
        "pay_pending": "الدفع قيد المراجعة لدى PayPal. سيعمل رابط التقرير بعد اكتماله.",
        "scan_again": "فحص نطاق آخر",
        "report_title": "تقرير الجاهزية لما بعد الكم",
        "findings_title": "النتائج",
        "remediation_title": "خطوات الإصلاح",
        "remediation_intro": "التفعيل يحتاج مكتبة TLS تدعم ML-KEM. أسرع طريق: ترقية OpenSSL إلى 3.5 أو أحدث، "
                             "أو خادم مبني بـ Go 1.24+، أو تفعيل وكيل مثل Cloudflare أمام موقعك.",
        "verify_after": "بعد التعديل أعد الفحص هنا للتأكد من أن الدرجة صارت A.",
        "details_title": "تفاصيل تقنية",
        "context_title": "السياق الزمني",
        "context_items": [
            "اعتمد NIST في أغسطس 2024 المعايير ML-KEM (FIPS 203) وML-DSA (FIPS 204) وSLH-DSA (FIPS 205).",
            "مسودة NIST IR 8547 (2024): إيقاف RSA وECC بمستوى أمان 112 بت بعد 2030 ومنعها بعد 2035.",
            "أحدث تقدير منشور لكسر RSA-2048: أقل من مليون كيوبت فيزيائي مشوّش وأقل من أسبوع (Gidney، 2025). "
            "الحواسيب الكمومية الحالية بعيدة عن ذلك، لكن البيانات المسجلة اليوم قد تبقى حساسة لسنوات.",
            "التشفير المتماثل (AES-128/256 وChaCha20) لا يتأثر عملياً: تسريع Grover لا يشكل تهديداً عملياً حسب NIST.",
        ],
        "dna_title": "الأرشيف الحيوي الرقمي",
        "dna_body": "نسخة JSON من هذا التقرير مرمّزة كسلسلة DNA رقمية (قاعدة واحدة لكل بتّين، بصيغة FASTA) "
                    "ومحمية بـ Reed-Solomon RS(255,223). هي ملف نصي ولم تُصنَّع جزيئياً.",
        "dna_download": "تنزيل سلسلة DNA",
        "print": "طباعة / حفظ PDF",
        "research_title": "الأبحاث: تجارب كمومية حقيقية",
        "research_intro": "دائرة GHZ بثلاثة كيوبتات نُفّذت على معالج IBM Quantum الحقيقي ibm_marrakesh. "
                          "أسماء الكيوبتات (السطح، محطة الترحيل، الباطن) تسمية رمزية من إطار المشروع؛ "
                          "القياسات نفسها تخص شريحة الحوسبة الكمومية وحدها.",
        "population_label": "نسبة الإشغال P(000)+P(111)",
        "population_note": "هذه النسبة حد أعلى لدقة حالة GHZ (fidelity) وليست الدقة نفسها؛ قياس الدقة يحتاج "
                           "قياسات في الأساسين X وY (السكربت ghz_fidelity.py).",
        "fidelity_label": "دقة حالة GHZ (fidelity)",
        "job_label": "معرّف المهمة",
        "backend_label": "المعالج",
        "shots_label": "عدد اللقطات",
        "source_label": "مصدر البيانات",
        "counts_title": "توزيع القياسات",
        "state": "الحالة",
        "count": "العدد",
        "dna_research_title": "أرشفة تقرير البحث في DNA رقمي",
        "dna_research_body": "تقرير البحث مرمّز في سلسلة DNA رقمية مع تصحيح أخطاء Reed-Solomon، "
                             "ويُسترجع حرفاً بحرف بالأمر: python bio_archive_report.py verify",
        "bases": "عدد القواعد",
        "gc": "نسبة GC",
        "homopolymer": "أطول تكرار متتالٍ لقاعدة واحدة",
        "admin_title": "لوحة الإدارة",
        "total_scans": "إجمالي الفحوصات",
        "paid_orders": "الطلبات المدفوعة (مؤكدة من PayPal)",
        "revenue": "الإيرادات المؤكدة",
        "orders_title": "آخر الطلبات",
        "scans_title": "آخر الفحوصات",
        "status": "الحالة",
        "domain": "النطاق",
        "date": "التاريخ",
        "amount": "المبلغ",
        "not_found": "الصفحة غير موجودة.",
        "rate_limited": "تجاوزت عدد الفحوصات المسموح في الساعة. حاول لاحقاً.",
        "server_error": "حدث خطأ غير متوقع.",
        "back_home": "العودة للرئيسية",
        "errors": {
            "invalid_domain": "اسم النطاق غير صالح. أدخل نطاقاً مثل example.com.",
            "private_address": "هذا النطاق يشير إلى عنوان داخلي أو محجوز. نفحص النطاقات العامة فقط.",
            "dns_failure": "تعذّر العثور على هذا النطاق في DNS.",
            "connect_failure": "تعذّر الاتصال بالمنفذ 443 لهذا النطاق.",
            "tls_failure": "الخادم لا يقبل اتصال HTTPS حديثاً (TLS 1.2 أو أحدث).",
        },
        "grades": {
            "A": "جاهز: تبادل مفاتيح مقاوم للكم",
            "B": "آمن اليوم، لكنه معرّض لهجوم «احفظ الآن، فُكّ لاحقاً»",
            "C": "يحتاج ترقية: لا يدعم TLS 1.3",
            "F": "مشكلة حرجة يجب إصلاحها أولاً",
        },
        "status_names": {"ok": "سليم", "info": "معلومة", "warning": "تحذير", "critical": "حرج"},
    },
    "en": {
        "dir": "ltr",
        "brand": "Quantum Aether",
        "nav_scan": "Scan",
        "nav_research": "Research",
        "nav_api": "API",
        "other_lang": "العربية",
        "hero_title": "Is your website ready for quantum computers?",
        "hero_sub": "A real HTTPS check: does your server agree keys with browsers using X25519MLKEM768 "
                    "(ML-KEM / FIPS 203), as Chrome and Firefox do today? And how does your certificate fare against Shor's algorithm?",
        "domain_label": "Domain name",
        "scan_button": "Scan for free",
        "scanning": "Scanning… this can take up to 20 seconds",
        "checks_title": "What we check",
        "checks": [
            "TLS version and TLS 1.3 support",
            "Key exchange: quantum-resistant hybrid, or classical and exposed to harvest-now-decrypt-later",
            "Whether the server copes with the large ClientHello modern browsers send",
            "Certificate algorithm, key size, validity and expiry",
        ],
        "how_title": "How the scan works",
        "how_body": "We make two ordinary connections to port 443, as any browser would, read what the server chooses and close. "
                    "No data is sent and no exploit is attempted. Only public internet domains are scanned.",
        "pricing_title": "Pricing",
        "free_title": "Free summary",
        "free_items": ["Grade (A / B / C / F)", "Quantum-resistant key exchange status", "TLS version and certificate algorithm"],
        "paid_title": "Full report",
        "paid_items": [
            "Every finding, with what it means and its priority",
            "Fix steps for nginx, Apache, Caddy and Cloudflare",
            "Certificate and handshake details",
            "Timeline context: NIST standards and published RSA-breaking estimates",
            "A copy of the report encoded as digital DNA with Reed-Solomon error correction",
        ],
        "privacy": "We store the domain and the scan result only. Your IP address is not stored, just a salted hash used for rate limiting.",
        "result_title": "Scan result",
        "grade": "Grade",
        "scanned_at": "Scanned at",
        "summary_title": "Summary",
        "tls_version": "TLS version",
        "key_exchange": "Key exchange",
        "pq_yes": "quantum-resistant hybrid",
        "pq_no": "classical",
        "certificate": "Certificate",
        "findings_count": "Findings in the full report",
        "buy_title": "Full report",
        "buy_sub": "Pay with PayPal or a card. The report link appears as soon as our server confirms the payment with PayPal.",
        "save_link": "Keep the report link: it is your key to the report.",
        "payments_off": "Payments are currently unavailable. The free summary above is complete and accurate.",
        "already_paid": "The report for this scan has been purchased. Use the link shown after payment.",
        "pay_error": "The payment could not be completed. Nothing was charged unless PayPal sent you a confirmation. Please try again.",
        "pay_pending": "PayPal is reviewing the payment. The report link will work once it completes.",
        "scan_again": "Scan another domain",
        "report_title": "Post-quantum readiness report",
        "findings_title": "Findings",
        "remediation_title": "How to fix",
        "remediation_intro": "You need a TLS library with ML-KEM. Quickest routes: upgrade to OpenSSL 3.5 or newer, "
                             "use a server built with Go 1.24+, or put a proxy such as Cloudflare in front of your site.",
        "verify_after": "After changing the configuration, scan again here to confirm the grade is A.",
        "details_title": "Technical details",
        "context_title": "Timeline context",
        "context_items": [
            "In August 2024 NIST published ML-KEM (FIPS 203), ML-DSA (FIPS 204) and SLH-DSA (FIPS 205).",
            "Draft NIST IR 8547 (2024): RSA and ECC at 112-bit security deprecated after 2030 and disallowed after 2035.",
            "Latest published estimate for breaking RSA-2048: under one million noisy physical qubits in under a week (Gidney, 2025). "
            "Today's quantum computers are far from that, but data recorded today may stay sensitive for years.",
            "Symmetric encryption (AES-128/256, ChaCha20) is not practically affected: per NIST, Grover's speed-up is not a practical threat.",
        ],
        "dna_title": "Digital bio-archive",
        "dna_body": "A JSON copy of this report encoded as a digital DNA sequence (2 bits per base, FASTA format) and protected "
                    "with Reed-Solomon RS(255,223). It is a text file; no molecule was synthesized.",
        "dna_download": "Download DNA sequence",
        "print": "Print / save as PDF",
        "research_title": "Research: real quantum experiments",
        "research_intro": "A 3-qubit GHZ circuit executed on IBM Quantum's ibm_marrakesh processor. The qubit names "
                          "(surface, relay station, deep layer) are the project's symbolic framing; the measurements concern the quantum chip only.",
        "population_label": "Population P(000)+P(111)",
        "population_note": "This is an upper bound on the GHZ state fidelity, not the fidelity itself; measuring fidelity needs "
                           "X- and Y-basis measurements (script ghz_fidelity.py).",
        "fidelity_label": "GHZ state fidelity",
        "job_label": "Job ID",
        "backend_label": "Backend",
        "shots_label": "Shots",
        "source_label": "Data source",
        "counts_title": "Measurement counts",
        "state": "State",
        "count": "Count",
        "dna_research_title": "Research report archived as digital DNA",
        "dna_research_body": "The research report is encoded as a digital DNA sequence with Reed-Solomon error correction and "
                             "restores byte for byte with: python bio_archive_report.py verify",
        "bases": "Bases",
        "gc": "GC content",
        "homopolymer": "Longest single-base run",
        "admin_title": "Admin",
        "total_scans": "Total scans",
        "paid_orders": "Paid orders (confirmed with PayPal)",
        "revenue": "Confirmed revenue",
        "orders_title": "Recent orders",
        "scans_title": "Recent scans",
        "status": "Status",
        "domain": "Domain",
        "date": "Date",
        "amount": "Amount",
        "not_found": "Page not found.",
        "rate_limited": "Too many scans this hour. Please try again later.",
        "server_error": "Something went wrong.",
        "back_home": "Back to home",
        "errors": {
            "invalid_domain": "That is not a valid domain name. Enter something like example.com.",
            "private_address": "That domain points to an internal or reserved address. Only public domains can be scanned.",
            "dns_failure": "That domain could not be found in DNS.",
            "connect_failure": "Could not connect to port 443 on that domain.",
            "tls_failure": "The server does not accept a modern HTTPS connection (TLS 1.2 or newer).",
        },
        "grades": {
            "A": "Ready: quantum-resistant key exchange",
            "B": "Secure today, exposed to harvest-now-decrypt-later",
            "C": "Needs an upgrade: no TLS 1.3",
            "F": "Critical issue to fix first",
        },
        "status_names": {"ok": "OK", "info": "Info", "warning": "Warning", "critical": "Critical"},
    },
}

FINDINGS = {
    "KX_PQ_HYBRID": {
        "ar": ("تبادل مفاتيح هجين مقاوم للكم ({group})",
               "يتفق خادمك مع المتصفحات الحديثة على مفتاح الجلسة عبر ML-KEM (FIPS 203) مدموجاً مع منحنى تقليدي. "
               "حتى لو سُجّلت حركة المرور اليوم، لن يستطيع حاسوب كمّي مستقبلي فك تشفيرها."),
        "en": ("Hybrid post-quantum key exchange ({group})",
               "Your server agrees session keys with modern browsers using ML-KEM (FIPS 203) combined with a classical curve. "
               "Traffic recorded today stays protected against a future quantum computer."),
    },
    "KX_CLASSICAL": {
        "ar": ("تبادل مفاتيح تقليدي فقط ({group})",
               "عرضنا على الخادم X25519MLKEM768 كما يفعل Chrome وFirefox، فاختار {group}. هذا آمن اليوم، لكن من يسجّل "
               "حركة المرور الآن يستطيع فك تشفيرها لاحقاً عندما يتوفر حاسوب كمّي قادر على تشغيل خوارزمية Shor "
               "(هجوم «احفظ الآن، فُكّ لاحقاً»). هذه أهم نقطة يجب إصلاحها للجاهزية الكمومية."),
        "en": ("Classical key exchange only ({group})",
               "We offered X25519MLKEM768, as Chrome and Firefox do, and the server chose {group}. That is secure today, but "
               "traffic recorded now could be decrypted once a quantum computer can run Shor's algorithm "
               "(\"harvest now, decrypt later\"). This is the most important item to fix for quantum readiness."),
    },
    "TLS12_ONLY": {
        "ar": ("الخادم لا يدعم TLS 1.3",
               "تبادل المفاتيح المقاوم للكم متاح فقط في TLS 1.3، لذا يجب تفعيل TLS 1.3 أولاً."),
        "en": ("Server does not support TLS 1.3",
               "Post-quantum key exchange only exists in TLS 1.3, so TLS 1.3 has to be enabled first."),
    },
    "KX_RSA_STATIC": {
        "ar": ("تبادل مفاتيح RSA ثابت (بلا سرية أمامية)",
               "يُشفَّر مفتاح الجلسة بمفتاح الشهادة مباشرة: من يحصل على مفتاح الشهادة الخاص، اليوم أو بحاسوب كمّي غداً، "
               "يفك كل الجلسات المسجلة. فعّل ECDHE وTLS 1.3."),
        "en": ("Static RSA key exchange (no forward secrecy)",
               "Session keys are encrypted directly to the certificate key: whoever obtains that private key, today or with a "
               "future quantum computer, can decrypt every recorded session. Enable ECDHE and TLS 1.3."),
    },
    "TLS_LEGACY": {
        "ar": ("إصدار TLS قديم ({version})",
               "الإصدارات الأقدم من TLS 1.2 فيها ضعف معروف وأوقفت المتصفحات دعمها."),
        "en": ("Legacy TLS version ({version})",
               "Versions older than TLS 1.2 have known weaknesses and browsers no longer support them."),
    },
    "KX_PQ_HELLO_REJECTED": {
        "ar": ("الخادم تعثّر مع ClientHello ما بعد الكمّي",
               "رسالة ClientHello التي تعرض ML-KEM أكبر (نحو 1.5 كيلوبايت). فشل خادمك أو جهاز وسيط أمامه في التعامل "
               "معها ونجح مع الرسالة التقليدية، وهذا قد يقطع الاتصال لمستخدمي المتصفحات الحديثة. التفاصيل: {error}"),
        "en": ("Server failed on a post-quantum ClientHello",
               "A ClientHello offering ML-KEM is larger (about 1.5 KB). Your server or a middlebox in front of it failed on it but "
               "accepted a classical one, which can break connections for users of current browsers. Details: {error}"),
    },
    "KX_PROBE_FAILED": {
        "ar": ("تعذّر تحديد مجموعة تبادل المفاتيح",
               "لم يكتمل مجسّ ClientHello: {error}. التقييم مبني على المصافحة القياسية فقط."),
        "en": ("Could not determine the key-exchange group",
               "The ClientHello probe did not complete: {error}. The grade is based on the standard handshake only."),
    },
    "CERT_INVALID": {
        "ar": ("الشهادة غير صالحة",
               "فشل التحقق من سلسلة الشهادة: {error}. سيرى الزوار تحذيراً أمنياً في المتصفح."),
        "en": ("Certificate is not valid",
               "Certificate chain verification failed: {error}. Visitors will see a browser security warning."),
    },
    "CERT_EXPIRING": {
        "ar": ("الشهادة تنتهي قريباً", "تبقى {days} يوماً على انتهاء الشهادة. فعّل التجديد التلقائي (ACME)."),
        "en": ("Certificate expires soon", "The certificate expires in {days} days. Enable automatic renewal (ACME)."),
    },
    "CERT_WEAK_RSA": {
        "ar": ("مفتاح RSA ضعيف ({bits} بت)", "مفاتيح RSA الأقل من 2048 بت ضعيفة حتى أمام الحواسيب التقليدية."),
        "en": ("Weak RSA key ({bits} bits)", "RSA keys below 2048 bits are weak even against classical computers."),
    },
    "CERT_SHOR_VULNERABLE": {
        "ar": ("توقيع الشهادة ({algorithm}) قابل للكسر بخوارزمية Shor",
               "كل خوارزميات الشهادات المستخدمة اليوم (RSA وECDSA وEdDSA) يكسرها حاسوب كمّي كبير بأي طول مفتاح؛ "
               "تكبير المفتاح إلى 4096 بت لا يحمي. الخطر أقل إلحاحاً من تبادل المفاتيح لأن انتحال الهوية يحتاج الحاسوب "
               "الكمّي لحظة الاتصال ولا يُطبَّق بأثر رجعي. الحل المستقبلي شهادات ML-DSA (FIPS 204) عندما تدعمها "
               "جهات الإصدار والمتصفحات؛ حتى ذلك الحين اجعل تجديد الشهادات آلياً لتسهيل الانتقال."),
        "en": ("Certificate signature ({algorithm}) is breakable by Shor's algorithm",
               "Every certificate algorithm in use today (RSA, ECDSA, EdDSA) falls to a large quantum computer at any key size; "
               "moving to RSA-4096 does not help. It is less urgent than key exchange because impersonation needs the quantum "
               "computer at connection time and cannot be done retroactively. The long-term fix is ML-DSA (FIPS 204) "
               "certificates once CAs and browsers support them; until then, automate certificate renewal to ease the switch."),
    },
    "CERT_UNKNOWN_ALGORITHM": {
        "ar": ("خوارزمية مفتاح لا تعرفها أداة الفحص", "قد تكون خوارزمية ما بعد كمّية أو خوارزمية غير شائعة."),
        "en": ("Key algorithm not recognized by the scanner", "It may be a post-quantum or an uncommon algorithm."),
    },
}

REMEDIATION = [
    ("nginx (OpenSSL 3.5+)",
     "# check first: nginx -V 2>&1 | grep -o 'OpenSSL [0-9.]*'   (needs 3.5 or newer)\n"
     "ssl_protocols TLSv1.2 TLSv1.3;\n"
     "ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;"),
    ("Apache httpd (OpenSSL 3.5+)",
     "SSLProtocol -all +TLSv1.2 +TLSv1.3\n"
     "SSLOpenSSLConfCmd Groups X25519MLKEM768:X25519:prime256v1"),
    ("Caddy / Go 1.24+",
     "# X25519MLKEM768 is enabled by default in Go 1.24+ crypto/tls.\n"
     "# Upgrade Caddy (or your Go server) to a build made with Go 1.24 or newer."),
    ("Cloudflare / CDN",
     "# Cloudflare negotiates X25519MLKEM768 with browsers by default.\n"
     "# Proxy the domain through it (orange cloud) and scan again."),
]


def finding_text(finding, lang):
    title, detail = FINDINGS[finding["code"]][lang]
    params = finding.get("params") or {}
    return title.format(**params), detail.format(**params)
