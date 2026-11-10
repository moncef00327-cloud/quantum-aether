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
        "scanning": "أُرسل الفحص… بانتظار استجابة الخادم",
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
        "scanning": "Scan submitted… waiting for the server response",
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
    "KX_RETRY_REQUESTED": {
        "ar": ("طلب الخادم إعادة المصافحة؛ الدعم غير محسوم",
               "طلب HelloRetryRequest المجموعة {group}، لكن المجسّ لم يكمل إعادة المصافحة. هذا لا يثبت تفاوض تبادل مفاتيح مقاوم للكم. أعد الفحص من عميل TLS متوافق."),
        "en": ("Server requested a retry; support is undetermined",
               "HelloRetryRequest requested group {group}, but the probe did not complete the retry. This does not establish negotiated post-quantum key exchange. Verify with a compatible TLS client."),
    },
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
    "crypto_network_label": "اختر العملة والشبكة",
    "crypto_create_order": "إنشاء طلب الدفع",
    "crypto_send": "أرسل بالضبط",
    "crypto_on": "على شبكة",
    "crypto_to": "إلى العنوان:",
    "crypto_copy": "نسخ",
    "crypto_warning": "أرسل على هذه الشبكة فقط وبهذا المبلغ بالضبط (الكسر العشري يعرّف دفعتك). "
                      "الإرسال على شبكة أخرى أو بعملة أخرى قد يضيع المبلغ. رسوم الشبكة على المرسل.",
    "crypto_email_label": "بريدك لإرسال إيصال الشراء (اختياري):",
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
    "crypto_network_label": "Choose currency and network",
    "crypto_create_order": "Create payment request",
    "crypto_send": "Send exactly",
    "crypto_on": "on",
    "crypto_to": "to this address:",
    "crypto_copy": "Copy",
    "crypto_warning": "Use this network only and this exact amount (the decimals identify your payment). "
                      "Sending on another network or another token may lose the funds. Network fees are paid by the sender.",
    "crypto_email_label": "Email for your purchase receipt (optional):",
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
DE_ENDPOINTS = {"site.pq_config", "site.pq_config_server", "site.business_page", "site.pricing_page", "site.index", "site.scan_form", "site.study", "site.monitoring", "site.monitor_login",
                "site.adoption_page", "site.scanning_page", "site.deadlines_page", "site.agency_page",
                "site.countries_page", "site.country_page", "site.hosting_page"}

TEXTS["ar"].update({
    "copy": "نسخ", "copied": "تم النسخ ✓",
    "nav_compare": "قارن",
    "site_title": "جاهزية TLS لما بعد الكم",
    "home_title": "فحص مجاني: هل يدعم موقعك TLS المقاوم للحوسبة الكمومية؟",
    "home_meta": "افحص مجاناً ودون حساب هل يتفق خادمك مع المتصفحات على X25519MLKEM768 (ML-KEM)، مع الدرجة وخطوات الإصلاح. مرصد أسبوعي لأكبر 10,000 موقع.",
    "research_meta": "تجارب كمومية حقيقية على حواسيب IBM: حالات Bell وGHZ ونتائجها الخام.",
    "sample_meta": "مثال حقيقي للتقرير الكامل لـ github.com: تبادل المفاتيح، الشهادة، النتائج وخطوات الإصلاح بالأوامر.",
    "site_question": "هل يستخدم {domain} تشفير TLS المقاوم للحوسبة الكمومية؟",
    "site_title_grade": "(الدرجة {grade})",
    "site_meta": "هل يستخدم {domain} تبادل المفاتيح الهجين المقاوم للحوسبة الكمومية؟ النتيجة وطريقة الإصلاح.",
    "site_source_scan": "من فحص حيّ بتاريخ",
    "site_source_study": "من دراستنا لأكبر 1000 موقع ({date}). افحص الآن لأحدث نتيجة.",
    "site_unknown": "لم نفحص {domain} بعد. افحصه الآن مجاناً.",
    "site_scan_cta": "افحص هذا الموقع الآن مجاناً",
    "site_source_weekly": "من متتبّعنا الأسبوعي لأكبر 10,000 موقع، فحص بتاريخ",
    "site_answer": "الإجابة المختصرة",
    "site_history": "السجل الأسبوعي",
    "site_network": "الشبكة المشغّلة",
    "site_related": "مواقع ذات صلة",
    "site_rank": "ترتيب Tranco",
    "compare_title": "قارن جاهزية موقعين لـ TLS ما بعد الكم",
    "compare_sub": "افحص موقعين جنباً إلى جنب وشارك النتيجة.",
    "compare_vs": "مقابل",
    "compare_button": "قارن",
})
TEXTS["en"].update({
    "copy": "Copy", "copied": "Copied ✓",
    "nav_compare": "Compare",
    "site_title": "Post-quantum TLS readiness",
    "home_title": "Free post-quantum TLS check (X25519MLKEM768)",
    "home_meta": "Free, no-account check: does your server negotiate X25519MLKEM768 (ML-KEM) with browsers? Grade, findings and fix steps, plus a weekly top-10k tracker.",
    "research_meta": "Real quantum experiments on IBM hardware: Bell and GHZ states with raw results.",
    "sample_meta": "A real full report for github.com: key exchange, certificate, findings and copy-paste fix steps.",
    "site_question": "Does {domain} use post-quantum TLS?",
    "site_title_grade": "(grade {grade})",
    "site_meta": "Does {domain} use hybrid post-quantum key exchange? Grade and how to fix it.",
    "site_source_scan": "From a live scan on",
    "site_source_study": "From our top-1000 study ({date}). Scan now for the latest result.",
    "site_unknown": "We have not scanned {domain} yet. Scan it now for free.",
    "site_scan_cta": "Scan this site now for free",
    "site_source_weekly": "From our weekly tracker of the top 10,000 sites, scanned on",
    "site_answer": "Short answer",
    "site_history": "Weekly history",
    "site_network": "Hosting network",
    "site_related": "Related sites",
    "site_rank": "Tranco rank",
    "compare_title": "Compare the post-quantum TLS of two sites",
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
    "hero_tagline": "افحص تبادل مفاتيح TLS المرصود في موقعك. ملخص مجاني، دون إنشاء حساب.",
    "try_label": "جرّب:",
    "trust_bar": "نفحص أكبر 10,000 موقع كل أسبوع · بيانات مفتوحة · مجاناً بلا حساب",
})
TEXTS["en"].update({
    "hero_tagline": "Check the TLS key exchange observed on your website. Free summary. No account needed.",
    "try_label": "Try:",
    "trust_bar": "We scan the top 10,000 sites every week · open dataset · free, no account",
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
    "scanning": "Prüfung gesendet… Warten auf die Serverantwort",
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
    "compare_title": "Post-Quantum-TLS zweier Websites vergleichen",
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
    "hero_tagline": "Prüfen Sie den beobachteten TLS-Schlüsselaustausch Ihrer Website. Kostenlose Zusammenfassung, ohne Anmeldung.",
    "try_label": "Beispiel:",
    "trust_bar": "Wir prüfen jede Woche die Top-10.000-Websites · offener Datensatz · kostenlos, ohne Konto",
})

LANG_NAMES = {"en": "English", "ar": "العربية", "de": "Deutsch"}


# ---------------------------------------------------------------- متتبّع التبنّي الأسبوعي (/adoption)

