"""PQ-TLS Index: /index (en/ar/de), /index.csv, /index.json and its correction form (2026-11-21).

Monthly, citable snapshot of post-quantum key exchange (X25519MLKEM768) on the main public website of a fixed panel of
banks, central banks, regulators, telecoms and government bodies in the GCC, Egypt, the Maghreb and DACH.
Self-contained like dach_hosting.py: texts live here, the panel is data/pq_index_orgs.csv, results are
data/pq_index_<edition>.json (written by the index scan, TLS handshakes on port 443 only). No certificate details are
published. Downloads carry the standard per-download canary rows (institution name left blank). Correction requests
reuse the dach_corrections table (provider "[PQ-INDEX] <host>"). Nothing here sends e-mail or contacts anyone.
"""
import csv
import datetime as dt
import glob
import io
import json
import os
from collections import OrderedDict

from flask import Response, abort, redirect, render_template, request, url_for

import dach_hosting

ENDPOINT = "site.pq_index_page"
CORRECTION_ENDPOINT = "site.pq_index_correction"
REGIONS = ("GCC", "Egypt", "Maghreb", "DACH")
REFERENCE = "EU institutions"
SECTORS = ("banking", "central-bank", "regulator", "telecom", "government")
CDN_PREFIXES = ("Cloudflare", "Amazon", "Akamai", "Incapsula", "Imperva", "Sucuri", "Microsoft", "Fastly", "Google")
CSV_COLUMNS = ("edition", "org_id", "country_code", "region", "sector", "role", "name", "host", "status", "group",
               "tls_version", "network", "asn", "scanned_at_utc")

COUNTRY = {
    "SA": ("Saudi Arabia", "السعودية", "Saudi-Arabien"), "AE": ("United Arab Emirates", "الإمارات", "Vereinigte Arabische Emirate"),
    "QA": ("Qatar", "قطر", "Katar"), "KW": ("Kuwait", "الكويت", "Kuwait"), "BH": ("Bahrain", "البحرين", "Bahrain"),
    "OM": ("Oman", "عُمان", "Oman"), "EG": ("Egypt", "مصر", "Ägypten"), "MA": ("Morocco", "المغرب", "Marokko"),
    "TN": ("Tunisia", "تونس", "Tunesien"), "DZ": ("Algeria", "الجزائر", "Algerien"), "DE": ("Germany", "ألمانيا", "Deutschland"),
    "AT": ("Austria", "النمسا", "Österreich"), "CH": ("Switzerland", "سويسرا", "Schweiz"),
    "EU": ("European Union", "الاتحاد الأوروبي", "Europäische Union"),
}
LANG_IDX = {"en": 0, "ar": 1, "de": 2}

