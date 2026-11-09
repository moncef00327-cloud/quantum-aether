# guides.py
# صفحات الأدلة التقنية (عربي / إنجليزي). المحتوى HTML مكتوب يدوياً هنا، لا يأتي من المستخدم.

GUIDES = {
    "enable-x25519mlkem768-nginx": {
        "updated": "2026-11-03",
        "en": {
            "title": "How to enable post-quantum TLS (X25519MLKEM768) on nginx",
            "description": "Turn on the hybrid ML-KEM key exchange that Chrome and Firefox already use, on nginx with OpenSSL 3.5, and verify it.",
            "body": """
<p>Chrome (since version 131) and Firefox already offer the hybrid key exchange <code>X25519MLKEM768</code> in every HTTPS connection. If your server accepts it, the session keys are protected against a future quantum computer. If it does not, the browser falls back to plain X25519 and the traffic can be recorded today and decrypted later (<a href="/guides/harvest-now-decrypt-later?lang=en">harvest now, decrypt later</a>).</p>

<h2>1. Check your OpenSSL version</h2>
<p>nginx gets its TLS from the OpenSSL library it was built against. ML-KEM arrived in <strong>OpenSSL 3.5</strong>.</p>
<pre dir="ltr">nginx -V 2>&amp;1 | grep -o 'OpenSSL [0-9.]*'
openssl version</pre>
<p>If either shows 3.0, 3.1, 3.2, 3.3 or 3.4, nginx cannot negotiate ML-KEM no matter what you put in the config. Ubuntu 22.04 and 24.04 ship OpenSSL 3.0; Debian 13 (trixie) ships 3.5. Your options are to upgrade the OS, use an nginx build linked against OpenSSL 3.5, or put a post-quantum capable proxy or CDN in front (see the <a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=en">other servers guide</a>).</p>

<h2>2. Configure nginx</h2>
<p>With OpenSSL 3.5, X25519MLKEM768 is in the default group list, so nginx's default <code>ssl_ecdh_curve auto</code> already offers it. The common mistake is an explicit curve list copied from an old hardening guide, which silently removes it. Make the list explicit and put the hybrid group first:</p>
<pre dir="ltr">server {
    listen 443 ssl;
    http2 on;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;
    # ... certificates and the rest of your config
}</pre>
<p>Also look in included files such as <code>/etc/letsencrypt/options-ssl-nginx.conf</code> for another <code>ssl_ecdh_curve</code> line. Then:</p>
<pre dir="ltr">nginx -t &amp;&amp; systemctl reload nginx</pre>

<h2>3. Verify</h2>
<p>With an OpenSSL 3.5 client:</p>
<pre dir="ltr">openssl s_client -connect example.com:443 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -i group</pre>
<p>You should see <code>X25519MLKEM768</code> as the negotiated group. Or run the <a href="/?lang=en">free scan</a>: grade A means TLS 1.3 with a hybrid post-quantum key exchange.</p>

<h2>Watch out for</h2>
<ul>
<li><strong>Large ClientHello.</strong> The ML-KEM key share makes the browser's first message about 1.2 KB larger and it often spans two TCP packets. Old firewalls, load balancers and middleboxes that expect it in one packet drop the connection. The scan reports this as a separate finding.</li>
<li><strong>Certificates are a separate problem.</strong> Your RSA or ECDSA certificate is still breakable by Shor's algorithm, but that only matters once a quantum computer exists and only for live impersonation. Key exchange is what protects recorded traffic, so fix it first.</li>
</ul>
""",
        },
        "ar": {
            "title": "كيف تفعّل TLS المقاوم للكم (X25519MLKEM768) على nginx",
            "description": "فعّل تبادل المفاتيح الهجين ML-KEM الذي تستخدمه Chrome وFirefox فعلاً، على nginx مع OpenSSL 3.5، ثم تحقق منه.",
            "body": """
<p>متصفح Chrome (منذ الإصدار 131) وFirefox يعرضان تبادل المفاتيح الهجين <code>X25519MLKEM768</code> في كل اتصال HTTPS. إذا قبله خادمك فمفاتيح الجلسة محمية من أي حاسوب كمومي مستقبلي. وإذا لم يقبله يرجع المتصفح إلى X25519 العادي، ويمكن تسجيل حركة المرور اليوم وفك تشفيرها لاحقاً (<a href="/guides/harvest-now-decrypt-later?lang=ar">احفظ الآن، فُكّ لاحقاً</a>).</p>

<h2>1. تحقق من إصدار OpenSSL</h2>
<p>يأخذ nginx تشفير TLS من مكتبة OpenSSL التي بُني عليها. دعم ML-KEM وصل في <strong>OpenSSL 3.5</strong>.</p>
<pre dir="ltr">nginx -V 2>&amp;1 | grep -o 'OpenSSL [0-9.]*'
openssl version</pre>
<p>إذا ظهر 3.0 أو 3.1 أو 3.2 أو 3.3 أو 3.4 فلن يستطيع nginx استخدام ML-KEM مهما كتبت في الإعدادات. Ubuntu 22.04 و24.04 يأتيان بـ OpenSSL 3.0، وDebian 13 (trixie) يأتي بـ 3.5. الحلول: ترقية النظام، أو نسخة nginx مبنية على OpenSSL 3.5، أو وضع وكيل أو CDN يدعم ما بعد الكم أمام الخادم (انظر <a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=ar">دليل الخوادم الأخرى</a>).</p>

<h2>2. إعداد nginx</h2>
<p>مع OpenSSL 3.5 تكون المجموعة X25519MLKEM768 ضمن القائمة الافتراضية، فالإعداد الافتراضي <code>ssl_ecdh_curve auto</code> يعرضها أصلاً. الخطأ الشائع هو قائمة منحنيات صريحة منسوخة من دليل حماية قديم تحذفها دون أن تشعر. اكتب القائمة صراحة وضع المجموعة الهجينة أولاً:</p>
<pre dir="ltr">server {
    listen 443 ssl;
    http2 on;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;
    # ... الشهادات وبقية الإعدادات
}</pre>
<p>ابحث أيضاً في الملفات المضمّنة مثل <code>/etc/letsencrypt/options-ssl-nginx.conf</code> عن سطر <code>ssl_ecdh_curve</code> آخر. ثم:</p>
<pre dir="ltr">nginx -t &amp;&amp; systemctl reload nginx</pre>

<h2>3. التحقق</h2>
<p>باستخدام عميل OpenSSL 3.5:</p>
<pre dir="ltr">openssl s_client -connect example.com:443 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -i group</pre>
<p>يجب أن تظهر <code>X25519MLKEM768</code> كمجموعة متفق عليها. أو شغّل <a href="/?lang=ar">الفحص المجاني</a>: الدرجة A تعني TLS 1.3 مع تبادل مفاتيح هجين مقاوم للكم.</p>

<h2>انتبه إلى</h2>
<ul>
<li><strong>رسالة ClientHello الكبيرة.</strong> مفتاح ML-KEM يزيد أول رسالة من المتصفح بنحو 1.2 كيلوبايت، فتمتد غالباً على حزمتي TCP. بعض الجدران النارية وموازنات الحمل القديمة تتوقعها في حزمة واحدة فتقطع الاتصال. الفحص يذكر هذا كنتيجة مستقلة.</li>
<li><strong>الشهادات مسألة منفصلة.</strong> شهادة RSA أو ECDSA قابلة للكسر بخوارزمية Shor، لكن هذا يهم فقط بعد وجود حاسوب كمومي وفقط لانتحال الموقع لحظياً. تبادل المفاتيح هو ما يحمي الحركة المسجلة، فابدأ به.</li>
</ul>
""",
        },
    },
    "post-quantum-tls-apache-caddy-haproxy-cloudflare": {
        "updated": "2026-11-03",
        "en": {
            "title": "Post-quantum TLS on Apache, Caddy, HAProxy and Cloudflare",
            "description": "Configuration for X25519MLKEM768 on Apache httpd, Caddy, HAProxy and behind Cloudflare, with the version each one needs.",
            "body": """
<p>Every server below negotiates the same hybrid group, <code>X25519MLKEM768</code> (X25519 combined with ML-KEM-768 from FIPS 203). What differs is which crypto library it uses and whether the group is on by default. For nginx see the <a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx guide</a>.</p>

<h2>Apache httpd</h2>
<p>Needs mod_ssl linked against <strong>OpenSSL 3.5+</strong> (check with <code>openssl version</code> and <code>apachectl -V</code>). The group is on by default there; set it explicitly if your config already has a <code>Groups</code> or <code>SSLOpenSSLConfCmd Curves</code> line:</p>
<pre dir="ltr">SSLProtocol -all +TLSv1.2 +TLSv1.3
SSLOpenSSLConfCmd Groups X25519MLKEM768:X25519:prime256v1</pre>

<h2>Caddy</h2>
<p>Caddy uses Go's crypto/tls, which enables X25519MLKEM768 by default from <strong>Go 1.24</strong>. Caddy 2.10 and newer are built with it, so upgrading is usually all you need. Remove any <code>curves</code> option in the <code>tls</code> block, or include the hybrid group in it.</p>
<pre dir="ltr">caddy version   # 2.10 or newer
example.com {
    reverse_proxy 127.0.0.1:8000
}</pre>
<p>Any other Go server (Traefik, custom services) gets the same default once it is built with Go 1.24+.</p>

<h2>HAProxy</h2>
<p>Needs HAProxy built against OpenSSL 3.5+ or AWS-LC. Set the groups on the bind line:</p>
<pre dir="ltr">bind :443 ssl crt /etc/haproxy/certs/ curves X25519MLKEM768:X25519:P-256</pre>

<h2>Cloudflare and other CDNs</h2>
<p>Cloudflare negotiates X25519MLKEM768 with browsers on all plans by default. Proxy the domain through it (the orange cloud) and the connection between the visitor and Cloudflare is post-quantum even if your origin is not. The hop from Cloudflare to your origin is a separate connection: upgrade the origin as well if that link crosses the public internet.</p>
<p>This is the fastest fix for an old server you cannot upgrade.</p>

<h2>Verify</h2>
<p>Run the <a href="/?lang=en">free scan</a>. Grade A means TLS 1.3 with a hybrid post-quantum key exchange. Grade B means TLS 1.3 with classical key exchange only.</p>
""",
        },
        "ar": {
            "title": "TLS المقاوم للكم على Apache وCaddy وHAProxy وCloudflare",
            "description": "إعدادات X25519MLKEM768 على Apache httpd وCaddy وHAProxy وخلف Cloudflare، والإصدار الذي يحتاجه كل منها.",
            "body": """
<p>كل الخوادم التالية تتفق على المجموعة الهجينة نفسها <code>X25519MLKEM768</code> (أي X25519 مع ML-KEM-768 من المعيار FIPS 203). الفرق هو مكتبة التشفير التي يستخدمها كل خادم وهل المجموعة مفعّلة افتراضياً. لـ nginx انظر <a href="/guides/enable-x25519mlkem768-nginx?lang=ar">دليل nginx</a>.</p>

<h2>Apache httpd</h2>
<p>يحتاج mod_ssl مبنياً على <strong>OpenSSL 3.5 أو أحدث</strong> (تحقق بـ <code>openssl version</code> و<code>apachectl -V</code>). المجموعة مفعّلة افتراضياً هناك؛ اكتبها صراحة إذا كان في إعداداتك سطر <code>Groups</code> أو <code>SSLOpenSSLConfCmd Curves</code>:</p>
<pre dir="ltr">SSLProtocol -all +TLSv1.2 +TLSv1.3
SSLOpenSSLConfCmd Groups X25519MLKEM768:X25519:prime256v1</pre>

<h2>Caddy</h2>
<p>يستخدم Caddy مكتبة crypto/tls في Go، وهي تفعّل X25519MLKEM768 افتراضياً منذ <strong>Go 1.24</strong>. الإصدار Caddy 2.10 وما بعده مبني عليها، فالترقية تكفي غالباً. احذف خيار <code>curves</code> من كتلة <code>tls</code> أو أضف المجموعة الهجينة إليه.</p>
<pre dir="ltr">caddy version   # 2.10 أو أحدث
example.com {
    reverse_proxy 127.0.0.1:8000
}</pre>
<p>أي خادم آخر مكتوب بـ Go (مثل Traefik أو خدماتك الخاصة) يحصل على الإعداد نفسه عند بنائه بـ Go 1.24 أو أحدث.</p>

<h2>HAProxy</h2>
<p>يحتاج HAProxy مبنياً على OpenSSL 3.5 أو AWS-LC. حدد المجموعات في سطر bind:</p>
<pre dir="ltr">bind :443 ssl crt /etc/haproxy/certs/ curves X25519MLKEM768:X25519:P-256</pre>

<h2>Cloudflare وشبكات CDN الأخرى</h2>
<p>تتفق Cloudflare مع المتصفحات على X25519MLKEM768 افتراضياً في كل الخطط. مرّر النطاق عبرها (السحابة البرتقالية) فيصبح الاتصال بين الزائر وCloudflare مقاوماً للكم حتى لو لم يكن خادمك كذلك. الاتصال من Cloudflare إلى خادمك منفصل: رقِّ خادمك أيضاً إذا كان هذا الاتصال يمر عبر الإنترنت العام.</p>
<p>هذا أسرع حل لخادم قديم لا تستطيع ترقيته.</p>

<h2>التحقق</h2>
<p>شغّل <a href="/?lang=ar">الفحص المجاني</a>. الدرجة A تعني TLS 1.3 مع تبادل مفاتيح هجين مقاوم للكم، والدرجة B تعني TLS 1.3 مع تبادل مفاتيح تقليدي فقط.</p>
""",
        },
    },
    "harvest-now-decrypt-later": {
        "updated": "2026-11-03",
        "en": {
            "title": "Harvest now, decrypt later: why key exchange comes first",
            "description": "What the harvest-now-decrypt-later threat is, why it makes post-quantum key exchange urgent today, and why certificates can wait.",
            "body": """
<p>A quantum computer large enough to run Shor's algorithm would break RSA and elliptic-curve cryptography. None exists yet. The reason to act before it does is simple: encrypted traffic can be recorded now and stored until it can be decrypted.</p>

<h2>What gets exposed</h2>
<p>In TLS, the <strong>key exchange</strong> decides the session keys that encrypt everything. With classical X25519 or ECDHE, someone who recorded the handshake and the traffic can recover those keys with a future quantum computer and read the whole session: logins, API tokens, personal data, business documents.</p>
<p>The <strong>certificate</strong> only proves who the server is at the moment of connection. Breaking it later does not reveal past traffic. It matters for live impersonation once a quantum computer exists, not for data recorded today.</p>
<p>That is why browsers moved key exchange first. Chrome, Firefox, Edge and Safari's newer releases offer the hybrid <code>X25519MLKEM768</code>, and post-quantum certificates are still being standardised for the web.</p>

<h2>Who should care now</h2>
<p>Anyone whose data must stay confidential for years: health and financial records, legal and government communication, trade secrets, long-lived credentials. If the data will still be sensitive when a large quantum computer arrives, recording it today is already the attack.</p>

<h2>Why hybrid</h2>
<p><code>X25519MLKEM768</code> combines classical X25519 with ML-KEM-768 (NIST FIPS 203, August 2024). An attacker has to break both. If a flaw is ever found in the newer ML-KEM, the connection is still as strong as today's X25519.</p>

<h2>What to do</h2>
<ol>
<li><a href="/?lang=en">Scan your domain</a> to see whether it negotiates the hybrid group today.</li>
<li>Enable it: <a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx</a> or <a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=en">Apache, Caddy, HAProxy, Cloudflare</a>.</li>
<li>Plan for post-quantum certificates later, when CAs and browsers support them.</li>
</ol>
""",
        },
        "ar": {
            "title": "احفظ الآن، فُكّ لاحقاً: لماذا يأتي تبادل المفاتيح أولاً",
            "description": "ما هو تهديد «احفظ الآن، فُكّ لاحقاً»، ولماذا يجعل تبادل المفاتيح المقاوم للكم أمراً عاجلاً اليوم، ولماذا تستطيع الشهادات الانتظار.",
            "body": """
<p>حاسوب كمومي كبير بما يكفي لتشغيل خوارزمية Shor سيكسر RSA والتشفير بالمنحنيات الإهليلجية. لا يوجد مثله بعد. والسبب في التحرك قبل وجوده بسيط: يمكن تسجيل حركة المرور المشفرة الآن وتخزينها حتى يصبح فكها ممكناً.</p>

<h2>ما الذي ينكشف</h2>
<p>في TLS، <strong>تبادل المفاتيح</strong> هو ما يحدد مفاتيح الجلسة التي تشفر كل شيء. مع X25519 أو ECDHE التقليدي، من سجّل المصافحة والحركة يستطيع استخراج هذه المفاتيح بحاسوب كمومي مستقبلي وقراءة الجلسة كاملة: كلمات المرور ومفاتيح API والبيانات الشخصية ووثائق العمل.</p>
<p>أما <strong>الشهادة</strong> فتثبت هوية الخادم لحظة الاتصال فقط. كسرها لاحقاً لا يكشف الحركة السابقة. أهميتها في انتحال الموقع لحظياً بعد وجود حاسوب كمومي، لا في البيانات المسجلة اليوم.</p>
<p>لهذا بدأت المتصفحات بتبادل المفاتيح. Chrome وFirefox وEdge والإصدارات الأحدث من Safari تعرض المجموعة الهجينة <code>X25519MLKEM768</code>، بينما ما زالت الشهادات المقاومة للكم قيد التوحيد للويب.</p>

<h2>من يجب أن يهتم الآن</h2>
<p>كل من يجب أن تبقى بياناته سرية لسنوات: السجلات الصحية والمالية، والمراسلات القانونية والحكومية، والأسرار التجارية، وبيانات الدخول طويلة العمر. إذا كانت البيانات ستبقى حساسة حين يصل الحاسوب الكمومي الكبير، فتسجيلها اليوم هو الهجوم نفسه.</p>

<h2>لماذا «هجين»</h2>
<p>تجمع <code>X25519MLKEM768</code> بين X25519 التقليدي وML-KEM-768 (المعيار NIST FIPS 203، أغسطس 2024). على المهاجم كسر الاثنين معاً. ولو ظهر خلل في ML-KEM الأحدث يبقى الاتصال بقوة X25519 الحالية.</p>

<h2>ماذا تفعل</h2>
<ol>
<li><a href="/?lang=ar">افحص نطاقك</a> لترى هل يتفق على المجموعة الهجينة اليوم.</li>
<li>فعّلها: <a href="/guides/enable-x25519mlkem768-nginx?lang=ar">nginx</a> أو <a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=ar">Apache وCaddy وHAProxy وCloudflare</a>.</li>
<li>خطط للشهادات المقاومة للكم لاحقاً، عندما تدعمها جهات الإصدار والمتصفحات.</li>
</ol>
""",
        },
    },
    "enterprise-pq-tls-readiness": {
        "updated": "2026-11-08",
        "en": {
            "title": "An enterprise checklist for post-quantum TLS readiness",
            "description": "Inventory public TLS endpoints, assess hybrid key exchange, prioritize long-lived sensitive data, and track remediation without overstating scan results.",
            "body": """
<p>A TLS scan is a useful inventory signal, not a certification. Use this checklist to decide which public endpoints to measure, how to interpret a hybrid key exchange result, and what evidence to retain for your security team. ML-KEM is standardized in <a href="https://csrc.nist.gov/pubs/fips/203/final" rel="noopener">NIST FIPS 203</a>; adopting a standardized algorithm does not by itself validate an entire service or its implementation.</p>

<h2>1. Build an endpoint inventory</h2>
<p>List the public hostnames that carry sensitive or business-critical traffic. Include customer portals, APIs, identity services, mail gateways, administrative interfaces, and vendor-managed subdomains. Record the owner, business function, data sensitivity, and the TLS termination point for each hostname.</p>
<p>Where a CDN, load balancer, WAF, or reverse proxy terminates TLS, record that edge separately from the origin. A public probe normally observes the connection from the probe to the public edge. It does not prove what the edge negotiates with the origin or what happens on internal links.</p>

<h2>2. Measure consistently</h2>
<ol>
<li>Check each hostname on port 443 from the same measurement service and record the observation date and result URL.</li>
<li>Keep the hostname, resolved address, protocol version, negotiated key-exchange group, certificate facts, and probe location together.</li>
<li>Repeat from another vantage point or test additional addresses when DNS, geographic routing, or a CDN can send clients to different TLS configurations.</li>
<li>Run a separate origin-side test from an authorized network if you need to assess the edge-to-origin connection.</li>
</ol>
<p><a href="/?lang=en">Run a public TLS check</a>, review the <a href="/sample-report?lang=en">sample report</a>, or see <a href="/business?lang=en">business monitoring options</a>.</p>

<h2>3. Interpret post-quantum evidence narrowly</h2>
<p>A negotiated hybrid group such as <code>X25519MLKEM768</code> is evidence about key establishment on that observed TLS connection. It is not evidence that the certificate is post-quantum, that every client and endpoint uses the same group, or that the application is free of vulnerabilities. Keep certificate findings, protocol policy, application security, and key-exchange results as separate controls.</p>
<p>Prioritize systems whose encrypted data must remain confidential for many years. Coordinate upgrades with the teams operating the TLS terminator and check compatibility with older clients, middleboxes, and inspection equipment.</p>

<h2>4. Track remediation and exceptions</h2>
<p>For each finding, capture the affected hostname and TLS termination point, the observed behavior, an accountable owner, a target date, and the retest result. Treat a failed or inconclusive probe as unknown until the cause is understood; do not record it as proof that an endpoint lacks support.</p>
<p>After a change, repeat the measurement and retain both the previous and current evidence. Recheck after CDN policy changes, certificate renewals, proxy migrations, and major server upgrades. Teams that need recurring coverage can review <a href="/monitoring?lang=en">continuous monitoring</a>.</p>

<h2>Measurement limits</h2>
<p>This service measures one public IPv4 endpoint and port 443 per scan. DNS and routing may expose other endpoints, and a CDN result describes the client-to-CDN connection rather than the origin. A scan is a point-in-time observation, not a penetration test, compliance attestation, or guarantee of security.</p>
""",
        },
        "ar": {
            "title": "قائمة تحقق للشركات لقياس جاهزية TLS لما بعد الكم",
            "description": "احصر نقاط TLS العامة، وافهم التبادل الهجين، ورتّب البيانات طويلة الحساسية، وتابع المعالجة دون المبالغة في دلالة الفحص.",
            "body": """
<p>فحص TLS إشارة مفيدة للجرد، لكنه ليس شهادة اعتماد. تساعدك هذه القائمة على تحديد النطاقات التي ينبغي قياسها، وفهم نتيجة تبادل المفاتيح الهجين، وحفظ الأدلة لفريق الأمن. يحدد <a href="https://csrc.nist.gov/pubs/fips/203/final" rel="noopener">معيار NIST FIPS 203</a> خوارزمية ML-KEM؛ واتباع معيار لا يثبت وحده سلامة الخدمة كاملة أو صحة تطبيقها.</p>

<h2>١. أنشئ جردًا لنقاط الاتصال</h2>
<p>أحصِ أسماء النطاقات العامة التي تنقل بيانات حساسة أو تشغّل أعمالًا أساسية. أدرج بوابات العملاء وواجهات API وخدمات الهوية وبوابات البريد ولوحات الإدارة والنطاقات الفرعية التي يديرها الموردون. سجّل مالك كل نطاق ووظيفته وحساسية بياناته والجهة التي تنهي اتصال TLS.</p>
<p>إذا أنهى CDN أو موازن حمل أو جدار حماية تطبيقي أو وكيل عكسي اتصال TLS، فسجّل نقطة الحافة منفصلة عن الخادم الأصلي. الفحص العام يرصد عادةً الاتصال بين أداة القياس والحافة العامة؛ ولا يثبت إعداد الاتصال من الحافة إلى الأصل أو الاتصالات الداخلية.</p>

<h2>٢. قِس بطريقة ثابتة</h2>
<ol>
<li>افحص كل نطاق على المنفذ 443 بالأداة نفسها، واحفظ تاريخ القياس ورابط النتيجة.</li>
<li>اجمع اسم النطاق وعنوان IP الذي جرى حله وإصدار البروتوكول ومجموعة تبادل المفاتيح المتفق عليها وبيانات الشهادة وموقع نقطة القياس.</li>
<li>أعد القياس من نقطة أخرى أو اختبر عناوين إضافية عندما يوزع DNS أو التوجيه الجغرافي أو CDN العملاء على إعدادات TLS مختلفة.</li>
<li>إذا أردت تقييم اتصال الحافة بالخادم الأصلي، فنفّذ فحصًا منفصلًا من شبكة مخوّلة.</li>
</ol>
<p><a href="/?lang=ar">ابدأ فحص TLS عامًا</a>، وراجع <a href="/sample-report?lang=ar">التقرير النموذجي</a> أو <a href="/business?lang=ar">خيارات المراقبة للشركات</a>.</p>

<h2>٣. فسّر دليل ما بعد الكم ضمن حدوده</h2>
<p>التفاوض على مجموعة هجينة مثل <code>X25519MLKEM768</code> دليل على إنشاء المفاتيح في اتصال TLS الذي جرى رصده. لكنه لا يثبت أن الشهادة مقاومة للكم، أو أن كل العملاء والنقاط تستخدم المجموعة نفسها، أو أن التطبيق خالٍ من الثغرات. تعامل مع الشهادة وسياسة البروتوكول وأمن التطبيق وتبادل المفاتيح بوصفها ضوابط منفصلة.</p>
<p>أعطِ الأولوية للأنظمة التي يجب أن تظل بياناتها المشفرة سرية لسنوات طويلة. نسّق التحديثات مع فرق تشغيل نقطة إنهاء TLS، واختبر التوافق مع العملاء الأقدم وأجهزة الشبكة وأنظمة فحص الاتصالات.</p>

<h2>٤. تابع المعالجة والاستثناءات</h2>
<p>لكل نتيجة، سجّل اسم النطاق ونقطة إنهاء TLS المتأثرة والسلوك المرصود والمالك المسؤول والموعد المستهدف ونتيجة إعادة الفحص. إذا فشل الفحص أو لم يحسم النتيجة، فسجّلها «غير محددة» إلى أن يتضح السبب؛ لا تعتبرها دليلاً على غياب الدعم.</p>
<p>بعد التغيير، أعد القياس واحفظ الدليلين السابق والحالي. كرر ذلك بعد تغييرات سياسة CDN وتجديد الشهادات ونقل الوكلاء والترقيات الرئيسية للخوادم. للمتابعة الدورية، راجع <a href="/monitoring?lang=ar">المراقبة المستمرة</a>.</p>

<h2>حدود القياس</h2>
<p>تقيس الخدمة نقطة IPv4 عامة واحدة والمنفذ 443 في كل فحص. قد يكشف DNS والتوجيه نقاطًا أخرى، ونتيجة CDN تصف الاتصال بين العميل وCDN لا الخادم الأصلي. الفحص ملاحظة في وقت محدد، وليس اختبار اختراق أو إقرار امتثال أو ضمانًا للأمان.</p>
""",
        },
    },
    "aws-alb-cloudfront-post-quantum-tls": {
        "updated": "2026-11-09",
        "en": {
            "title": "Post-quantum TLS on AWS: Application Load Balancer, NLB and CloudFront",
            "description": "Which AWS endpoints negotiate X25519MLKEM768, the exact ELB security policy to select, and why load balancers created with Terraform, CDK or the CLI are still classical.",
            "body": """
<p>In our <a href="/adoption/hosting?lang=en">hosting tracker</a>, only about 7% of top-10,000 sites on AWS's EC2 network (AS14618) negotiate post-quantum key exchange, against about 61% on AS16509, where CloudFront and the load balancers live. On AWS the answer depends on <em>which</em> endpoint terminates TLS and <em>how</em> it was created.</p>

<h2>CloudFront: already on</h2>
<p>For connections between browsers and CloudFront, AWS lists <code>X25519MLKEM768</code> and <code>SecP256r1MLKEM768</code> as supported quantum-safe key exchanges. There is nothing to configure. Two limits: hybrid key exchange works only over <strong>TLS 1.3</strong>, and it covers the viewer connection, not the separate connection from CloudFront to your origin.</p>

<h2>Application and Network Load Balancers: choose a PQ policy</h2>
<p>ELB security policies with <code>PQ</code> in their name offer hybrid post-quantum key exchange (<code>X25519MLKEM768</code>, <code>SecP256r1MLKEM768</code>, <code>SecP384r1MLKEM1024</code>) alongside the classical groups, so older clients keep working. AWS recommends:</p>
<pre dir="ltr">ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09        # TLS 1.3 + 1.2, hybrid PQ
ELBSecurityPolicy-TLS13-1-2-Res-FIPS-PQ-2025-09   # same, FIPS</pre>
<p><strong>The trap:</strong> the console now defaults to the PQ policy, but listeners created with the AWS CLI, CloudFormation or the CDK still default to <code>ELBSecurityPolicy-2016-08</code>, which has no post-quantum key exchange. Infrastructure-as-code setups are therefore usually classical until you set the policy explicitly.</p>
<p>AWS CLI:</p>
<pre dir="ltr">aws elbv2 modify-listener \\
  --listener-arn arn:aws:elasticloadbalancing:...:listener/app/my-alb/... \\
  --ssl-policy ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09</pre>
<p>Terraform:</p>
<pre dir="ltr">resource "aws_lb_listener" "https" {
  # ...
  protocol   = "HTTPS"
  ssl_policy = "ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09"
}</pre>
<p>Application Load Balancers do not support custom security policies, so pick one of the predefined <code>PQ</code> policies.</p>

<h2>EC2 instances and containers: it is your OpenSSL</h2>
<p>If TLS ends on the instance itself (nginx, Apache, Node.js, Java), AWS has no say: the server software and its TLS library decide. Ubuntu 22.04 and 24.04 ship OpenSSL 3.0, which cannot negotiate ML-KEM. Either upgrade to a stack with OpenSSL 3.5 (see the <a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx guide</a>) or put a PQ-enabled ALB or CloudFront in front.</p>

<h2>Verify</h2>
<pre dir="ltr">openssl s_client -connect example.com:443 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -i group</pre>
<p>This needs an OpenSSL 3.5 client. Or run the <a href="/?lang=en">free scan</a>; grade A means TLS 1.3 with a hybrid post-quantum key exchange. ALB connection logs also record the negotiated key exchange (log field 13).</p>
<p class="muted small">Sources: AWS documentation "Security policies for your Application Load Balancer" and "Supported protocols and ciphers between viewers and CloudFront", checked 2026-11-09.</p>
""",
        },
        "ar": {
            "title": "TLS المقاوم للكم على AWS: موازن التحميل ALB وNLB وCloudFront",
            "description": "أي نقاط AWS تتفق على X25519MLKEM768، وسياسة ELB الدقيقة التي تختارها، ولماذا تبقى موازنات التحميل المنشأة بـ Terraform أو CDK أو CLI كلاسيكية.",
            "body": """
<p>في <a href="/adoption/hosting?lang=ar">متتبّع الاستضافة</a> نجد أن نحو 7% فقط من مواقع أكبر 10,000 موقع على شبكة خوادم EC2 (AS14618) تتفق على تبادل مفاتيح ما بعد الكم، مقابل نحو 61% على AS16509 حيث يعمل CloudFront وموازنات التحميل. على AWS يتوقف الأمر على <em>أي</em> نقطة تُنهي اتصال TLS و<em>كيف</em> أُنشئت.</p>

<h2>CloudFront: مفعّل أصلاً</h2>
<p>للاتصال بين المتصفح وCloudFront تذكر AWS أن <code>X25519MLKEM768</code> و<code>SecP256r1MLKEM768</code> مدعومان. لا شيء تضبطه. حدّان: التبادل الهجين يعمل فقط مع <strong>TLS 1.3</strong>، ويشمل اتصال الزائر لا الاتصال المنفصل من CloudFront إلى خادمك الأصلي.</p>

<h2>موازنات التحميل ALB وNLB: اختر سياسة PQ</h2>
<p>سياسات أمان ELB التي في اسمها <code>PQ</code> تعرض تبادل المفاتيح الهجين (<code>X25519MLKEM768</code> و<code>SecP256r1MLKEM768</code> و<code>SecP384r1MLKEM1024</code>) إلى جانب المجموعات الكلاسيكية، فتبقى العملاء القديمة تعمل. توصي AWS بـ:</p>
<pre dir="ltr">ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09        # TLS 1.3 + 1.2, hybrid PQ
ELBSecurityPolicy-TLS13-1-2-Res-FIPS-PQ-2025-09   # same, FIPS</pre>
<p><strong>الفخ:</strong> لوحة التحكم تختار سياسة PQ افتراضياً الآن، لكن المستمعات (listeners) المنشأة بـ AWS CLI أو CloudFormation أو CDK ما زالت تأخذ افتراضياً <code>ELBSecurityPolicy-2016-08</code> التي لا تدعم ما بعد الكم. لذلك تبقى إعدادات البنية ككود كلاسيكية عادةً حتى تحدد السياسة صراحة.</p>
<p>AWS CLI:</p>
<pre dir="ltr">aws elbv2 modify-listener \\
  --listener-arn arn:aws:elasticloadbalancing:...:listener/app/my-alb/... \\
  --ssl-policy ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09</pre>
<p>Terraform:</p>
<pre dir="ltr">resource "aws_lb_listener" "https" {
  # ...
  protocol   = "HTTPS"
  ssl_policy = "ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09"
}</pre>
<p>موازن ALB لا يقبل سياسات مخصصة، فاختر إحدى سياسات <code>PQ</code> الجاهزة.</p>

<h2>خوادم EC2 والحاويات: القرار لـ OpenSSL عندك</h2>
<p>إذا انتهى TLS على الخادم نفسه (nginx أو Apache أو Node.js أو Java) فلا دور لـ AWS: برنامج الخادم ومكتبة TLS فيه هما من يقرر. Ubuntu 22.04 و24.04 يأتيان بـ OpenSSL 3.0 الذي لا يدعم ML-KEM. إما أن ترقّي إلى بيئة فيها OpenSSL 3.5 (انظر <a href="/guides/enable-x25519mlkem768-nginx?lang=ar">دليل nginx</a>)، أو تضع ALB أو CloudFront مفعّلاً أمام الخادم.</p>

<h2>التحقق</h2>
<pre dir="ltr">openssl s_client -connect example.com:443 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -i group</pre>
<p>يحتاج عميل OpenSSL 3.5. أو استخدم <a href="/?lang=ar">الفحص المجاني</a>: الدرجة A تعني TLS 1.3 مع تبادل مفاتيح هجين. وسجلات اتصال ALB تسجّل أيضاً تبادل المفاتيح المتفق عليه (الحقل 13).</p>
<p class="muted small">المصادر: وثائق AWS «Security policies for your Application Load Balancer» و«Supported protocols and ciphers between viewers and CloudFront»، راجعناها في 2026-11-09.</p>
""",
        },
    },
    "nodejs-post-quantum-tls-x25519mlkem768": {
        "updated": "2026-11-09",
        "en": {
            "title": "Post-quantum TLS in Node.js (X25519MLKEM768): versions, config and checks",
            "description": "Node.js 24 official builds include OpenSSL 3.5, which offers X25519MLKEM768 by default. How to check your build, avoid the ecdhCurve trap and verify the handshake.",
            "body": """
<p>Node.js does its own TLS through the OpenSSL library it was built with. Since <strong>OpenSSL 3.5</strong>, the default TLS key shares offer the hybrid <code>X25519MLKEM768</code> and plain X25519, so a Node.js HTTPS server on OpenSSL 3.5 is post-quantum ready without code changes.</p>

<h2>1. Check which OpenSSL your Node.js uses</h2>
<pre dir="ltr">node -p process.versions.openssl</pre>
<p>Official Node.js 24 LTS binaries include OpenSSL 3.5. Node.js packages from Linux distributions are often linked against the system OpenSSL instead (3.0 on Ubuntu 22.04 and 24.04), so the same Node major version can behave differently. Anything below 3.5 cannot negotiate ML-KEM.</p>

<h2>2. Don't pin the curve list</h2>
<p>By default <code>ecdhCurve</code> is <code>'auto'</code>, which uses OpenSSL's defaults and therefore includes the hybrid group. Old hardening snippets often set something like <code>ecdhCurve: 'prime256v1'</code>, which silently removes it. Either delete the option or list the hybrid group first:</p>
<pre dir="ltr">const https = require('node:https');
https.createServer({
  key, cert,
  minVersion: 'TLSv1.2',
  ecdhCurve: 'X25519MLKEM768:X25519:prime256v1',
}, app).listen(443);</pre>

<h2>3. Behind a proxy, the proxy decides</h2>
<p>If nginx, a load balancer or a CDN terminates TLS in front of Node.js, browsers never talk TLS to Node.js directly; configure that layer instead (<a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx</a>, <a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=en">AWS ALB/CloudFront</a>).</p>

<h2>4. Outgoing requests</h2>
<p>The same rule applies when Node.js is the client (<code>fetch</code>, <code>https.request</code>): on OpenSSL 3.5 it offers X25519MLKEM768 to servers that support it.</p>

<h2>Verify</h2>
<pre dir="ltr">openssl s_client -connect example.com:443 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -i group</pre>
<p>Or run the <a href="/?lang=en">free scan</a>; grade A means TLS 1.3 with a hybrid post-quantum key exchange.</p>
<p class="muted small">Sources: Node.js "v22 to v24" migration guide; OpenSSL 3.5 release notes. Checked 2026-11-09.</p>
""",
        },
        "ar": {
            "title": "TLS المقاوم للكم في Node.js (X25519MLKEM768): الإصدارات والإعداد والتحقق",
            "description": "نسخ Node.js 24 الرسمية تأتي مع OpenSSL 3.5 الذي يعرض X25519MLKEM768 افتراضياً. كيف تتحقق من نسختك، وتتجنب فخ ecdhCurve، وتتأكد من الاتصال.",
            "body": """
<p>يتولى Node.js تشفير TLS بنفسه عبر مكتبة OpenSSL التي بُني عليها. منذ <strong>OpenSSL 3.5</strong> تعرض مفاتيح TLS الافتراضية المجموعة الهجينة <code>X25519MLKEM768</code> وX25519 العادي، فخادم HTTPS في Node.js على OpenSSL 3.5 جاهز لما بعد الكم دون تعديل في الكود.</p>

<h2>1. تحقق من نسخة OpenSSL في Node.js عندك</h2>
<pre dir="ltr">node -p process.versions.openssl</pre>
<p>نسخ Node.js 24 LTS الرسمية تأتي مع OpenSSL 3.5. أما حزم Node.js من توزيعات Linux فغالباً مربوطة بـ OpenSSL النظام (3.0 في Ubuntu 22.04 و24.04)، فقد يتصرف الإصدار نفسه بشكل مختلف. أي نسخة أقل من 3.5 لا تدعم ML-KEM.</p>

<h2>2. لا تثبّت قائمة المنحنيات</h2>
<p>القيمة الافتراضية لـ <code>ecdhCurve</code> هي <code>'auto'</code> فتستخدم إعدادات OpenSSL وتشمل المجموعة الهجينة. مقتطفات الحماية القديمة تضع غالباً <code>ecdhCurve: 'prime256v1'</code> فتحذفها دون أن تشعر. احذف الخيار، أو ضع المجموعة الهجينة أولاً:</p>
<pre dir="ltr">const https = require('node:https');
https.createServer({
  key, cert,
  minVersion: 'TLSv1.2',
  ecdhCurve: 'X25519MLKEM768:X25519:prime256v1',
}, app).listen(443);</pre>

<h2>3. خلف وكيل، الوكيل هو من يقرر</h2>
<p>إذا كان nginx أو موازن تحميل أو CDN يُنهي TLS أمام Node.js فالمتصفح لا يتصل بـ Node.js مباشرة؛ اضبط تلك الطبقة بدلاً منه (<a href="/guides/enable-x25519mlkem768-nginx?lang=ar">nginx</a>، <a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=ar">AWS ALB/CloudFront</a>).</p>

<h2>4. الطلبات الصادرة</h2>
<p>القاعدة نفسها حين يكون Node.js هو العميل (<code>fetch</code> و<code>https.request</code>): على OpenSSL 3.5 يعرض X25519MLKEM768 على الخوادم التي تدعمه.</p>

<h2>التحقق</h2>
<pre dir="ltr">openssl s_client -connect example.com:443 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -i group</pre>
<p>أو استخدم <a href="/?lang=ar">الفحص المجاني</a>: الدرجة A تعني TLS 1.3 مع تبادل مفاتيح هجين.</p>
<p class="muted small">المصادر: دليل الترحيل «v22 to v24» من Node.js، وملاحظات إصدار OpenSSL 3.5. راجعناها في 2026-11-09.</p>
""",
        },
    },
    "java-post-quantum-tls-jdk27": {
        "updated": "2026-11-09",
        "en": {
            "title": "Post-quantum TLS in Java: X25519MLKEM768 in JDK 27 (JEP 527)",
            "description": "JDK 27 adds hybrid ML-KEM key exchange to TLS 1.3 and enables X25519MLKEM768 by default. What changes for Tomcat, Spring Boot and HTTP clients, and what to do on JDK 21 or 25.",
            "body": """
<p><strong>JEP 527</strong> brings hybrid post-quantum key exchange to Java's built-in TLS (SunJSSE) in <strong>JDK 27</strong>, released in September 2026. It adds three hybrid groups, <code>X25519MLKEM768</code>, <code>SecP256r1MLKEM768</code> and <code>SecP384r1MLKEM1024</code>, and enables <code>X25519MLKEM768</code> by default next to the classical groups.</p>

<h2>What you get without code changes</h2>
<p>Applications using the standard <code>javax.net.ssl</code> APIs (embedded Tomcat, Jetty or Undertow on JSSE, <code>java.net.http.HttpClient</code>, <code>HttpsURLConnection</code>) negotiate X25519MLKEM768 on JDK 27 automatically, as long as they do not override the named groups. As a client, JDK 27 sends two key shares: one X25519MLKEM768 and one x25519.</p>

<h2>Check for overrides</h2>
<p>Look for the system property <code>jdk.tls.namedGroups</code> (in start scripts, <code>JAVA_TOOL_OPTIONS</code> or container env) and for <code>SSLParameters.setNamedGroups(...)</code> in code. A list without the hybrid group turns it off. If you set it, put the hybrid group first:</p>
<pre dir="ltr">-Djdk.tls.namedGroups=X25519MLKEM768,x25519,secp256r1,secp384r1</pre>

<h2>On JDK 21 or JDK 25 (LTS)</h2>
<p>These releases have no hybrid ML-KEM key exchange in SunJSSE. JDK 27 is a short-term release, so many teams will stay on an LTS. The practical route is to terminate TLS in front of the JVM on a component that supports it: nginx with OpenSSL 3.5, a PQ-enabled AWS load balancer or a CDN (see <a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx</a> and <a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=en">AWS</a>).</p>

<h2>Verify</h2>
<pre dir="ltr">java -version
openssl s_client -connect example.com:443 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -i group</pre>
<p>Or run the <a href="/?lang=en">free scan</a>; grade A means TLS 1.3 with a hybrid post-quantum key exchange.</p>
<p class="muted small">Sources: OpenJDK JEP 527 and the Inside Java article "Post-Quantum Hybrid Key Exchange for TLS 1.3" (2026-02-17). Checked 2026-11-09.</p>
""",
        },
        "ar": {
            "title": "TLS المقاوم للكم في Java: ‏X25519MLKEM768 في JDK 27 (JEP 527)",
            "description": "يضيف JDK 27 تبادل المفاتيح الهجين ML-KEM إلى TLS 1.3 ويفعّل X25519MLKEM768 افتراضياً. ما الذي يتغير في Tomcat وSpring Boot وعملاء HTTP، وماذا تفعل على JDK 21 أو 25.",
            "body": """
<p>يضيف <strong>JEP 527</strong> تبادل المفاتيح الهجين لما بعد الكم إلى TLS المدمج في Java ‏(SunJSSE) في <strong>JDK 27</strong> الذي صدر في سبتمبر 2026. يضيف ثلاث مجموعات هجينة: <code>X25519MLKEM768</code> و<code>SecP256r1MLKEM768</code> و<code>SecP384r1MLKEM1024</code>، ويفعّل <code>X25519MLKEM768</code> افتراضياً بجانب المجموعات الكلاسيكية.</p>

<h2>ما تحصل عليه دون تعديل الكود</h2>
<p>التطبيقات التي تستخدم واجهات <code>javax.net.ssl</code> القياسية (Tomcat أو Jetty أو Undertow المدمجة على JSSE، و<code>java.net.http.HttpClient</code>، و<code>HttpsURLConnection</code>) تتفق على X25519MLKEM768 تلقائياً على JDK 27 ما لم تغيّر قائمة المجموعات. وكعميل يرسل JDK 27 مفتاحين: واحد X25519MLKEM768 وآخر x25519.</p>

<h2>ابحث عن الإعدادات التي تلغيه</h2>
<p>ابحث عن الخاصية <code>jdk.tls.namedGroups</code> (في سكربتات التشغيل أو <code>JAVA_TOOL_OPTIONS</code> أو متغيرات الحاوية) وعن <code>SSLParameters.setNamedGroups(...)</code> في الكود. قائمة لا تحتوي المجموعة الهجينة تلغيها. إن ضبطتها فضع المجموعة الهجينة أولاً:</p>
<pre dir="ltr">-Djdk.tls.namedGroups=X25519MLKEM768,x25519,secp256r1,secp384r1</pre>

<h2>على JDK 21 أو JDK 25 (LTS)</h2>
<p>هذه الإصدارات لا تملك تبادل المفاتيح الهجين في SunJSSE. وJDK 27 إصدار قصير الدعم، فكثير من الفرق ستبقى على إصدار LTS. الحل العملي أن يُنهى TLS أمام JVM على مكوّن يدعمه: nginx مع OpenSSL 3.5، أو موازن تحميل AWS مفعّل، أو CDN (انظر <a href="/guides/enable-x25519mlkem768-nginx?lang=ar">nginx</a> و<a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=ar">AWS</a>).</p>

<h2>التحقق</h2>
<pre dir="ltr">java -version
openssl s_client -connect example.com:443 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -i group</pre>
<p>أو استخدم <a href="/?lang=ar">الفحص المجاني</a>: الدرجة A تعني TLS 1.3 مع تبادل مفاتيح هجين.</p>
<p class="muted small">المصادر: OpenJDK JEP 527، ومقال Inside Java «Post-Quantum Hybrid Key Exchange for TLS 1.3» ‏(2026-02-17). راجعناها في 2026-11-09.</p>
""",
        },
    },
}
