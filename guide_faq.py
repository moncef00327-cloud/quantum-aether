"""Short answer (under the H1) and FAQ for the guides that already rank in Google (GSC 7-19 Nov 2026).

Facts come from each guide's own body; the few additions were checked on 2026-11-21 against the source linked
in the answer (RFC 10024, Apple support 122756, go.dev/doc/go1.26, nginx community thread 9558, a DEV test of
Node 22.22.0, PostQuantum's summary of the SAMA circular). Unverifiable items from the draft were left out.
Each entry: {"short": html, "faq": [(question, answer_html), ...]}. Answers are visible HTML, also used in FAQPage
JSON-LD (tags stripped).
"""

CHECKED = "2026-11-21"

_S = "openssl s_client -connect example.com:443 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -i group"

FAQ = {
    "enable-x25519mlkem768-nginx": {
        "en": {
            "short": "<p>To enable post-quantum TLS on nginx, run nginx linked against <strong>OpenSSL 3.5 or newer</strong> "
                     "and delete any old <code>ssl_ecdh_curve</code> line. OpenSSL 3.5 already puts X25519MLKEM768 in its "
                     "default groups, so nginx offers it with no extra config. If you must pin a list, put the hybrid first: "
                     "<code>ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;</code></p>",
            "faq": [
                ("Why won't nginx start after I add X25519MLKEM768 to ssl_ecdh_curve?",
                 "<p>The error <code>SSL_CTX_set1_curves_list(...) failed</code> means nginx is linked against OpenSSL older "
                 "than 3.5, which does not know the name X25519MLKEM768. OpenSSL rejects the whole list if one name is unknown. "
                 "Remove the group or the whole line, run <code>nginx -t &amp;&amp; systemctl reload nginx</code>, then upgrade OpenSSL.</p>"),
                ("Do I need to set ssl_ecdh_curve if nginx already uses OpenSSL 3.5?",
                 "<p>No. With OpenSSL 3.5 or newer, the default (<code>ssl_ecdh_curve auto</code>) already offers X25519MLKEM768, "
                 "with X25519 as a fallback. A list copied from an old hardening guide can silently remove the hybrid.</p>"),
                ("How do I check which OpenSSL version nginx actually uses?",
                 "<p>Run <code>nginx -V 2&gt;&amp;1 | grep -i openssl</code>. The <code>openssl version</code> command can report a "
                 "different library from the one nginx loads.</p>"),
                ("Why do clients fail with \"no suitable key share\" when I list only X25519MLKEM768?",
                 "<p>With only the hybrid in the list, any client that does not offer it (older tools, or another server on OpenSSL "
                 "below 3.5) shares no group with yours, so the handshake fails. Keep a classical fallback after it: "
                 "<code>X25519MLKEM768:X25519:prime256v1</code>. Reported on the "
                 "<a href=\"https://community.nginx.org/t/error-when-trying-to-enforce-pqc-hndl-resistant-nginx-configuration-no-suitable-key-share/9558\" rel=\"noopener\">nginx community forum</a>.</p>"),
                ("How can I confirm nginx negotiated X25519MLKEM768?",
                 f"<p>From an OpenSSL 3.5 client: <code>{_S}</code> should print <code>Negotiated TLS1.3 group: X25519MLKEM768</code>. "
                 "Inside nginx you can log the <code>$ssl_curve</code> variable; depending on the build it shows X25519MLKEM768 "
                 "or the group's code point <code>0x11ec</code>.</p>"),
            ],
        },
        "ar": {
            "short": "<p>لتفعيل TLS المقاوم للكم على nginx شغّل nginx مربوطاً بـ <strong>OpenSSL 3.5 أو أحدث</strong> واحذف أي سطر "
                     "<code>ssl_ecdh_curve</code> قديم. يضع OpenSSL 3.5 المجموعة X25519MLKEM768 في مجموعاته الافتراضية، فيعرضها nginx "
                     "دون إعداد إضافي. وإن احتجت قائمة صريحة فضع الهجينة أولاً: <code dir=\"ltr\">ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;</code></p>",
            "faq": [
                ("لماذا لا يعمل nginx بعد إضافة X25519MLKEM768 إلى ssl_ecdh_curve؟",
                 "<p>الخطأ <code dir=\"ltr\">SSL_CTX_set1_curves_list(...) failed</code> يعني أن nginx مربوط بـ OpenSSL أقدم من 3.5 لا يعرف "
                 "اسم X25519MLKEM768، وOpenSSL يرفض القائمة كلها إن جهل اسماً واحداً. احذف المجموعة أو السطر كله، ثم نفّذ "
                 "<code dir=\"ltr\">nginx -t &amp;&amp; systemctl reload nginx</code>، ثم حدّث OpenSSL.</p>"),
                ("هل أحتاج إلى ضبط ssl_ecdh_curve إذا كان nginx يستخدم OpenSSL 3.5؟",
                 "<p>لا. مع OpenSSL 3.5 أو أحدث تعرض القيمة الافتراضية (<code dir=\"ltr\">ssl_ecdh_curve auto</code>) المجموعة X25519MLKEM768 "
                 "مع X25519 احتياطاً. أما القائمة المنسوخة من دليل حماية قديم فقد تحذف الهجينة دون أن تلاحظ.</p>"),
                ("كيف أعرف نسخة OpenSSL التي يستخدمها nginx فعلاً؟",
                 "<p>نفّذ <code dir=\"ltr\">nginx -V 2&gt;&amp;1 | grep -i openssl</code>. أمر <code dir=\"ltr\">openssl version</code> قد يُظهر مكتبة "
                 "غير التي يحمّلها nginx.</p>"),
                ("لماذا يفشل الاتصال برسالة «no suitable key share» عندما أضع X25519MLKEM768 وحدها؟",
                 "<p>إذا كانت الهجينة وحدها في القائمة فأي عميل لا يعرضها (أدوات قديمة أو خادم آخر على OpenSSL أقدم من 3.5) لا يشترك مع "
                 "خادمك في أي مجموعة، فيفشل الاتصال. أبقِ بعدها مجموعة تقليدية احتياطاً: <code dir=\"ltr\">X25519MLKEM768:X25519:prime256v1</code>. "
                 "طُرحت المشكلة في <a href=\"https://community.nginx.org/t/error-when-trying-to-enforce-pqc-hndl-resistant-nginx-configuration-no-suitable-key-share/9558\" rel=\"noopener\">منتدى مجتمع nginx</a>.</p>"),
                ("كيف أتأكد أن nginx تفاوض على X25519MLKEM768؟",
                 f"<p>من عميل OpenSSL 3.5: <code dir=\"ltr\">{_S}</code> يجب أن يطبع <code dir=\"ltr\">Negotiated TLS1.3 group: X25519MLKEM768</code>. "
                 "وداخل nginx يمكنك تسجيل المتغير <code dir=\"ltr\">$ssl_curve</code>؛ يُظهر حسب البناء X25519MLKEM768 أو رمز المجموعة "
                 "<code dir=\"ltr\">0x11ec</code>.</p>"),
            ],
        },
        "de": {
            "short": "<p>Für Post-Quanten-TLS auf nginx muss nginx gegen <strong>OpenSSL 3.5 oder neuer</strong> gebaut sein, und eine "
                     "alte <code>ssl_ecdh_curve</code>-Zeile gehört gelöscht. OpenSSL 3.5 führt X25519MLKEM768 bereits in seinen "
                     "Standardgruppen, nginx bietet die Gruppe also ohne weitere Konfiguration an. Wenn Sie eine Liste festlegen müssen, "
                     "steht die hybride Gruppe vorne: <code>ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;</code></p>",
            "faq": [
                ("Warum startet nginx nicht mehr, nachdem ich X25519MLKEM768 zu ssl_ecdh_curve hinzugefügt habe?",
                 "<p>Der Fehler <code>SSL_CTX_set1_curves_list(...) failed</code> bedeutet, dass nginx gegen ein OpenSSL älter als 3.5 "
                 "gebaut ist, das den Namen X25519MLKEM768 nicht kennt. OpenSSL verwirft die ganze Liste, wenn ein Name unbekannt ist. "
                 "Entfernen Sie die Gruppe oder die ganze Zeile, führen Sie <code>nginx -t &amp;&amp; systemctl reload nginx</code> aus "
                 "und aktualisieren Sie danach OpenSSL.</p>"),
                ("Muss ich ssl_ecdh_curve setzen, wenn nginx schon OpenSSL 3.5 nutzt?",
                 "<p>Nein. Ab OpenSSL 3.5 bietet die Voreinstellung (<code>ssl_ecdh_curve auto</code>) X25519MLKEM768 bereits an, mit "
                 "X25519 als Rückfall. Eine Liste aus einer alten Hardening-Anleitung kann die hybride Gruppe unbemerkt entfernen.</p>"),
                ("Wie prüfe ich, welche OpenSSL-Version nginx tatsächlich nutzt?",
                 "<p>Mit <code>nginx -V 2&gt;&amp;1 | grep -i openssl</code>. Der Befehl <code>openssl version</code> kann eine andere "
                 "Bibliothek melden als die, die nginx lädt.</p>"),
                ("Warum scheitern Clients mit „no suitable key share“, wenn nur X25519MLKEM768 eingetragen ist?",
                 "<p>Steht nur die hybride Gruppe in der Liste, hat jeder Client, der sie nicht anbietet (ältere Tools oder ein anderer "
                 "Server mit OpenSSL unter 3.5), keine gemeinsame Gruppe mit Ihrem Server, und der Handshake scheitert. Lassen Sie eine "
                 "klassische Gruppe dahinter: <code>X25519MLKEM768:X25519:prime256v1</code>. Gemeldet im "
                 "<a href=\"https://community.nginx.org/t/error-when-trying-to-enforce-pqc-hndl-resistant-nginx-configuration-no-suitable-key-share/9558\" rel=\"noopener\">nginx-Community-Forum</a>.</p>"),
                ("Wie bestätige ich, dass nginx X25519MLKEM768 aushandelt?",
                 f"<p>Mit einem OpenSSL-3.5-Client sollte <code>{_S}</code> die Zeile <code>Negotiated TLS1.3 group: X25519MLKEM768</code> "
                 "ausgeben. In nginx selbst können Sie die Variable <code>$ssl_curve</code> protokollieren; je nach Build zeigt sie "
                 "X25519MLKEM768 oder den Codepunkt <code>0x11ec</code>.</p>"),
            ],
        },
    },
    "gulf-banks-post-quantum-cryptography-requirements": {
        "en": {
            "short": "<p>Saudi Arabia is so far the only Gulf state with a binding post-quantum requirement for banks. SAMA's circular "
                     "of 27 August 2026 requires a cryptographic inventory by <strong>31 December 2026</strong> and an enterprise "
                     "quantum-risk assessment with action plans by <strong>31 March 2027</strong>. The UAE has a national policy for "
                     "government entities but no bank deadline; we found none published for Qatar, Bahrain, Oman or Kuwait (November 2026).</p>",
            "faq": [
                ("What does SAMA require from Saudi banks on post-quantum cryptography?",
                 "<p>By 31 December 2026: identify and classify cryptographic assets and assess the resilience of priority assets, "
                 "including third-party dependencies. By 31 March 2027: an enterprise-level quantum risk assessment with action plans. "
                 "Reaching the target resilience, and standing reporting to the risk and information-security committees and the "
                 "board, have no date.</p>"),
                ("Does the SAMA circular require ML-KEM or a specific algorithm?",
                 "<p>No. The circular names no algorithm and sets no migration completion date. Algorithms appear in the NCA's draft "
                 "NCS-2:2025: ML-KEM for key exchange, ML-DSA and SLH-DSA for signatures, used in hybrid with approved classical "
                 "schemes. Check its final status before citing it in an audit.</p>"),
                ("Who does the SAMA quantum circular apply to?",
                 "<p>According to <a href=\"https://postquantum.com/security-pqc/sama-quantum-circular-inventory/\" rel=\"noopener\">PostQuantum's "
                 "summary</a> of circular 482021280: banks, finance and payment-services companies operating in the Kingdom, "
                 "credit-information companies, and financing-support entities licensed by SAMA. The binding text is the Arabic circular.</p>"),
                ("Do UAE banks have a post-quantum deadline?",
                 "<p>Not a bank-specific one. The National Encryption Policy (approval announced November 2025) applies to government "
                 "entities. The national transition programme (May 2026) names critical sectors without a deadline. We found no "
                 "post-quantum requirement in public reporting on the Central Bank's 2026 operational-risk regulation.</p>"),
                ("What can a Saudi bank do before 31 December 2026?",
                 "<p>Start the inventory with public TLS endpoints: TLS version, negotiated group and who terminates TLS. Record vendors "
                 "without hybrid key exchange and their roadmaps. Enable X25519MLKEM768 on servers you control and keep repeated scan "
                 "evidence. A public scan does not cover internal systems, HSMs or payment protocols, which the inventory must include.</p>"),
            ],
        },
        "ar": {
            "short": "<p>السعودية حتى الآن هي الدولة الخليجية الوحيدة التي تفرض على البنوك متطلباً ملزماً للتشفير ما بعد الكمومي. يطلب "
                     "تعميم البنك المركزي السعودي (ساما) الصادر في 27 أغسطس 2026 حصر الأصول التشفيرية بحلول <strong>31 ديسمبر 2026</strong>، "
                     "وتقييماً لمخاطر الحوسبة الكمومية على مستوى المؤسسة مع خطط عمل بحلول <strong>31 مارس 2027</strong>. للإمارات سياسة وطنية "
                     "للجهات الحكومية دون موعد للبنوك، ولم نجد متطلباً منشوراً في قطر والبحرين وعُمان والكويت (نوفمبر 2026).</p>",
            "faq": [
                ("ماذا يطلب البنك المركزي السعودي من البنوك بشأن التشفير ما بعد الكمومي؟",
                 "<p>بحلول 31 ديسمبر 2026: تحديد الأصول التشفيرية وتصنيفها وتقييم صمود الأصول ذات الأولوية، بما فيها الاعتماد على "
                 "أطراف ثالثة. وبحلول 31 مارس 2027: تقييم لمخاطر الحوسبة الكمومية على مستوى المؤسسة مع خطط عمل. أما بلوغ مستوى الصمود "
                 "المطلوب، والتقارير الدائمة إلى لجنتي المخاطر وأمن المعلومات ومجلس الإدارة، فبلا موعد.</p>"),
                ("هل يشترط تعميم ساما خوارزمية ML-KEM أو خوارزمية محددة؟",
                 "<p>لا. التعميم لا يسمّي خوارزمية ولا يحدد موعداً لإكمال الانتقال. الخوارزميات واردة في مسودة الهيئة الوطنية للأمن "
                 "السيبراني NCS-2:2025: ‏ML-KEM لتبادل المفاتيح، وML-DSA وSLH-DSA للتوقيع، مع استخدامها هجيناً مع خوارزميات تقليدية "
                 "معتمدة. تحقق من وضعها النهائي قبل الاستشهاد بها في تدقيق.</p>"),
                ("على من ينطبق تعميم ساما بشأن الحوسبة الكمومية؟",
                 "<p>وفق <a href=\"https://postquantum.com/security-pqc/sama-quantum-circular-inventory/\" rel=\"noopener\">ملخص PostQuantum</a> "
                 "للتعميم 482021280: البنوك، وشركات التمويل وخدمات الدفع العاملة في المملكة، وشركات المعلومات الائتمانية، وجهات دعم "
                 "التمويل المرخصة من ساما. النص الملزم هو التعميم العربي.</p>"),
                ("هل لدى البنوك الإماراتية موعد نهائي للتشفير ما بعد الكمومي؟",
                 "<p>ليس موعداً خاصاً بالبنوك. السياسة الوطنية للتشفير (أُعلن اعتمادها في نوفمبر 2025) تخص الجهات الحكومية. والبرنامج "
                 "الوطني للانتقال (مايو 2026) يذكر القطاعات الحيوية دون موعد. ولم نجد متطلباً ما بعد كمومي فيما نُشر عن لائحة مخاطر "
                 "التشغيل لعام 2026 لدى المصرف المركزي.</p>"),
                ("ماذا يستطيع بنك سعودي أن يفعل قبل 31 ديسمبر 2026؟",
                 "<p>ابدأ الحصر بنقاط TLS العامة: نسخة TLS، والمجموعة المتفاوض عليها، ومن يُنهي TLS. سجّل المورّدين الذين لا يدعمون "
                 "تبادل المفاتيح الهجين وخرائط طريقهم. فعّل X25519MLKEM768 على الخوادم التي تديرها واحتفظ بأدلة فحص متكررة. الفحص العام "
                 "لا يغطي الأنظمة الداخلية ولا وحدات HSM ولا بروتوكولات الدفع، ويجب أن يشملها الحصر.</p>"),
            ],
        },
    },
    "nodejs-post-quantum-tls-x25519mlkem768": {
        "en": {
            "short": "<p>Node.js uses post-quantum TLS (X25519MLKEM768) automatically when it runs on <strong>OpenSSL 3.5 or newer</strong>, "
                     "with no code change. Official Node.js 24 LTS binaries include OpenSSL 3.5. Check with "
                     "<code>node -p process.versions.openssl</code>: a version below 3.5 (common with distro-built Node on Ubuntu 22.04 "
                     "and 24.04), or an <code>ecdhCurve</code> pinned to one curve, means classical X25519 only.</p>",
            "faq": [
                ("Do I need to set ecdhCurve to X25519MLKEM768 in Node.js?",
                 "<p>No. The default <code>ecdhCurve: 'auto'</code> keeps the hybrid group. Setting one curve such as "
                 "<code>'prime256v1'</code> removes it. If you need an explicit list, put the hybrid first: "
                 "<code>'X25519MLKEM768:X25519:prime256v1'</code>.</p>"),
                ("Does Node.js 22 support X25519MLKEM768?",
                 "<p>Recent Node.js 22 builds can: in a <a href=\"https://dev.to/daan_acohen/is-your-nodejs-app-quantum-safe-tracing-pqc-in-tls-connections-10b8\" rel=\"noopener\">published test</a>, "
                 "Node 22.22.0 reported OpenSSL 3.5.4 and negotiated X25519MLKEM768. Older 22.x builds do not. Check "
                 "<code>process.versions.openssl</code>, not the major version.</p>"),
                ("Why does my Node.js server behind nginx or a load balancer not show X25519MLKEM768?",
                 "<p>The layer that terminates TLS decides the key exchange. If nginx, a load balancer or a CDN sits in front, configure "
                 "that layer; Node's own settings never reach the client.</p>"),
                ("Are outgoing fetch() and https.request() calls post-quantum?",
                 "<p>On OpenSSL 3.5 they offer the hybrid group too. The connection uses it only when the remote server supports it.</p>"),
                ("How do I test a Node.js HTTPS server for X25519MLKEM768?",
                 f"<p>From an OpenSSL 3.5 client run <code>{_S}</code> and look for the negotiated group, or use the "
                 "<a href=\"/?lang=en\">free scan</a>: grade A means TLS 1.3 with a hybrid post-quantum key exchange.</p>"),
            ],
        },
        "ar": {
            "short": "<p>يستخدم Node.js تبادل المفاتيح المقاوم للكم (X25519MLKEM768) تلقائياً حين يعمل على <strong>OpenSSL 3.5 أو أحدث</strong>، "
                     "دون تغيير في الكود. نسخ Node.js 24 LTS الرسمية تأتي مع OpenSSL 3.5. تحقق بالأمر "
                     "<code dir=\"ltr\">node -p process.versions.openssl</code>: نسخة أقدم من 3.5 (شائعة في حزم التوزيعات على Ubuntu 22.04 و24.04)، "
                     "أو <code dir=\"ltr\">ecdhCurve</code> مثبّت على منحنى واحد، تعني X25519 التقليدي فقط.</p>",
            "faq": [
                ("هل أحتاج إلى ضبط ecdhCurve على X25519MLKEM768 في Node.js؟",
                 "<p>لا. القيمة الافتراضية <code dir=\"ltr\">ecdhCurve: 'auto'</code> تُبقي المجموعة الهجينة. ضبط منحنى واحد مثل "
                 "<code dir=\"ltr\">'prime256v1'</code> يحذفها. وإن احتجت قائمة صريحة فضع الهجينة أولاً: "
                 "<code dir=\"ltr\">'X25519MLKEM768:X25519:prime256v1'</code>.</p>"),
                ("هل يدعم Node.js 22 المجموعة X25519MLKEM768؟",
                 "<p>النسخ الحديثة من Node.js 22 قد تدعمها: في <a href=\"https://dev.to/daan_acohen/is-your-nodejs-app-quantum-safe-tracing-pqc-in-tls-connections-10b8\" rel=\"noopener\">اختبار منشور</a> "
                 "أظهر Node 22.22.0 مكتبة OpenSSL 3.5.4 وتفاوض على X25519MLKEM768. أما نسخ 22.x الأقدم فلا. تحقق من "
                 "<code dir=\"ltr\">process.versions.openssl</code> لا من رقم الإصدار الرئيسي.</p>"),
                ("لماذا لا يظهر X25519MLKEM768 لخادم Node.js خلف nginx أو موازن تحميل؟",
                 "<p>الطبقة التي تُنهي TLS هي التي تحدد تبادل المفاتيح. إذا كان أمامه nginx أو موازن تحميل أو CDN فاضبط تلك الطبقة؛ "
                 "إعدادات Node.js لا تصل إلى العميل.</p>"),
                ("هل طلبات fetch()‎ وhttps.request()‎ الصادرة مقاومة للكم؟",
                 "<p>على OpenSSL 3.5 تعرض المجموعة الهجينة أيضاً، ولا يستخدمها الاتصال إلا إذا دعمها الخادم البعيد.</p>"),
                ("كيف أختبر خادم HTTPS في Node.js؟",
                 f"<p>من عميل OpenSSL 3.5 نفّذ <code dir=\"ltr\">{_S}</code> وابحث عن المجموعة المتفاوض عليها، أو استخدم "
                 "<a href=\"/?lang=ar\">الفحص المجاني</a>: الدرجة A تعني TLS 1.3 مع تبادل مفاتيح هجين.</p>"),
            ],
        },
    },
    "java-post-quantum-tls-jdk27": {
        "en": {
            "short": "<p>Java supports post-quantum TLS from <strong>JDK 27</strong> (JEP 527). X25519MLKEM768 is on by default for TLS 1.3, "
                     "so apps using javax.net.ssl, HttpClient or embedded Tomcat and Jetty negotiate it with no code change. JDK 21 and "
                     "JDK 25 LTS do not include it; on those, terminate TLS in front of the JVM with nginx on OpenSSL 3.5, a "
                     "PQ-enabled load balancer or a CDN.</p>",
            "faq": [
                ("How do I enable X25519MLKEM768 in Java?",
                 "<p>On JDK 27 you don't need to: it is enabled by default. If your start scripts set <code>jdk.tls.namedGroups</code>, "
                 "put it first: <code>-Djdk.tls.namedGroups=X25519MLKEM768,x25519,secp256r1,secp384r1</code>.</p>"),
                ("Why does my JDK 27 app still negotiate x25519?",
                 "<p>Something overrides the named groups: <code>jdk.tls.namedGroups</code> in a start script, "
                 "<code>JAVA_TOOL_OPTIONS</code> or a container variable, or <code>SSLParameters.setNamedGroups(...)</code> in code. "
                 "A proxy or load balancer that terminates TLS in front of the JVM also decides instead of Java.</p>"),
                ("Which hybrid groups does JDK 27 support?",
                 "<p>X25519MLKEM768, SecP256r1MLKEM768 and SecP384r1MLKEM1024, the three groups of "
                 "<a href=\"https://www.rfc-editor.org/rfc/rfc10024\" rel=\"noopener\">RFC 10024</a>. Only X25519MLKEM768 is enabled by "
                 "default. As a client, JDK 27 sends two key shares: X25519MLKEM768 and x25519.</p>"),
                ("Does JDK 21 or JDK 25 support post-quantum TLS?",
                 "<p>No. Their SunJSSE has no hybrid ML-KEM key exchange (checked November 2026). Until a release adds it, put a "
                 "PQ-capable TLS terminator in front of the JVM.</p>"),
                ("How do I verify a Java server negotiates X25519MLKEM768?",
                 f"<p>Check the runtime with <code>java -version</code>, then run <code>{_S}</code> from an OpenSSL 3.5 client, or use "
                 "the <a href=\"/?lang=en\">free scan</a>.</p>"),
            ],
        },
        "ar": {
            "short": "<p>تدعم Java تبادل المفاتيح المقاوم للكم بدءاً من <strong>JDK 27</strong> ‏(JEP 527). المجموعة X25519MLKEM768 مفعّلة افتراضياً "
                     "في TLS 1.3، فالتطبيقات التي تستخدم javax.net.ssl أو HttpClient أو Tomcat وJetty المدمجين تتفاوض عليها دون تغيير في "
                     "الكود. لا يتضمنها JDK 21 ولا JDK 25 LTS؛ وعليهما أنهِ TLS أمام JVM عبر nginx على OpenSSL 3.5 أو موازن تحميل يدعمها أو CDN.</p>",
            "faq": [
                ("كيف أفعّل X25519MLKEM768 في Java؟",
                 "<p>على JDK 27 لا حاجة لذلك: هي مفعّلة افتراضياً. وإذا كانت سكربتات التشغيل تضبط <code dir=\"ltr\">jdk.tls.namedGroups</code> "
                 "فضعها أولاً: <code dir=\"ltr\">-Djdk.tls.namedGroups=X25519MLKEM768,x25519,secp256r1,secp384r1</code>.</p>"),
                ("لماذا ما زال تطبيقي على JDK 27 يتفاوض على x25519؟",
                 "<p>شيء ما يتجاوز المجموعات الافتراضية: <code dir=\"ltr\">jdk.tls.namedGroups</code> في سكربت تشغيل، أو "
                 "<code dir=\"ltr\">JAVA_TOOL_OPTIONS</code> أو متغير في الحاوية، أو <code dir=\"ltr\">SSLParameters.setNamedGroups(...)</code> في الكود. "
                 "والوكيل أو موازن التحميل الذي يُنهي TLS أمام JVM يقرر بدلاً من Java.</p>"),
                ("ما المجموعات الهجينة التي يدعمها JDK 27؟",
                 "<p>X25519MLKEM768 وSecP256r1MLKEM768 وSecP384r1MLKEM1024، وهي المجموعات الثلاث في "
                 "<a href=\"https://www.rfc-editor.org/rfc/rfc10024\" rel=\"noopener\">RFC 10024</a>. المفعّلة افتراضياً X25519MLKEM768 وحدها. "
                 "وبصفته عميلاً يرسل JDK 27 مفتاحين: X25519MLKEM768 وx25519.</p>"),
                ("هل يدعم JDK 21 أو JDK 25 تبادل المفاتيح المقاوم للكم؟",
                 "<p>لا. لا يحتوي SunJSSE فيهما على تبادل مفاتيح هجين بـ ML-KEM (راجعنا ذلك في نوفمبر 2026). إلى أن يضيفه إصدار، ضع أمام "
                 "JVM طبقة تُنهي TLS وتدعم المجموعة الهجينة.</p>"),
                ("كيف أتحقق أن خادم Java يتفاوض على X25519MLKEM768؟",
                 f"<p>تحقق من النسخة بـ <code dir=\"ltr\">java -version</code>، ثم نفّذ <code dir=\"ltr\">{_S}</code> من عميل OpenSSL 3.5، أو استخدم "
                 "<a href=\"/?lang=ar\">الفحص المجاني</a>.</p>"),
            ],
        },
    },
    "check-website-post-quantum-tls": {
        "en": {
            "short": "<p>Open the site in Chrome or Edge, press F12 and open the <strong>Privacy and security</strong> panel (older versions: "
                     "Security): if <em>Key exchange</em> shows X25519MLKEM768, the site uses post-quantum key exchange; X25519 means "
                     f"classical only. From a terminal with OpenSSL 3.5 or newer, run <code>{_S}</code> and look for "
                     "<code>Negotiated TLS1.3 group: X25519MLKEM768</code>. Or <a href=\"/?lang=en\">scan the domain free</a>.</p>",
            "faq": [
                ("What does it mean if the result shows X25519 instead of X25519MLKEM768?",
                 "<p>The connection used classical key exchange only. Usually the server's TLS library is older than OpenSSL 3.5, a "
                 "curve list pins classical groups, or a CDN or load balancer in front has not enabled the hybrid.</p>"),
                ("If a site uses X25519MLKEM768, is its certificate quantum-safe too?",
                 "<p>No. The hybrid protects the key exchange, so recorded traffic cannot be decrypted later "
                 "(<a href=\"/guides/harvest-now-decrypt-later?lang=en\">harvest now, decrypt later</a>). The certificate is still RSA "
                 "or ECDSA; post-quantum certificates are not in browsers yet.</p>"),
                ("Which browsers use post-quantum key exchange?",
                 "<p>Chrome and Edge from version 131 and Firefox from version 132 offer X25519MLKEM768 by default. Apple added it "
                 "to its TLS stack with iOS 26 and macOS Tahoe 26 "
                 "(<a href=\"https://support.apple.com/en-us/122756\" rel=\"noopener\">Apple</a>).</p>"),
                ("How can I check on a Mac without installing OpenSSL?",
                 "<p>On macOS Tahoe 26 run <code>nscurl --tls-diagnostics https://example.com</code>; look for "
                 "<code>Negotiated TLS key exchange group (name): X25519MLKEM768</code> "
                 "(<a href=\"https://support.apple.com/en-us/122756\" rel=\"noopener\">Apple</a>).</p>"),
                ("Does a passing check mean the whole website is quantum-safe?",
                 "<p>No. It covers one endpoint's TLS key exchange at one moment, not certificates, other subdomains, APIs, stored data "
                 "or internal systems. For a whole domain, see the <a href=\"/audit?lang=en\">estate audit</a>.</p>"),
            ],
        },
        "ar": {
            "short": "<p>افتح الموقع في Chrome أو Edge، واضغط F12، وافتح لوحة <strong>Privacy and security</strong> (في النسخ الأقدم: Security): "
                     "إذا أظهر حقل <em>Key exchange</em> القيمة X25519MLKEM768 فالموقع يستخدم تبادل مفاتيح مقاوماً للكم، وX25519 يعني "
                     f"تقليدياً فقط. ومن الطرفية مع OpenSSL 3.5 أو أحدث نفّذ <code dir=\"ltr\">{_S}</code> وابحث عن "
                     "<code dir=\"ltr\">Negotiated TLS1.3 group: X25519MLKEM768</code>. أو <a href=\"/?lang=ar\">افحص النطاق مجاناً</a>.</p>",
            "faq": [
                ("ماذا يعني ظهور X25519 بدلاً من X25519MLKEM768؟",
                 "<p>الاتصال استخدم تبادل مفاتيح تقليدياً فقط. السبب عادةً أن مكتبة TLS في الخادم أقدم من OpenSSL 3.5، أو أن قائمة "
                 "منحنيات تثبّت مجموعات تقليدية، أو أن CDN أو موازن تحميل في الأمام لم يفعّل المجموعة الهجينة.</p>"),
                ("إذا استخدم الموقع X25519MLKEM768 فهل شهادته مقاومة للكم أيضاً؟",
                 "<p>لا. المجموعة الهجينة تحمي تبادل المفاتيح، فلا يمكن فك تشفير حركة مسجلة لاحقاً "
                 "(<a href=\"/guides/harvest-now-decrypt-later?lang=ar\">احفظ الآن، فُكّ لاحقاً</a>). أما الشهادة فما زالت RSA أو ECDSA، "
                 "والشهادات المقاومة للكم ليست في المتصفحات بعد.</p>"),
                ("ما المتصفحات التي تستخدم تبادل المفاتيح المقاوم للكم؟",
                 "<p>Chrome وEdge منذ الإصدار 131 وFirefox منذ الإصدار 132 تعرض X25519MLKEM768 افتراضياً. وأضافتها Apple إلى TLS في "
                 "iOS 26 وmacOS Tahoe 26 (<a href=\"https://support.apple.com/en-us/122756\" rel=\"noopener\">Apple</a>).</p>"),
                ("كيف أتحقق على Mac دون تثبيت OpenSSL؟",
                 "<p>على macOS Tahoe 26 نفّذ <code dir=\"ltr\">nscurl --tls-diagnostics https://example.com</code> وابحث عن "
                 "<code dir=\"ltr\">Negotiated TLS key exchange group (name): X25519MLKEM768</code> "
                 "(<a href=\"https://support.apple.com/en-us/122756\" rel=\"noopener\">Apple</a>).</p>"),
                ("هل نجاح الفحص يعني أن الموقع كله مقاوم للكم؟",
                 "<p>لا. يغطي تبادل المفاتيح في نقطة واحدة وفي لحظة واحدة، لا الشهادات ولا النطاقات الفرعية الأخرى ولا الواجهات "
                 "البرمجية ولا البيانات المخزنة ولا الأنظمة الداخلية. وللنطاق كله راجع <a href=\"/audit?lang=ar\">تدقيق النطاق</a>.</p>"),
            ],
        },
    },
    "go-post-quantum-tls-x25519mlkem768": {
        "en": {
            "short": "<p>Go enables post-quantum TLS (X25519MLKEM768) by default from <strong>Go 1.24</strong>, but only when the "
                     "<code>go</code> line in your go.mod says 1.24 or newer. A binary built with a newer toolchain but "
                     "<code>go 1.23</code> in go.mod still negotiates plain X25519. Fix it with <code>go mod edit -go=1.24</code> "
                     "(or add <code>godebug tlsmlkem=1</code>), and don't pin CurvePreferences without <code>tls.X25519MLKEM768</code>.</p>",
            "faq": [
                ("Why does my Go program built with a new Go version not use X25519MLKEM768?",
                 "<p>Check, in order: the <code>go</code> line in go.mod (below 1.24 keeps the old defaults), a "
                 "<code>GODEBUG=tlsmlkem=0</code> in a Dockerfile, systemd unit or Kubernetes manifest, a <code>CurvePreferences</code> "
                 "list without the hybrid, and a proxy or CDN that terminates TLS in front.</p>"),
                ("How do I check the negotiated group in Go?",
                 "<p>After <code>tls.Dial</code>, print <code>conn.ConnectionState().CurveID</code>. It should show X25519MLKEM768.</p>"),
                ("What does GODEBUG tlsmlkem=0 do?",
                 "<p>It turns the default hybrid off. Teams set it to work around middleboxes that drop the larger ClientHello: the "
                 "X25519MLKEM768 client key share alone is 1,216 bytes "
                 "(<a href=\"https://www.rfc-editor.org/rfc/rfc10024\" rel=\"noopener\">RFC 10024</a>). Remove it once the middlebox is fixed.</p>"),
                ("Which post-quantum groups does Go support?",
                 "<p>Go 1.24 added X25519MLKEM768 to the default key exchanges. Go 1.26 added SecP256r1MLKEM768 and SecP384r1MLKEM1024, "
                 "also enabled by default (<a href=\"https://go.dev/doc/go1.26\" rel=\"noopener\">Go 1.26 release notes</a>).</p>"),
            ],
        },
        "ar": {
            "short": "<p>تفعّل Go تبادل المفاتيح المقاوم للكم (X25519MLKEM768) افتراضياً منذ <strong>Go 1.24</strong>، لكن فقط إذا كان سطر "
                     "<code dir=\"ltr\">go</code> في go.mod يقول 1.24 أو أحدث. البرنامج المبني بأداة أحدث مع <code dir=\"ltr\">go 1.23</code> في go.mod "
                     "يبقى على X25519 التقليدي. أصلحه بـ <code dir=\"ltr\">go mod edit -go=1.24</code> (أو أضف <code dir=\"ltr\">godebug tlsmlkem=1</code>)، "
                     "ولا تثبّت CurvePreferences دون <code dir=\"ltr\">tls.X25519MLKEM768</code>.</p>",
            "faq": [
                ("لماذا لا يستخدم برنامجي المبني بنسخة Go حديثة المجموعة X25519MLKEM768؟",
                 "<p>تحقق بالترتيب من: سطر <code dir=\"ltr\">go</code> في go.mod (أقل من 1.24 يُبقي الإعدادات القديمة)، ووجود "
                 "<code dir=\"ltr\">GODEBUG=tlsmlkem=0</code> في Dockerfile أو وحدة systemd أو ملف Kubernetes، وقائمة "
                 "<code dir=\"ltr\">CurvePreferences</code> بلا الهجينة، ووكيل أو CDN يُنهي TLS في الأمام.</p>"),
                ("كيف أعرف المجموعة المتفاوض عليها في Go؟",
                 "<p>بعد <code dir=\"ltr\">tls.Dial</code> اطبع <code dir=\"ltr\">conn.ConnectionState().CurveID</code>، ويجب أن يظهر X25519MLKEM768.</p>"),
                ("ماذا يفعل GODEBUG tlsmlkem=0؟",
                 "<p>يوقف المجموعة الهجينة الافتراضية. يضبطه البعض لتجاوز أجهزة وسيطة تُسقط رسالة ClientHello الأكبر: مفتاح العميل "
                 "في X25519MLKEM768 وحده 1216 بايت (<a href=\"https://www.rfc-editor.org/rfc/rfc10024\" rel=\"noopener\">RFC 10024</a>). "
                 "احذفه بعد إصلاح الجهاز الوسيط.</p>"),
                ("ما المجموعات المقاومة للكم التي تدعمها Go؟",
                 "<p>أضافت Go 1.24 المجموعة X25519MLKEM768 إلى التبادلات الافتراضية، وأضافت Go 1.26 المجموعتين SecP256r1MLKEM768 "
                 "وSecP384r1MLKEM1024 مفعّلتين افتراضياً أيضاً (<a href=\"https://go.dev/doc/go1.26\" rel=\"noopener\">ملاحظات إصدار Go 1.26</a>).</p>"),
            ],
        },
    },
    "ssl-labs-post-quantum-tls-check": {
        "en": {
            "short": "<p><strong>Yes, Qualys SSL Labs now lists post-quantum key-exchange groups</strong>, but it is a slower one-off full TLS audit that can fail on PQ-only configurations and offers no regression alerts. Use SSL Labs for a deep cipher/certificate audit, and a dedicated check like Quantum Aether for instant X25519MLKEM768 verification, HelloRetryRequest handling, CI checks and daily silent-downgrade monitoring.</p>",
            "faq": [
                ("Does SSL Labs test X25519MLKEM768?",
                 "<p>Yes, SSL Labs reports supported post-quantum named groups during its full TLS test, though F5 has documented cases where PQ-only configurations fail in SSL Labs. Dedicated probes also answer HelloRetryRequest once as browsers do.</p>"),
                ("Why did SSL Labs and Quantum Aether show different results for my domain?",
                 "<p>Usually because the two tests hit different IP addresses behind an anycast CDN or multiple DNS A/AAAA records, or a config changed between runs. Compare the IP shown in both results.</p>"),
                ("Does an SSL Labs A+ grade mean my site is quantum-safe?",
                 "<p>No. A site can score A+ on SSL Labs using only classical X25519 or P-256 key exchange, which remains exposed to harvest-now, decrypt-later interception.</p>"),
            ],
        },
        "ar": {
            "short": "<p><strong>نعم، يعرض Qualys SSL Labs الآن مجموعات تبادل المفاتيح المقاومة للكم</strong>، لكنه تدقيق شامل أبطأ لمرة واحدة وقد يفشل مع الخوادم المقاومة للكم فقط ولا يوفّر تنبيهات تراجع. استخدم SSL Labs لتدقيق الشهادات والتشفير بالكامل، وفحص Quantum Aether للتحقق الفوري من X25519MLKEM768 والمراقبة اليومية للتراجع الصامت.</p>",
            "faq": [
                ("هل يفحص SSL Labs مجموعة X25519MLKEM768؟",
                 "<p>نعم، يعرض SSL Labs المجموعات المقاومة للكم المدعومة ضمن اختباره الكامل، إلا أن F5 وثّقت حالات فشل مع الإعدادات الكمومية فقط. الفحص المخصص يتعامل أيضاً مع HelloRetryRequest كما تفعل المتصفحات.</p>"),
                ("هل تعني درجة A+ في SSL Labs أن الموقع مقاوم للكم؟",
                 "<p>لا. يمكن لموقع أن يحصل على A+ في SSL Labs بتبادل مفاتيح تقليدي X25519 فقط، وهو ما يظل عرضة لهجوم احفظ الآن وفكّ لاحقاً.</p>"),
                ("لماذا قد تختلف النتيجة بين SSL Labs وQuantum Aether؟",
                 "<p>غالباً لأن الفحصين وصلا إلى عنوانَي IP مختلفين خلف شبكة CDN أو عدة سجلات DNS، أو تغيّر الإعداد بين الفحصين.</p>"),
            ],
        },
        "de": {
            "short": "<p><strong>Ja, Qualys SSL Labs zeigt inzwischen Post-Quanten-Gruppen an</strong>, bleibt aber ein langsameres Einzel-Audit ohne tägliche Regressionswarnungen. Nutzen Sie SSL Labs für das vollständige Cipher-/Zertifikats-Audit und Quantum Aether für schnelle X25519MLKEM768-Prüfungen und tägliche Überwachung.</p>",
            "faq": [
                ("Bedeutet die Note A+ bei SSL Labs, dass meine Website quantensicher ist?",
                 "<p>Nein. Eine Website kann bei SSL Labs A+ mit rein klassischem X25519 erhalten und bleibt dennoch gegen Harvest-Now-Decrypt-Later ungeschützt.</p>"),
                ("Warum weichen SSL Labs und Quantum Aether manchmal voneinander ab?",
                 "<p>Meist treffen beide Tests unterschiedliche IP-Adressen hinter einem Anycast-CDN oder mehreren DNS-Einträgen.</p>"),
            ],
        },
    },
    "x25519mlkem768-handshake-latency-performance": {
        "en": {
            "short": "<p><code>X25519MLKEM768</code> adds only <strong>~150–350 microseconds</strong> of CPU time on modern servers (under 1 ms) and zero extra TLS round trips when offered first. The main network change is a <strong>1,216-byte ClientHello key share</strong>, which pushes ClientHello across two TCP segments and can trip legacy middleboxes.</p>",
            "faq": [
                ("How much latency does X25519MLKEM768 add to a TLS 1.3 handshake?",
                 "<p>On modern x86_64 or ARM64 CPUs, ML-KEM-768 key operations typically add 150–350 microseconds (roughly 0.5–2% of a normal internet RTT) and zero extra network round trips when both sides prefer X25519MLKEM768.</p>"),
                ("How big is the X25519MLKEM768 ClientHello key share?",
                 "<p>1,216 bytes (1,184 bytes for the ML-KEM-768 public key plus 32 bytes for X25519), compared with 32 bytes for classical X25519. That usually makes the full ClientHello span two TCP packets on a 1,500-byte MTU link.</p>"),
                ("Why can X25519MLKEM768 cause connection hangs on some networks?",
                 "<p>Because legacy firewalls or DPI middleboxes sometimes expect the entire TLS ClientHello in a single TCP segment and drop or stall two-segment handshakes.</p>"),
            ],
        },
        "ar": {
            "short": "<p>تضيف مجموعة <code>X25519MLKEM768</code> نحو <strong>150–350 ميكروثانية فقط</strong> على المعالج (أقل من 1 مللي ثانية) وصفر جولات شبكية إضافية. التغيير الفعلي هو حجم المفتاح في ClientHello البالغ <strong>1,216 بايت</strong> مما يقسم الرسالة على حزمتي TCP.</p>",
            "faq": [
                ("كم يضيف X25519MLKEM768 من تأخير لمصافحة TLS 1.3؟",
                 "<p>على المعالجات الحديثة يضيف نحو 150–350 ميكروثانية فقط (قرابة 0.5–2% من زمن جولة الإنترنت المعتادة) دون أي جولة شبكية إضافية إذا اتفق الطرفان عليها أولاً.</p>"),
                ("ما حجم مفتاح X25519MLKEM768 في ClientHello؟",
                 "<p>1,216 بايت (1,184 بايت لمفتاح ML-KEM-768 و32 بايت لـ X25519)، مقارنة بـ 32 بايت فقط في X25519 التقليدي.</p>"),
            ],
        },
        "de": {
            "short": "<p><code>X25519MLKEM768</code> kostet auf modernen Servern nur <strong>ca. 150–350 Mikrosekunden</strong> CPU-Zeit und keinen zusätzlichen Round-Trip. Entscheidend ist der <strong>1.216 Byte große ClientHello Key Share</strong>, der zwei TCP-Segmente belegt.</p>",
            "faq": [
                ("Wie viel Latenz fügt X25519MLKEM768 hinzu?",
                 "<p>Typischerweise 150–350 Mikrosekunden Rechenzeit (unter 1 ms) und keinen zusätzlichen Netzwerk-Round-Trip, solange kein HelloRetryRequest ausgelöst wird.</p>"),
                ("Wie groß ist der Key Share von X25519MLKEM768?",
                 "<p>1.216 Byte im ClientHello (1.184 Byte ML-KEM-768 + 32 Byte X25519) und 1.120 Byte im ServerHello.</p>"),
            ],
        },
    },
    "openssl-3-5-curl-test-x25519mlkem768": {
        "en": {
            "short": "<p>Run <code>openssl s_client -connect example.com:443 -groups X25519MLKEM768</code> with <strong>OpenSSL 3.5 or newer</strong> and check for <code>Negotiated TLS1.3 group: X25519MLKEM768</code>, or run <code>curl -Iv --tlsv1.3 --curves X25519MLKEM768 https://example.com</code>.</p>",
            "faq": [
                ("Which OpenSSL version is required to test X25519MLKEM768?",
                 "<p>OpenSSL 3.5.0 or newer. Earlier OpenSSL 3.0–3.4 releases do not recognize X25519MLKEM768 and fail with an unknown group error.</p>"),
                ("How can I test X25519MLKEM768 if my machine only has OpenSSL 3.0?",
                 "<p>Use an external probe such as curl https://ather-quantum.com/api/v1/scan?domain=example.com&amp;format=text or run openssl inside a newer container image (for example Debian 13 or Alpine 3.22+).</p>"),
            ],
        },
        "ar": {
            "short": "<p>شغّل <code>openssl s_client -connect example.com:443 -groups X25519MLKEM768</code> مع <strong>OpenSSL 3.5 أو أحدث</strong> وتأكد من ظهور <code>Negotiated TLS1.3 group: X25519MLKEM768</code>، أو استخدم <code>curl -Iv --tlsv1.3 --curves X25519MLKEM768</code>.</p>",
            "faq": [
                ("ما إصدار OpenSSL المطلوب لاختبار X25519MLKEM768؟",
                 "<p>OpenSSL 3.5.0 أو أحدث؛ الإصدارات 3.0 إلى 3.4 لا تعرف هذه المجموعة وتعيد خطأ.</p>"),
                ("كيف أفحص دون ترقية OpenSSL على جهازي؟",
                 "<p>عبر الواجهة النصية curl https://ather-quantum.com/api/v1/scan?domain=example.com&amp;format=text أو عبر الفاحص المجاني على الموقع.</p>"),
            ],
        },
        "de": {
            "short": "<p>Führen Sie <code>openssl s_client -connect example.com:443 -groups X25519MLKEM768</code> mit <strong>OpenSSL 3.5+</strong> aus und prüfen Sie auf <code>Negotiated TLS1.3 group: X25519MLKEM768</code>.</p>",
            "faq": [
                ("Welche OpenSSL-Version wird benötigt?",
                 "<p>Mindestens OpenSSL 3.5.0; ältere Versionen (3.0–3.4) kennen X25519MLKEM768 nicht.</p>"),
            ],
        },
    },
    "windows-server-iis-dotnet-post-quantum-tls": {
        "en": {
            "short": "<p>IIS delegates TLS 1.3 to Windows <strong>Schannel / SymCrypt</strong>. Windows Server 2019 and 2022 do not negotiate <code>X25519MLKEM768</code> natively; while Windows Server 2025 introduces ML-KEM in CNG, the fastest way to enable hybrid PQ TLS for IIS today is terminating TLS on a PQ-capable reverse proxy or CDN in front of IIS.</p>",
            "faq": [
                ("Does Windows Server 2022 IIS support X25519MLKEM768?",
                 "<p>No. Windows Server 2022 supports TLS 1.3 with classical curves (X25519, P-256, P-384) but does not natively negotiate X25519MLKEM768 in Schannel.</p>"),
                ("How can I enable post-quantum TLS for an IIS site without replacing Windows Server?",
                 "<p>Terminate public HTTPS in front of IIS with Cloudflare, AWS CloudFront, Caddy, HAProxy, or nginx built with OpenSSL 3.5+, then verify the public hostname with a live TLS scan.</p>"),
            ],
        },
        "ar": {
            "short": "<p>يعتمد IIS على <strong>Schannel وSymCrypt</strong> في نظام Windows. إصدارا Windows Server 2019 و2022 لا يدعمان <code>X25519MLKEM768</code> أصلياً، وأسرع حل إنتاجي اليوم هو إنهاء TLS العام أمام IIS عبر وكيل عكسي أو CDN يدعم ما بعد الكم.</p>",
            "faq": [
                ("هل يدعم IIS على Windows Server 2022 مجموعة X25519MLKEM768؟",
                 "<p>لا، يدعم Windows Server 2022 بروتوكول TLS 1.3 بالمنحنيات التقليدية فقط دون X25519MLKEM768 أصلياً.</p>"),
                ("كيف أفعّل TLS المقاوم للكم لموقع IIS دون استبدال الخادم؟",
                 "<p>ضع أمام IIS شبكة CDN مثل Cloudflare أو وكيلاً عكسياً مثل Caddy أو nginx (OpenSSL 3.5+) ثم افحص النطاق العام للتأكد.</p>"),
            ],
        },
        "de": {
            "short": "<p>IIS nutzt Windows <strong>Schannel / SymCrypt</strong>. Windows Server 2019 und 2022 handeln <code>X25519MLKEM768</code> nicht nativ aus; am schnellsten sichern Sie IIS heute über einen PQ-fähigen Reverse Proxy oder ein CDN davor ab.</p>",
            "faq": [
                ("Unterstützt Windows Server 2022 IIS X25519MLKEM768?",
                 "<p>Nein, Schannel auf Windows Server 2022 bietet nur klassische TLS-1.3-Gruppen an.</p>"),
            ],
        },
    },
}

LABELS = {"en": ("Short answer", "Frequently asked questions"),
          "ar": ("الجواب المختصر", "أسئلة شائعة"),
          "de": ("Kurze Antwort", "Häufige Fragen")}


def for_page(slug, lang):
    return FAQ.get(slug, {}).get(lang)

import guide_pages_seo_gap
FAQ.update(guide_pages_seo_gap.FAQ)