T = {
"en": {
    "title": "PQ-TLS Index: post-quantum encryption at banks, telecoms and governments",
    "meta": "Monthly open index: {pq} of {n} measured banks, telecoms and government bodies in the GCC, Egypt, the Maghreb and "
            "DACH ({pct}%) negotiate post-quantum key exchange (X25519MLKEM768). Edition {edition}, CC BY 4.0.",
    "kicker": "Monthly index · edition {edition}",
    "lead": "Which banks, central banks, regulators, telecoms and government portals already protect their public website "
            "with the post-quantum hybrid key exchange X25519MLKEM768 that Chrome, Firefox, Safari and Edge offer by default? "
            "We test the main public site of {total} institutions in the GCC, Egypt, the Maghreb and Germany, Austria and Switzerland.",
    "scanned": "Scanned {start}–{end} UTC · scanner version {version} · vantage point {vantage}",
    "k_overall": "post-quantum ({pq} of {n} measured)", "k_regions": "DACH · {gcc}% GCC", "k_tls12": "sites answer with TLS 1.2 only",
    "k_cdn": "of post-quantum results come from CDN / cloud defaults", "k_nm": "not measured from our vantage point",
    "cdn_title": "Read this first: the CDN effect",
    "cdn": "{cdn_pct}% of the post-quantum results ({cdn} of {pq}) come from CDN and cloud edges (Cloudflare, AWS, Akamai, "
           "Imperva and others) that enable hybrid key exchange by default. A post-quantum result therefore often reflects "
           "the provider's default, not the institution's own migration, and the connection from the CDN to the "
           "institution's servers is not visible from outside. The network column below shows this for every row.",
    "regions": "By region", "sectors": "By sector", "countries": "By country", "reference": "EU reference group (not in the headline figure)",
    "col_group": "Group", "col_pq": "Post-quantum", "col_classical": "Classical", "col_nm": "Not measured",
    "col_inst": "Institution", "col_country": "Country", "col_sector": "Sector", "col_host": "Host tested",
    "col_result": "Result", "col_tls": "TLS", "col_network": "Network",
    "pct_fmt": "{pq} / {n} ({pct}%)",
    "status": {"pq_hybrid": "post-quantum", "classical": "classical", "not_measured": "not measured"},
    "region": {"GCC": "GCC", "Egypt": "Egypt", "Maghreb": "Maghreb", "DACH": "DACH", "EU institutions": "EU institutions"},
    "sector": {"banking": "Banks", "central-bank": "Central banks", "regulator": "Regulators", "telecom": "Telecoms", "government": "Government"},
    "rows_title": "All institutions", "rows_intro": "Sorted by region, country and name (not by result). "
                  "“Not measured” means no complete TLS measurement from our vantage point; it is never counted as classical.",
    "comp_title": "Why compliance teams track this (informational, not legal advice)",
    "comp": [("EU NIS2, Art. 21(2)(h)", "Policies on cryptography and encryption; the EU PQC roadmap (June 2025) asks member states to start the transition by the end of 2026."),
             ("EU DORA + RTS (EU) 2024/1774, Art. 6–7", "Encryption and cryptographic controls for financial entities that follow developments in cryptanalysis, including quantum."),
             ("Germany: BSI TR-02102", "BSI recommends hybrid post-quantum key exchange."),
             ("Saudi Arabia: SAMA circular 482021280, NCA ECC-2:2024", "Cryptographic inventory for financial institutions by 31 December 2026; national cryptography controls."),
             ("UAE, Qatar, Bahrain, Kuwait, Oman, Egypt, Maghreb", "Central-bank and national cyber-agency frameworks require cryptography that follows current standards.")],
    "comp_note": "A public homepage is one host only; online banking, apps, APIs and internal systems are not covered.",
    "method_title": "Methodology and panel",
    "method": ["What we measure: for each institution we test one public HTTPS host (normally www.) on port 443 and record the key-exchange group the server selects when a browser-like TLS 1.3 client offers X25519MLKEM768 together with classical groups. Post-quantum = an ML-KEM hybrid group was selected. Classical = a classical group or TLS 1.2 only.",
               "How: the same scanner as the free check and the weekly /adoption tracker (one DNS lookup, two to three TLS handshakes per host, first IPv4 address, no HTTP request, no other ports, at most two hosts in parallel). Hosts that fail are retried once; if they still fail they are listed as not measured and left out of the percentages.",
               "Panel ({total} institutions, fixed for a year): per country the central bank, the 4–6 largest banks by total assets, the financial and telecom regulators, all licensed mobile operators and the incumbent, the national e-government portal, the national cyber authority and the ministry of finance; plus six EU bodies as a reference group. The list is published as CSV.",
               "Limits: one host per institution, one vantage point (London), point in time. A classical result is not a vulnerability today; it marks exposure to “harvest now, decrypt later”. Sites that block traffic from abroad show as not measured.",
               "Schedule: a new edition is scanned on the first Monday of each month. Published editions are not edited; corrections are logged as new versions."],
    "data_title": "Data, citation and licence",
    "data": "Download the edition as CSV or JSON (CC BY 4.0). The panel list is available as CSV.",
    "cite": "Quantum Aether (2026). PQ-TLS Index, edition {edition}. {url} (CC BY 4.0)",
    "changes": "Change log: {edition} is the first edition, so there is no month-over-month comparison yet.",
    "correction_title": "Corrections and right of reply",
    "correction_intro": "Does an institution use a different main website, or would it like a short statement next to its row? "
                        "Send a correction: we re-test within five working days with the same TLS-only method and log any change.",
    "f_inst": "Institution", "f_name": "Your name", "f_email": "E-mail", "f_role": "Organisation / role (optional)",
    "f_domains": "Host to test instead (optional)", "f_message": "Correction or statement", "f_rescan": "Please re-test",
    "f_submit": "Send correction", "f_privacy": "We store your request only to handle it.",
    "f_alt": "Or by e-mail:", "sent": "Thank you. Your request has been recorded.",
    "err": {"invalid": "Please check the fields and try again.", "rate_limited": "Too many requests today. Please try again tomorrow."},
    "signature": "Quantum Aether Team",
    "cta": "Check your own domain for free",
},
"ar": {
    "title": "مؤشر PQ-TLS: التشفير المقاوم للحوسبة الكمومية في البنوك والاتصالات والجهات الحكومية",
    "meta": "مؤشر شهري مفتوح: {pq} من {n} بنكاً وشركة اتصالات وجهة حكومية أمكن قياسها في الخليج ومصر والمغرب العربي وDACH "
            "({pct}%) تعتمد تبادل مفاتيح مقاوماً للكم (X25519MLKEM768). الإصدار {edition}، رخصة CC BY 4.0.",
    "kicker": "مؤشر شهري · الإصدار {edition}",
    "lead": "أيّ البنوك والبنوك المركزية والجهات الرقابية وشركات الاتصالات والبوابات الحكومية تحمي موقعها العام اليوم بتبادل المفاتيح الهجين "
            "المقاوم للحوسبة الكمومية X25519MLKEM768 الذي تعرضه متصفحات Chrome وFirefox وSafari وEdge افتراضياً؟ "
            "نفحص الموقع الرئيسي لـ{total} مؤسسة في الخليج ومصر والمغرب العربي وألمانيا والنمسا وسويسرا.",
    "scanned": "تاريخ الفحص {start}–{end} بتوقيت UTC · إصدار الماسح {version} · نقطة القياس {vantage}",
    "k_overall": "مقاوم للكم ({pq} من {n} أمكن قياسها)", "k_regions": "DACH · ‏{gcc}% الخليج", "k_tls12": "موقعاً يجيب بـTLS 1.2 فقط",
    "k_cdn": "من النتائج المقاومة للكم مصدرها إعدادات CDN أو السحابة الافتراضية", "k_nm": "لم يُقَس من نقطة القياس",
    "cdn_title": "اقرأ هذا أولاً: أثر شبكات توصيل المحتوى (CDN)",
    "cdn": "{cdn_pct}% من النتائج المقاومة للكم ({cdn} من {pq}) مصدرها شبكات CDN والسحابة (Cloudflare وAWS وAkamai وImperva وغيرها) "
           "التي تفعّل التبادل الهجين افتراضياً. لذلك تعكس النتيجة المقاومة للكم غالباً إعداد المزوّد الافتراضي لا ترحيل المؤسسة نفسها، "
           "ولا يمكن من الخارج رؤية الاتصال بين الـCDN وخوادم المؤسسة. عمود الشبكة أدناه يوضح ذلك لكل صف.",
    "regions": "حسب المنطقة", "sectors": "حسب القطاع", "countries": "حسب الدولة", "reference": "المجموعة المرجعية للاتحاد الأوروبي (خارج الرقم الرئيسي)",
    "col_group": "المجموعة", "col_pq": "مقاوم للكم", "col_classical": "تقليدي", "col_nm": "لم يُقَس",
    "col_inst": "المؤسسة", "col_country": "الدولة", "col_sector": "القطاع", "col_host": "المضيف المفحوص",
    "col_result": "النتيجة", "col_tls": "TLS", "col_network": "الشبكة",
    "pct_fmt": "{pq} / {n} ({pct}%)",
    "status": {"pq_hybrid": "مقاوم للكم", "classical": "تقليدي", "not_measured": "لم يُقَس"},
    "region": {"GCC": "الخليج", "Egypt": "مصر", "Maghreb": "المغرب العربي", "DACH": "ألمانيا والنمسا وسويسرا", "EU institutions": "مؤسسات الاتحاد الأوروبي"},
    "sector": {"banking": "البنوك", "central-bank": "البنوك المركزية", "regulator": "الجهات الرقابية", "telecom": "الاتصالات", "government": "الجهات الحكومية"},
    "rows_title": "كل المؤسسات", "rows_intro": "مرتبة حسب المنطقة والدولة والاسم (لا حسب النتيجة). "
                  "«لم يُقَس» تعني أنه لم يكتمل قياس TLS من نقطة القياس، ولا تُحسب أبداً كتقليدي.",
    "comp_title": "لماذا يتابع مسؤولو الامتثال هذا المؤشر (للمعلومة، وليس استشارة قانونية)",
    "comp": [("تعميم ساما رقم 482021280 وضوابط NCA ECC-2:2024", "حصر أصول التشفير في المؤسسات المالية السعودية بنهاية 31 ديسمبر 2026، وضوابط التشفير الوطنية."),
             ("الإمارات وقطر والبحرين والكويت وعُمان ومصر والمغرب العربي", "أطر البنوك المركزية وهيئات الأمن السيبراني الوطنية تشترط تشفيراً يواكب المعايير الحالية."),
             ("الاتحاد الأوروبي NIS2، المادة 21(2)(h)", "سياسات التشفير؛ وخارطة الطريق الأوروبية (يونيو 2025) تطلب بدء الانتقال بنهاية 2026."),
             ("الاتحاد الأوروبي DORA واللائحة 2024/1774، المادتان 6–7", "ضوابط التشفير للمؤسسات المالية بما يواكب تطور تحليل الشفرات، ومنه الحوسبة الكمومية."),
             ("ألمانيا: BSI TR-02102", "يوصي BSI بتبادل المفاتيح الهجين المقاوم للكم.")],
    "comp_note": "الموقع الرئيسي مضيف واحد فقط؛ لا يشمل الفحص الخدمات المصرفية الإلكترونية ولا التطبيقات ولا الواجهات البرمجية ولا الأنظمة الداخلية.",
    "method_title": "المنهجية وقائمة المؤسسات",
    "method": ["ما نقيسه: لكل مؤسسة نفحص مضيف HTTPS عاماً واحداً (عادةً www.) على المنفذ 443، ونسجّل مجموعة تبادل المفاتيح التي يختارها الخادم حين يعرض عميل TLS 1.3 يشبه المتصفح X25519MLKEM768 مع المجموعات التقليدية. مقاوم للكم = اختار الخادم مجموعة هجينة من ML-KEM. تقليدي = مجموعة تقليدية أو TLS 1.2 فقط.",
               "كيف: الماسح نفسه المستخدم في الفحص المجاني والمتتبع الأسبوعي /adoption (استعلام DNS واحد ومصافحتا TLS أو ثلاث لكل مضيف، أول عنوان IPv4، دون أي طلب HTTP ودون منافذ أخرى، ومضيفان بالتوازي كحد أقصى). يُعاد فحص المضيف الفاشل مرة واحدة، وإن فشل يُدرج «لم يُقَس» ويُستبعد من النسب.",
               "القائمة ({total} مؤسسة، ثابتة لسنة): في كل دولة البنك المركزي، وأكبر 4–6 بنوك حسب إجمالي الأصول، والجهات الرقابية المالية والاتصالات، وكل مشغلي الهاتف المرخصين والمشغل التاريخي، والبوابة الحكومية الوطنية، والهيئة الوطنية للأمن السيبراني، ووزارة المالية؛ إضافة إلى ست هيئات أوروبية كمجموعة مرجعية. القائمة منشورة بصيغة CSV.",
               "الحدود: مضيف واحد لكل مؤسسة، ونقطة قياس واحدة (لندن)، ولحظة زمنية محددة. النتيجة التقليدية ليست ثغرة اليوم، لكنها تكشف التعرض لهجمات «اجمع الآن وفكّ لاحقاً». المواقع التي تحجب الزيارات من الخارج تظهر «لم يُقَس».",
               "الجدول: يُفحص إصدار جديد في أول اثنين من كل شهر. الإصدارات المنشورة لا تُعدَّل؛ التصحيحات تُسجَّل كنسخ جديدة."],
    "data_title": "البيانات والاستشهاد والترخيص",
    "data": "نزّل الإصدار بصيغة CSV أو JSON (رخصة CC BY 4.0). وقائمة المؤسسات متاحة بصيغة CSV.",
    "cite": "Quantum Aether (2026). PQ-TLS Index, edition {edition}. {url} (CC BY 4.0)",
    "changes": "سجل التغييرات: {edition} هو الإصدار الأول، فلا توجد مقارنة شهرية بعد.",
    "correction_title": "التصحيحات وحق الرد",
    "correction_intro": "هل تستخدم مؤسسة موقعاً رئيسياً آخر، أو تودّ إضافة بيان قصير بجانب صفها؟ أرسل تصحيحاً: نعيد الفحص خلال خمسة أيام عمل بالطريقة نفسها (TLS فقط) ونسجّل أي تغيير.",
    "f_inst": "المؤسسة", "f_name": "الاسم", "f_email": "البريد الإلكتروني", "f_role": "الجهة / المنصب (اختياري)",
    "f_domains": "مضيف يُفحص بدلاً منه (اختياري)", "f_message": "التصحيح أو البيان", "f_rescan": "يرجى إعادة الفحص",
    "f_submit": "إرسال التصحيح", "f_privacy": "نحفظ طلبك فقط لمعالجته.",
    "f_alt": "أو بالبريد:", "sent": "شكراً، تم تسجيل طلبك.",
    "err": {"invalid": "يرجى مراجعة الحقول والمحاولة مجدداً.", "rate_limited": "طلبات كثيرة اليوم، يرجى المحاولة غداً."},
    "signature": "فريق Quantum Aether",
    "cta": "افحص نطاقك مجاناً",
},
"de": {
    "title": "PQ-TLS-Index: Post-Quanten-Verschlüsselung bei Banken, Telcos und Behörden",
    "meta": "Monatlicher offener Index: {pq} von {n} messbaren Banken, Telcos und Behörden am Golf, in Ägypten, im Maghreb und in DACH "
            "({pct} %) handeln Post-Quanten-Schlüsselaustausch (X25519MLKEM768) aus. Ausgabe {edition}, CC BY 4.0.",
    "kicker": "Monatlicher Index · Ausgabe {edition}",
    "lead": "Welche Banken, Zentralbanken, Aufsichtsbehörden, Telcos und Behördenportale schützen ihre öffentliche Website bereits mit dem "
            "hybriden Post-Quanten-Schlüsselaustausch X25519MLKEM768, den Chrome, Firefox, Safari und Edge standardmäßig anbieten? "
            "Wir testen die Hauptwebsite von {total} Institutionen am Golf, in Ägypten, im Maghreb sowie in Deutschland, Österreich und der Schweiz.",
    "scanned": "Gemessen {start}–{end} UTC · Scanner-Version {version} · Messpunkt {vantage}",
    "k_overall": "Post-Quanten ({pq} von {n} gemessen)", "k_regions": "DACH · {gcc} % Golfstaaten", "k_tls12": "Websites nur mit TLS 1.2",
    "k_cdn": "der Post-Quanten-Ergebnisse stammen aus CDN-/Cloud-Voreinstellungen", "k_nm": "von unserem Messpunkt nicht messbar",
    "cdn_title": "Bitte zuerst lesen: der CDN-Effekt",
    "cdn": "{cdn_pct} % der Post-Quanten-Ergebnisse ({cdn} von {pq}) stammen von CDN- und Cloud-Edges (Cloudflare, AWS, Akamai, Imperva u. a.), "
           "die hybriden Schlüsselaustausch standardmäßig aktivieren. Ein Post-Quanten-Ergebnis spiegelt daher oft die Voreinstellung des "
           "Anbieters wider, nicht die eigene Migration der Institution; die Verbindung vom CDN zu den Servern der Institution ist von außen "
           "nicht sichtbar. Die Spalte Netzwerk zeigt das für jede Zeile.",
    "regions": "Nach Region", "sectors": "Nach Sektor", "countries": "Nach Land", "reference": "EU-Referenzgruppe (nicht in der Hauptzahl)",
    "col_group": "Gruppe", "col_pq": "Post-Quanten", "col_classical": "Klassisch", "col_nm": "Nicht gemessen",
    "col_inst": "Institution", "col_country": "Land", "col_sector": "Sektor", "col_host": "Getesteter Host",
    "col_result": "Ergebnis", "col_tls": "TLS", "col_network": "Netzwerk",
    "pct_fmt": "{pq} / {n} ({pct} %)",
    "status": {"pq_hybrid": "Post-Quanten", "classical": "klassisch", "not_measured": "nicht gemessen"},
    "region": {"GCC": "Golfstaaten", "Egypt": "Ägypten", "Maghreb": "Maghreb", "DACH": "DACH", "EU institutions": "EU-Institutionen"},
    "sector": {"banking": "Banken", "central-bank": "Zentralbanken", "regulator": "Aufsichtsbehörden", "telecom": "Telekommunikation", "government": "Behörden"},
    "rows_title": "Alle Institutionen", "rows_intro": "Sortiert nach Region, Land und Name (nicht nach Ergebnis). "
                  "„Nicht gemessen“ heißt: keine vollständige TLS-Messung von unserem Messpunkt; das wird nie als klassisch gezählt.",
    "comp_title": "Warum Compliance-Teams das verfolgen (zur Information, keine Rechtsberatung)",
    "comp": [("EU NIS2, Art. 21 Abs. 2 lit. h", "Konzepte für Kryptografie und Verschlüsselung; die EU-PQC-Roadmap (Juni 2025) sieht den Start der Umstellung bis Ende 2026 vor."),
             ("EU DORA + RTS (EU) 2024/1774, Art. 6–7", "Verschlüsselung und kryptografische Kontrollen für Finanzunternehmen, die Entwicklungen der Kryptoanalyse einschließlich Quantencomputing berücksichtigen."),
             ("Deutschland: BSI TR-02102", "Das BSI empfiehlt hybriden Post-Quanten-Schlüsselaustausch."),
             ("Saudi-Arabien: SAMA-Rundschreiben 482021280, NCA ECC-2:2024", "Kryptografie-Inventar für Finanzinstitute bis 31. Dezember 2026; nationale Kryptografie-Kontrollen."),
             ("VAE, Katar, Bahrain, Kuwait, Oman, Ägypten, Maghreb", "Rahmenwerke der Zentralbanken und nationalen Cyberbehörden verlangen Kryptografie nach aktuellem Stand.")],
    "comp_note": "Eine Startseite ist nur ein Host; Online-Banking, Apps, APIs und interne Systeme sind nicht abgedeckt.",
    "method_title": "Methodik und Auswahl",
    "method": ["Was wir messen: Pro Institution testen wir einen öffentlichen HTTPS-Host (meist www.) auf Port 443 und erfassen, welche Schlüsselaustausch-Gruppe der Server wählt, wenn ein browserähnlicher TLS-1.3-Client X25519MLKEM768 zusammen mit klassischen Gruppen anbietet. Post-Quanten = eine ML-KEM-Hybridgruppe wurde gewählt. Klassisch = klassische Gruppe oder nur TLS 1.2.",
               "Wie: derselbe Scanner wie beim kostenlosen Check und beim wöchentlichen /adoption-Tracker (eine DNS-Abfrage, zwei bis drei TLS-Handshakes pro Host, erste IPv4-Adresse, keine HTTP-Anfrage, keine anderen Ports, höchstens zwei Hosts parallel). Fehlgeschlagene Hosts werden einmal wiederholt; scheitern sie erneut, erscheinen sie als nicht gemessen und zählen nicht zu den Prozentwerten.",
               "Auswahl ({total} Institutionen, ein Jahr fest): pro Land die Zentralbank, die 4–6 größten Banken nach Bilanzsumme, Finanz- und Telekom-Aufsicht, alle lizenzierten Mobilfunkbetreiber und der Incumbent, das nationale E-Government-Portal, die nationale Cyberbehörde und das Finanzministerium; dazu sechs EU-Stellen als Referenzgruppe. Die Liste ist als CSV veröffentlicht.",
               "Grenzen: ein Host pro Institution, ein Messpunkt (London), Momentaufnahme. Ein klassisches Ergebnis ist heute keine Schwachstelle; es zeigt das Risiko „jetzt speichern, später entschlüsseln“. Websites, die Zugriffe aus dem Ausland sperren, erscheinen als nicht gemessen.",
               "Turnus: Jeden ersten Montag im Monat wird eine neue Ausgabe gemessen. Veröffentlichte Ausgaben werden nicht verändert; Korrekturen werden als neue Versionen protokolliert."],
    "data_title": "Daten, Zitation und Lizenz",
    "data": "Die Ausgabe als CSV oder JSON herunterladen (CC BY 4.0). Die Auswahl-Liste gibt es als CSV.",
    "cite": "Quantum Aether (2026). PQ-TLS Index, edition {edition}. {url} (CC BY 4.0)",
    "changes": "Änderungsprotokoll: {edition} ist die erste Ausgabe, daher gibt es noch keinen Monatsvergleich.",
    "correction_title": "Korrekturen und Gegendarstellung",
    "correction_intro": "Nutzt eine Institution eine andere Hauptwebsite, oder möchte sie eine kurze Stellungnahme neben ihrer Zeile? "
                        "Senden Sie eine Korrektur: Wir messen innerhalb von fünf Werktagen mit derselben TLS-Methode neu und protokollieren Änderungen.",
    "f_inst": "Institution", "f_name": "Ihr Name", "f_email": "E-Mail", "f_role": "Organisation / Funktion (optional)",
    "f_domains": "Stattdessen zu testender Host (optional)", "f_message": "Korrektur oder Stellungnahme", "f_rescan": "Bitte neu messen",
    "f_submit": "Korrektur senden", "f_privacy": "Wir speichern Ihre Anfrage nur zur Bearbeitung.",
    "f_alt": "Oder per E-Mail:", "sent": "Danke. Ihre Anfrage wurde gespeichert.",
    "err": {"invalid": "Bitte prüfen Sie die Felder und versuchen Sie es erneut.", "rate_limited": "Zu viele Anfragen heute. Bitte morgen erneut versuchen."},
    "signature": "Quantum Aether Team",
    "cta": "Eigene Domain kostenlos prüfen",
},
}