TEXTS["en"].update({
    "nav_adoption": "Tracker",
    "adoption_title": "Post-quantum TLS adoption tracker",
    "adoption_lead": "Every Monday we re-scan the Tranco top 10,000 and watchlists for Germany, Austria and Switzerland; "
                     "once a month the top 100,000. Week {week} (from {date}): {pq} of the {reachable} top-1,000 sites that "
                     "answered ({pct}%) negotiate the hybrid X25519MLKEM768 key exchange.",
    "adoption_stat_pct": "Top sites with post-quantum key exchange",
    "adoption_stat_delta": "Change vs previous week",
    "adoption_stat_switched": "Switched this week",
    "adoption_stat_lost": "Lost it this week",
    "adoption_pp": "pp",
    "adoption_first_week": "This is the first week on record (the published study). The first week-over-week comparison "
                           "appears after the next Monday scan.",
    "adoption_timeline": "Weekly share of top sites with post-quantum key exchange",
    "adoption_switched_title": "Switched to post-quantum key exchange this week",
    "adoption_switched_none": "No site switched this week.",
    "adoption_lost_title": "Stopped negotiating post-quantum key exchange this week",
    "adoption_lost_none": "No site lost it this week.",
    "adoption_regraded_title": "Other grade changes",
    "adoption_before": "Before",
    "adoption_after": "Now",
    "adoption_sectors_title": "Watchlists: Germany, Austria, Switzerland",
    "adoption_sectors_note": "Hostnames as visitors reach them. Every list is checked each Monday.",
    "adoption_enabled_of": "{pq} of {reachable} enabled",
    "adoption_status_on": "Enabled",
    "adoption_status_since": "since {week}",
    "adoption_status_off": "Not yet enabled",
    "adoption_status_noanswer": "No HTTPS answer",
    "adoption_status_unsure": "Undetermined, will be rescanned",
    "adoption_unsure_count": "{n} undetermined (not counted)",
    "adoption_method_title": "Methodology and limits",
    "adoption_method": "Each hostname gets two connections to port 443 from a single server: one offering X25519MLKEM768 "
                       "plus X25519 as Chrome does, and one ordinary TLS connection to read the certificate. Nothing else is "
                       "sent and nothing is attempted. Results come from one vantage point at scan time; behind a CDN we see "
                       "the visitor-to-CDN connection, not the CDN-to-origin one. \"Not yet enabled\" describes the key "
                       "exchange only; it is not a judgement of a site's overall security.",
    "adoption_correction": "Spotted an error, or want a hostname added or removed? Contact us via the",
    "adoption_download": "Open data (CC BY 4.0):",
    "adoption_link": "Weekly adoption tracker →",
    "adoption_week_col": "Week",
    "adoption_status_col": "Status",
    "host_col": "Hostname",
})

TEXTS["ar"].update({
    "nav_adoption": "المتتبّع",
    "adoption_title": "متتبّع تبنّي TLS المقاوم للكم",
    "adoption_lead": "كل يوم اثنين نعيد فحص أكبر 10,000 نطاق في قائمة Tranco وقوائم مراقبة لألمانيا والنمسا وسويسرا، "
                     "وكل شهر أكبر 100,000. الأسبوع {week} (من {date}): {pq} من أصل {reachable} موقعاً من الأكبر 1000 أجاب "
                     "({pct}%) تتفق على تبادل المفاتيح الهجين X25519MLKEM768.",
    "adoption_stat_pct": "المواقع الكبرى بتبادل مفاتيح مقاوم للكم",
    "adoption_stat_delta": "التغيّر عن الأسبوع السابق",
    "adoption_stat_switched": "انتقلت هذا الأسبوع",
    "adoption_stat_lost": "فقدته هذا الأسبوع",
    "adoption_pp": "نقطة",
    "adoption_first_week": "هذا أول أسبوع مسجّل (بيانات الدراسة المنشورة). تظهر أول مقارنة أسبوعية بعد فحص يوم الاثنين القادم.",
    "adoption_timeline": "النسبة الأسبوعية للمواقع الكبرى التي تستخدم تبادل مفاتيح مقاوماً للكم",
    "adoption_switched_title": "انتقلت إلى تبادل المفاتيح المقاوم للكم هذا الأسبوع",
    "adoption_switched_none": "لم ينتقل أي موقع هذا الأسبوع.",
    "adoption_lost_title": "توقفت عن تبادل المفاتيح المقاوم للكم هذا الأسبوع",
    "adoption_lost_none": "لم يفقده أي موقع هذا الأسبوع.",
    "adoption_regraded_title": "تغيّرات أخرى في الدرجة",
    "adoption_before": "قبل",
    "adoption_after": "الآن",
    "adoption_sectors_title": "قوائم المراقبة: ألمانيا والنمسا وسويسرا",
    "adoption_sectors_note": "أسماء المواقع كما يصلها الزوار. تُفحص كل قائمة كل يوم اثنين.",
    "adoption_enabled_of": "{pq} من {reachable} مفعّل",
    "adoption_status_on": "مفعّل",
    "adoption_status_since": "منذ {week}",
    "adoption_status_off": "لم يُفعَّل بعد",
    "adoption_status_noanswer": "لا إجابة عبر HTTPS",
    "adoption_status_unsure": "غير محسوم، يُعاد فحصه",
    "adoption_unsure_count": "{n} غير محسوم (لا يُحتسب)",
    "adoption_method_title": "المنهجية والحدود",
    "adoption_method": "لكل اسم موقع نجري اتصالين بالمنفذ 443 من خادم واحد: الأول يعرض X25519MLKEM768 مع X25519 كما يفعل "
                       "Chrome، والثاني اتصال TLS عادي لقراءة الشهادة. لا نرسل شيئاً آخر ولا نحاول أي اختراق. النتائج من "
                       "نقطة رصد واحدة وقت الفحص، وخلف CDN نرى الاتصال بين الزائر والـ CDN لا بين الـ CDN والخادم الأصلي. "
                       "«لم يُفعَّل بعد» يصف تبادل المفاتيح وحده، وليس حكماً على أمان الموقع عموماً.",
    "adoption_correction": "وجدت خطأً أو تريد إضافة موقع أو حذفه؟ تواصل معنا عبر صفحة",
    "adoption_download": "بيانات مفتوحة (CC BY 4.0):",
    "adoption_link": "متتبّع التبنّي الأسبوعي ←",
    "adoption_week_col": "الأسبوع",
    "adoption_status_col": "الحالة",
    "host_col": "اسم الموقع",
})

TEXTS["de"].update({
    "nav_adoption": "Tracker",
    "adoption_title": "Post-Quanten-TLS: Wochen-Tracker",
    "adoption_lead": "Jeden Montag prüfen wir die 10.000 größten Domains der Tranco-Liste sowie Beobachtungslisten für "
                     "Deutschland, Österreich und die Schweiz erneut, einmal im Monat die 100.000 größten. Woche {week} "
                     "(ab {date}): {pq} der {reachable} erreichbaren Top-1.000-Websites ({pct} %) vereinbaren den hybriden "
                     "Schlüsselaustausch X25519MLKEM768.",
    "adoption_stat_pct": "Top-Websites mit Post-Quanten-Schlüsselaustausch",
    "adoption_stat_delta": "Veränderung zur Vorwoche",
    "adoption_stat_switched": "Diese Woche umgestellt",
    "adoption_stat_lost": "Diese Woche verloren",
    "adoption_pp": "Pp.",
    "adoption_first_week": "Dies ist die erste erfasste Woche (die veröffentlichte Studie). Der erste Wochenvergleich "
                           "erscheint nach dem nächsten Montagsscan.",
    "adoption_timeline": "Wöchentlicher Anteil der Top-Websites mit Post-Quanten-Schlüsselaustausch",
    "adoption_switched_title": "Diese Woche auf Post-Quanten-Schlüsselaustausch umgestellt",
    "adoption_switched_none": "Diese Woche hat keine Website umgestellt.",
    "adoption_lost_title": "Diese Woche kein Post-Quanten-Schlüsselaustausch mehr",
    "adoption_lost_none": "Diese Woche hat ihn keine Website verloren.",
    "adoption_regraded_title": "Weitere Notenänderungen",
    "adoption_before": "Vorher",
    "adoption_after": "Jetzt",
    "adoption_sectors_title": "Beobachtungslisten: Deutschland, Österreich, Schweiz",
    "adoption_sectors_note": "Hostnamen so, wie Besucher sie aufrufen. Jede Liste wird jeden Montag geprüft.",
    "adoption_enabled_of": "{pq} von {reachable} aktiviert",
    "adoption_status_on": "Aktiviert",
    "adoption_status_since": "seit {week}",
    "adoption_status_off": "Noch nicht aktiviert",
    "adoption_status_noanswer": "Keine HTTPS-Antwort",
    "adoption_status_unsure": "Unklar, wird erneut geprüft",
    "adoption_unsure_count": "{n} unklar (nicht gezählt)",
    "adoption_method_title": "Methodik und Grenzen",
    "adoption_method": "Für jeden Hostnamen bauen wir von einem einzigen Server aus zwei Verbindungen zu Port 443 auf: eine "
                       "mit X25519MLKEM768 und X25519 wie Chrome und eine gewöhnliche TLS-Verbindung zum Lesen des "
                       "Zertifikats. Sonst wird nichts gesendet und nichts versucht. Die Ergebnisse stammen von einem "
                       "Messpunkt zum Zeitpunkt der Prüfung; hinter einem CDN sehen wir die Verbindung Besucher–CDN, nicht "
                       "CDN–Ursprungsserver. „Noch nicht aktiviert“ beschreibt nur den Schlüsselaustausch und ist kein "
                       "Urteil über die Sicherheit der Website insgesamt.",
    "adoption_correction": "Fehler entdeckt, oder soll ein Hostname aufgenommen bzw. entfernt werden? Kontakt über das",
    "adoption_download": "Offene Daten (CC BY 4.0):",
    "adoption_link": "Wöchentlicher Adoptions-Tracker →",
    "adoption_week_col": "Woche",
    "adoption_status_col": "Status",
    "host_col": "Hostname",
})


