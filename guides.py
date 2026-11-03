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
}