def _data_dir(base_dir):
    return os.environ.get("PQ_INDEX_DIR") or os.path.join(base_dir, "data")


def editions(base_dir):
    names = glob.glob(os.path.join(_data_dir(base_dir), "pq_index_????-??.json"))
    return sorted(os.path.basename(n)[9:16] for n in names)


def load(base_dir, edition=None):
    eds = editions(base_dir)
    if not eds:
        return None
    edition = edition or eds[-1]
    if edition not in eds:
        return None
    try:
        with open(os.path.join(_data_dir(base_dir), f"pq_index_{edition}.json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    data["meta"]["edition"] = edition
    return data


def panel_path(base_dir):
    return os.path.join(_data_dir(base_dir), "pq_index_orgs.csv")


def updated(data):
    return (data["meta"].get("scan_finished_utc") or "")[:10]


def _pct(pq, n):
    return round(100 * pq / n, 1) if n else None


def _count(rows):
    pq = sum(1 for r in rows if r["status"] == "pq_hybrid")
    cl = sum(1 for r in rows if r["status"] == "classical")
    return {"pq": pq, "classical": cl, "n": pq + cl, "not_measured": len(rows) - pq - cl, "total": len(rows), "pct": _pct(pq, pq + cl)}


def is_cdn(row):
    return (row.get("network") or "").startswith(CDN_PREFIXES)


def view(data):
    rows = data["results"]
    core = [r for r in rows if r["region"] in REGIONS]
    pq_rows = [r for r in rows if r["status"] == "pq_hybrid"]
    cdn = sum(1 for r in pq_rows if is_cdn(r))
    countries = OrderedDict()
    for region in REGIONS + (REFERENCE,):
        for code in sorted({r["country_code"] for r in rows if r["region"] == region}):
            countries[code] = _count([r for r in rows if r["country_code"] == code])
    order = {g: i for i, g in enumerate(REGIONS + (REFERENCE,))}
    return {
        "overall": _count(core), "total": len(rows), "core_total": len(core),
        "regions": [(g, _count([r for r in core if r["region"] == g])) for g in REGIONS],
        "reference": _count([r for r in rows if r["region"] == REFERENCE]),
        "sectors": [(s, _count([r for r in core if r["sector"] == s])) for s in SECTORS],
        "countries": countries,
        "tls12": sum(1 for r in rows if r["tls_version"] == "TLSv1.2"),
        "cdn": cdn, "pq_all": len(pq_rows), "cdn_pct": round(100 * cdn / len(pq_rows)) if pq_rows else 0,
        "rows": sorted(rows, key=lambda r: (order.get(r["region"], 9), r["country_code"], r["name"].lower())),
    }


def public_rows(data):
    ed = data["meta"]["edition"]
    out = []
    for r in data["results"]:
        row = {k: r.get(k) for k in CSV_COLUMNS if k != "edition"}
        row.update(edition=ed, domain=r["host"], ok=1 if r["status"] != "not_measured" else 0, as_name=r.get("network") or "")
        out.append(row)
    return out


def finish_marked(rows, real_hosts):
    """Canary rows copy a real row's values; blank everything that names an institution."""
    out = []
    for r in rows:
        r = dict(r)
        if r["domain"] not in real_hosts:
            r.update(name="", org_id="", role="", sector="", host=r["domain"])
        out.append({k: r.get(k) for k in CSV_COLUMNS})
    return out


def to_csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(CSV_COLUMNS), extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in CSV_COLUMNS})
    return buf.getvalue()