# ---------------------------------------------------------------- المزوّدون والفحص الواسع وصفحة /scanning

TEXTS["en"].update({
    "adoption_stat_top10k": "Top 10,000 sites with post-quantum key exchange",
    "adoption_providers_title": "Hosting providers and CDNs",
    "adoption_providers_note": "Share of sites that negotiate X25519MLKEM768, by the network that serves them ({sites} answering sites, {period}). "
                               "Behind a CDN this is the CDN's edge. Networks with fewer than 20 sites are not listed.",
    "adoption_provider_col": "Network",
    "adoption_sites_col": "Sites",
    "adoption_enabled_col": "Enabled",
    "adoption_pct_col": "% enabled",
    "scanning_link": "How we scan, and how to opt out →",
    "scanning_title": "About our scans",
    "scanning_lead": "Quantum Aether measures how many public websites already use post-quantum key exchange. If you saw TLS connections "
                     "from our server in your logs, this page explains them.",
    "scanning_what_title": "What the scan does",
    "scanning_what": [
        "Two TLS connections to port 443 per hostname: one offering X25519MLKEM768 with X25519 as Chrome does, one ordinary "
        "connection to read the certificate. Then the connection is closed.",
        "No HTTP request, no paths, no content, no login attempts, no vulnerability tests.",
        "Weekly for the Tranco top 10,000 and a few public watchlists; monthly for the top 100,000; a limited number of parallel "
        "connections.",
        "Results are published per hostname and in aggregate as open data (CC BY 4.0).",
    ],
    "scanning_optout_title": "Opt out",
    "scanning_optout": "To have a hostname (and its subdomains) excluded from future scans and removed from the published tables, "
                       "email us from an address at that domain or describe your relationship to it:",
    "scanning_source": "Scans come from",
})
TEXTS["ar"].update({
    "adoption_stat_top10k": "أكبر 10,000 موقع بتبادل مفاتيح مقاوم للكم",
    "adoption_providers_title": "مزوّدو الاستضافة وشبكات CDN",
    "adoption_providers_note": "نسبة المواقع التي تتفق على X25519MLKEM768 حسب الشبكة التي تخدمها ({sites} موقعاً أجاب، {period}). "
                               "خلف CDN تظهر شبكة الـ CDN. لا نعرض شبكة بأقل من 20 موقعاً.",
    "adoption_provider_col": "الشبكة",
    "adoption_sites_col": "المواقع",
    "adoption_enabled_col": "مفعّل",
    "adoption_pct_col": "% مفعّل",
    "scanning_link": "كيف نفحص، وكيف تطلب الاستبعاد ←",
    "scanning_title": "عن فحوصاتنا",
    "scanning_lead": "يقيس الأثير الكمومي عدد المواقع العامة التي تستخدم تبادل مفاتيح مقاوماً للكم. إن رأيت اتصالات TLS من خادمنا في "
                     "سجلاتك، فهذه الصفحة تشرحها.",
    "scanning_what_title": "ماذا يفعل الفحص",
    "scanning_what": [
        "اتصالا TLS بالمنفذ 443 لكل اسم موقع: الأول يعرض X25519MLKEM768 مع X25519 كما يفعل Chrome، والثاني اتصال عادي لقراءة "
        "الشهادة، ثم يُغلق الاتصال.",
        "لا طلب HTTP، ولا مسارات، ولا محتوى، ولا محاولات دخول، ولا اختبار ثغرات.",
        "أسبوعياً لأكبر 10,000 نطاق في Tranco وقوائم مراقبة عامة، وشهرياً لأكبر 100,000، بعدد اتصالات متوازية محدود.",
        "تُنشر النتائج لكل اسم موقع وإجمالاً كبيانات مفتوحة (CC BY 4.0).",
    ],
    "scanning_optout_title": "طلب الاستبعاد",
    "scanning_optout": "لاستبعاد اسم موقع (ونطاقاته الفرعية) من الفحوص القادمة وحذفه من الجداول المنشورة، راسلنا من عنوان بريد على ذلك "
                       "النطاق، أو اشرح صلتك به:",
    "scanning_source": "تأتي الفحوص من",
})
TEXTS["de"].update({
    "adoption_stat_top10k": "Top-10.000-Websites mit Post-Quanten-Schlüsselaustausch",
    "adoption_providers_title": "Hoster und CDNs",
    "adoption_providers_note": "Anteil der Websites mit X25519MLKEM768 nach dem Netz, das sie ausliefert ({sites} antwortende Websites, "
                               "{period}). Hinter einem CDN ist das die CDN-Kante. Netze mit weniger als 20 Websites werden nicht gezeigt.",
    "adoption_provider_col": "Netz",
    "adoption_sites_col": "Websites",
    "adoption_enabled_col": "Aktiviert",
    "adoption_pct_col": "% aktiviert",
    "scanning_link": "Wie wir prüfen und wie Sie sich ausnehmen lassen →",
    "scanning_title": "Über unsere Prüfungen",
    "scanning_lead": "Quantum Aether misst, wie viele öffentliche Websites bereits Post-Quanten-Schlüsselaustausch nutzen. Wenn Sie "
                     "TLS-Verbindungen von unserem Server in Ihren Logs sehen, erklärt diese Seite sie.",
    "scanning_what_title": "Was die Prüfung tut",
    "scanning_what": [
        "Zwei TLS-Verbindungen zu Port 443 pro Hostname: eine mit X25519MLKEM768 und X25519 wie Chrome, eine gewöhnliche "
        "zum Lesen des Zertifikats. Danach wird die Verbindung geschlossen.",
        "Keine HTTP-Anfrage, keine Pfade, keine Inhalte, keine Anmeldeversuche, keine Schwachstellentests.",
        "Wöchentlich für die Tranco-Top-10.000 und einige öffentliche Beobachtungslisten, monatlich für die Top-100.000, "
        "mit begrenzter Zahl paralleler Verbindungen.",
        "Die Ergebnisse werden pro Hostname und aggregiert als offene Daten (CC BY 4.0) veröffentlicht.",
    ],
    "scanning_optout_title": "Ausnahme beantragen",
    "scanning_optout": "Um einen Hostnamen (samt Subdomains) von künftigen Prüfungen auszunehmen und aus den veröffentlichten Tabellen zu "
                       "entfernen, schreiben Sie uns von einer Adresse dieser Domain oder beschreiben Sie Ihre Verbindung dazu:",
    "scanning_source": "Prüfungen kommen von",
})


