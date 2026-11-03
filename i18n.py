# i18n.py
# نصوص الموقع والتقرير بالعربية والإنجليزية.

TEXTS = {
    "ar": {
        "dir": "rtl",
        "brand": "الأثير الكمومي",
        "nav_scan": "الفحص",
        "nav_research": "الأبحاث",
        "nav_api": "API",
        "nav_guides": "الأدلة",
        "nav_study": "الدراسة",
        "guides_title": "أدلة TLS المقاوم للكم",
        "guides_intro": "خطوات عملية لتفعيل تبادل المفاتيح الهجين X25519MLKEM768 على خادمك، مع طريقة التحقق.",
        "updated_label": "آخر تحديث",
        "scan_cta": "افحص نطاقك مجاناً",
        "study_title": "كم من أكبر 1000 موقع في العالم جاهز لما بعد الكم؟",
        "study_lead": "فحصنا أكبر 1000 نطاق في قائمة Tranco يوم {date}. من {reachable} نطاقاً أجاب على HTTPS، {pq} ({pct}%) تتفق مع المتصفحات على تبادل المفاتيح الهجين X25519MLKEM768.",
        "study_reachable": "نطاقات أجابت",
        "study_pq": "تدعم ما بعد الكم",
        "study_top100": "من أول 100 نطاق",
        "study_grades": "توزيع الدرجات",
        "study_groups": "مجموعة تبادل المفاتيح المتفق عليها",
        "study_certs": "مفاتيح الشهادات",
        "study_notable": "مواقع كبيرة بلا تبادل مفاتيح مقاوم للكم",
        "study_notable_note": "هذه النطاقات تتفق مع المتصفحات على تبادل مفاتيح تقليدي فقط، فحركتها معرّضة لهجوم «احفظ الآن، فُكّ لاحقاً».",
        "study_method_title": "المنهجية",
        "study_method": "لكل نطاق (بلا www) أجرينا اتصالين بالمنفذ 443 من خادم واحد: الأول يعرض X25519MLKEM768 مع X25519 كما يفعل Chrome، والثاني اتصال TLS عادي لقراءة الشهادة. «لم يُجب» تعني أن النطاق ليس له عنوان عام أو لا يقدم HTTPS على اسمه المجرد، وأغلبها نطاقات بنية تحتية وCDN. نتائج نقطة رصد واحدة قد تختلف عن مناطق أخرى.",
        "study_full_table": "كل النتائج",
        "study_download": "تنزيل البيانات (JSON)",
        "rank": "الترتيب",
        "domain_col": "النطاق",
        "grade_col": "الدرجة",
        "group_col": "المجموعة",
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
            "نسخة قابلة للطباعة أو الحفظ PDF",
        ],
        "sample_link": "شاهد نموذج تقرير كامل حقيقي",
        "sample_title": "نموذج تقرير كامل",
        "sample_banner": "هذا تقرير حقيقي كامل لموقع github.com كما يصل للمشتري بعد الدفع، من فحص أُجري في {date}. "
                         "النتيجة تتغير إن غيّر الموقع إعداداته.",
        "sample_buy": "افحص موقعك واحصل على تقريرك",
        "limits_title": "ما الذي لا يغطيه الفحص",
        "limits_items": [
            "الدرجة A لا تعني أن موقعك «آمن كمومياً» بالكامل أو خالٍ من الثغرات. الفحص يقيس اتصال TLS العام على المنفذ 443 فقط.",
            "إن كان موقعك خلف CDN أو وكيل (مثل Cloudflare) فنحن نفحص الاتصال بين الزائر والـ CDN، لا الاتصال بين الـ CDN وخادمك الأصلي.",
            "لا نفحص تطبيق الويب نفسه، ولا البريد، ولا VPN، ولا الأنظمة الداخلية، ولا كيفية تخزين بياناتك.",
            "الشهادات الرقمية ما زالت تقليدية (RSA/ECDSA) في كل المواقع حالياً، لأن المتصفحات لا تدعم شهادات ML-DSA بعد. هذا ليس خطأ في إعدادك.",
            "النتيجة صورة لحظة الفحص؛ أي تغيير في الخادم أو الـ CDN قد يغيّرها.",
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
        "nav_guides": "Guides",
        "nav_study": "Study",
        "guides_title": "Post-quantum TLS guides",
        "guides_intro": "Practical steps to enable the hybrid X25519MLKEM768 key exchange on your server, and how to verify it.",
        "updated_label": "Updated",
        "scan_cta": "Scan your domain for free",
        "study_title": "How many of the top 1,000 websites are ready for post-quantum TLS?",
        "study_lead": "We scanned the Tranco top 1,000 domains on {date}. Of the {reachable} that answered on HTTPS, {pq} ({pct}%) negotiate the hybrid X25519MLKEM768 key exchange with browsers.",
        "study_reachable": "domains answered",
        "study_pq": "post-quantum ready",
        "study_top100": "of the top 100",
        "study_grades": "Grade distribution",
        "study_groups": "Negotiated key-exchange group",
        "study_certs": "Certificate keys",
        "study_notable": "Large sites without post-quantum key exchange",
        "study_notable_note": "These domains negotiate classical key exchange only, so their traffic is exposed to harvest-now-decrypt-later.",
        "study_method_title": "Methodology",
        "study_method": "For each bare domain (no www) we made two connections to port 443 from a single server: one offering X25519MLKEM768 plus X25519 as Chrome does, and one ordinary TLS connection to read the certificate. \"Did not answer\" means the name has no public address or serves no HTTPS on the bare domain; most are infrastructure and CDN names. Results are from one vantage point and may differ elsewhere.",
        "study_full_table": "All results",
        "study_download": "Download the data (JSON)",
        "rank": "Rank",
        "domain_col": "Domain",
        "grade_col": "Grade",
        "group_col": "Group",
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
            "A printable copy you can save as PDF",
        ],
        "sample_link": "See a real full sample report",
        "sample_title": "Sample full report",
        "sample_banner": "This is a real, complete report for github.com, exactly as a buyer receives it after payment, from a scan run on {date}. "
                         "The result changes if the site changes its configuration.",
        "sample_buy": "Scan your site and get your report",
        "limits_title": "What this scan does not cover",
        "limits_items": [
            "Grade A does not mean your site is fully \"quantum-safe\" or free of vulnerabilities. We measure the public TLS connection on port 443 only.",
            "If your site is behind a CDN or proxy (such as Cloudflare), we test the visitor-to-CDN connection, not the CDN-to-origin connection.",
            "We do not test the web application itself, email, VPNs, internal systems or how your data is stored.",
            "Certificates are still classical (RSA/ECDSA) on every site today, because browsers do not accept ML-DSA certificates yet. That is not a mistake in your setup.",
            "The result is a snapshot at scan time; any change to the server or CDN can change it.",
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


TEXTS["ar"].update({
    "crypto_title": "أو ادفع بـ USDT / USDC",
    "crypto_sub": "تحويل مباشر من محفظتك أو من منصة تداول. يتحقق خادمنا من المعاملة على الشبكة نفسها ثم يفتح التقرير.",
    "crypto_send": "أرسل بالضبط",
    "crypto_on": "على شبكة",
    "crypto_to": "إلى العنوان:",
    "crypto_copy": "نسخ",
    "crypto_warning": "أرسل على هذه الشبكة فقط وبهذا المبلغ بالضبط (الكسر العشري يعرّف دفعتك). "
                      "الإرسال على شبكة أخرى أو بعملة أخرى قد يضيع المبلغ. رسوم الشبكة على المرسل.",
    "crypto_tx_label": "بعد الإرسال، الصق رقم المعاملة (Transaction hash / TxID):",
    "crypto_verify": "تحقق وافتح التقرير",
    "crypto_msgs": {
        "choose_failed": "تعذّر إنشاء طلب الدفع. حاول مجدداً.",
        "invalid_tx_hash": "رقم المعاملة غير صحيح: يبدأ بـ 0x ويليه 64 حرفاً.",
        "pending": "لم تظهر المعاملة على الشبكة بعد. انتظر قليلاً ثم اضغط مجدداً.",
        "confirming": "وصلت الدفعة وتنتظر التأكيدات ({c} من {n}). اضغط مجدداً بعد دقيقة.",
        "no_transfer": "هذه المعاملة لا تحوي تحويل {token} إلى عنواننا على هذه الشبكة.",
        "wrong_amount": "المبلغ المستلم ({received}) أقل من المطلوب ({expected}). راسلنا عبر البريد في صفحة Impressum.",
        "too_old": "هذه المعاملة أقدم من الطلب، فهي ليست دفعته.",
        "failed": "المعاملة فشلت على الشبكة.",
        "tx_already_used": "هذه المعاملة استُخدمت لطلب آخر.",
        "chain_unavailable": "تعذّر الاتصال بالشبكة الآن. حاول بعد دقيقة؛ دفعتك محفوظة على الشبكة.",
        "copied": "تم النسخ",
    },
})
TEXTS["en"].update({
    "crypto_title": "Or pay with USDT / USDC",
    "crypto_sub": "Direct transfer from your wallet or an exchange. Our server checks the transaction on the blockchain itself, then unlocks the report.",
    "crypto_send": "Send exactly",
    "crypto_on": "on",
    "crypto_to": "to this address:",
    "crypto_copy": "Copy",
    "crypto_warning": "Use this network only and this exact amount (the decimals identify your payment). "
                      "Sending on another network or another token may lose the funds. Network fees are paid by the sender.",
    "crypto_tx_label": "After sending, paste the transaction hash (TxID):",
    "crypto_verify": "Verify and open the report",
    "crypto_msgs": {
        "choose_failed": "Could not create the payment request. Please try again.",
        "invalid_tx_hash": "That is not a transaction hash: it starts with 0x followed by 64 characters.",
        "pending": "The transaction is not on the blockchain yet. Wait a moment and try again.",
        "confirming": "Payment received, waiting for confirmations ({c} of {n}). Try again in a minute.",
        "no_transfer": "This transaction does not transfer {token} to our address on this network.",
        "wrong_amount": "The amount received ({received}) is less than required ({expected}). Contact us via the email in the Impressum.",
        "too_old": "This transaction is older than the order, so it is not its payment.",
        "failed": "The transaction failed on the blockchain.",
        "tx_already_used": "This transaction was already used for another order.",
        "chain_unavailable": "The blockchain cannot be reached right now. Try again in a minute; your payment is safe on-chain.",
        "copied": "Copied",
    },
})

# ---------------------------------------------------------------- نصوص اشتراك المراقبة الشهري
TEXTS["ar"].update({
    "nav_monitoring": "للشركات",
    "mon_title": "مراقبة يومية لجاهزية نطاقاتك لما بعد الكم",
    "mon_sub": "نفحص كل نطاقاتك يومياً ونراسلك فور أي تراجع: فقدان التبادل المقاوم للكم، أو انخفاض الدرجة، أو شهادة توشك على الانتهاء.",
    "mon_features": [
        "فحص يومي تلقائي لكل النطاقات",
        "تنبيه بالبريد عند تغيّر الدرجة أو فقدان X25519MLKEM768",
        "تنبيه قبل انتهاء الشهادة بـ 14 يوماً ثم 3 أيام",
        "لوحة تحكم بحالة كل النطاقات وسجل التنبيهات، قابلة للطباعة كتقرير",
        "إلغاء في أي وقت من اللوحة",
    ],
    "mon_per_month": "شهرياً",
    "mon_domains": "حتى {n} نطاقاً",
    "mon_email_label": "بريدك (يصل إليه رابط لوحة التحكم والتنبيهات)",
    "mon_choose": "اختر الخطة وادفع عبر PayPal أو البطاقة:",
    "mon_disabled": "الاشتراكات غير مفعّلة بعد. راسلنا إن أردت الاشتراك.",
    "mon_email_first": "اكتب بريداً صحيحاً أولاً.",
    "mon_error": "تعذّر إتمام الاشتراك. لم يُخصم شيء إن لم تكمل الموافقة في PayPal. حاول مجدداً.",
    "mon_login_title": "مشترك بالفعل؟",
    "mon_login_sub": "اكتب بريدك ونرسل لك رابط لوحة التحكم.",
    "mon_login_button": "أرسل الرابط",
    "mon_login_sent": "إن كان لهذا البريد اشتراك فعّال فسيصله الرابط خلال دقائق.",
    "dash_title": "لوحة المراقبة",
    "dash_plan": "الخطة",
    "dash_status": "الحالة",
    "dash_used": "النطاقات المستخدمة",
    "dash_keep_private": "هذا الرابط مفتاح حسابك: احفظه ولا تشاركه.",
    "dash_add_title": "إضافة نطاقات",
    "dash_add_hint": "نطاق في كل سطر، أو افصل بينها بفواصل.",
    "dash_add_button": "أضف",
    "dash_domains_title": "النطاقات",
    "dash_none": "لا توجد نطاقات بعد.",
    "dash_pending": "في انتظار أول فحص",
    "dash_checked": "آخر فحص",
    "dash_days_left": "أيام الشهادة",
    "dash_remove": "حذف",
    "dash_scan_now": "افحص الكل الآن",
    "dash_alerts_title": "سجل التنبيهات",
    "dash_no_alerts": "لا تنبيهات حتى الآن.",
    "dash_print": "اطبع التقرير",
    "dash_cancel": "إلغاء الاشتراك",
    "dash_cancel_confirm": "إلغاء الاشتراك يوقف الدفع الشهري والمراقبة فوراً. متأكد؟",
    "dash_status_names": {"ACTIVE": "فعّال", "CANCELLED": "ملغى", "SUSPENDED": "موقوف", "EXPIRED": "منتهٍ"},
    "dash_notices": {
        "added": "تمت الإضافة. ستظهر النتائج بعد الفحص التالي أو اضغط «افحص الكل الآن».",
        "limit": "وصلت إلى حد خطتك من النطاقات.",
        "invalid": "بعض النطاقات غير صالحة ولم تُضف.",
        "removed": "تم الحذف.",
        "scanned": "تم الفحص.",
        "wait": "يمكن الفحص اليدوي مرة كل ساعة.",
        "inactive": "الاشتراك غير فعّال.",
        "cancelled": "تم إلغاء الاشتراك.",
        "cancel_failed": "تعذّر الإلغاء الآن عبر PayPal. حاول لاحقاً أو ألغه من حسابك في PayPal.",
    },
    "mon_cta_home": "للشركات: مراقبة يومية لعدة نطاقات مع تنبيهات بالبريد، من 29$ شهرياً",
    "badge_title": "اعرض جاهزيتك على موقعك",
    "badge_sub": "انسخ هذا الكود في موقعك لعرض الشارة. تتحدث تلقائياً حسب آخر فحص خلال 30 يوماً.",
    "admin_subs_active": "اشتراكات فعّالة",
    "admin_mrr": "الدخل الشهري المتكرر",
    "admin_churned": "ملغاة أو موقوفة",
    "admin_subs_title": "المشتركون",
    "adm_visitors": "زوار",
    "adm_views": "مشاهدات",
    "adm_scanners": "زوار شاهدوا نتيجة فحص",
    "adm_pricing_views": "زوار صفحة الاشتراك",
    "adm_window": "آخر 14 يوماً، بشر فقط",
    "adm_bots": "زيارات روبوتات مستبعدة",
    "adm_daily": "يومياً",
    "adm_sources": "مصادر الزوار",
    "adm_source": "المصدر",
    "adm_pages": "أكثر الصفحات زيارة",
    "adm_self_excluded": "زياراتك وفحوصاتك أنت (المدير) مستثناة من كل الإحصاءات على هذا المتصفح لمدة سنة منذ آخر دخول للوحة. كل ما سُجل قبل 3 نوفمبر 2026 معلَّم كاختبار.",
    "adm_test": "(اختبار)",
    "adm_incomplete": "طلبات لم تكتمل",
    "adm_order_status": {"COMPLETED": "مدفوع", "CREATED": "بانتظار الدفع", "INCOMPLETE": "لم يكتمل", "PENDING": "قيد المراجعة في PayPal", "FAILED": "فشل التحقق"},
    "legal_imprint": "Impressum",
    "legal_privacy": "الخصوصية (Datenschutz)",
    "legal_terms": "الشروط (AGB)",
    "consent_report": "أطلب صراحةً تسليم التقرير فور الدفع، وأعلم أنني بذلك أفقد حق التراجع عن الشراء.",
    "consent_subscription": "أطلب صراحةً أن تبدأ المراقبة فوراً، وأعلم أنني إن تراجعت خلال 14 يوماً أدفع مقابل الأيام التي قُدمت فيها الخدمة.",
    "consent_missing": "ضع علامة على خانة الموافقة أولاً.",
})

TEXTS["en"].update({
    "nav_monitoring": "For teams",
    "mon_title": "Daily post-quantum readiness monitoring for your domains",
    "mon_sub": "We scan all your domains every day and email you the moment something regresses: post-quantum key exchange lost, grade dropped, or a certificate about to expire.",
    "mon_features": [
        "Automatic daily scan of every domain",
        "Email alert when a grade changes or X25519MLKEM768 disappears",
        "Certificate expiry alerts at 14 days and again at 3 days",
        "Dashboard with every domain's status and alert history, printable as a report",
        "Cancel any time from the dashboard",
    ],
    "mon_per_month": "per month",
    "mon_domains": "up to {n} domains",
    "mon_email_label": "Your email (dashboard link and alerts are sent here)",
    "mon_choose": "Choose a plan and pay with PayPal or card:",
    "mon_disabled": "Subscriptions are not enabled yet. Contact us if you want to subscribe.",
    "mon_email_first": "Enter a valid email first.",
    "mon_error": "The subscription could not be completed. Nothing is charged unless you finish the approval in PayPal. Please try again.",
    "mon_login_title": "Already subscribed?",
    "mon_login_sub": "Enter your email and we'll send you your dashboard link.",
    "mon_login_button": "Send link",
    "mon_login_sent": "If this email has an active subscription, the link will arrive within a few minutes.",
    "dash_title": "Monitoring dashboard",
    "dash_plan": "Plan",
    "dash_status": "Status",
    "dash_used": "Domains used",
    "dash_keep_private": "This link is the key to your account: bookmark it and don't share it.",
    "dash_add_title": "Add domains",
    "dash_add_hint": "One domain per line, or separate them with commas.",
    "dash_add_button": "Add",
    "dash_domains_title": "Domains",
    "dash_none": "No domains yet.",
    "dash_pending": "Waiting for first scan",
    "dash_checked": "Last check",
    "dash_days_left": "Cert days",
    "dash_remove": "Remove",
    "dash_scan_now": "Scan all now",
    "dash_alerts_title": "Alert history",
    "dash_no_alerts": "No alerts yet.",
    "dash_print": "Print report",
    "dash_cancel": "Cancel subscription",
    "dash_cancel_confirm": "Cancelling stops monthly billing and monitoring immediately. Are you sure?",
    "dash_status_names": {"ACTIVE": "Active", "CANCELLED": "Cancelled", "SUSPENDED": "Suspended", "EXPIRED": "Expired"},
    "dash_notices": {
        "added": "Added. Results appear after the next check, or press \"Scan all now\".",
        "limit": "You have reached your plan's domain limit.",
        "invalid": "Some domains were invalid and were not added.",
        "removed": "Removed.",
        "scanned": "Scan complete.",
        "wait": "Manual scans are limited to once per hour.",
        "inactive": "The subscription is not active.",
        "cancelled": "Your subscription has been cancelled.",
        "cancel_failed": "Could not cancel through PayPal right now. Try again later or cancel it in your PayPal account.",
    },
    "mon_cta_home": "For teams: daily monitoring of many domains with email alerts, from $29/month",
    "badge_title": "Show your readiness on your site",
    "badge_sub": "Paste this code into your site to display the badge. It updates from your latest scan within 30 days.",
    "admin_subs_active": "Active subscriptions",
    "admin_mrr": "Monthly recurring revenue",
    "admin_churned": "Cancelled or suspended",
    "admin_subs_title": "Subscribers",
    "adm_visitors": "Visitors",
    "adm_views": "Views",
    "adm_scanners": "Visitors who saw a scan result",
    "adm_pricing_views": "Visitors on the subscription page",
    "adm_window": "Last 14 days, humans only",
    "adm_bots": "bot views excluded",
    "adm_daily": "Daily",
    "adm_sources": "Traffic sources",
    "adm_source": "Source",
    "adm_pages": "Top pages",
    "adm_self_excluded": "Your own visits and scans (admin) are excluded from all statistics in this browser for one year after your last dashboard login. Everything recorded before 3 November 2026 is marked as a test.",
    "adm_test": "(test)",
    "adm_incomplete": "Incomplete orders",
    "adm_order_status": {"COMPLETED": "Paid", "CREATED": "Awaiting payment", "INCOMPLETE": "Incomplete", "PENDING": "Pending at PayPal", "FAILED": "Verification failed"},
    "legal_imprint": "Impressum",
    "legal_privacy": "Privacy (Datenschutz)",
    "legal_terms": "Terms (AGB)",
    "consent_report": "I expressly request that the report is delivered immediately after payment, and I acknowledge that I thereby lose my right of withdrawal.",
    "consent_subscription": "I expressly request that monitoring starts immediately, and I acknowledge that if I withdraw within 14 days I pay for the days already provided.",
    "consent_missing": "Please tick the consent box first.",
})


# ---------------------------------------------------------------- الفحص السريع في نهاية الأدلة والدراسة
TEXTS["ar"]["scanbox_title"] = "افحص موقعك الآن مجاناً"
TEXTS["en"]["scanbox_title"] = "Scan your site now, free"

# ---------------------------------------------------------------- الألمانية (Sie)
# متاحة للصفحة الرئيسية والدراسة وصفحة الشركات فقط؛ أي نص غير مترجم هنا يبقى بالإنجليزية.
DE_ENDPOINTS = {"site.index", "site.scan_form", "site.study", "site.monitoring", "site.monitor_login"}

TEXTS["ar"].update({
    "copy": "نسخ", "copied": "تم النسخ ✓",
    "nav_compare": "قارن",
    "site_title": "جاهزية TLS لما بعد الكم",
    "site_meta": "هل يستخدم {domain} تبادل المفاتيح الهجين المقاوم للحوسبة الكمومية؟ النتيجة وطريقة الإصلاح.",
    "site_source_scan": "من فحص حيّ بتاريخ",
    "site_source_study": "من دراستنا لأكبر 1000 موقع ({date}). افحص الآن لأحدث نتيجة.",
    "site_unknown": "لم نفحص {domain} بعد. افحصه الآن مجاناً.",
    "site_scan_cta": "افحص هذا الموقع الآن مجاناً",
    "compare_title": "قارن موقعين",
    "compare_sub": "افحص موقعين جنباً إلى جنب وشارك النتيجة.",
    "compare_vs": "مقابل",
    "compare_button": "قارن",
})
TEXTS["en"].update({
    "copy": "Copy", "copied": "Copied ✓",
    "nav_compare": "Compare",
    "site_title": "Post-quantum TLS readiness",
    "site_meta": "Does {domain} use hybrid post-quantum key exchange? Grade and how to fix it.",
    "site_source_scan": "From a live scan on",
    "site_source_study": "From our top-1000 study ({date}). Scan now for the latest result.",
    "site_unknown": "We have not scanned {domain} yet. Scan it now for free.",
    "site_scan_cta": "Scan this site now for free",
    "compare_title": "Compare two sites",
    "compare_sub": "Scan two sites side by side and share the result.",
    "compare_vs": "vs",
    "compare_button": "Compare",
})


TEXTS["ar"].update({
    "ladder_title": "الفحص هو الجزء السهل",
    "ladder_sub": "أي أداة مجانية، ونحن منها، تقول لك «نعم أو لا» مرة واحدة. الصعب أن تُصلح الخلل وأن يبقى مُصلحاً مع تغيّر خوادمك وشبكات CDN والمتصفحات.",
    "ladder_step1_h": "افحص — مجاناً",
    "ladder_step1_b": "درجة موقعك في 10 ثوانٍ، نفس الفحص العام الذي تجريه أي أداة.",
    "ladder_step2_h": "أصلِح — تقرير $49",
    "ladder_step2_b": "خطوات إصلاح دقيقة لـ nginx وApache وCaddy وCloudflare، لا مجرد درجة.",
    "ladder_step3_h": "ابقَ آمناً — مراقبة يومية",
    "ladder_step3_b": "نفحص كل نطاقاتك يومياً ونراسلك فور فقدان التبادل المقاوم للكم، أو هبوط الدرجة، أو اقتراب انتهاء شهادة. من 29$ شهرياً — وهذا ما لا تقدّمه أدوات الفحص اللحظي.",
    "ladder_cta": "ابدأ المراقبة اليومية ←",
})
TEXTS["en"].update({
    "ladder_title": "The scan is the easy part",
    "ladder_sub": "Every free checker — ours included — tells you yes or no, once. The hard part is fixing it, and keeping it fixed as your servers, CDNs and browsers change.",
    "ladder_step1_h": "Scan — free",
    "ladder_step1_b": "Grade your TLS in 10 seconds, the same public check any free tool runs.",
    "ladder_step2_h": "Fix — the $49 report",
    "ladder_step2_b": "Exact remediation for nginx, Apache, Caddy and Cloudflare, not just a grade.",
    "ladder_step3_h": "Stay safe — daily monitoring",
    "ladder_step3_b": "We scan all your domains every day and email you the moment post-quantum key exchange drops, a grade falls, or a certificate nears expiry. From $29/month — the thing one-off checkers do not do.",
    "ladder_cta": "Start daily monitoring →",
})


TEXTS["ar"].update({
    "faq_title": "أسئلة شائعة",
    "faq": [
        ["ما هو X25519MLKEM768؟",
         "تبادل مفاتيح هجين لـ TLS 1.3 يجمع X25519 التقليدي مع ML-KEM (المعيار FIPS 203) المقاوم للحواسيب الكمومية. تتفاوض عليه Chrome وFirefox وEdge تلقائياً اليوم. وجوده يحمي مفاتيح الجلسة من هجوم «احفظ الآن، فُكّ لاحقاً»."],
        ["هل موقعي في خطر من الحواسيب الكمومية اليوم؟",
         "لا يوجد حاسوب كمومي قادر على كسر TLS الآن، لكن الحركة المشفّرة التي تُسجَّل اليوم قد تُفكّ بعد سنوات عند توفّره. لذا تبادل المفاتيح المقاوم للكم مهم الآن لأي بيانات تبقى حساسة لسنوات."],
        ["كيف أفعّل TLS المقاوم للكم على خادمي؟",
         "تحتاج مكتبة TLS تدعم ML-KEM: OpenSSL 3.5+ لـ nginx وApache، أو Caddy حديث، أو تفعيل Cloudflare أمام موقعك. لدينا أدلة خطوة بخطوة لكل خادم."],
        ["هل الدرجة A تعني أن موقعي آمن كموميّاً بالكامل؟",
         "لا. نحن نقيس تبادل المفاتيح في اتصال TLS العام فقط. الشهادات ما زالت تقليدية في كل المواقع (المتصفحات لا تقبل شهادات ML-DSA بعد)، ولا نفحص تطبيقك ولا الاتصال بين CDN وخادمك الأصلي."],
        ["كم يكلّف؟",
         "الفحص والملخص مجانيان. التقرير الكامل بخطوات الإصلاح 49$ لمرة واحدة. المراقبة اليومية لكل نطاقاتك من 29$ شهرياً."],
    ],
})
TEXTS["en"].update({
    "faq_title": "Frequently asked questions",
    "faq": [
        ["What is X25519MLKEM768?",
         "A hybrid TLS 1.3 key exchange combining classical X25519 with post-quantum ML-KEM (FIPS 203). Chrome, Firefox and Edge negotiate it by default today. It protects session keys against \"harvest now, decrypt later\" attacks."],
        ["Is my website at risk from quantum computers today?",
         "No quantum computer can break TLS yet, but traffic recorded today could be decrypted years from now once one exists. Post-quantum key exchange matters now for any data that stays sensitive for years."],
        ["How do I enable post-quantum TLS on my server?",
         "You need a TLS library with ML-KEM: OpenSSL 3.5+ for nginx and Apache, a recent Caddy, or putting Cloudflare in front of your site. We publish step-by-step guides for each."],
        ["Does an A grade mean my site is fully quantum-safe?",
         "No. We measure the key exchange on the public TLS connection only. Certificates are still classical on every site (browsers do not accept ML-DSA certificates yet), and we do not test your application or the CDN-to-origin link."],
        ["How much does it cost?",
         "The scan and summary are free. The full report with fix steps is a one-off $49. Daily monitoring of all your domains starts at $29/month."],
    ],
})


TEXTS["ar"].update({
    "share_title": "شارك نتيجتك",
    "share_text": "درجة {domain} في جاهزية TLS لما بعد الكم: {grade}. افحص موقعك عبر Quantum Aether",
})
TEXTS["en"].update({
    "share_title": "Share your result",
    "share_text": "{domain} scored {grade} on post-quantum TLS readiness. Check your site with Quantum Aether",
})


TEXTS["ar"].update({
    "hero_tagline": "في 10 ثوانٍ، اعرف هل يستخدم موقعك التشفير المقاوم للحوسبة الكمومية. مجاناً وبلا حساب.",
    "try_label": "جرّب:",
    "trust_bar": "فحصنا أكبر 712 موقعاً · بيانات مفتوحة · مجاناً بلا حساب",
})
TEXTS["en"].update({
    "hero_tagline": "In 10 seconds, find out if your HTTPS already uses post-quantum encryption. Free, no sign-up.",
    "try_label": "Try:",
    "trust_bar": "We scanned the top 712 sites · open dataset · free, no account",
})

TEXTS["de"] = dict(TEXTS["en"])
TEXTS["de"].update({
    "dir": "ltr",
    "brand": "Quantum Aether",
    "nav_scan": "Prüfung",
    "nav_monitoring": "Für Unternehmen",
    "nav_guides": "Anleitungen",
    "nav_study": "Studie",
    "nav_research": "Forschung",
    "nav_api": "API",
    "hero_title": "Ist Ihre Website bereit für Quantencomputer?",
    "hero_sub": "Eine echte HTTPS-Prüfung: Vereinbart Ihr Server die Schlüssel mit Browsern über X25519MLKEM768 "
                "(ML-KEM / FIPS 203), wie es Chrome und Firefox heute tun? Und wie steht Ihr Zertifikat gegenüber dem Shor-Algorithmus da?",
    "domain_label": "Domainname",
    "scan_button": "Kostenlos prüfen",
    "scanning": "Prüfung läuft… das kann bis zu 20 Sekunden dauern",
    "checks_title": "Was wir prüfen",
    "checks": [
        "TLS-Version und Unterstützung von TLS 1.3",
        "Schlüsselaustausch: quantenresistent (hybrid) oder klassisch und damit „Harvest now, decrypt later“ ausgesetzt",
        "Ob der Server mit dem großen ClientHello moderner Browser zurechtkommt",
        "Zertifikatsalgorithmus, Schlüssellänge, Gültigkeit und Ablaufdatum",
    ],
    "how_title": "So funktioniert die Prüfung",
    "how_body": "Wir bauen zwei gewöhnliche Verbindungen zu Port 443 auf, wie es jeder Browser tut, lesen die Auswahl des Servers "
                "und schließen die Verbindung. Es werden keine Daten gesendet und keine Schwachstellen ausprobiert. "
                "Geprüft werden nur öffentliche Domains.",
    "pricing_title": "Preise",
    "free_title": "Kostenlose Zusammenfassung",
    "free_items": ["Note (A / B / C / F)", "Status des quantenresistenten Schlüsselaustauschs", "TLS-Version und Zertifikatsalgorithmus"],
    "paid_title": "Vollständiger Bericht",
    "paid_items": [
        "Alle Befunde mit Erklärung und Priorität",
        "Schritte zur Behebung für nginx, Apache, Caddy und Cloudflare",
        "Details zu Zertifikat und Handshake",
        "Zeitlicher Kontext: NIST-Standards und veröffentlichte Schätzungen zum Brechen von RSA",
        "Eine druckbare Fassung, auch als PDF speicherbar",
    ],
    "sample_link": "Echten vollständigen Beispielbericht ansehen",
    "sample_title": "Beispiel: vollständiger Bericht",
    "sample_banner": "Dies ist ein echter, vollständiger Bericht für github.com, genau so, wie Käufer ihn nach der Zahlung erhalten, "
                     "aus einer Prüfung vom {date}. Ändert die Website ihre Konfiguration, ändert sich auch das Ergebnis.",
    "sample_buy": "Prüfen Sie Ihre Website und erhalten Sie Ihren Bericht",
    "limits_title": "Was die Prüfung nicht abdeckt",
    "limits_items": [
        "Note A bedeutet nicht, dass Ihre Website vollständig „quantensicher“ oder frei von Schwachstellen ist. Wir messen nur die öffentliche TLS-Verbindung auf Port 443.",
        "Liegt Ihre Website hinter einem CDN oder Proxy (z. B. Cloudflare), prüfen wir die Verbindung Besucher–CDN, nicht CDN–Ursprungsserver.",
        "Nicht geprüft werden die Webanwendung selbst, E-Mail, VPNs, interne Systeme oder die Speicherung Ihrer Daten.",
        "Zertifikate sind heute auf allen Websites noch klassisch (RSA/ECDSA), da Browser noch keine ML-DSA-Zertifikate akzeptieren. Das ist kein Fehler Ihrer Konfiguration.",
        "Das Ergebnis ist eine Momentaufnahme; jede Änderung an Server oder CDN kann es verändern.",
    ],
    "privacy": "Wir speichern nur die Domain und das Prüfergebnis. Ihre IP-Adresse wird nicht gespeichert, nur ein verschlüsselter "
               "Hashwert zur Begrenzung von Anfragen.",
    "errors": {
        "invalid_domain": "Das ist kein gültiger Domainname. Geben Sie zum Beispiel example.com ein.",
        "private_address": "Diese Domain zeigt auf eine interne oder reservierte Adresse. Geprüft werden nur öffentliche Domains.",
        "dns_failure": "Diese Domain wurde im DNS nicht gefunden.",
        "connect_failure": "Port 443 dieser Domain ist nicht erreichbar.",
        "tls_failure": "Der Server akzeptiert keine moderne HTTPS-Verbindung (TLS 1.2 oder neuer).",
    },
    "mon_cta_home": "Für Unternehmen: tägliche Überwachung vieler Domains mit E-Mail-Benachrichtigungen, ab 29 $ pro Monat",
    "scanbox_title": "Prüfen Sie Ihre Website jetzt kostenlos",
    "scan_cta": "Prüfen Sie Ihre Domain kostenlos",
    # الدراسة
    "study_title": "Wie viele der 1.000 größten Websites sind bereit für Post-Quanten-TLS?",
    "study_lead": "Wir haben am {date} die 1.000 größten Domains der Tranco-Liste geprüft. Von den {reachable}, die über HTTPS "
                  "antworteten, vereinbaren {pq} ({pct} %) mit Browsern den hybriden Schlüsselaustausch X25519MLKEM768.",
    "study_reachable": "Domains antworteten",
    "study_pq": "Post-Quanten-bereit",
    "study_top100": "der Top 100",
    "study_grades": "Verteilung der Noten",
    "study_groups": "Vereinbarte Schlüsselaustausch-Gruppe",
    "study_certs": "Zertifikatsschlüssel",
    "study_notable": "Große Websites ohne Post-Quanten-Schlüsselaustausch",
    "study_notable_note": "Diese Domains vereinbaren nur klassischen Schlüsselaustausch. Ihr Datenverkehr ist damit "
                          "„Harvest now, decrypt later“ ausgesetzt.",
    "study_method_title": "Methodik",
    "study_method": "Für jede Domain (ohne www) haben wir von einem einzigen Server aus zwei Verbindungen zu Port 443 aufgebaut: "
                    "eine mit X25519MLKEM768 und X25519, wie Chrome sie anbietet, und eine gewöhnliche TLS-Verbindung zum Auslesen "
                    "des Zertifikats. „Nicht geantwortet“ bedeutet, dass der Name keine öffentliche Adresse hat oder auf der "
                    "nackten Domain kein HTTPS anbietet; meist sind das Infrastruktur- und CDN-Namen. Die Ergebnisse stammen von "
                    "einem Messpunkt und können anderswo abweichen.",
    "study_full_table": "Alle Ergebnisse",
    "study_download": "Daten herunterladen (JSON)",
    "rank": "Rang",
    "domain_col": "Domain",
    "grade_col": "Note",
    "group_col": "Gruppe",
    # الشركات
    "mon_title": "Tägliche Überwachung der Post-Quanten-Bereitschaft Ihrer Domains",
    "mon_sub": "Wir prüfen alle Ihre Domains täglich und benachrichtigen Sie sofort per E-Mail, wenn sich etwas verschlechtert: "
               "Post-Quanten-Schlüsselaustausch verloren, Note gesunken oder Zertifikat kurz vor dem Ablauf.",
    "mon_features": [
        "Automatische tägliche Prüfung jeder Domain",
        "E-Mail-Benachrichtigung, wenn sich die Note ändert oder X25519MLKEM768 wegfällt",
        "Warnung vor Zertifikatsablauf 14 Tage und erneut 3 Tage vorher",
        "Dashboard mit dem Status aller Domains und dem Verlauf der Benachrichtigungen, als Bericht druckbar",
        "Jederzeit im Dashboard kündbar",
    ],
    "mon_per_month": "pro Monat",
    "mon_domains": "bis zu {n} Domains",
    "mon_email_label": "Ihre E-Mail-Adresse (dorthin senden wir den Dashboard-Link und die Benachrichtigungen)",
    "mon_choose": "Wählen Sie einen Tarif und bezahlen Sie mit PayPal oder Karte:",
    "mon_disabled": "Abonnements sind noch nicht aktiviert. Bitte kontaktieren Sie uns, wenn Sie abonnieren möchten.",
    "mon_email_first": "Bitte geben Sie zuerst eine gültige E-Mail-Adresse ein.",
    "mon_error": "Das Abonnement konnte nicht abgeschlossen werden. Es wird nichts abgebucht, solange Sie die Freigabe bei "
                 "PayPal nicht abschließen. Bitte versuchen Sie es erneut.",
    "mon_login_title": "Bereits Abonnent?",
    "mon_login_sub": "Geben Sie Ihre E-Mail-Adresse ein, und wir senden Ihnen Ihren Dashboard-Link.",
    "mon_login_button": "Link senden",
    "mon_login_sent": "Wenn für diese E-Mail-Adresse ein aktives Abonnement besteht, erhalten Sie den Link in wenigen Minuten.",
    "consent_subscription": "Ich verlange ausdrücklich, dass die Überwachung sofort beginnt, und nehme zur Kenntnis, dass ich bei "
                            "einem Rücktritt innerhalb von 14 Tagen die bereits erbrachten Tage bezahle.",
    "consent_missing": "Bitte setzen Sie zuerst das Häkchen bei der Zustimmung.",
    "legal_imprint": "Impressum",
    "legal_privacy": "Datenschutz",
    "legal_terms": "AGB",
})

TEXTS["de"].update({
    "copy": "Kopieren", "copied": "Kopiert ✓",
    "nav_compare": "Vergleichen",
    "compare_title": "Zwei Websites vergleichen",
    "compare_sub": "Zwei Websites nebeneinander prüfen und das Ergebnis teilen.",
    "compare_vs": "gegen",
    "compare_button": "Vergleichen",
})


TEXTS["de"].update({
    "ladder_title": "Das Prüfen ist der einfache Teil",
    "ladder_sub": "Jedes kostenlose Prüftool, auch unseres, sagt einmal Ja oder Nein. Schwierig ist, den Mangel zu beheben und behoben zu halten, während sich Server, CDNs und Browser ändern.",
    "ladder_step1_h": "Prüfen — kostenlos",
    "ladder_step1_b": "Ihre TLS-Note in 10 Sekunden, dieselbe öffentliche Prüfung, die jedes kostenlose Tool macht.",
    "ladder_step2_h": "Beheben — der 49-$-Bericht",
    "ladder_step2_b": "Konkrete Behebung für nginx, Apache, Caddy und Cloudflare, nicht nur eine Note.",
    "ladder_step3_h": "Sicher bleiben — tägliche Überwachung",
    "ladder_step3_b": "Wir prüfen alle Ihre Domains täglich und mailen Ihnen sofort, wenn der quantenresistente Schlüsselaustausch wegfällt, die Note sinkt oder ein Zertifikat abläuft. Ab 29 $/Monat — genau das, was einmalige Prüftools nicht leisten.",
    "ladder_cta": "Tägliche Überwachung starten →",
})


TEXTS["de"].update({
    "faq_title": "Häufige Fragen",
    "faq": [
        ["Was ist X25519MLKEM768?",
         "Ein hybrider TLS-1.3-Schlüsselaustausch, der klassisches X25519 mit dem quantenresistenten ML-KEM (FIPS 203) verbindet. Chrome, Firefox und Edge handeln ihn heute standardmäßig aus. Er schützt Sitzungsschlüssel vor „Harvest now, decrypt later“."],
        ["Ist meine Website heute durch Quantencomputer gefährdet?",
         "Noch kann kein Quantencomputer TLS brechen, aber heute aufgezeichneter Verkehr könnte in einigen Jahren entschlüsselt werden. Quantenresistenter Schlüsselaustausch zählt daher jetzt für Daten, die lange sensibel bleiben."],
        ["Wie aktiviere ich quantenresistentes TLS auf meinem Server?",
         "Sie brauchen eine TLS-Bibliothek mit ML-KEM: OpenSSL 3.5+ für nginx und Apache, ein aktuelles Caddy oder Cloudflare vor Ihrer Website. Wir veröffentlichen Schritt-für-Schritt-Anleitungen."],
        ["Bedeutet Note A, dass meine Website vollständig quantensicher ist?",
         "Nein. Wir messen nur den Schlüsselaustausch der öffentlichen TLS-Verbindung. Zertifikate sind überall noch klassisch, und wir prüfen weder Ihre Anwendung noch die Verbindung CDN–Ursprungsserver."],
        ["Was kostet es?",
         "Prüfung und Zusammenfassung sind kostenlos. Der vollständige Bericht mit Behebungsschritten kostet einmalig 49 $. Tägliche Überwachung aller Domains ab 29 $/Monat."],
    ],
})


TEXTS["de"].update({
    "share_title": "Ergebnis teilen",
    "share_text": "{domain} erreichte Note {grade} bei der quantenresistenten TLS-Prüfung. Prüfen Sie Ihre Website mit Quantum Aether",
})


TEXTS["de"].update({
    "hero_tagline": "In 10 Sekunden sehen, ob Ihr HTTPS schon quantenresistent verschlüsselt ist. Kostenlos, ohne Anmeldung.",
    "try_label": "Beispiel:",
    "trust_bar": "Wir haben die Top-712-Websites geprüft · offener Datensatz · kostenlos, ohne Konto",
})

LANG_NAMES = {"en": "English", "ar": "العربية", "de": "Deutsch"}