def register(bp, deps):
    """deps: base_dir, db, lang, client_hash, de_pages, de_endpoints, watermark(conn, rows, export, week), open_data(resp), base()."""
    deps["de_pages"].add(ENDPOINT)
    deps["de_endpoints"].add(ENDPOINT)

    def marked_rows(export):
        data = load(deps["base_dir"]) or abort(404)
        rows = public_rows(data)
        marked = deps["watermark"](deps["db"](), rows, export, data["meta"]["edition"])
        return data, finish_marked(marked, {r["host"] for r in data["results"]})

    @bp.get("/index")
    def pq_index_page():
        data = load(deps["base_dir"]) or abort(404)
        lang = deps["lang"]()
        d = T.get(lang, T["en"])
        v = view(data)
        return render_template("pq_index.html", d=d, v=v, m=data["meta"], ci=LANG_IDX.get(lang, 0), country=COUNTRY,
                               lang_code=lang, page_url=deps["base"]() + url_for(ENDPOINT),
                               inst=[(r["host"], r["name"]) for r in v["rows"]], fallback_email=dach_hosting.FALLBACK_EMAIL,
                               sent=request.args.get("sent") == "1", error=d["err"].get(request.args.get("error", "")))

    @bp.get("/index.csv")
    def pq_index_csv():
        data, rows = marked_rows("pq_index.csv")
        resp = Response(to_csv(rows), mimetype="text/csv")
        resp.headers["Content-Disposition"] = f'inline; filename="pq-tls-index-{data["meta"]["edition"]}.csv"'
        return deps["open_data"](resp)

    @bp.get("/index.json")
    def pq_index_json():
        data, rows = marked_rows("pq_index.json")
        v = view(data)
        body = {"meta": dict(data["meta"], source=deps["base"]() + url_for(ENDPOINT), panel_csv=deps["base"]() + url_for("site.pq_index_panel")),
                "summary": {"overall_core": v["overall"], "regions": dict(v["regions"]), "sectors": dict(v["sectors"]),
                            "eu_reference": v["reference"], "pq_via_cdn": {"cdn": v["cdn"], "pq": v["pq_all"], "pct": v["cdn_pct"]}},
                "results": rows}
        resp = Response(json.dumps(body, ensure_ascii=False), mimetype="application/json")
        return deps["open_data"](resp)

    @bp.get("/index/panel.csv")
    def pq_index_panel():
        try:
            with open(panel_path(deps["base_dir"]), encoding="utf-8") as f:
                body = f.read()
        except OSError:
            abort(404)
        resp = Response(body, mimetype="text/csv")
        resp.headers["Content-Disposition"] = 'inline; filename="pq-tls-index-panel.csv"'
        return deps["open_data"](resp)

    @bp.post("/index/correction")
    def pq_index_correction():
        if request.headers.get("Sec-Fetch-Site", "same-origin") not in ("same-origin", "none"):
            abort(400)
        lang = request.form.get("lang") if request.form.get("lang") in T else "en"
        back = lambda **kw: redirect(url_for(ENDPOINT, lang=lang, **kw) + "#correction", code=303)
        data = load(deps["base_dir"]) or abort(404)
        if request.form.get("website"):  # honeypot
            return back(sent="1")
        f = {k: (request.form.get(k) or "").strip() for k in ("institution", "name", "email", "role", "domains", "message")}
        hosts = {r["host"] for r in data["results"]}
        if (f["institution"] not in hosts or not (1 <= len(f["name"]) <= 120) or not dach_hosting.EMAIL_RE.match(f["email"])
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
                         ("[PQ-INDEX] " + f["institution"], f["name"], f["email"], f["role"] or None, f["domains"] or None,
                          f["message"], int(bool(request.form.get("rescan"))), lang, client))
        return back(sent="1")