# الصفحة الرئيسية: أمثلة بنتائجها + جملة لمن لا يملك موقعاً
TEXTS["ar"].update({
    "example_ready": "جاهز",
    "example_not_ready": "غير جاهز",
    "example_unsure": "غير محسوم",
    "hero_no_site": "لا تملك موقعاً؟ افحص موقع بنكك أو شركتك أو متجرك المفضل.",
})
TEXTS["en"].update({
    "example_ready": "ready",
    "example_not_ready": "not ready",
    "example_unsure": "undetermined",
    "hero_no_site": "No website of your own? Check your bank, your employer or your favourite shop.",
})
TEXTS["de"].update({
    "example_ready": "bereit",
    "example_not_ready": "nicht bereit",
    "example_unsure": "unklar",
    "hero_no_site": "Keine eigene Website? Prüfen Sie Ihre Bank, Ihren Arbeitgeber oder Ihren Lieblingsshop.",
})

TEXTS["ar"]["deadlines_link"] = "متى يجب الانتقال؟ مواعيد NIST وCNSA 2.0 والاتحاد الأوروبي"
TEXTS["en"]["deadlines_link"] = "When do you have to move? NIST, CNSA 2.0, EU and UK deadlines"
TEXTS["de"]["deadlines_link"] = "Bis wann umstellen? Fristen von NIST, CNSA 2.0, EU und Großbritannien"


# صفحة النتيجة: الملاحظات، الإصلاح المجاني، «مرة واحدة»، «نبّهني مجاناً»
TEXTS["en"].update({
    "findings_title": "What we found",
    "free_fix_hint": "You can enable post-quantum key exchange yourself, free, with our step-by-step guides:",
    "findings_paid_note": "The full report explains every finding for your server, with its priority and the exact configuration to fix it.",
    "one_time": "One-time payment. No subscription.",
    "alert_card_title": "Get an email if this changes (free)",
    "alert_card_sub": "We re-check {domain} every week and email you only when its post-quantum status, grade or certificate warning changes. One domain, free, unsubscribe in one click.",
    "alert_email_label": "Your email address",
    "alert_button": "Notify me",
    "alert_consent": "I agree that Quantum Aether may email me about this domain. I can withdraw at any time with the link in every email.",
    "alerts_more": "More than one domain, checked daily? See monitoring",
    "alerts_title": "Free change alert",
    "alerts_confirm_button": "Confirm my alert",
    "alerts_stop_button": "Stop emails and delete my address",
    "alerts_states": {
        "check_inbox": "Almost done: we sent a confirmation link. Your alert for {domain} starts when you click it.",
        "consent_missing": "Please tick the consent box so we may email you.",
        "bad_email": "That email address does not look right. Please go back and check it.",
        "rate_limited": "Too many requests from your connection today. Please try again tomorrow.",
        "already_active": "An alert for {domain} is already active for this address.",
        "unavailable": "Email is temporarily unavailable. Please try again later.",
        "confirm_prompt": "Confirm that you want a weekly-checked change alert for {domain}.",
        "confirmed": "Confirmed. We will email you when the post-quantum status of {domain} changes. (A free alert covers one domain; confirming another domain replaces this one.)",
        "stop_prompt": "Stop the alerts for {domain}? Your email address will be deleted.",
        "stopped": "Done. No more emails, and your address has been deleted.",
    },
})
TEXTS["ar"].update({
    "findings_title": "ما وجدناه",
    "free_fix_hint": "يمكنك تفعيل تبادل المفاتيح ما بعد الكمومي بنفسك مجاناً عبر أدلتنا خطوة بخطوة:",
    "findings_paid_note": "التقرير الكامل يشرح كل ملاحظة لخادمك، مع أولويتها والإعدادات الدقيقة لإصلاحها.",
    "one_time": "دفعة واحدة. بلا اشتراك.",
    "alert_card_title": "تلقَّ رسالة إن تغيّر هذا (مجاناً)",
    "alert_card_sub": "نعيد فحص {domain} كل أسبوع ونراسلك فقط حين يتغيّر وضعه ما بعد الكمومي أو درجته أو تحذير شهادته. نطاق واحد، مجاناً، وإلغاء بنقرة.",
    "alert_email_label": "بريدك الإلكتروني",
    "alert_button": "نبّهني",
    "alert_consent": "أوافق على أن يراسلني الأثير الكمومي بخصوص هذا النطاق، ويمكنني سحب الموافقة في أي وقت عبر الرابط في كل رسالة.",
    "alerts_more": "أكثر من نطاق، بفحص يومي؟ اطّلع على المراقبة",
    "alerts_title": "تنبيه مجاني عند التغيير",
    "alerts_confirm_button": "أكّد التنبيه",
    "alerts_stop_button": "أوقف الرسائل واحذف بريدي",
    "alerts_states": {
        "check_inbox": "خطوة أخيرة: أرسلنا لك رابط تأكيد. يبدأ تنبيهك لـ {domain} حين تضغط عليه.",
        "consent_missing": "ضع علامة على مربع الموافقة من فضلك حتى نستطيع مراسلتك.",
        "bad_email": "يبدو أن عنوان البريد غير صحيح. ارجع وتحقق منه.",
        "rate_limited": "طلبات كثيرة من اتصالك اليوم. حاول غداً.",
        "already_active": "يوجد تنبيه فعّال لـ {domain} على هذا البريد.",
        "unavailable": "البريد غير متاح مؤقتاً. حاول لاحقاً.",
        "confirm_prompt": "أكّد أنك تريد تنبيهاً أسبوعياً عند تغيّر وضع {domain}.",
        "confirmed": "تم التأكيد. سنراسلك حين يتغيّر وضع {domain} ما بعد الكمومي. (التنبيه المجاني لنطاق واحد؛ تأكيد نطاق آخر يحلّ محلّه.)",
        "stop_prompt": "إيقاف التنبيهات لـ {domain}؟ سيُحذف بريدك.",
        "stopped": "تم. لا رسائل بعد الآن، وحُذف بريدك.",
    },
})
TEXTS["de"].update({k: v for k, v in TEXTS["en"].items() if k.startswith(("findings_title", "free_fix", "findings_paid", "one_time", "alert", "alerts"))})


# باقة الوكالات
TEXTS["en"].update({
    "agency_title": "Agency pack",
    "agency_meta": "{credits} full post-quantum TLS reports for ${price}, one payment, no expiry. For agencies, MSPs and auditors checking client sites.",
    "agency_lead": "Checking post-quantum readiness for clients? Get {credits} full reports for ${price}: one payment, no subscription, no expiry.",
    "agency_items": [
        "{credits} full reports, ${each} each instead of ${single}",
        "Use them on any domains, whenever you like: enter a domain on your private pack page and its full report opens at once",
        "Every report: all findings with priority, fix steps for nginx, Apache, Caddy and Cloudflare, certificate and handshake details, printable as PDF for your client",
        "All your reports stay listed on your pack page",
    ],
    "agency_buy_title": "{credits} full reports",
    "agency_consent": "I agree that each report is delivered immediately when I use a credit, and I understand that I lose the right of withdrawal for every report already generated; unused reports can be withdrawn from within 14 days.",
    "agency_compare_title": "One report, or ongoing checks?",
    "agency_compare": "Need just one site? A single full report is ${single} from any scan result. Need to know the moment something changes? Daily monitoring covers up to 100 domains.",
    "agency_home_link": "Agencies: 10 full reports for $199",
    "pack_title": "Your agency pack",
    "pack_left": "{left} of {total} reports left.",
    "pack_keep_link": "Keep this page's link private: anyone who has it can use your reports. We also emailed it to you.",
    "pack_redeem_button": "Scan and open the full report (1 credit)",
    "pack_empty": "All reports in this pack have been used.",
    "pack_reports_title": "Your reports",
    "pack_open_report": "Open report",
})
TEXTS["ar"].update({
    "agency_title": "باقة الوكالات",
    "agency_meta": "{credits} تقارير كاملة لجاهزية TLS ما بعد الكم مقابل {price}$، دفعة واحدة وبلا انتهاء صلاحية. للوكالات ومزوّدي الخدمات والمدققين الذين يفحصون مواقع عملائهم.",
    "agency_lead": "تفحص جاهزية مواقع عملائك لما بعد الكم؟ احصل على {credits} تقارير كاملة مقابل {price}$: دفعة واحدة، بلا اشتراك، بلا انتهاء صلاحية.",
    "agency_items": [
        "{credits} تقارير كاملة، {each}$ للتقرير بدل {single}$",
        "استخدمها لأي نطاقات ومتى شئت: اكتب النطاق في صفحة باقتك الخاصة فيُفتح تقريره الكامل فوراً",
        "كل تقرير: جميع الملاحظات بأولوياتها، وخطوات الإصلاح لـ nginx وApache وCaddy وCloudflare، وتفاصيل الشهادة والمصافحة، وقابل للطباعة PDF لعميلك",
        "كل تقاريرك تبقى مدرجة في صفحة باقتك",
    ],
    "agency_buy_title": "{credits} تقارير كاملة",
    "agency_consent": "أوافق على تسليم كل تقرير فوراً عند استخدام رصيد، وأعلم أنني أفقد حق التراجع عن كل تقرير أُنشئ؛ ويمكن التراجع عن التقارير غير المستخدمة خلال 14 يوماً.",
    "agency_compare_title": "تقرير واحد، أم فحص مستمر؟",
    "agency_compare": "تحتاج موقعاً واحداً فقط؟ التقرير الكامل الواحد بـ {single}$ من صفحة أي نتيجة فحص. تريد أن تعرف فور تغيّر شيء؟ المراقبة اليومية تغطي حتى 100 نطاق.",
    "agency_home_link": "للوكالات: 10 تقارير كاملة مقابل 199$",
    "pack_title": "باقة الوكالة الخاصة بك",
    "pack_left": "بقي {left} من {total} تقارير.",
    "pack_keep_link": "احفظ رابط هذه الصفحة سرّاً: من يملكه يستطيع استخدام تقاريرك. أرسلناه لك بالبريد أيضاً.",
    "pack_redeem_button": "افحص وافتح التقرير الكامل (رصيد واحد)",
    "pack_empty": "استُخدمت كل تقارير هذه الباقة.",
    "pack_reports_title": "تقاريرك",
    "pack_open_report": "افتح التقرير",
})
TEXTS["de"].update({
    "agency_title": "Agenturpaket",
    "agency_meta": "{credits} vollständige Post-Quanten-TLS-Berichte für {price} $, einmalige Zahlung, ohne Ablaufdatum. Für Agenturen, IT-Dienstleister und Prüfer, die Kunden-Websites prüfen.",
    "agency_lead": "Sie prüfen die Post-Quanten-Bereitschaft Ihrer Kunden? {credits} vollständige Berichte für {price} $: einmalige Zahlung, kein Abonnement, kein Ablaufdatum.",
    "agency_items": [
        "{credits} vollständige Berichte, {each} $ pro Bericht statt {single} $",
        "Für beliebige Domains, wann Sie wollen: Domain auf Ihrer privaten Paketseite eingeben, der vollständige Bericht öffnet sich sofort",
        "Jeder Bericht: alle Befunde mit Priorität, Schritte für nginx, Apache, Caddy und Cloudflare, Zertifikats- und Handshake-Details, als PDF für Ihren Kunden druckbar",
        "Alle Berichte bleiben auf Ihrer Paketseite aufgelistet",
    ],
    "agency_buy_title": "{credits} vollständige Berichte",
    "agency_consent": "Ich stimme zu, dass jeder Bericht bei Nutzung eines Guthabens sofort bereitgestellt wird, und nehme zur Kenntnis, dass ich für jeden bereits erstellten Bericht mein Rücktrittsrecht verliere; vom Kauf nicht genutzter Berichte kann ich binnen 14 Tagen zurücktreten.",
    "agency_compare_title": "Ein Bericht oder laufende Prüfung?",
    "agency_compare": "Nur eine Website? Ein einzelner vollständiger Bericht kostet {single} $ auf jeder Ergebnisseite. Sie wollen sofort wissen, wenn sich etwas ändert? Die tägliche Überwachung deckt bis zu 100 Domains ab.",
    "agency_home_link": "Für Agenturen: 10 vollständige Berichte für 199 $",
    "pack_title": "Ihr Agenturpaket",
    "pack_left": "{left} von {total} Berichten übrig.",
    "pack_keep_link": "Halten Sie den Link dieser Seite privat: Wer ihn hat, kann Ihre Berichte nutzen. Wir haben ihn Ihnen auch per E-Mail geschickt.",
    "pack_redeem_button": "Prüfen und vollständigen Bericht öffnen (1 Guthaben)",
    "pack_empty": "Alle Berichte dieses Pakets wurden genutzt.",
    "pack_reports_title": "Ihre Berichte",
    "pack_open_report": "Bericht öffnen",
})


# ترتيب الدول
TEXTS["en"].update({
    "countries_title": "Post-quantum TLS by country",
    "countries_lead": "Which countries' top websites already protect visitors with post-quantum key exchange? {sites} sites with a country domain from the Tranco top 10,000, {countries} countries, week {week}. Updated every Monday.",
    "countries_col_country": "Country", "countries_col_ready": "Ready", "countries_col_sites": "Sites", "countries_col_change": "vs last week (pp)",
    "countries_caveat": "Country = the country-code domain (.de, .fr, ...), not where the server or company is. Domains such as .io, .ai, .tv, .co and .me are excluded because they are sold worldwide. Countries need at least {min} measured sites to be ranked.",
    "country_title": "{name}: post-quantum TLS readiness",
    "country_lead": "{pct}% of {name}'s top websites ({measured} measured) negotiate post-quantum key exchange: rank {rank} of {total} countries in week {week}.",
    "country_share": "{name} ranks #{rank} of {total} countries for post-quantum TLS: {pct}% of its top sites are ready.",
    "country_ready": "Ready (post-quantum key exchange)", "country_not_ready": "Not ready yet (classical key exchange)", "country_unsure": "Undetermined (probe blocked)",
    "countries_link": "Ranking by country",
})
TEXTS["ar"].update({
    "countries_title": "TLS ما بعد الكمومي حسب الدولة",
    "countries_lead": "مواقع أي الدول تحمي زوارها بتبادل مفاتيح ما بعد كمومي؟ {sites} موقعاً بامتداد دولة من أكبر 10,000 في Tranco، {countries} دولة، الأسبوع {week}. يُحدَّث كل اثنين.",
    "countries_col_country": "الدولة", "countries_col_ready": "جاهز", "countries_col_sites": "المواقع", "countries_col_change": "عن الأسبوع الماضي (نقطة)",
    "countries_caveat": "الدولة = امتداد النطاق (.de و.fr...)، لا مكان الخادم أو الشركة. امتدادات مثل .io و.ai و.tv و.co و.me مستبعدة لأنها تُباع عالمياً. تحتاج الدولة {min} موقعاً مُقاساً على الأقل لتدخل الترتيب.",
    "country_title": "{name}: الجاهزية لـ TLS ما بعد الكمومي",
    "country_lead": "{pct}% من أكبر مواقع {name} ({measured} موقعاً مُقاساً) تتفق على تبادل مفاتيح ما بعد كمومي: المرتبة {rank} من {total} دولة في الأسبوع {week}.",
    "country_share": "{name} في المرتبة {rank} من {total} دولة في TLS ما بعد الكمومي: {pct}% من أكبر مواقعها جاهزة.",
    "country_ready": "جاهزة (تبادل مفاتيح ما بعد كمومي)", "country_not_ready": "غير جاهزة بعد (تبادل مفاتيح تقليدي)", "country_unsure": "غير محسومة (الفحص محجوب)",
    "countries_link": "الترتيب حسب الدولة",
})
TEXTS["de"].update({
    "countries_title": "Post-Quanten-TLS nach Ländern",
    "countries_lead": "Die Top-Websites welcher Länder schützen Besucher schon mit Post-Quanten-Schlüsselaustausch? {sites} Websites mit Länderdomain aus den Tranco-Top-10.000, {countries} Länder, Woche {week}. Jeden Montag aktualisiert.",
    "countries_col_country": "Land", "countries_col_ready": "Bereit", "countries_col_sites": "Websites", "countries_col_change": "zur Vorwoche (Pp.)",
    "countries_caveat": "Land = Länderdomain (.de, .fr, ...), nicht der Standort von Server oder Firma. Domains wie .io, .ai, .tv, .co und .me sind ausgenommen, weil sie weltweit verkauft werden. Ein Land braucht mindestens {min} gemessene Websites für die Rangliste.",
    "country_title": "{name}: Bereitschaft für Post-Quanten-TLS",
    "country_lead": "{pct} % der Top-Websites von {name} ({measured} gemessen) handeln Post-Quanten-Schlüsselaustausch aus: Platz {rank} von {total} Ländern in Woche {week}.",
    "country_share": "{name} liegt bei Post-Quanten-TLS auf Platz {rank} von {total} Ländern: {pct} % der Top-Websites sind bereit.",
    "country_ready": "Bereit (Post-Quanten-Schlüsselaustausch)", "country_not_ready": "Noch nicht bereit (klassischer Schlüsselaustausch)", "country_unsure": "Unklar (Prüfung blockiert)",
    "countries_link": "Rangliste nach Ländern",
})

# /adoption/hosting (2026-11-09): readiness by hosting network / CDN
TEXTS["en"].update({
    "hosting_title": "Which hosting providers and CDNs support post-quantum TLS?",
    "hosting_meta": "Share of the top 10,000 websites on each hosting network and CDN that negotiate X25519MLKEM768. Cloudflare, Akamai, AWS, Google, Hetzner, OVH and more, updated weekly.",
    "hosting_lead": "We group {sites} measured websites from the Tranco top 10,000 by the network that answers their HTTPS ({period}), and count how many negotiate the hybrid post-quantum key exchange X25519MLKEM768.",
    "hosting_why_title": "Why the gap is so large",
    "hosting_why": "On CDNs and edge networks (Cloudflare, Akamai, Fastly, Google's front ends) the provider terminates TLS and turned post-quantum key exchange on for everyone. On cloud servers and classic hosting (for example EC2 instances, Hetzner, OVH, DigitalOcean) each customer's own server software decides: Ubuntu 22.04 and 24.04 still ship OpenSSL 3.0, which cannot negotiate ML-KEM. So a low share on a hosting network usually reflects its customers' operating systems, not a choice by the provider.",
    "hosting_fix": "Running your own server? Check it in one click, then follow the guide for nginx or for Apache, Caddy and HAProxy.",
    "hosting_col_net": "Network", "hosting_col_sites": "Ready / sites", "hosting_col_ready": "Post-quantum", "hosting_col_pct": "Share",
    "hosting_caveat": "Network = the autonomous system (AS) that answered the site's IP address; a site behind a CDN counts for the CDN. Only networks with at least {min} measured sites are listed.",
    "hosting_faq_q": "Which hosting providers support post-quantum TLS?",
    "hosting_faq_a": "As of {period}, the networks with the highest share of post-quantum ready sites among the Tranco top 10,000 were {top}. The lowest were {bottom}.",
    "hosting_link": "Readiness by hosting provider",
})
TEXTS["ar"].update({
    "hosting_title": "أي شركات الاستضافة وشبكات CDN تدعم TLS المقاوم للحوسبة الكمومية؟",
    "hosting_meta": "نسبة المواقع ضمن أكبر 10,000 موقع على كل شبكة استضافة وCDN التي تتفق على X25519MLKEM768: Cloudflare وAkamai وAWS وGoogle وHetzner وOVH وغيرها، أسبوعياً.",
    "hosting_lead": "نجمع {sites} موقعاً مقيساً من أكبر 10,000 موقع (Tranco) حسب الشبكة التي تجيب على اتصال HTTPS ({period})، ونحسب كم منها يتفق على تبادل المفاتيح الهجين X25519MLKEM768.",
    "hosting_why_title": "لماذا الفرق كبير إلى هذا الحد",
    "hosting_why": "في شبكات CDN والشبكات الطرفية (Cloudflare وAkamai وFastly وواجهات Google) يُنهي المزوّد اتصال TLS بنفسه وقد فعّل تبادل المفاتيح لما بعد الكم للجميع. أما على الخوادم السحابية والاستضافة التقليدية (مثل خوادم EC2 وHetzner وOVH وDigitalOcean) فبرنامج خادم كل عميل هو الذي يقرر: Ubuntu 22.04 و24.04 ما زالا يأتيان بـ OpenSSL 3.0 الذي لا يدعم ML-KEM. لذلك تعكس النسبة المنخفضة على شبكة استضافة غالباً أنظمة عملائها، لا قراراً من المزوّد.",
    "hosting_fix": "تدير خادمك بنفسك؟ افحصه بنقرة، ثم اتبع دليل nginx أو دليل Apache وCaddy وHAProxy.",
    "hosting_col_net": "الشبكة", "hosting_col_sites": "جاهز / المواقع", "hosting_col_ready": "ما بعد الكم", "hosting_col_pct": "النسبة",
    "hosting_caveat": "الشبكة = النظام المستقل (AS) الذي أجاب على عنوان IP للموقع؛ الموقع خلف CDN يُحسب للـ CDN. نعرض فقط الشبكات التي فيها {min} موقعاً مقيساً على الأقل.",
    "hosting_faq_q": "أي شركات الاستضافة تدعم TLS المقاوم للحوسبة الكمومية؟",
    "hosting_faq_a": "حتى {period}، كانت أعلى الشبكات نسبةً في المواقع الجاهزة ضمن أكبر 10,000 موقع: {top}. وأدناها: {bottom}.",
    "hosting_link": "الجاهزية حسب شركة الاستضافة",
})
TEXTS["de"].update({
    "hosting_title": "Welche Hoster und CDNs unterstützen Post-Quanten-TLS?",
    "hosting_meta": "Anteil der Top-10.000-Websites je Hoster und CDN, die X25519MLKEM768 aushandeln: Cloudflare, Akamai, AWS, Google, Hetzner, OVH und mehr, wöchentlich aktualisiert.",
    "hosting_lead": "Wir gruppieren {sites} gemessene Websites aus den Tranco-Top-10.000 nach dem Netz, das ihr HTTPS beantwortet ({period}), und zählen, wie viele den hybriden Post-Quanten-Schlüsselaustausch X25519MLKEM768 aushandeln.",
    "hosting_why_title": "Warum der Unterschied so groß ist",
    "hosting_why": "Bei CDNs und Edge-Netzen (Cloudflare, Akamai, Fastly, Google-Frontends) terminiert der Anbieter TLS selbst und hat Post-Quanten-Schlüsselaustausch für alle aktiviert. Bei Cloud-Servern und klassischem Hosting (z. B. EC2, Hetzner, OVH, DigitalOcean) entscheidet die Serversoftware jedes Kunden: Ubuntu 22.04 und 24.04 liefern noch OpenSSL 3.0, das kein ML-KEM kann. Ein niedriger Anteil spiegelt daher meist die Betriebssysteme der Kunden wider, nicht eine Entscheidung des Hosters.",
    "hosting_fix": "Eigener Server? Mit einem Klick prüfen, dann der Anleitung für nginx oder für Apache, Caddy und HAProxy folgen.",
    "hosting_col_net": "Netz", "hosting_col_sites": "Bereit / Websites", "hosting_col_ready": "Post-Quanten", "hosting_col_pct": "Anteil",
    "hosting_caveat": "Netz = das autonome System (AS), das auf die IP-Adresse der Website antwortet; eine Website hinter einem CDN zählt für das CDN. Aufgeführt sind nur Netze mit mindestens {min} gemessenen Websites.",
    "hosting_faq_q": "Welche Hoster unterstützen Post-Quanten-TLS?",
    "hosting_faq_a": "Stand {period} hatten unter den Tranco-Top-10.000 diese Netze den höchsten Anteil bereiter Websites: {top}. Den niedrigsten: {bottom}.",
    "hosting_link": "Bereitschaft nach Hoster",
})


# كشف النطاقات الفرعية (صفحة النتيجة): أعداد علناً، والقائمة بعد تأكيد بريد على النطاق نفسه
TEXTS["en"].update({
    "disc_title": "Your other subdomains",
    "disc_sub": "{base} is rarely the only host. Public certificate logs list its subdomains; we check each one that responds for post-quantum key exchange. Only the numbers appear here; the names are never shown publicly.",
    "disc_button": "Check all subdomains",
    "disc_running": "Checking subdomains from public certificate logs. This usually takes 10–40 seconds…",
    "disc_result": "We found {responding} subdomains of {base} that respond on port 443: {not_pq} without post-quantum key exchange, {pq} with it, {unknown} undetermined.",
    "disc_none": "Public certificate logs list no other responding subdomains of {base}.",
    "disc_failed": "The certificate logs could not be reached just now. Please try again in a few minutes.",
    "disc_limited": "Too many subdomain checks from your connection today. Please try again tomorrow.",
    "disc_busy": "Several subdomain checks are running right now. Please try again in a minute.",
    "disc_list_title": "Get the full list",
    "disc_list_sub": "Enter an email address at {base}. We send the list only to an address at the domain itself, so that only the organisation can see its subdomain names.",
    "disc_email_label": "Work email at {base}",
    "disc_list_button": "Email me the list",
    "disc_consent": "I agree that Quantum Aether may email me this list and one follow-up about monitoring. My address is deleted after 7 days if I do not confirm.",
    "disc_states": {
        "check_inbox": "Check your inbox: we sent a link to the full list for {base}.",
        "consent_missing": "Please tick the consent box so we may email you.",
        "bad_email": "That email address does not look right. Please go back and check it.",
        "wrong_domain": "The list is only sent to an address at {base} (for example you@{base}).",
        "rate_limited": "Too many requests from your connection today. Please try again tomorrow.",
        "unavailable": "Email is temporarily unavailable. Please try again later.",
        "not_ready": "The subdomain check for {base} is not finished or has expired. Please run it again from the result page.",
        "confirm_prompt": "Open the full subdomain list for {base}?",
    },
    "disc_open_button": "Show the list",
    "disc_page_title": "Subdomains of {base}",
    "disc_page_note": "Checked {when} from one public vantage point, port 443, first IPv4 address. Names come from public certificate-transparency logs; hosts that did not resolve or respond are not listed. A point-in-time observation, not a security guarantee.",
    "disc_col_host": "Host", "disc_col_status": "Post-quantum key exchange", "disc_col_group": "Group",
    "disc_status": {"pq": "Yes", "not_pq": "No", "unknown": "Undetermined"},
    "disc_cta": "Want these checked every day, with an email when one changes? Monitoring covers up to 100 domains.",
})
TEXTS["ar"].update({
    "disc_title": "نطاقاتك الفرعية الأخرى",
    "disc_sub": "نادراً ما يكون {base} الخادم الوحيد. سجلات الشهادات العامة تذكر نطاقاته الفرعية، ونفحص كل نطاق منها يرد على الاتصال لنعرف هل يدعم تبادل المفاتيح ما بعد الكمومي. تظهر هنا الأعداد فقط، ولا تُعرض الأسماء علناً أبداً.",
    "disc_button": "افحص كل النطاقات الفرعية",
    "disc_running": "نفحص النطاقات الفرعية من سجلات الشهادات العامة. يستغرق ذلك عادةً من 10 إلى 40 ثانية…",
    "disc_result": "وجدنا {responding} نطاقاً فرعياً لـ {base} يرد على المنفذ 443: {not_pq} بلا تبادل مفاتيح ما بعد كمومي، و{pq} يدعمه، و{unknown} غير محدد.",
    "disc_none": "لا تذكر سجلات الشهادات العامة نطاقات فرعية أخرى لـ {base} ترد على الاتصال.",
    "disc_failed": "تعذّر الوصول إلى سجلات الشهادات الآن. حاول بعد دقائق.",
    "disc_limited": "فحوصات كثيرة للنطاقات الفرعية من اتصالك اليوم. حاول غداً.",
    "disc_busy": "تجري عدة فحوصات الآن. حاول بعد دقيقة.",
    "disc_list_title": "احصل على القائمة الكاملة",
    "disc_list_sub": "أدخل بريداً على {base}. نرسل القائمة فقط إلى عنوان على النطاق نفسه، حتى لا يرى أسماء النطاقات الفرعية إلا أصحابها.",
    "disc_email_label": "بريد العمل على {base}",
    "disc_list_button": "أرسل لي القائمة",
    "disc_consent": "أوافق على أن يرسل لي الأثير الكمومي هذه القائمة ورسالة متابعة واحدة عن المراقبة. يُحذف بريدي بعد 7 أيام إن لم أؤكد.",
    "disc_states": {
        "check_inbox": "افحص بريدك: أرسلنا رابط القائمة الكاملة لـ {base}.",
        "consent_missing": "ضع علامة على مربع الموافقة من فضلك حتى نستطيع مراسلتك.",
        "bad_email": "يبدو أن عنوان البريد غير صحيح. ارجع وتحقق منه.",
        "wrong_domain": "نرسل القائمة فقط إلى عنوان على {base} (مثل you@{base}).",
        "rate_limited": "طلبات كثيرة من اتصالك اليوم. حاول غداً.",
        "unavailable": "البريد غير متاح مؤقتاً. حاول لاحقاً.",
        "not_ready": "فحص النطاقات الفرعية لـ {base} لم يكتمل أو انتهت صلاحيته. أعد تشغيله من صفحة النتيجة.",
        "confirm_prompt": "هل تريد فتح القائمة الكاملة للنطاقات الفرعية لـ {base}؟",
    },
    "disc_open_button": "اعرض القائمة",
    "disc_page_title": "النطاقات الفرعية لـ {base}",
    "disc_page_note": "فُحصت في {when} من نقطة قياس عامة واحدة، المنفذ 443، أول عنوان IPv4. الأسماء من سجلات شفافية الشهادات العامة، ولا نذكر ما لم يُحل اسمه أو لم يرد. ملاحظة في وقت محدد، لا ضمان أمني.",
    "disc_col_host": "النطاق", "disc_col_status": "تبادل مفاتيح ما بعد كمومي", "disc_col_group": "المجموعة",
    "disc_status": {"pq": "نعم", "not_pq": "لا", "unknown": "غير محدد"},
    "disc_cta": "تريد فحصها يومياً مع رسالة عند أي تغيير؟ المراقبة تغطي حتى 100 نطاق.",
})
TEXTS["de"].update({
    "disc_title": "Ihre weiteren Subdomains",
    "disc_sub": "{base} ist selten der einzige Host. Öffentliche Zertifikatslogs nennen seine Subdomains; wir prüfen jede erreichbare auf Post-Quanten-Schlüsselaustausch. Hier erscheinen nur die Zahlen; die Namen werden nie öffentlich gezeigt.",
    "disc_button": "Alle Subdomains prüfen",
    "disc_running": "Wir prüfen Subdomains aus öffentlichen Zertifikatslogs. Das dauert meist 10–40 Sekunden…",
    "disc_result": "Wir haben {responding} Subdomains von {base} gefunden, die auf Port 443 antworten: {not_pq} ohne Post-Quanten-Schlüsselaustausch, {pq} mit, {unknown} unbestimmt.",
    "disc_none": "Öffentliche Zertifikatslogs nennen keine weiteren erreichbaren Subdomains von {base}.",
    "disc_failed": "Die Zertifikatslogs sind gerade nicht erreichbar. Bitte in einigen Minuten erneut versuchen.",
    "disc_limited": "Heute zu viele Subdomain-Prüfungen von Ihrer Verbindung. Bitte morgen erneut versuchen.",
    "disc_busy": "Gerade laufen mehrere Prüfungen. Bitte in einer Minute erneut versuchen.",
    "disc_list_title": "Vollständige Liste erhalten",
    "disc_list_sub": "Geben Sie eine E-Mail-Adresse unter {base} an. Wir senden die Liste nur an eine Adresse der Domain selbst, damit nur die Organisation ihre Subdomain-Namen sieht.",
    "disc_email_label": "Geschäftliche E-Mail unter {base}",
    "disc_list_button": "Liste per E-Mail senden",
    "disc_consent": "Ich bin einverstanden, dass Quantum Aether mir diese Liste und eine Folge-E-Mail zur Überwachung sendet. Ohne Bestätigung wird meine Adresse nach 7 Tagen gelöscht.",
    "disc_states": {
        "check_inbox": "Bitte Posteingang prüfen: Wir haben einen Link zur vollständigen Liste für {base} gesendet.",
        "consent_missing": "Bitte setzen Sie das Häkchen bei der Einwilligung.",
        "bad_email": "Diese E-Mail-Adresse scheint nicht zu stimmen. Bitte prüfen.",
        "wrong_domain": "Die Liste wird nur an eine Adresse unter {base} gesendet (z. B. sie@{base}).",
        "rate_limited": "Heute zu viele Anfragen von Ihrer Verbindung. Bitte morgen erneut versuchen.",
        "unavailable": "E-Mail ist vorübergehend nicht verfügbar. Bitte später erneut versuchen.",
        "not_ready": "Die Subdomain-Prüfung für {base} ist nicht fertig oder abgelaufen. Bitte auf der Ergebnisseite erneut starten.",
        "confirm_prompt": "Vollständige Subdomain-Liste für {base} öffnen?",
    },
    "disc_open_button": "Liste anzeigen",
    "disc_page_title": "Subdomains von {base}",
    "disc_page_note": "Geprüft am {when} von einem öffentlichen Messpunkt, Port 443, erste IPv4-Adresse. Namen aus öffentlichen Certificate-Transparency-Logs; nicht auflösbare oder nicht antwortende Hosts sind nicht aufgeführt. Momentaufnahme, keine Sicherheitsgarantie.",
    "disc_col_host": "Host", "disc_col_status": "Post-Quanten-Schlüsselaustausch", "disc_col_group": "Gruppe",
    "disc_status": {"pq": "Ja", "not_pq": "Nein", "unknown": "Unbestimmt"},
    "disc_cta": "Täglich prüfen lassen, mit E-Mail bei Änderungen? Die Überwachung umfasst bis zu 100 Domains.",
})


# مولّد إعدادات TLS ما بعد الكمومي (/tools/pq-tls-config)
TEXTS["en"].update({
    "cfg_title": "Post-quantum TLS configuration generator",
    "cfg_meta": "Copy-ready settings to enable the hybrid X25519MLKEM768 key exchange on nginx, Apache, HAProxy, Caddy, Go, Node.js, Java, Python, AWS load balancers, CloudFront and Cloudflare, with the version each one needs.",
    "cfg_server_title": "Enable post-quantum TLS on {name} (X25519MLKEM768)",
    "cfg_server_meta": "Copy-ready {name} settings for the hybrid X25519MLKEM768 key exchange, the version it needs, and how to verify it.",
    "cfg_intro": "Choose your server or platform. You get the version check, the configuration, and how to verify that browsers now negotiate X25519MLKEM768.",
    "cfg_pick": "Servers and platforms",
    "cfg_which": "Which version do you run?",
    "cfg_show": "Show settings",
    "cfg_not_possible": "This version cannot negotiate post-quantum key exchange. A configuration change alone will not help; see the options below.",
    "cfg_full_guide": "Full guide with background and pitfalls",
    "cfg_after_title": "After the change",
    "cfg_after": "Run a free check of your domain below. Grade A means TLS 1.3 with hybrid post-quantum key exchange. The result page can also check every subdomain listed in public certificate logs, so you can see which hosts still need the same change.",
})
TEXTS["ar"].update({
    "cfg_title": "مولّد إعدادات TLS لما بعد الكم",
    "cfg_meta": "إعدادات جاهزة للنسخ لتفعيل تبادل المفاتيح الهجين X25519MLKEM768 على nginx وApache وHAProxy وCaddy وGo وNode.js وJava وPython وموازنات حمل AWS وCloudFront وCloudflare، مع الإصدار الذي يحتاجه كل منها.",
    "cfg_server_title": "فعّل TLS ما بعد الكمومي على {name}: X25519MLKEM768",
    "cfg_server_meta": "إعدادات {name} جاهزة للنسخ لتبادل المفاتيح الهجين X25519MLKEM768، والإصدار المطلوب، وطريقة التحقق.",
    "cfg_intro": "اختر خادمك أو منصتك. تحصل على طريقة فحص الإصدار، والإعدادات، وكيف تتأكد أن المتصفحات صارت تتفاوض على X25519MLKEM768.",
    "cfg_pick": "الخوادم والمنصات",
    "cfg_which": "أي إصدار تستخدم؟",
    "cfg_show": "اعرض الإعدادات",
    "cfg_not_possible": "هذا الإصدار لا يستطيع التفاوض على تبادل مفاتيح ما بعد كمومي. تغيير الإعدادات وحده لن يفيد؛ راجع الخيارات أدناه.",
    "cfg_full_guide": "الدليل الكامل مع الخلفية والأخطاء الشائعة",
    "cfg_after_title": "بعد التغيير",
    "cfg_after": "افحص نطاقك مجاناً أدناه. الدرجة A تعني TLS 1.3 مع تبادل مفاتيح هجين ما بعد كمومي. ويمكنك من صفحة النتيجة فحص كل النطاقات الفرعية المذكورة في سجلات الشهادات العامة، لتعرف أي خوادم ما زالت تحتاج التغيير نفسه.",
})
TEXTS["de"].update({
    "cfg_title": "Post-Quanten-TLS-Konfigurationsgenerator",
    "cfg_meta": "Kopierfertige Einstellungen für den hybriden Schlüsselaustausch X25519MLKEM768 auf nginx, Apache, HAProxy, Caddy, Go, Node.js, Java, Python, AWS Load Balancern, CloudFront und Cloudflare, mit der jeweils nötigen Version.",
    "cfg_server_title": "Post-Quanten-TLS auf {name} aktivieren (X25519MLKEM768)",
    "cfg_server_meta": "Kopierfertige {name}-Einstellungen für den hybriden Schlüsselaustausch X25519MLKEM768, die nötige Version und die Prüfung.",
    "cfg_intro": "Wählen Sie Ihren Server oder Ihre Plattform. Sie erhalten die Versionsprüfung, die Konfiguration und die Kontrolle, ob Browser jetzt X25519MLKEM768 aushandeln.",
    "cfg_pick": "Server und Plattformen",
    "cfg_which": "Welche Version nutzen Sie?",
    "cfg_show": "Einstellungen anzeigen",
    "cfg_not_possible": "Diese Version kann keinen Post-Quanten-Schlüsselaustausch aushandeln. Eine Konfigurationsänderung allein hilft nicht; siehe die Optionen unten.",
    "cfg_full_guide": "Vollständige Anleitung mit Hintergrund und Fallstricken (Englisch)",
    "cfg_after_title": "Nach der Änderung",
    "cfg_after": "Prüfen Sie Ihre Domain unten kostenlos. Note A bedeutet TLS 1.3 mit hybridem Post-Quanten-Schlüsselaustausch. Auf der Ergebnisseite können Sie zudem alle Subdomains aus öffentlichen Zertifikatslogs prüfen und sehen, welche Hosts dieselbe Änderung noch brauchen.",
})
