# guides.py
# صفحات الأدلة التقنية (عربي / إنجليزي). المحتوى HTML مكتوب يدوياً هنا، لا يأتي من المستخدم.

GUIDES = {
    "enable-x25519mlkem768-nginx": {
        "updated": "2026-11-21",
        "en": {
            "title": "How to enable post-quantum TLS (X25519MLKEM768) on nginx",
            "description": "Turn on the hybrid ML-KEM key exchange that Chrome and Firefox already use, on nginx with OpenSSL 3.5, and verify it.",
            "body": """
<p>Chrome (since version 131) and Firefox already offer the hybrid key exchange <code>X25519MLKEM768</code> in every HTTPS connection. If your server accepts it, the session keys are protected against a future quantum computer. If it does not, the browser falls back to plain X25519 and the traffic can be recorded today and decrypted later (<a href="/guides/harvest-now-decrypt-later?lang=en">harvest now, decrypt later</a>).</p>

<div class="card"><p><strong>Security release, 18 November 2026:</strong> nginx 1.30.7 (stable) and 1.31.9 (mainline) fix ten vulnerabilities, including memory corruption in HTTP/2 flow control (CVE-2026-123007) and use-after-free in HTTP/2 (CVE-2026-123633) (<a href="https://nginx.org/news.html" rel="noopener">nginx.org</a>). Update first, and check the version you actually run with <code>nginx -v</code>: distribution packages and container images can lag behind. Updating nginx does <strong>not</strong> by itself enable post-quantum TLS, because that depends on the OpenSSL version nginx is built against (step 1). Use the same maintenance window for both.</p></div>

<h2>1. Check your OpenSSL version</h2>
<p>nginx gets its TLS from the OpenSSL library it was built against. ML-KEM arrived in <strong>OpenSSL 3.5</strong>.</p>
<pre dir="ltr">nginx -V 2>&amp;1 | grep -o 'OpenSSL [0-9.]*'
openssl version</pre>
<p>If either shows 3.0, 3.1, 3.2, 3.3 or 3.4, nginx cannot negotiate ML-KEM no matter what you put in the config. Ubuntu 22.04 and 24.04 ship OpenSSL 3.0; Debian 13 (trixie) ships 3.5. On Ubuntu, the <a href="/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=en">Ubuntu / OpenSSL 3.0 guide</a> walks through all three ways out. Your options are to upgrade the OS, use an nginx build linked against OpenSSL 3.5, or put a post-quantum capable proxy or CDN in front (see the <a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=en">other servers guide</a>).</p>

<h2>2. Configure nginx</h2>
<p>With OpenSSL 3.5, X25519MLKEM768 is in the default group list, so nginx's default <code>ssl_ecdh_curve auto</code> already offers it. The common mistake is an explicit curve list copied from an old hardening guide: it replaces OpenSSL's default list instead of extending it, and silently removes the hybrid. The cleanest fix is to delete that line. If you want an explicit list, put the hybrid group first:</p>
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

<h2>nginx won't start after adding X25519MLKEM768</h2>
<p>If <code>nginx -t</code> or a restart fails with an error like this:</p>
<pre dir="ltr">nginx: [emerg] SSL_CTX_set1_curves_list("X25519MLKEM768:X25519:prime256v1") failed</pre>
<p>then the OpenSSL that nginx actually uses does not know the group, which means it is older than 3.5. OpenSSL rejects the whole list when one name is unknown, so nginx stops while reading its configuration. Check the library nginx runs with, which can differ from the <code>openssl</code> command on the same machine:</p>
<pre dir="ltr">nginx -V 2&gt;&amp;1 | grep -i openssl</pre>
<ul>
<li><strong>Get the site back now:</strong> remove <code>X25519MLKEM768</code> from the line, or delete the <code>ssl_ecdh_curve</code> line entirely (safe on every OpenSSL version), then <code>nginx -t &amp;&amp; systemctl reload nginx</code>.</li>
<li><strong>Then get a newer OpenSSL:</strong> on Ubuntu 22.04 / 24.04 see <a href="/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=en">the Ubuntu guide</a> (upgrade to 26.04, put Caddy or a CDN in front, or build nginx with OpenSSL 3.5).</li>
<li><strong>Always run <code>nginx -t</code> first.</strong> A <code>reload</code> with a broken config keeps the old workers serving, but a <code>restart</code> or a reboot leaves the site down.</li>
</ul>

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

<div class="card"><p><strong>تحديث أمني، 18 نوفمبر 2026:</strong> يصلح nginx 1.30.7 (المستقر) و1.31.9 (الرئيسي) عشر ثغرات، منها إفساد الذاكرة في التحكم بتدفق HTTP/2 (CVE-2026-123007) واستخدام الذاكرة بعد تحريرها في HTTP/2 (CVE-2026-123633) (<a href="https://nginx.org/news.html" rel="noopener">nginx.org</a>). حدّث أولاً، وتحقق من الإصدار الذي يعمل فعلاً بالأمر <code>nginx -v</code>، فحزم التوزيعات وصور الحاويات قد تتأخر. تحديث nginx <strong>لا</strong> يفعّل وحده TLS المقاوم للكم، لأن ذلك يعتمد على إصدار OpenSSL الذي بُني عليه nginx (الخطوة 1). استغل نافذة الصيانة نفسها للأمرين.</p></div>

<h2>1. تحقق من إصدار OpenSSL</h2>
<p>يأخذ nginx تشفير TLS من مكتبة OpenSSL التي بُني عليها. دعم ML-KEM وصل في <strong>OpenSSL 3.5</strong>.</p>
<pre dir="ltr">nginx -V 2>&amp;1 | grep -o 'OpenSSL [0-9.]*'
openssl version</pre>
<p>إذا ظهر 3.0 أو 3.1 أو 3.2 أو 3.3 أو 3.4 فلن يستطيع nginx استخدام ML-KEM مهما كتبت في الإعدادات. Ubuntu 22.04 و24.04 يأتيان بـ OpenSSL 3.0، وDebian 13 (trixie) يأتي بـ 3.5. على Ubuntu يشرح <a href="/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=ar">دليل Ubuntu وOpenSSL 3.0</a> الطرق الثلاثة بالتفصيل. الحلول: ترقية النظام، أو نسخة nginx مبنية على OpenSSL 3.5، أو وضع وكيل أو CDN يدعم ما بعد الكم أمام الخادم (انظر <a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=ar">دليل الخوادم الأخرى</a>).</p>

<h2>2. إعداد nginx</h2>
<p>مع OpenSSL 3.5 تكون المجموعة X25519MLKEM768 ضمن القائمة الافتراضية، فالإعداد الافتراضي <code>ssl_ecdh_curve auto</code> يعرضها أصلاً. الخطأ الشائع هو قائمة منحنيات صريحة منسوخة من دليل حماية قديم: تحلّ محل القائمة الافتراضية لـ OpenSSL ولا تضيف إليها، فتحذف المجموعة الهجينة دون أن تشعر. أنظف حل هو حذف ذلك السطر. وإن أردت قائمة صريحة فضع المجموعة الهجينة أولاً:</p>
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

<h2>nginx لا يعمل بعد إضافة X25519MLKEM768</h2>
<p>إذا فشل <code>nginx -t</code> أو إعادة التشغيل برسالة مثل هذه:</p>
<pre dir="ltr">nginx: [emerg] SSL_CTX_set1_curves_list("X25519MLKEM768:X25519:prime256v1") failed</pre>
<p>فمكتبة OpenSSL التي يستخدمها nginx فعلاً لا تعرف هذه المجموعة، أي أنها أقدم من 3.5. ترفض OpenSSL القائمة كلها إذا كان فيها اسم واحد غير معروف، فيتوقف nginx أثناء قراءة إعداداته. تحقق من المكتبة التي يعمل بها nginx، فقد تختلف عن أمر <code>openssl</code> على نفس الجهاز:</p>
<pre dir="ltr">nginx -V 2&gt;&amp;1 | grep -i openssl</pre>
<ul>
<li><strong>أعِد الموقع للعمل الآن:</strong> احذف <code>X25519MLKEM768</code> من السطر، أو احذف سطر <code>ssl_ecdh_curve</code> كله (آمن على كل إصدارات OpenSSL)، ثم <code>nginx -t &amp;&amp; systemctl reload nginx</code>.</li>
<li><strong>ثم احصل على OpenSSL أحدث:</strong> على Ubuntu 22.04 و24.04 راجع <a href="/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=ar">دليل Ubuntu</a> (الترقية إلى 26.04، أو Caddy أو CDN أمام الخادم، أو بناء nginx مع OpenSSL 3.5).</li>
<li><strong>شغّل <code>nginx -t</code> دائماً أولاً.</strong> أمر <code>reload</code> مع إعداد معطوب يُبقي العمليات القديمة تخدم الموقع، أما <code>restart</code> أو إعادة تشغيل الجهاز فتُسقط الموقع.</li>
</ul>

<h2>انتبه إلى</h2>
<ul>
<li><strong>رسالة ClientHello الكبيرة.</strong> مفتاح ML-KEM يزيد أول رسالة من المتصفح بنحو 1.2 كيلوبايت، فتمتد غالباً على حزمتي TCP. بعض الجدران النارية وموازنات الحمل القديمة تتوقعها في حزمة واحدة فتقطع الاتصال. الفحص يذكر هذا كنتيجة مستقلة.</li>
<li><strong>الشهادات مسألة منفصلة.</strong> شهادة RSA أو ECDSA قابلة للكسر بخوارزمية Shor، لكن هذا يهم فقط بعد وجود حاسوب كمومي وفقط لانتحال الموقع لحظياً. تبادل المفاتيح هو ما يحمي الحركة المسجلة، فابدأ به.</li>
</ul>
""",
        },
        "de": {
            "title": "So aktivieren Sie Post-Quantum-TLS (X25519MLKEM768) auf nginx",
            "description": "Aktivieren Sie den hybriden ML-KEM-Schlüsselaustausch, den Chrome und Firefox bereits nutzen, auf nginx mit OpenSSL 3.5, und prüfen Sie ihn.",
            "body": """
<p>Chrome (ab Version 131) und Firefox bieten den hybriden Schlüsselaustausch <code>X25519MLKEM768</code> bereits bei jeder HTTPS-Verbindung an. Akzeptiert Ihr Server ihn, sind die Sitzungsschlüssel gegen einen künftigen Quantencomputer geschützt. Akzeptiert er ihn nicht, fällt der Browser auf reines X25519 zurück, und der Datenverkehr kann heute aufgezeichnet und später entschlüsselt werden (<a href="/guides/harvest-now-decrypt-later?lang=en">Harvest now, decrypt later</a>).</p>

<h2>1. OpenSSL-Version prüfen</h2>
<p>nginx bezieht TLS aus der OpenSSL-Bibliothek, gegen die es gebaut wurde. ML-KEM gibt es ab <strong>OpenSSL 3.5</strong>.</p>
<pre dir="ltr">nginx -V 2>&amp;1 | grep -o 'OpenSSL [0-9.]*'
openssl version</pre>
<p>Zeigt einer der beiden Befehle 3.0, 3.1, 3.2, 3.3 oder 3.4, kann nginx ML-KEM nicht aushandeln, egal was in der Konfiguration steht. Ubuntu 22.04 und 24.04 liefern OpenSSL 3.0 aus, Debian 13 (trixie) liefert 3.5. Für Ubuntu beschreibt der <a href="/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=en">Leitfaden zu Ubuntu / OpenSSL 3.0</a> alle drei Auswege. Sie können das Betriebssystem aktualisieren, einen nginx-Build mit OpenSSL 3.5 verwenden oder einen Post-Quantum-fähigen Proxy bzw. ein CDN vorschalten (siehe den <a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=en">Leitfaden für andere Server</a>).</p>

<h2>2. nginx konfigurieren</h2>
<p>Mit OpenSSL 3.5 steht X25519MLKEM768 in der Standardliste der Gruppen, daher bietet nginx mit der Voreinstellung <code>ssl_ecdh_curve auto</code> die Gruppe bereits an. Der häufigste Fehler ist eine explizite Kurvenliste aus einer alten Hardening-Anleitung: Sie ersetzt die Standardliste von OpenSSL, statt sie zu erweitern, und entfernt die hybride Gruppe stillschweigend. Am saubersten ist es, diese Zeile zu löschen. Wenn Sie eine explizite Liste möchten, setzen Sie die hybride Gruppe an den Anfang:</p>
<pre dir="ltr">server {
    listen 443 ssl;
    http2 on;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;
    # ... certificates and the rest of your config
}</pre>
<p>Prüfen Sie auch eingebundene Dateien wie <code>/etc/letsencrypt/options-ssl-nginx.conf</code> auf eine weitere <code>ssl_ecdh_curve</code>-Zeile. Danach:</p>
<pre dir="ltr">nginx -t &amp;&amp; systemctl reload nginx</pre>

<h2>3. Überprüfen</h2>
<p>Mit einem OpenSSL-3.5-Client:</p>
<pre dir="ltr">openssl s_client -connect example.com:443 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -i group</pre>
<p>Als ausgehandelte Gruppe sollte <code>X25519MLKEM768</code> erscheinen. Oder nutzen Sie den <a href="/?lang=de">kostenlosen Scan</a>: Note A bedeutet TLS 1.3 mit hybridem Post-Quantum-Schlüsselaustausch.</p>

<h2>nginx startet nach dem Hinzufügen von X25519MLKEM768 nicht mehr</h2>
<p>Wenn <code>nginx -t</code> oder ein Neustart mit einem Fehler wie diesem abbricht:</p>
<pre dir="ltr">nginx: [emerg] SSL_CTX_set1_curves_list("X25519MLKEM768:X25519:prime256v1") failed</pre>
<p>dann kennt das OpenSSL, das nginx tatsächlich verwendet, die Gruppe nicht, ist also älter als 3.5. OpenSSL lehnt die gesamte Liste ab, sobald ein Name unbekannt ist, und nginx bricht beim Lesen der Konfiguration ab. Prüfen Sie die Bibliothek, mit der nginx läuft; sie kann sich vom Befehl <code>openssl</code> auf derselben Maschine unterscheiden:</p>
<pre dir="ltr">nginx -V 2&gt;&amp;1 | grep -i openssl</pre>
<ul>
<li><strong>Website sofort wieder erreichbar machen:</strong> Entfernen Sie <code>X25519MLKEM768</code> aus der Zeile oder löschen Sie die <code>ssl_ecdh_curve</code>-Zeile ganz (auf jeder OpenSSL-Version unbedenklich), dann <code>nginx -t &amp;&amp; systemctl reload nginx</code>.</li>
<li><strong>Danach ein neueres OpenSSL besorgen:</strong> Für Ubuntu 22.04 / 24.04 siehe <a href="/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=en">den Ubuntu-Leitfaden</a> (Upgrade auf 26.04, Caddy oder ein CDN vorschalten oder nginx mit OpenSSL 3.5 bauen).</li>
<li><strong>Immer zuerst <code>nginx -t</code> ausführen.</strong> Ein <code>reload</code> mit fehlerhafter Konfiguration lässt die alten Worker weiterlaufen, ein <code>restart</code> oder Neustart des Servers legt die Website dagegen lahm.</li>
</ul>

<h2>Worauf Sie achten sollten</h2>
<ul>
<li><strong>Großes ClientHello.</strong> Der ML-KEM-Schlüsselanteil macht die erste Nachricht des Browsers etwa 1,2 KB größer, sodass sie oft auf zwei TCP-Pakete verteilt wird. Alte Firewalls, Load Balancer und Middleboxes, die sie in einem Paket erwarten, verwerfen die Verbindung. Der Scan meldet das als eigenen Befund.</li>
<li><strong>Zertifikate sind ein eigenes Thema.</strong> Ihr RSA- oder ECDSA-Zertifikat bleibt mit dem Shor-Algorithmus brechbar, das spielt aber erst eine Rolle, wenn ein Quantencomputer existiert, und nur für eine Echtzeit-Imitation der Website. Der Schlüsselaustausch schützt aufgezeichneten Datenverkehr, deshalb zuerst ihn absichern.</li>
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
    "nis2-dora-post-quantum-cryptography": {
        "updated": "2026-11-10",
        "en": {
            "title": "NIS2 and DORA: what they require for cryptography, and where post-quantum TLS fits",
            "description": "What NIS2, its implementing regulation, Germany's BSIG and the DORA technical standard actually say about cryptography, with exact article references, and what evidence a post-quantum TLS check can and cannot provide.",
            "body": """
<p>Neither NIS2 nor DORA names a post-quantum algorithm or sets a post-quantum deadline. Both do require a documented cryptography policy that keeps pace with the state of the art, and the DORA technical standard explicitly mentions threats from quantum advancements. This page lists what the texts say, with article references, so you can check them yourself. It is not legal advice.</p>

<h2>NIS2 (Directive (EU) 2022/2555)</h2>
<ul>
<li><strong>Article 21(1):</strong> essential and important entities must take appropriate and proportionate measures, "taking into account the state-of-the-art".</li>
<li><strong>Article 21(2)(h):</strong> the minimum measures include "policies and procedures regarding the use of cryptography and, where appropriate, encryption".</li>
</ul>
<p><strong>Implementing Regulation (EU) 2024/2690</strong> details these measures for DNS providers, TLD registries, cloud, data centre and CDN providers, managed (security) service providers, online marketplaces, search engines, social networks and trust service providers. Point 9 of its annex requires that the cryptography policy set out the approved protocols and algorithms "following, where appropriate, a cryptographic agility approach" (9.2(b)), and that entities review and update it "at planned intervals, taking into account the state of the art in cryptography" (9.3).</p>
<p><strong>Germany:</strong> the NIS2 implementation act (NIS2UmsuCG) has applied since 6 December 2025. Under <a href="https://www.gesetze-im-internet.de/bsig_2025/__30.html" rel="noopener">§ 30 BSIG</a>, measures "sollen den Stand der Technik einhalten" (paragraph 2), and point 8 requires "Konzepte und Prozesse für den Einsatz von kryptographischen Verfahren".</p>

<h2>DORA (Regulation (EU) 2022/2554)</h2>
<p>DORA has applied to financial entities since 17 January 2025. Its ICT risk-management standard, <strong>Delegated Regulation (EU) 2024/1774</strong>, is the most specific text on this topic:</p>
<ul>
<li><strong>Article 6(2):</strong> the encryption policy must cover data in transit and "traffic with external parties".</li>
<li><strong>Article 6(4):</strong> the policy must include provisions for "updating or changing, where necessary, the cryptographic technology on the basis of developments in cryptanalysis".</li>
<li><strong>Article 6(3)–(5):</strong> an entity that cannot follow leading practices or cannot update its cryptography must adopt mitigation and monitoring measures, record them and give "a reasoned explanation".</li>
<li><strong>Article 7(4):</strong> a register of certificates, at least for ICT assets supporting critical or important functions.</li>
<li><strong>Recital 9:</strong> financial entities should follow a flexible approach to cryptographic threats, "including threats from quantum advancements".</li>
</ul>

<h2>What this means in practice</h2>
<p>Expect auditors to ask for a cryptographic inventory, a plan to replace algorithms that quantum computers will break, and documented reasons for any exception. Public TLS endpoints are usually the easiest place to start:</p>
<ol>
<li><strong>Key exchange first.</strong> Recorded traffic can be decrypted later once quantum computers exist (<a href="/guides/harvest-now-decrypt-later?lang=en">harvest now, decrypt later</a>). The hybrid group <code>X25519MLKEM768</code> (ML-KEM, <a href="https://csrc.nist.gov/pubs/fips/203/final" rel="noopener">NIST FIPS 203</a>) is already supported by current browsers, major CDNs and recent server software. See the <a href="/guides?lang=en">configuration guides</a>.</li>
<li><strong>Record evidence per endpoint:</strong> hostname, date, negotiated group, TLS version and who terminates TLS (CDN, load balancer or origin).</li>
<li><strong>Document exceptions.</strong> For an endpoint you cannot upgrade yet (legacy appliance, vendor platform), record the reason, the mitigation and a target date. That matches the "reasoned explanation" in DORA Article 6(5).</li>
<li><strong>Repeat the check</strong> after CDN, proxy or certificate changes, and at your policy's planned review interval.</li>
</ol>
<p>For timelines (NIST IR 8547, the EU coordinated roadmap, CNSA 2.0), see <a href="/deadlines?lang=en">post-quantum deadlines</a>.</p>

<h2>What a TLS check does not prove</h2>
<p>A public scan observes one public endpoint on port 443 at one point in time. It does not cover internal links, the CDN-to-origin connection, certificates and signatures, stored data or key management. It is evidence for one line of your inventory, not a NIS2 or DORA compliance attestation. <a href="/?lang=en">Check a domain</a>, or see <a href="/business?lang=en">business monitoring</a> for many hosts.</p>

<h2>Sources</h2>
<ul>
<li><a href="https://eur-lex.europa.eu/eli/dir/2022/2555/oj" rel="noopener">Directive (EU) 2022/2555 (NIS2)</a>, Article 21</li>
<li><a href="https://eur-lex.europa.eu/eli/reg_impl/2024/2690/oj" rel="noopener">Implementing Regulation (EU) 2024/2690</a>, Annex point 9</li>
<li><a href="https://www.gesetze-im-internet.de/bsig_2025/__30.html" rel="noopener">§ 30 BSIG (Germany)</a></li>
<li><a href="https://eur-lex.europa.eu/eli/reg/2022/2554/oj" rel="noopener">Regulation (EU) 2022/2554 (DORA)</a></li>
<li><a href="https://eur-lex.europa.eu/eli/reg_del/2024/1774/oj" rel="noopener">Delegated Regulation (EU) 2024/1774</a>, recital 9, Articles 6 and 7</li>
</ul>
""",
        },
        "ar": {
            "title": "NIS2 وDORA: ماذا تشترطان في التشفير، وأين يقع TLS لما بعد الكم",
            "description": "ما تقوله فعلاً NIS2 ولائحتها التنفيذية وقانون BSIG الألماني والمعيار التقني لـ DORA عن التشفير، مع أرقام المواد، وما يثبته فحص TLS لما بعد الكم وما لا يثبته.",
            "body": """
<p>لا تذكر NIS2 ولا DORA خوارزمية ما بعد كمومية بالاسم، ولا تحددان موعداً للانتقال. لكن كلتيهما تشترط سياسة تشفير موثّقة تواكب أحدث ما وصلت إليه التقنية، والمعيار التقني لـ DORA يذكر صراحةً التهديدات الناتجة عن تقدّم الحوسبة الكمومية. تجمع هذه الصفحة النصوص مع أرقام المواد لتتحقق منها بنفسك. وهي ليست استشارة قانونية.</p>

<h2>NIS2 (التوجيه الأوروبي 2022/2555)</h2>
<ul>
<li><strong>المادة 21(1):</strong> على الجهات الأساسية والمهمة اتخاذ تدابير مناسبة ومتناسبة مع مراعاة أحدث ما وصلت إليه التقنية (state-of-the-art).</li>
<li><strong>المادة 21(2)(h):</strong> من التدابير الدنيا وضع سياسات وإجراءات لاستخدام التشفير، والتعمية حيث يلزم.</li>
</ul>
<p><strong>اللائحة التنفيذية 2024/2690</strong> تفصّل هذه التدابير لمزوّدي DNS وسجلات النطاقات العليا والحوسبة السحابية ومراكز البيانات وشبكات CDN والخدمات المُدارة والأمنية المُدارة والأسواق الإلكترونية ومحركات البحث والشبكات الاجتماعية وخدمات الثقة. البند 9 من ملحقها يشترط أن تحدد سياسة التشفير البروتوكولات والخوارزميات المعتمدة وفق نهج «المرونة التشفيرية» (cryptographic agility) حيث يكون مناسباً (9.2(b))، وأن تُراجع وتُحدَّث على فترات مخططة مع مراعاة أحدث ما وصل إليه علم التشفير (9.3).</p>
<p><strong>ألمانيا:</strong> قانون تطبيق NIS2 (NIS2UmsuCG) نافذ منذ 6 ديسمبر 2025. تنص <a href="https://www.gesetze-im-internet.de/bsig_2025/__30.html" rel="noopener">المادة 30 من BSIG</a> على أن تلتزم التدابير بأحدث ما وصلت إليه التقنية (الفقرة 2)، ويشترط البند 8 وضع مفاهيم وإجراءات لاستخدام أساليب التشفير.</p>

<h2>DORA (اللائحة الأوروبية 2022/2554)</h2>
<p>تسري DORA على المؤسسات المالية منذ 17 يناير 2025. ومعيارها التقني لإدارة مخاطر تقنية المعلومات، <strong>اللائحة المفوَّضة 2024/1774</strong>، هو النص الأكثر تحديداً في هذا الموضوع:</p>
<ul>
<li><strong>المادة 6(2):</strong> يجب أن تشمل سياسة التشفير البيانات أثناء النقل والاتصالات مع الأطراف الخارجية.</li>
<li><strong>المادة 6(4):</strong> يجب أن تتضمن السياسة أحكاماً لتحديث تقنية التشفير أو تغييرها عند الحاجة بناءً على التطورات في تحليل الشفرات (cryptanalysis).</li>
<li><strong>المادة 6(3) إلى 6(5):</strong> الجهة التي لا تستطيع اتباع أفضل الممارسات أو تحديث تشفيرها عليها اتخاذ تدابير تخفيف ومراقبة، وتسجيلها مع تبرير مُعلَّل.</li>
<li><strong>المادة 7(4):</strong> سجلّ للشهادات، على الأقل للأصول التي تدعم الوظائف الحرجة أو المهمة.</li>
<li><strong>الحيثية 9:</strong> على المؤسسات المالية اتباع نهج مرن تجاه التهديدات التشفيرية، بما فيها التهديدات الناتجة عن تقدّم الحوسبة الكمومية.</li>
</ul>

<h2>ماذا يعني ذلك عملياً</h2>
<p>توقّع أن يطلب المدققون حصراً لأنظمة التشفير، وخطة لاستبدال الخوارزميات التي سيكسرها الحاسوب الكمومي، وتبريراً موثّقاً لأي استثناء. ونقاط TLS العامة هي عادةً أسهل مكان للبدء:</p>
<ol>
<li><strong>ابدأ بتبادل المفاتيح.</strong> الاتصالات المسجّلة اليوم يمكن فكّها لاحقاً عند ظهور الحاسوب الكمومي (<a href="/guides/harvest-now-decrypt-later?lang=ar">احصد الآن وفكّ لاحقاً</a>). المجموعة الهجينة <code>X25519MLKEM768</code> (خوارزمية ML-KEM في <a href="https://csrc.nist.gov/pubs/fips/203/final" rel="noopener">NIST FIPS 203</a>) مدعومة بالفعل في المتصفحات الحالية وشبكات CDN الكبرى وإصدارات الخوادم الحديثة. راجع <a href="/guides?lang=ar">أدلة الإعداد</a>.</li>
<li><strong>سجّل دليلاً لكل نقطة اتصال:</strong> اسم النطاق والتاريخ والمجموعة المتفق عليها وإصدار TLS والجهة التي تنهي اتصال TLS (CDN أو موازن حمل أو الخادم الأصلي).</li>
<li><strong>وثّق الاستثناءات.</strong> لكل نقطة لا يمكن ترقيتها بعد (جهاز قديم أو منصة مورّد)، سجّل السبب والتدبير البديل والموعد المستهدف. وهذا يوافق «التبرير المُعلَّل» في المادة 6(5) من DORA.</li>
<li><strong>أعد الفحص</strong> بعد تغييرات CDN أو الوكيل أو الشهادات، وفي موعد المراجعة الدورية لسياستك.</li>
</ol>
<p>للمواعيد (NIST IR 8547 وخارطة الطريق الأوروبية وCNSA 2.0) راجع <a href="/deadlines?lang=ar">مواعيد الانتقال إلى ما بعد الكم</a>.</p>

<h2>ما لا يثبته فحص TLS</h2>
<p>الفحص العام يرصد نقطة عامة واحدة على المنفذ 443 في وقت محدد. لا يغطي الاتصالات الداخلية، ولا الاتصال بين CDN والخادم الأصلي، ولا الشهادات والتواقيع، ولا البيانات المخزنة أو إدارة المفاتيح. هو دليل لسطر واحد في حصرك، لا شهادة امتثال لـ NIS2 أو DORA. <a href="/?lang=ar">افحص نطاقاً</a>، أو راجع <a href="/business?lang=ar">المراقبة للشركات</a> لعدد كبير من النطاقات.</p>

<h2>المصادر</h2>
<ul>
<li><a href="https://eur-lex.europa.eu/eli/dir/2022/2555/oj" rel="noopener">التوجيه (EU) 2022/2555 (NIS2)</a>، المادة 21</li>
<li><a href="https://eur-lex.europa.eu/eli/reg_impl/2024/2690/oj" rel="noopener">اللائحة التنفيذية (EU) 2024/2690</a>، البند 9 من الملحق</li>
<li><a href="https://www.gesetze-im-internet.de/bsig_2025/__30.html" rel="noopener">المادة 30 من BSIG (ألمانيا)</a></li>
<li><a href="https://eur-lex.europa.eu/eli/reg/2022/2554/oj" rel="noopener">اللائحة (EU) 2022/2554 (DORA)</a></li>
<li><a href="https://eur-lex.europa.eu/eli/reg_del/2024/1774/oj" rel="noopener">اللائحة المفوَّضة (EU) 2024/1774</a>، الحيثية 9 والمادتان 6 و7</li>
</ul>
""",
        },
        "de": {
            "title": "NIS2 und DORA: Was sie für Kryptografie verlangen und wo Post-Quanten-TLS ansetzt",
            "description": "Was NIS2, die Durchführungsverordnung, das BSIG und der technische DORA-Standard tatsächlich zur Kryptografie sagen, mit genauen Fundstellen, und welche Nachweise eine Post-Quanten-TLS-Prüfung liefern kann und welche nicht.",
            "body": """
<p>Weder NIS2 noch DORA nennen einen Post-Quanten-Algorithmus oder eine Post-Quanten-Frist. Beide verlangen aber ein dokumentiertes Kryptografie-Konzept, das mit dem Stand der Technik Schritt hält, und der technische DORA-Standard nennt ausdrücklich Bedrohungen durch Fortschritte der Quantentechnologie. Diese Seite fasst die Texte mit Fundstellen zusammen, damit Sie sie selbst prüfen können. Sie ist keine Rechtsberatung.</p>

<h2>NIS2 (Richtlinie (EU) 2022/2555)</h2>
<ul>
<li><strong>Artikel 21 Absatz 1:</strong> Wesentliche und wichtige Einrichtungen ergreifen geeignete und verhältnismäßige Maßnahmen unter Berücksichtigung des Stands der Technik.</li>
<li><strong>Artikel 21 Absatz 2 Buchstabe h:</strong> Zu den Mindestmaßnahmen gehören „Konzepte und Verfahren für den Einsatz von Kryptografie und gegebenenfalls Verschlüsselung“.</li>
</ul>
<p>Die <strong>Durchführungsverordnung (EU) 2024/2690</strong> konkretisiert diese Maßnahmen für DNS-Diensteanbieter, TLD-Namenregister, Cloud-, Rechenzentrums- und CDN-Anbieter, Anbieter verwalteter (Sicherheits-)Dienste, Online-Marktplätze, Suchmaschinen, soziale Netzwerke und Vertrauensdiensteanbieter. Nummer 9 des Anhangs verlangt, dass das Konzept die zugelassenen Protokolle und Algorithmen „soweit angemessen – nach einem Krypto-Agilitätsansatz“ festlegt (9.2 b) und dass die Einrichtungen es „in geplanten Zeitabständen“ überprüfen und dabei „dem Stand der Technik im Bereich der Kryptografie Rechnung tragen“ (9.3).</p>
<p><strong>Deutschland:</strong> Das NIS2-Umsetzungsgesetz (NIS2UmsuCG) gilt seit dem 6. Dezember 2025. Nach <a href="https://www.gesetze-im-internet.de/bsig_2025/__30.html" rel="noopener">§ 30 BSIG</a> „sollen [Maßnahmen] den Stand der Technik einhalten“ (Absatz 2), und Nummer 8 verlangt „Konzepte und Prozesse für den Einsatz von kryptographischen Verfahren“.</p>

<h2>DORA (Verordnung (EU) 2022/2554)</h2>
<p>DORA gilt für Finanzunternehmen seit dem 17. Januar 2025. Der technische Regulierungsstandard zum IKT-Risikomanagement, die <strong>Delegierte Verordnung (EU) 2024/1774</strong>, ist hier am konkretesten:</p>
<ul>
<li><strong>Artikel 6 Absatz 2:</strong> Die Verschlüsselungsrichtlinie muss Daten bei der Übertragung und den Datenverkehr mit externen Parteien abdecken.</li>
<li><strong>Artikel 6 Absatz 4:</strong> Die Richtlinie muss regeln, „wie die kryptografische Technologie aufgrund von Entwicklungen im Bereich der Kryptoanalyse gegebenenfalls zu aktualisieren oder zu ändern ist“.</li>
<li><strong>Artikel 6 Absätze 3 bis 5:</strong> Wer führende Praktiken nicht einhalten oder die Kryptografie nicht aktualisieren kann, ergreift Abhilfe- und Überwachungsmaßnahmen, dokumentiert sie und begründet dies.</li>
<li><strong>Artikel 7 Absatz 4:</strong> ein Register der Zertifikate, mindestens für IKT-Assets, die kritische oder wichtige Funktionen unterstützen.</li>
<li><strong>Erwägungsgrund 9:</strong> Finanzunternehmen sollen einen flexiblen Ansatz verfolgen, um kryptografische Bedrohungen zu bewältigen, „einschließlich Bedrohungen aufgrund der Fortschritte im Bereich der Quantentechnologie“.</li>
</ul>

<h2>Was das in der Praxis bedeutet</h2>
<p>Rechnen Sie damit, dass Prüfer ein Kryptografie-Inventar, einen Plan zum Ersatz quantenanfälliger Verfahren und begründete Ausnahmen sehen wollen. Öffentliche TLS-Endpunkte sind meist der einfachste Einstieg:</p>
<ol>
<li><strong>Zuerst der Schlüsselaustausch.</strong> Heute aufgezeichneter Verkehr kann später mit Quantencomputern entschlüsselt werden (<a href="/guides/harvest-now-decrypt-later?lang=en">„harvest now, decrypt later“</a>). Die hybride Gruppe <code>X25519MLKEM768</code> (ML-KEM, <a href="https://csrc.nist.gov/pubs/fips/203/final" rel="noopener">NIST FIPS 203</a>) unterstützen aktuelle Browser, große CDNs und neuere Serversoftware bereits. Siehe die <a href="/guides?lang=en">Konfigurationsanleitungen</a> (Englisch).</li>
<li><strong>Nachweis je Endpunkt festhalten:</strong> Hostname, Datum, ausgehandelte Gruppe, TLS-Version und wer TLS terminiert (CDN, Load Balancer oder Origin).</li>
<li><strong>Ausnahmen dokumentieren.</strong> Für Endpunkte, die sich noch nicht umstellen lassen (Altgeräte, Herstellerplattformen), Grund, Ausgleichsmaßnahme und Zieltermin festhalten. Das entspricht der Begründungspflicht in Artikel 6 Absatz 5 der Delegierten Verordnung (EU) 2024/1774.</li>
<li><strong>Erneut prüfen</strong> nach Änderungen an CDN, Proxy oder Zertifikaten sowie im geplanten Überprüfungsintervall Ihres Konzepts.</li>
</ol>
<p>Zu Fristen (NIST IR 8547, EU-Roadmap, CNSA 2.0) siehe <a href="/deadlines?lang=de">Post-Quanten-Fristen</a>.</p>

<h2>Was eine TLS-Prüfung nicht belegt</h2>
<p>Ein öffentlicher Scan beobachtet einen öffentlichen Endpunkt auf Port 443 zu einem Zeitpunkt. Er deckt keine internen Verbindungen, nicht die Verbindung vom CDN zum Origin, keine Zertifikate und Signaturen, keine gespeicherten Daten und kein Schlüsselmanagement ab. Er ist ein Nachweis für eine Zeile Ihres Inventars, keine NIS2- oder DORA-Konformitätsbestätigung. <a href="/?lang=de">Domain prüfen</a> oder <a href="/business?lang=de">Monitoring für Unternehmen</a> ansehen.</p>

<h2>Quellen</h2>
<ul>
<li><a href="https://eur-lex.europa.eu/eli/dir/2022/2555/oj?locale=de" rel="noopener">Richtlinie (EU) 2022/2555 (NIS2)</a>, Artikel 21</li>
<li><a href="https://eur-lex.europa.eu/eli/reg_impl/2024/2690/oj?locale=de" rel="noopener">Durchführungsverordnung (EU) 2024/2690</a>, Anhang Nummer 9</li>
<li><a href="https://www.gesetze-im-internet.de/bsig_2025/__30.html" rel="noopener">§ 30 BSIG</a></li>
<li><a href="https://eur-lex.europa.eu/eli/reg/2022/2554/oj?locale=de" rel="noopener">Verordnung (EU) 2022/2554 (DORA)</a></li>
<li><a href="https://eur-lex.europa.eu/eli/reg_del/2024/1774/oj?locale=de" rel="noopener">Delegierte Verordnung (EU) 2024/1774</a>, Erwägungsgrund 9, Artikel 6 und 7</li>
</ul>
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
        "updated": "2026-11-21",
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
        "updated": "2026-11-21",
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

    "go-post-quantum-tls-x25519mlkem768": {
        "updated": "2026-11-21",
        "en": {
            "title": "Post-quantum TLS in Go (crypto/tls): X25519MLKEM768 and the go.mod trap",
            "description": "Go 1.24+ enables X25519MLKEM768 by default, but only if your go.mod says go 1.24 or newer. How to check, fix CurvePreferences and verify the handshake.",
            "body": """
<p>Go does TLS in its own standard library (<code>crypto/tls</code>), not through OpenSSL. Since <strong>Go 1.24</strong> the default key exchange list includes the hybrid <code>X25519MLKEM768</code>, the same group Chrome and Firefox offer. Go 1.26 added <code>SecP256r1MLKEM768</code> and <code>SecP384r1MLKEM1024</code> to the defaults. This covers Go servers (<code>net/http</code> with <code>ListenAndServeTLS</code>) and Go clients (<code>http.Get</code>). Tools written in Go, such as Caddy and Traefik, follow the same rules in their own builds.</p>

<h2>1. The trap: the <code>go</code> line in go.mod</h2>
<p>Go keeps old behaviour for old modules. The defaults come from the <code>go</code> line of your main module, not from the toolchain you build with. We tested this with Go 1.27.3 against cloudflare.com:</p>
<pre dir="ltr">go.mod "go 1.22"  →  X25519            (no post-quantum)
go.mod "go 1.23"  →  X25519            (no post-quantum)
go.mod "go 1.24"  →  X25519MLKEM768
go.mod "go 1.25"  →  X25519MLKEM768</pre>
<p>So a service built with the newest Go can still be classical-only. Fix it by raising the line (<code>go mod edit -go=1.24</code> or newer), or, if you cannot yet, by adding this line to go.mod:</p>
<pre dir="ltr">godebug tlsmlkem=1</pre>

<h2>2. Don't pin CurvePreferences</h2>
<p>When <code>tls.Config.CurvePreferences</code> is empty, Go uses its defaults. Old hardening code often sets an explicit list, which silently removes the hybrid group. Delete the field, or put the hybrid group first:</p>
<pre dir="ltr">srv := &amp;http.Server{
    Addr: ":443",
    TLSConfig: &amp;tls.Config{
        CurvePreferences: []tls.CurveID{
            tls.X25519MLKEM768, tls.X25519, tls.CurveP256,
        },
    },
}
log.Fatal(srv.ListenAndServeTLS("cert.pem", "key.pem"))</pre>
<p>In our test, a Go server with <code>CurvePreferences: {X25519, CurveP256}</code> negotiated only X25519 with a Go client that offered ML-KEM; with the list empty it negotiated X25519MLKEM768.</p>

<h2>3. Check for GODEBUG in the environment</h2>
<p><code>GODEBUG=tlsmlkem=0</code> (and <code>tlssecpmlkem=0</code> for the Go 1.26 groups) turns the defaults off. It is sometimes set to work around old middleboxes that drop the larger ClientHello. Look in Dockerfiles, systemd units and Kubernetes manifests. Since Go 1.27, groups listed explicitly in CurvePreferences still work even with these settings.</p>

<h2>4. Behind a proxy, the proxy decides</h2>
<p>If nginx, a load balancer or a CDN terminates TLS in front of your Go service, configure that layer instead (<a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx</a>, <a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=en">AWS ALB/CloudFront</a>).</p>

<h2>Verify</h2>
<p>Print the negotiated group from Go itself:</p>
<pre dir="ltr">c, err := tls.Dial("tcp", "example.com:443", &amp;tls.Config{})
if err != nil { log.Fatal(err) }
fmt.Println(c.ConnectionState().CurveID) // X25519MLKEM768</pre>
<p>Or run the <a href="/?lang=en">free scan</a>; grade A means TLS 1.3 with a hybrid post-quantum key exchange. More ways to check: <a href="/guides/check-website-post-quantum-tls?lang=en">how to check any website</a>.</p>
<p class="muted small">Sources: Go crypto/tls documentation (Config.CurvePreferences), "GODEBUG history" and Go 1.27 release notes; our own tests with Go 1.27.3. Checked 2026-11-10.</p>
""",
        },
        "ar": {
            "title": "TLS المقاوم للكم في Go ‏(crypto/tls): ‏X25519MLKEM768 وفخ go.mod",
            "description": "Go 1.24 وما بعده يفعّل X25519MLKEM768 افتراضياً، لكن بشرط أن يكون سطر go في go.mod هو 1.24 أو أحدث. كيف تتحقق، وتصلح CurvePreferences، وتتأكد من الاتصال.",
            "body": """
<p>يتولى Go تشفير TLS في مكتبته القياسية (<code>crypto/tls</code>) دون OpenSSL. منذ <strong>Go 1.24</strong> تشمل قائمة تبادل المفاتيح الافتراضية المجموعة الهجينة <code>X25519MLKEM768</code>، وهي نفسها التي يعرضها Chrome وFirefox. وأضاف Go 1.26 المجموعتين <code>SecP256r1MLKEM768</code> و<code>SecP384r1MLKEM1024</code> إلى القائمة الافتراضية. هذا يشمل خوادم Go ‏(<code>net/http</code> مع <code>ListenAndServeTLS</code>) والعملاء (<code>http.Get</code>). والأدوات المكتوبة بـ Go مثل Caddy وTraefik تتبع القواعد نفسها في نسخها.</p>

<h2>1. الفخ: سطر <code>go</code> في go.mod</h2>
<p>يحافظ Go على السلوك القديم للوحدات القديمة. الإعدادات الافتراضية تأتي من سطر <code>go</code> في الوحدة الرئيسية، لا من نسخة Go التي تبني بها. جرّبنا ذلك بـ Go 1.27.3 على cloudflare.com:</p>
<pre dir="ltr">go.mod "go 1.22"  →  X25519            (no post-quantum)
go.mod "go 1.23"  →  X25519            (no post-quantum)
go.mod "go 1.24"  →  X25519MLKEM768
go.mod "go 1.25"  →  X25519MLKEM768</pre>
<p>أي أن خدمة مبنية بأحدث Go قد تبقى كلاسيكية فقط. الحل أن ترفع السطر (<code>go mod edit -go=1.24</code> أو أحدث)، أو إن لم تستطع بعد، أن تضيف هذا السطر إلى go.mod:</p>
<pre dir="ltr">godebug tlsmlkem=1</pre>

<h2>2. لا تثبّت CurvePreferences</h2>
<p>إذا كان الحقل <code>tls.Config.CurvePreferences</code> فارغاً استخدم Go قائمته الافتراضية. كود الحماية القديم يضع غالباً قائمة صريحة تحذف المجموعة الهجينة دون أن تشعر. احذف الحقل، أو ضع المجموعة الهجينة أولاً:</p>
<pre dir="ltr">srv := &amp;http.Server{
    Addr: ":443",
    TLSConfig: &amp;tls.Config{
        CurvePreferences: []tls.CurveID{
            tls.X25519MLKEM768, tls.X25519, tls.CurveP256,
        },
    },
}
log.Fatal(srv.ListenAndServeTLS("cert.pem", "key.pem"))</pre>
<p>في تجربتنا، خادم Go مع <code>CurvePreferences: {X25519, CurveP256}</code> اتفق على X25519 فقط مع عميل يعرض ML-KEM، ومع قائمة فارغة اتفق على X25519MLKEM768.</p>

<h2>3. ابحث عن GODEBUG في البيئة</h2>
<p>الإعداد <code>GODEBUG=tlsmlkem=0</code> (و<code>tlssecpmlkem=0</code> لمجموعات Go 1.26) يلغي القائمة الافتراضية. يُضبط أحياناً لتجاوز أجهزة شبكة قديمة تُسقط رسالة ClientHello الأكبر. ابحث عنه في ملفات Docker ووحدات systemd وملفات Kubernetes. ومنذ Go 1.27 تعمل المجموعات المكتوبة صراحة في CurvePreferences حتى مع هذا الإعداد.</p>

<h2>4. خلف وكيل، الوكيل هو من يقرر</h2>
<p>إذا كان nginx أو موازن تحميل أو CDN يُنهي TLS أمام خدمة Go فاضبط تلك الطبقة بدلاً منها (<a href="/guides/enable-x25519mlkem768-nginx?lang=ar">nginx</a>، <a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=ar">AWS ALB/CloudFront</a>).</p>

<h2>التحقق</h2>
<p>اطبع المجموعة المتفق عليها من Go نفسه:</p>
<pre dir="ltr">c, err := tls.Dial("tcp", "example.com:443", &amp;tls.Config{})
if err != nil { log.Fatal(err) }
fmt.Println(c.ConnectionState().CurveID) // X25519MLKEM768</pre>
<p>أو استخدم <a href="/?lang=ar">الفحص المجاني</a>: الدرجة A تعني TLS 1.3 مع تبادل مفاتيح هجين. طرق أخرى: <a href="/guides/check-website-post-quantum-tls?lang=ar">كيف تفحص أي موقع</a>.</p>
<p class="muted small">المصادر: توثيق crypto/tls في Go ‏(Config.CurvePreferences)، وصفحة «GODEBUG history»، وملاحظات إصدار Go 1.27، وتجاربنا بـ Go 1.27.3. راجعناها في 2026-11-10.</p>
""",
        },
    },
    "python-post-quantum-tls-x25519mlkem768": {
        "updated": "2026-11-10",
        "en": {
            "title": "Post-quantum TLS in Python (ssl, requests, httpx): it depends on OpenSSL",
            "description": "Python's ssl module offers X25519MLKEM768 when it is linked to OpenSSL 3.5, whatever the Python version. How to check, the Python 3.15 set_groups() API, and verification.",
            "body": """
<p>Python's <code>ssl</code> module, and everything built on it (<code>urllib</code>, <code>requests</code>, <code>httpx</code>, <code>aiohttp</code>, uvicorn and gunicorn with TLS), uses the OpenSSL library Python was linked to. Since <strong>OpenSSL 3.5</strong>, OpenSSL's defaults offer the hybrid <code>X25519MLKEM768</code>. So the question is not "which Python?" but "which OpenSSL?".</p>

<h2>1. Check which OpenSSL your Python uses</h2>
<pre dir="ltr">python3 -c "import ssl; print(ssl.OPENSSL_VERSION)"</pre>
<p>We tested the same Python 3.12.16 two ways. Linked to OpenSSL 3.0.2 (Ubuntu 22.04's system Python), it connected to a server with plain x25519. Linked to OpenSSL 3.5.9, it negotiated X25519MLKEM768, with no code change. The python.org installers for Windows and macOS moved from OpenSSL 3.0 to 3.5.9 in 2026 (for example Python 3.13.16, released 30 September 2026), and the Pythons that uv installs ship with 3.5 as well. Linux distribution Pythons use the system OpenSSL (3.0 on Ubuntu 22.04 and 24.04).</p>

<h2>2. Python 3.15: control and read the group</h2>
<p>Python 3.15 (October 2026) adds <code>SSLContext.set_groups()</code>, <code>SSLContext.get_groups()</code> and <code>SSLSocket.group()</code>. Earlier versions have only <code>set_ecdh_curve()</code>, which takes a single classical curve. Watch out for servers that call <code>set_ecdh_curve('prime256v1')</code>: in our test it removed the hybrid group, and a client offering X25519MLKEM768 ended up on secp256r1. Delete the call and keep the defaults.</p>
<pre dir="ltr">import ssl, socket
ctx = ssl.create_default_context()
# optional, Python 3.15+: hybrid first, classical fallback
ctx.set_groups("X25519MLKEM768:X25519:prime256v1")
with socket.create_connection(("example.com", 443)) as s:
    with ctx.wrap_socket(s, server_hostname="example.com") as t:
        print(t.version(), t.group())   # TLSv1.3 X25519MLKEM768</pre>
<p>Like other "hardening" lists, <code>set_groups("X25519:prime256v1")</code> removes the hybrid group: in our test the same connection then used x25519.</p>

<h2>3. Behind a proxy, the proxy decides</h2>
<p>Most Python web apps (Django, Flask, FastAPI) sit behind nginx, a load balancer or a CDN that terminates TLS. Browsers never talk TLS to Python directly, so configure that layer (<a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx</a>, <a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=en">AWS ALB/CloudFront</a>). The OpenSSL version still matters for your outgoing requests to APIs.</p>

<h2>Verify</h2>
<p>On Python 3.15, use the snippet above. On older versions, check <code>ssl.OPENSSL_VERSION</code> is 3.5 or newer, or run the <a href="/?lang=en">free scan</a> against your site; grade A means TLS 1.3 with a hybrid post-quantum key exchange. More ways: <a href="/guides/check-website-post-quantum-tls?lang=en">how to check any website</a>.</p>
<p class="muted small">Sources: Python 3.15 "What's New" (ssl) and ssl module docs; OpenSSL 3.5 release notes; our own tests with Python 3.12.16 and 3.15.2. Checked 2026-11-10.</p>
""",
        },
        "ar": {
            "title": "TLS المقاوم للكم في Python ‏(ssl وrequests وhttpx): الأمر يعتمد على OpenSSL",
            "description": "وحدة ssl في Python تعرض X25519MLKEM768 حين تكون مربوطة بـ OpenSSL 3.5، مهما كان إصدار Python. كيف تتحقق، وواجهة set_groups() في Python 3.15، والتأكد من الاتصال.",
            "body": """
<p>وحدة <code>ssl</code> في Python، وكل ما بُني عليها (<code>urllib</code> و<code>requests</code> و<code>httpx</code> و<code>aiohttp</code> وuvicorn وgunicorn مع TLS)، تستخدم مكتبة OpenSSL التي رُبط بها Python. منذ <strong>OpenSSL 3.5</strong> تعرض إعدادات OpenSSL الافتراضية المجموعة الهجينة <code>X25519MLKEM768</code>. فالسؤال ليس «أي Python؟» بل «أي OpenSSL؟».</p>

<h2>1. تحقق من نسخة OpenSSL في Python عندك</h2>
<pre dir="ltr">python3 -c "import ssl; print(ssl.OPENSSL_VERSION)"</pre>
<p>جرّبنا Python 3.12.16 نفسه بطريقتين. مربوطاً بـ OpenSSL 3.0.2 (Python النظام في Ubuntu 22.04) اتصل بالخادم بـ x25519 العادي. ومربوطاً بـ OpenSSL 3.5.9 اتفق على X25519MLKEM768 دون أي تعديل في الكود. مثبّتات python.org لـ Windows وmacOS انتقلت من OpenSSL 3.0 إلى 3.5.9 في 2026 (مثلاً Python 3.13.16 الصادر في 30 سبتمبر 2026)، ونسخ Python التي يثبّتها uv تأتي مع 3.5 أيضاً. أما Python توزيعات Linux فيستخدم OpenSSL النظام (3.0 في Ubuntu 22.04 و24.04).</p>

<h2>2. Python 3.15: تحكّم في المجموعة واقرأها</h2>
<p>يضيف Python 3.15 ‏(أكتوبر 2026) الدوال <code>SSLContext.set_groups()</code> و<code>SSLContext.get_groups()</code> و<code>SSLSocket.group()</code>. الإصدارات الأقدم فيها <code>set_ecdh_curve()</code> فقط، وهي تأخذ منحنياً كلاسيكياً واحداً. انتبه للخوادم التي تستدعي <code>set_ecdh_curve('prime256v1')</code>: في تجربتنا حذف هذا الاستدعاء المجموعة الهجينة، فانتهى عميل يعرض X25519MLKEM768 إلى secp256r1. احذف الاستدعاء واترك الافتراضي.</p>
<pre dir="ltr">import ssl, socket
ctx = ssl.create_default_context()
# optional, Python 3.15+: hybrid first, classical fallback
ctx.set_groups("X25519MLKEM768:X25519:prime256v1")
with socket.create_connection(("example.com", 443)) as s:
    with ctx.wrap_socket(s, server_hostname="example.com") as t:
        print(t.version(), t.group())   # TLSv1.3 X25519MLKEM768</pre>
<p>ومثل قوائم «الحماية» الأخرى، <code>set_groups("X25519:prime256v1")</code> تحذف المجموعة الهجينة: في تجربتنا صار الاتصال نفسه يستخدم x25519.</p>

<h2>3. خلف وكيل، الوكيل هو من يقرر</h2>
<p>معظم تطبيقات Python ‏(Django وFlask وFastAPI) تعمل خلف nginx أو موازن تحميل أو CDN يُنهي TLS، فالمتصفح لا يتصل بـ Python مباشرة؛ اضبط تلك الطبقة (<a href="/guides/enable-x25519mlkem768-nginx?lang=ar">nginx</a>، <a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=ar">AWS ALB/CloudFront</a>). لكن نسخة OpenSSL تبقى مهمة لطلباتك الصادرة إلى الواجهات البرمجية.</p>

<h2>التحقق</h2>
<p>على Python 3.15 استخدم المقتطف أعلاه. وعلى الإصدارات الأقدم تأكد أن <code>ssl.OPENSSL_VERSION</code> هي 3.5 أو أحدث، أو استخدم <a href="/?lang=ar">الفحص المجاني</a> على موقعك: الدرجة A تعني TLS 1.3 مع تبادل مفاتيح هجين. طرق أخرى: <a href="/guides/check-website-post-quantum-tls?lang=ar">كيف تفحص أي موقع</a>.</p>
<p class="muted small">المصادر: صفحة «What's New» لـ Python 3.15 ‏(ssl) وتوثيق وحدة ssl، وملاحظات إصدار OpenSSL 3.5، وتجاربنا بـ Python 3.12.16 و3.15.2. راجعناها في 2026-11-10.</p>
""",
        },
    },
    "check-website-post-quantum-tls": {
        "updated": "2026-11-21",
        "en": {
            "title": "How to check if a website uses post-quantum TLS (X25519MLKEM768)",
            "description": "Four ways to see whether a site negotiates the hybrid ML-KEM key exchange: Chrome DevTools, openssl s_client, a few lines of Go or Python, and a free online scan.",
            "body": """
<p>A connection is protected against "harvest now, decrypt later" when the browser and the server agree on a hybrid post-quantum key exchange, today almost always <code>X25519MLKEM768</code>. The padlock does not tell you this. Here are four ways to check.</p>

<h2>1. Online, no install</h2>
<p>Enter the domain in the <a href="/?lang=en">free scan</a>. Grade A means TLS 1.3 with a hybrid post-quantum key exchange; the report also flags problems such as middleboxes that drop the larger ClientHello. To compare two sites side by side, use <a href="/compare?lang=en">compare</a>.</p>

<h2>2. Chrome or Edge DevTools</h2>
<ol>
<li>Open the site, press F12 (or Ctrl+Shift+I, Cmd+Option+I on Mac).</li>
<li>Open the <strong>Privacy and security</strong> panel (older versions call it <strong>Security</strong>). If you don't see it: Ctrl+Shift+P, type <code>privacy</code>, choose "Show privacy and security".</li>
<li>Reload the page, then click the site's origin in the left column.</li>
<li>Under <strong>Connection</strong>, read <strong>Key exchange</strong>. <code>X25519MLKEM768</code> means post-quantum; <code>X25519</code> means classical only.</li>
</ol>
<p>Chrome offers X25519MLKEM768 by default since version 131, so what you see is decided by the server.</p>

<h2>3. Command line (OpenSSL 3.5+)</h2>
<pre dir="ltr">openssl version   # must be 3.5 or newer
openssl s_client -connect example.com:443 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -i group</pre>
<p>With <code>-groups X25519MLKEM768</code> the client offers only the hybrid group, so a classical-only server fails the handshake instead of silently falling back. OpenSSL 3.0 to 3.4 cannot test this; their output says nothing about ML-KEM.</p>

<h2>4. A few lines of code</h2>
<p>Go 1.24+ (with <code>go 1.24</code> or newer in go.mod):</p>
<pre dir="ltr">c, err := tls.Dial("tcp", "example.com:443", &amp;tls.Config{})
if err != nil { log.Fatal(err) }
fmt.Println(c.ConnectionState().CurveID)</pre>
<p>Python 3.15 linked to OpenSSL 3.5:</p>
<pre dir="ltr">python3 -c "import ssl,socket; h='example.com'; t=ssl.create_default_context().wrap_socket(socket.create_connection((h,443)),server_hostname=h); print(t.group())"</pre>

<h2>Result says X25519?</h2>
<p>Then the server, load balancer or CDN that terminates TLS does not support it yet. Guides: <a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx</a>, <a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=en">Apache, Caddy, HAProxy, Cloudflare</a>, <a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=en">AWS</a>, <a href="/guides/nodejs-post-quantum-tls-x25519mlkem768?lang=en">Node.js</a>, <a href="/guides/java-post-quantum-tls-jdk27?lang=en">Java</a>, <a href="/guides/go-post-quantum-tls-x25519mlkem768?lang=en">Go</a>, <a href="/guides/python-post-quantum-tls-x25519mlkem768?lang=en">Python</a>. To see which hosting networks are ready, see <a href="/adoption/hosting?lang=en">readiness by hosting provider</a>.</p>
<p class="muted small">Sources: Chrome DevTools documentation and devtools-frontend source (Security panel "Connection / Key exchange"); OpenSSL 3.5 s_client; Go crypto/tls and Python ssl docs. Checked 2026-11-10.</p>
""",
        },
        "ar": {
            "title": "كيف تعرف إن كان موقع يستخدم TLS المقاوم للكم (X25519MLKEM768)",
            "description": "أربع طرق لتعرف هل يتفق الموقع على تبادل المفاتيح الهجين ML-KEM: أدوات المطوّر في Chrome، وopenssl s_client، وأسطر قليلة بـ Go أو Python، وفحص مجاني على الإنترنت.",
            "body": """
<p>الاتصال محمي من «احفظ الآن، فُكّ لاحقاً» حين يتفق المتصفح والخادم على تبادل مفاتيح هجين لما بعد الكم، وهو اليوم غالباً <code>X25519MLKEM768</code>. رمز القفل في المتصفح لا يخبرك بذلك. إليك أربع طرق للتحقق.</p>

<h2>1. على الإنترنت دون تثبيت</h2>
<p>اكتب النطاق في <a href="/?lang=ar">الفحص المجاني</a>. الدرجة A تعني TLS 1.3 مع تبادل مفاتيح هجين، ويشير التقرير أيضاً إلى مشاكل مثل أجهزة الشبكة التي تُسقط رسالة ClientHello الأكبر. ولمقارنة موقعين جنباً إلى جنب استخدم <a href="/compare?lang=ar">المقارنة</a>.</p>

<h2>2. أدوات المطوّر في Chrome أو Edge</h2>
<ol>
<li>افتح الموقع واضغط F12 (أو Ctrl+Shift+I، وفي Mac ‏Cmd+Option+I).</li>
<li>افتح لوحة <strong>Privacy and security</strong> (اسمها في الإصدارات الأقدم <strong>Security</strong>). إن لم تجدها: اضغط Ctrl+Shift+P واكتب <code>privacy</code> واختر «Show privacy and security».</li>
<li>أعد تحميل الصفحة، ثم اضغط على عنوان الموقع في العمود الأيسر.</li>
<li>تحت <strong>Connection</strong> اقرأ <strong>Key exchange</strong>. القيمة <code>X25519MLKEM768</code> تعني مقاوماً للكم، و<code>X25519</code> تعني كلاسيكياً فقط.</li>
</ol>
<p>Chrome يعرض X25519MLKEM768 افتراضياً منذ الإصدار 131، فما تراه يقرره الخادم.</p>

<h2>3. سطر الأوامر (OpenSSL 3.5 أو أحدث)</h2>
<pre dir="ltr">openssl version   # must be 3.5 or newer
openssl s_client -connect example.com:443 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -i group</pre>
<p>مع <code>-groups X25519MLKEM768</code> يعرض العميل المجموعة الهجينة فقط، فالخادم الكلاسيكي يفشل في الاتصال بدل أن يرجع بصمت إلى X25519. نسخ OpenSSL من 3.0 إلى 3.4 لا تستطيع هذا الفحص، ولا يذكر ناتجها ML-KEM أصلاً.</p>

<h2>4. أسطر قليلة من الكود</h2>
<p>Go 1.24 أو أحدث (مع <code>go 1.24</code> أو أحدث في go.mod):</p>
<pre dir="ltr">c, err := tls.Dial("tcp", "example.com:443", &amp;tls.Config{})
if err != nil { log.Fatal(err) }
fmt.Println(c.ConnectionState().CurveID)</pre>
<p>Python 3.15 مربوطاً بـ OpenSSL 3.5:</p>
<pre dir="ltr">python3 -c "import ssl,socket; h='example.com'; t=ssl.create_default_context().wrap_socket(socket.create_connection((h,443)),server_hostname=h); print(t.group())"</pre>

<h2>النتيجة X25519؟</h2>
<p>إذن الخادم أو موازن التحميل أو CDN الذي يُنهي TLS لا يدعمه بعد. الأدلة: <a href="/guides/enable-x25519mlkem768-nginx?lang=ar">nginx</a>، <a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=ar">Apache وCaddy وHAProxy وCloudflare</a>، <a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=ar">AWS</a>، <a href="/guides/nodejs-post-quantum-tls-x25519mlkem768?lang=ar">Node.js</a>، <a href="/guides/java-post-quantum-tls-jdk27?lang=ar">Java</a>، <a href="/guides/go-post-quantum-tls-x25519mlkem768?lang=ar">Go</a>، <a href="/guides/python-post-quantum-tls-x25519mlkem768?lang=ar">Python</a>. ولمعرفة شبكات الاستضافة الجاهزة انظر <a href="/adoption/hosting?lang=ar">الجاهزية حسب الاستضافة</a>.</p>
<p class="muted small">المصادر: توثيق أدوات المطوّر في Chrome وكود devtools-frontend (لوحة Security: ‏Connection / Key exchange)، وأداة s_client في OpenSSL 3.5، وتوثيق crypto/tls في Go وssl في Python. راجعناها في 2026-11-10.</p>
""",
        },
    },
    "ubuntu-openssl-3-0-post-quantum-tls": {
        "updated": "2026-11-13",
        "en": {
            "title": "Post-quantum TLS on Ubuntu 22.04, 24.04 and 26.04 LTS",
            "description": "Ubuntu 25.10 and 26.04 LTS negotiate X25519MLKEM768 by default, unless an old curve list overrides it. On 22.04 / 24.04 (OpenSSL 3.0): Caddy or a CDN in front, nginx with OpenSSL 3.5, or oqs-provider for testing.",
            "body": """
<p>Ubuntu 22.04 and 24.04 ship <strong>OpenSSL 3.0</strong>. ML-KEM arrived in OpenSSL 3.5, so nginx or Apache built against the system library cannot negotiate <code>X25519MLKEM768</code>, whatever the config says. That is why so many servers scan as "classical" even though Chrome and Firefox offer the hybrid exchange on every connection. There are three ways out; pick the first one that fits.</p>
<pre dir="ltr">openssl version                              # OpenSSL 3.0.x on Ubuntu 22.04 / 24.04
nginx -V 2&gt;&amp;1 | grep -o 'OpenSSL [0-9.]*'   # the library nginx was built with</pre>

<h2>Ubuntu 25.10 and 26.04 LTS: already on by default</h2>
<p>Ubuntu 25.10 ships OpenSSL 3.5, and its stock nginx negotiates <code>X25519MLKEM768</code> with no extra configuration. Canonical says Ubuntu 26.04 LTS uses a hybrid post-quantum key exchange by default as well. So upgrading from 24.04 is the simplest way to get it, with one catch: <strong>an explicit curve list from an old hardening guide replaces the new default instead of extending it</strong>, and the server stays classical after the upgrade. Look for such lines before and after upgrading:</p>
<pre dir="ltr">grep -rnE 'ssl_ecdh_curve|SSLOpenSSLConfCmd +(Curves|Groups)' /etc/nginx /etc/apache2 /etc/letsencrypt 2&gt;/dev/null</pre>
<p>If a line turns up, the cleanest fix is to delete it so the library default applies (nginx's default is <code>ssl_ecdh_curve auto</code>). If you must keep an explicit list, put <code>X25519MLKEM768</code> first, as in the <a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx guide</a>. Then run <code>nginx -t</code> (or <code>apachectl configtest</code>) and reload. One more thing to expect: the hybrid key share makes the first TLS message about 1.2 KB larger, and a few old middleboxes mishandle that, so test clients behind corporate firewalls too.</p>

<h2>Option 1 (easiest): put Caddy or a CDN in front</h2>
<p>Caddy is written in Go, whose TLS stack supports X25519MLKEM768 by default, independent of the system OpenSSL. Let Caddy terminate TLS on port 443 and pass requests to your existing server on localhost. This very site runs this way and grades A.</p>
<pre dir="ltr"># /etc/caddy/Caddyfile
example.com {
    reverse_proxy 127.0.0.1:8080   # nginx/Apache now listen on 8080 without TLS
}</pre>
<p>Caddy obtains and renews the certificate itself. Move nginx's <code>listen 443 ssl</code> to <code>listen 127.0.0.1:8080</code>, reload both, and scan again. A CDN that already offers the hybrid (for example Cloudflare's proxy) has the same effect for visitors; the connection from the CDN to your origin is a separate leg.</p>

<h2>Option 2 (production nginx): OpenSSL 3.5</h2>
<p>Either move to a release that ships OpenSSL 3.5 (Debian 13 "trixie" does; check <code>openssl version</code> on newer Ubuntu releases), or build nginx against an OpenSSL 3.5 source tree. nginx links it statically, so the system library stays untouched:</p>
<pre dir="ltr">sudo apt install -y build-essential libpcre2-dev zlib1g-dev
# download and verify the nginx and OpenSSL 3.5.x source tarballs from nginx.org and openssl-library.org
cd nginx-1.x.y
./configure --with-openssl=../openssl-3.5.x --with-http_ssl_module --with-http_v2_module \
            --prefix=/etc/nginx --sbin-path=/usr/sbin/nginx   # match your current nginx -V flags
make -j"$(nproc)" &amp;&amp; sudo make install</pre>
<p>Copy the remaining <code>configure</code> arguments from your current <code>nginx -V</code> output so modules and paths stay the same. Then follow the <a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx guide</a> for the <code>ssl_ecdh_curve</code> line. A self-built nginx no longer receives Ubuntu security updates: you have to rebuild it for every nginx or OpenSSL fix.</p>

<h2>Option 3 (testing only): oqs-provider on OpenSSL 3.0</h2>
<p>The Open Quantum Safe project's <a href="https://github.com/open-quantum-safe/oqs-provider" rel="noopener">oqs-provider</a> adds ML-KEM to OpenSSL 3.0 as a loadable provider, built on <a href="https://github.com/open-quantum-safe/liboqs" rel="noopener">liboqs</a>. The project itself states that it is intended for prototyping and evaluation, not production. Use it on a test server to try the hybrid exchange before you upgrade.</p>
<pre dir="ltr">sudo apt install -y build-essential cmake ninja-build libssl-dev git
git clone https://github.com/open-quantum-safe/liboqs.git
cmake -S liboqs -B liboqs/build -GNinja -DBUILD_SHARED_LIBS=ON
sudo cmake --build liboqs/build --target install &amp;&amp; sudo ldconfig
git clone https://github.com/open-quantum-safe/oqs-provider.git
cmake -S oqs-provider -B oqs-provider/build -GNinja
sudo cmake --build oqs-provider/build --target install
openssl version -m   # MODULESDIR: where oqsprovider.so was installed</pre>
<p>Do <strong>not</strong> edit the system-wide <code>/etc/ssl/openssl.cnf</code>: apt, curl, Python and every other program read it. Give nginx its own file instead:</p>
<pre dir="ltr"># /etc/nginx/openssl-oqs.cnf
openssl_conf = openssl_init
[openssl_init]
providers = provider_sect
[provider_sect]
default = default_sect
oqsprovider = oqs_sect
[default_sect]
activate = 1
[oqs_sect]
activate = 1</pre>
<pre dir="ltr">sudo systemctl edit nginx
# add:
[Service]
Environment=OPENSSL_CONF=/etc/nginx/openssl-oqs.cnf</pre>
<p>Check the exact group name your build offers with <code>OPENSSL_CONF=/etc/nginx/openssl-oqs.cnf openssl list -kem-algorithms</code>, put it first in <code>ssl_ecdh_curve</code> (for example <code>X25519MLKEM768:X25519:prime256v1</code>), then <code>nginx -t &amp;&amp; systemctl restart nginx</code>. These steps follow the OQS documentation; we have not run them on our own servers, so read the project's README for the requirements of the version you build.</p>

<h2>Verify</h2>
<p>Run the <a href="/?lang=en">free scan</a>: grade A means TLS 1.3 with a hybrid post-quantum key exchange. The scan also answers a HelloRetryRequest the way browsers do, so servers that ask for a different group are measured too. For continuous checks, the <a href="https://github.com/marketplace/actions/post-quantum-tls-check-quantum-aether" rel="noopener">GitHub Action</a> fails a build when the hybrid disappears.</p>
<p class="muted small">Sources: Canonical's "Post-quantum support in the upcoming 26.04 LTS" (Ubuntu Discourse), OpenSSL 3.5 release notes (ML-KEM), nginx <code>--with-openssl</code> build option, Open Quantum Safe liboqs and oqs-provider READMEs, Go crypto/tls default key exchanges.</p>
""",
        },
        "ar": {
            "title": "TLS المقاوم للكم على Ubuntu 22.04 و24.04 و26.04 LTS",
            "description": "يتفاوض Ubuntu 25.10 و26.04 LTS على X25519MLKEM768 افتراضياً، ما لم تُلغِه قائمة منحنيات قديمة. على 22.04 و24.04 (OpenSSL 3.0): ‏Caddy أو CDN أمام الخادم، أو nginx مع OpenSSL 3.5، أو oqs-provider للتجربة.",
            "body": """
<p>يأتي Ubuntu 22.04 و24.04 مع <strong>OpenSSL 3.0</strong>. دعم ML-KEM وصل في OpenSSL 3.5، لذلك لا يستطيع nginx أو Apache المبنيّ على مكتبة النظام التفاوض على <code>X25519MLKEM768</code> مهما كتبت في الإعدادات. هذا سبب ظهور خوادم كثيرة «تقليدية» في الفحص رغم أن Chrome وFirefox يعرضان التبادل الهجين في كل اتصال. أمامك ثلاثة طرق؛ اختر أول طريق يناسبك.</p>
<pre dir="ltr">openssl version                              # OpenSSL 3.0.x on Ubuntu 22.04 / 24.04
nginx -V 2&gt;&amp;1 | grep -o 'OpenSSL [0-9.]*'   # the library nginx was built with</pre>

<h2>Ubuntu 25.10 و26.04 LTS: مفعّل افتراضياً</h2>
<p>يأتي Ubuntu 25.10 مع OpenSSL 3.5، ويتفاوض nginx الأصلي فيه على <code>X25519MLKEM768</code> دون أي إعداد إضافي. وتقول Canonical إن Ubuntu 26.04 LTS يستخدم تبادل مفاتيح هجيناً مقاوماً للكم افتراضياً أيضاً. لذلك الترقية من 24.04 أبسط طريق، مع تنبيه واحد: <strong>قائمة المنحنيات الصريحة المنسوخة من دليل حماية قديم تحلّ محل القائمة الافتراضية الجديدة ولا تضيف إليها</strong>، فيبقى الخادم «تقليدياً» بعد الترقية. ابحث عن هذه الأسطر قبل الترقية وبعدها:</p>
<pre dir="ltr">grep -rnE 'ssl_ecdh_curve|SSLOpenSSLConfCmd +(Curves|Groups)' /etc/nginx /etc/apache2 /etc/letsencrypt 2&gt;/dev/null</pre>
<p>إن ظهر سطر، فأنظف حل هو حذفه لتُطبَّق القائمة الافتراضية للمكتبة (الإعداد الافتراضي في nginx هو <code>ssl_ecdh_curve auto</code>). وإن احتجت قائمة صريحة فضع <code>X25519MLKEM768</code> أولاً كما في <a href="/guides/enable-x25519mlkem768-nginx?lang=ar">دليل nginx</a>. ثم شغّل <code>nginx -t</code> (أو <code>apachectl configtest</code>) وأعد التحميل. وتوقّع أمراً آخر: المفتاح الهجين يزيد أول رسالة TLS بنحو 1.2 كيلوبايت، وبعض أجهزة الشبكة القديمة لا تتعامل معها جيداً، فجرّب أيضاً من أجهزة خلف جدران نارية مؤسسية.</p>

<h2>الطريق 1 (الأسهل): Caddy أو CDN أمام الخادم</h2>
<p>Caddy مكتوب بلغة Go، ومكتبة TLS فيها تدعم X25519MLKEM768 افتراضياً بمعزل عن OpenSSL النظام. اجعل Caddy يستقبل TLS على المنفذ 443 ويمرّر الطلبات إلى خادمك الحالي على العنوان المحلي. هذا الموقع نفسه يعمل بهذه الطريقة ودرجته A.</p>
<pre dir="ltr"># /etc/caddy/Caddyfile
example.com {
    reverse_proxy 127.0.0.1:8080   # nginx/Apache now listen on 8080 without TLS
}</pre>
<p>يحصل Caddy على الشهادة ويجددها بنفسه. غيّر في nginx السطر <code>listen 443 ssl</code> إلى <code>listen 127.0.0.1:8080</code>، وأعد تحميل الاثنين، ثم افحص من جديد. شبكة CDN تدعم الهجين (مثل وكيل Cloudflare) تعطي الأثر نفسه للزوار؛ أما الاتصال من CDN إلى خادمك الأصلي فمرحلة منفصلة.</p>

<h2>الطريق 2 (nginx للإنتاج): OpenSSL 3.5</h2>
<p>إما أن تنتقل إلى إصدار يأتي مع OpenSSL 3.5 (مثل Debian 13 «trixie»؛ وتحقق بـ <code>openssl version</code> في إصدارات Ubuntu الأحدث)، أو تبني nginx على شجرة مصدر OpenSSL 3.5. يربطها nginx ربطاً ثابتاً فتبقى مكتبة النظام كما هي:</p>
<pre dir="ltr">sudo apt install -y build-essential libpcre2-dev zlib1g-dev
# download and verify the nginx and OpenSSL 3.5.x source tarballs from nginx.org and openssl-library.org
cd nginx-1.x.y
./configure --with-openssl=../openssl-3.5.x --with-http_ssl_module --with-http_v2_module \
            --prefix=/etc/nginx --sbin-path=/usr/sbin/nginx   # match your current nginx -V flags
make -j"$(nproc)" &amp;&amp; sudo make install</pre>
<p>انسخ بقية خيارات <code>configure</code> من ناتج <code>nginx -V</code> الحالي حتى تبقى الوحدات والمسارات كما هي. ثم اتبع <a href="/guides/enable-x25519mlkem768-nginx?lang=ar">دليل nginx</a> لسطر <code>ssl_ecdh_curve</code>. انتبه: nginx المبني يدوياً لا يصله تحديث Ubuntu الأمني، فعليك إعادة بنائه مع كل إصلاح لـ nginx أو OpenSSL.</p>

<h2>الطريق 3 (للتجربة فقط): oqs-provider على OpenSSL 3.0</h2>
<p>مشروع Open Quantum Safe يقدّم <a href="https://github.com/open-quantum-safe/oqs-provider" rel="noopener">oqs-provider</a> الذي يضيف ML-KEM إلى OpenSSL 3.0 كمزوّد قابل للتحميل، مبنياً على <a href="https://github.com/open-quantum-safe/liboqs" rel="noopener">liboqs</a>. المشروع نفسه يقول إنه للنماذج الأولية والتقييم، لا للإنتاج. استخدمه على خادم تجربة لتختبر التبادل الهجين قبل الترقية.</p>
<pre dir="ltr">sudo apt install -y build-essential cmake ninja-build libssl-dev git
git clone https://github.com/open-quantum-safe/liboqs.git
cmake -S liboqs -B liboqs/build -GNinja -DBUILD_SHARED_LIBS=ON
sudo cmake --build liboqs/build --target install &amp;&amp; sudo ldconfig
git clone https://github.com/open-quantum-safe/oqs-provider.git
cmake -S oqs-provider -B oqs-provider/build -GNinja
sudo cmake --build oqs-provider/build --target install
openssl version -m   # MODULESDIR: where oqsprovider.so was installed</pre>
<p><strong>لا</strong> تعدّل الملف العام <code>/etc/ssl/openssl.cnf</code>: يقرؤه apt وcurl وPython وكل برنامج آخر. أعطِ nginx ملفاً خاصاً به:</p>
<pre dir="ltr"># /etc/nginx/openssl-oqs.cnf
openssl_conf = openssl_init
[openssl_init]
providers = provider_sect
[provider_sect]
default = default_sect
oqsprovider = oqs_sect
[default_sect]
activate = 1
[oqs_sect]
activate = 1</pre>
<pre dir="ltr">sudo systemctl edit nginx
# add:
[Service]
Environment=OPENSSL_CONF=/etc/nginx/openssl-oqs.cnf</pre>
<p>تحقق من الاسم الدقيق للمجموعة في نسختك بالأمر <code>OPENSSL_CONF=/etc/nginx/openssl-oqs.cnf openssl list -kem-algorithms</code>، وضعه أولاً في <code>ssl_ecdh_curve</code> (مثلاً <code>X25519MLKEM768:X25519:prime256v1</code>)، ثم <code>nginx -t &amp;&amp; systemctl restart nginx</code>. هذه الخطوات تتبع توثيق OQS، ولم نشغّلها على خوادمنا، فراجع ملف README للمشروع لمتطلبات النسخة التي تبنيها.</p>

<h2>التحقق</h2>
<p>شغّل <a href="/?lang=ar">الفحص المجاني</a>: الدرجة A تعني TLS 1.3 مع تبادل مفاتيح هجين مقاوم للكم. الفحص يجيب أيضاً على طلب HelloRetryRequest كما تفعل المتصفحات، فتُقاس الخوادم التي تطلب مجموعة أخرى كذلك. وللفحص المستمر، <a href="https://github.com/marketplace/actions/post-quantum-tls-check-quantum-aether" rel="noopener">GitHub Action</a> يُفشل البناء إذا اختفى التبادل الهجين.</p>
<p class="muted small">المصادر: إعلان Canonical عن دعم التشفير المقاوم للكم في 26.04 LTS ‏(Ubuntu Discourse)، وملاحظات إصدار OpenSSL 3.5 (ML-KEM)، وخيار البناء <code>--with-openssl</code> في nginx، وملفات README لمشروعي liboqs وoqs-provider من Open Quantum Safe، والمجموعات الافتراضية في crypto/tls بلغة Go.</p>
""",
        },
    },
    "ssl-labs-post-quantum-tls-check": {
        "updated": "2026-11-24",
        "en": {
            "title": "SSL Labs vs post-quantum TLS check (X25519MLKEM768)",
            "description": "Does SSL Labs test post-quantum TLS (X25519MLKEM768)? Compare SSL Labs with a dedicated PQ-TLS check for HelloRetryRequest, PQ-only servers and daily alerts.",
            "body": """
<p><a href="https://www.ssllabs.com/ssltest/" rel="noopener">Qualys SSL Labs</a> is the best-known free TLS audit tool, and it now lists post-quantum key exchange groups as well. So when do you still need a dedicated post-quantum TLS check? Because the two tools answer different operational questions.</p>

<h2>Side-by-side comparison</h2>
<table class="data">
<thead><tr><th>Check</th><th>SSL Labs</th><th>Quantum Aether</th></tr></thead>
<tbody>
<tr><td>Full one-off TLS &amp; cipher audit</td><td>Yes (60–120s)</td><td>Focused on PQ key exchange + cert summary (2–5s)</td></tr>
<tr><td>X25519MLKEM768 &amp; HelloRetryRequest</td><td>Reports groups; PQ-only configs can fail</td><td>Offers hybrid + pure ML-KEM, handles HRR like browsers</td></tr>
<tr><td>IPv4 + IPv6 endpoint consistency</td><td>All A/AAAA IPs</td><td>Up to 6 public IPs, flags mixed CDN edges</td></tr>
<tr><td>Daily regression alerts (silent downgrade)</td><td>No (manual one-off)</td><td>Yes (<a href="/monitoring?lang=en">14-day free trial</a>, CI GitHub Action)</td></tr>
<tr><td>Automation (API, CLI, MCP, A2A)</td><td>REST API</td><td>REST API, CLI (<code>npx quantum-aether</code>), MCP &amp; A2A</td></tr>
</tbody>
</table>

<h2>What SSL Labs is best at</h2>
<ul>
<li>A thorough one-off audit of the whole TLS configuration: protocol versions, cipher suites, certificate chain, known vulnerabilities, and a letter grade for all of it.</li>
<li>Testing every IP address a hostname resolves to.</li>
<li>A widely recognised result to show auditors and customers.</li>
</ul>

<h2>Where a dedicated post-quantum check helps</h2>
<ul>
<li><strong>Post-quantum-only servers.</strong> Some deployments accept only hybrid or pure ML-KEM groups. F5 documents cases of <a href="https://my.f5.com/manage/s/article/K000161411" rel="noopener">post-quantum configurations failing in SSL Labs</a>. Our probe offers X25519MLKEM768, the other hybrids and pure ML-KEM-768/1024, and answers a HelloRetryRequest once as browsers do, so the group the server finally selects is recorded.</li>
<li><strong>One question, answered in seconds.</strong> Does the server negotiate X25519MLKEM768 with a browser today: yes, no, or undetermined, with the evidence.</li>
<li><strong>Staying fixed.</strong> A one-off test cannot tell you that a load-balancer update or a CDN change quietly removed the hybrid exchange. <a href="/monitoring?lang=en">Daily monitoring</a> emails you when it disappears, and the <a href="https://github.com/marketplace/actions/post-quantum-tls-check-quantum-aether" rel="noopener">GitHub Action</a> fails a deployment that drops it.</li>
<li><strong>Fix steps for your stack.</strong> Guides for <a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx</a>, <a href="/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=en">Ubuntu with OpenSSL 3.0</a>, <a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=en">Apache, Caddy, HAProxy and Cloudflare</a>, <a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=en">AWS</a>, and <a href="/guides/openssl-3-5-curl-test-x25519mlkem768?lang=en">OpenSSL 3.5 / curl CLI verification</a>.</li>
<li><strong>Context.</strong> How your site compares with the top 10,000 sites, every week, in an <a href="/adoption?lang=en">open dataset</a>.</li>
</ul>

<h2>What neither test can tell you</h2>
<p>Both see one public HTTPS connection. Neither sees the connection from a CDN to your origin, internal services, or other protocols such as SSH and VPNs. And a hybrid key exchange does not make certificates post-quantum: browsers do not accept ML-DSA certificates yet, so RSA and ECDSA certificates are expected today.</p>

<h2>When results differ</h2>
<p>Different results usually have a simple cause: the two tests reached different IP addresses (anycast CDNs, several A records), or the server was changed between the two runs. Run our <a href="/?lang=en">free scan</a> again and compare the IP address in the result with the one SSL Labs tested.</p>
""",
        },
        "ar": {
            "title": "مقارنة SSL Labs مع فحص TLS المقاوم للكم (X25519MLKEM768)",
            "description": "هل يفحص SSL Labs التشفير المقاوم للكم X25519MLKEM768؟ مقارنة عملية مع الفحص المخصص لما بعد الكم وHelloRetryRequest والمراقبة اليومية.",
            "body": """
<p><a href="https://www.ssllabs.com/ssltest/" rel="noopener">Qualys SSL Labs</a> أشهر أداة مجانية لتدقيق TLS، وصار يعرض أيضاً مجموعات تبادل المفاتيح المقاومة للكم. فمتى تحتاج مع ذلك إلى فحص مخصص لـ TLS المقاوم للكم؟ لأن الأداتين تجيبان عن سؤالين تشغيليين مختلفين.</p>

<h2>مقارنة مباشرة</h2>
<table class="data">
<thead><tr><th>المعيار</th><th>SSL Labs</th><th>Quantum Aether</th></tr></thead>
<tbody>
<tr><td>تدقيق TLS الكامل والشهادات</td><td>شامل لمرة واحدة (60–120 ثانية)</td><td>مركّز على تبادل المفاتيح الكمومي + ملخص الشهادة (2–5 ثوانٍ)</td></tr>
<tr><td>X25519MLKEM768 وHelloRetryRequest</td><td>يعرض المجموعات؛ قد تفشل إعدادات PQ فقط</td><td>يعرض الهجين وML-KEM الخالص ويجيب HRR كالمتصفحات</td></tr>
<tr><td>اتساق نقاط IPv4 وIPv6</td><td>كل العناوين</td><td>حتى 6 عناوين عامة مع تنبيه اختلاف حواف CDN</td></tr>
<tr><td>مراقبة يومية للتراجع الصامت</td><td>لا (فحص يدوي لمرة واحدة)</td><td>نعم (<a href="/monitoring?lang=ar">تجربة 14 يوماً مجاناً</a> + GitHub Action)</td></tr>
<tr><td>الأتمتة (API / CLI / MCP)</td><td>REST API</td><td>REST API وCLI وMCP وA2A</td></tr>
</tbody>
</table>

<h2>ما يتفوق فيه SSL Labs</h2>
<ul>
<li>تدقيق شامل لمرة واحدة لكامل إعدادات TLS: إصدارات البروتوكول، ومجموعات التشفير، وسلسلة الشهادات، والثغرات المعروفة، ودرجة لكل ذلك.</li>
<li>فحص كل عنوان IP يشير إليه اسم النطاق.</li>
<li>نتيجة معروفة على نطاق واسع تعرضها على المدققين والعملاء.</li>
</ul>

<h2>أين يفيد فحص مخصص لما بعد الكم</h2>
<ul>
<li><strong>الخوادم التي لا تقبل إلا التشفير المقاوم للكم.</strong> بعض الإعدادات تقبل المجموعات الهجينة أو ML-KEM الخالص فقط. وتوثّق F5 حالات <a href="https://my.f5.com/manage/s/article/K000161411" rel="noopener">فشل إعدادات ما بعد الكم في SSL Labs</a>. مجسّنا يعرض X25519MLKEM768 وبقية المجموعات الهجينة وML-KEM-768/1024 الخالص، ويجيب على طلب HelloRetryRequest مرة واحدة كما تفعل المتصفحات، فيسجّل المجموعة التي يختارها الخادم في النهاية.</li>
<li><strong>سؤال واحد بإجابة خلال ثوانٍ.</strong> هل يتفاوض الخادم اليوم على X25519MLKEM768 مع المتصفح: نعم، أو لا، أو غير محسوم، مع الدليل.</li>
<li><strong>بقاء الإصلاح.</strong> الفحص لمرة واحدة لا يخبرك أن تحديثاً لموازن التحميل أو تغييراً في CDN أزال التبادل الهجين بصمت. <a href="/monitoring?lang=ar">المراقبة اليومية</a> تراسلك حين يختفي، و<a href="https://github.com/marketplace/actions/post-quantum-tls-check-quantum-aether" rel="noopener">GitHub Action</a> يُفشل أي نشر يُسقطه.</li>
<li><strong>خطوات إصلاح لبيئتك.</strong> أدلة لـ <a href="/guides/enable-x25519mlkem768-nginx?lang=ar">nginx</a>، و<a href="/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=ar">Ubuntu مع OpenSSL 3.0</a>، و<a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=ar">Apache وCaddy وHAProxy وCloudflare</a>، و<a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=ar">AWS</a>، و<a href="/guides/openssl-3-5-curl-test-x25519mlkem768?lang=ar">الفحص عبر OpenSSL 3.5 وcurl</a>.</li>
<li><strong>السياق.</strong> موقعك مقارنة بأكبر 10,000 موقع، كل أسبوع، في <a href="/adoption?lang=ar">بيانات مفتوحة</a>.</li>
</ul>

<h2>ما لا يخبرك به أي من الفحصين</h2>
<p>كلاهما يرى اتصال HTTPS عاماً واحداً. لا يرى أيٌّ منهما الاتصال بين CDN وخادمك الأصلي، ولا الخدمات الداخلية، ولا بروتوكولات أخرى مثل SSH وVPN. والتبادل الهجين لا يجعل الشهادات مقاومة للكم: المتصفحات لا تقبل شهادات ML-DSA بعد، فشهادات RSA وECDSA متوقعة اليوم.</p>

<h2>إذا اختلفت النتيجتان</h2>
<p>للاختلاف عادة سبب بسيط: وصل الفحصان إلى عنوانَي IP مختلفين (شبكات CDN أو عدة سجلات A)، أو تغيّر الخادم بين الفحصين. أعد <a href="/?lang=ar">الفحص المجاني</a> وقارن عنوان IP في النتيجة بالعنوان الذي فحصه SSL Labs.</p>
""",
        },
        "de": {
            "title": "SSL Labs vs. Post-Quanten-TLS-Check (X25519MLKEM768)",
            "description": "Prüft SSL Labs Post-Quanten-TLS (X25519MLKEM768)? Vergleich mit einem dedizierten PQ-TLS-Check für HelloRetryRequest, PQ-only-Server und tägliche Warnungen.",
            "body": """
<p><a href="https://www.ssllabs.com/ssltest/" rel="noopener">Qualys SSL Labs</a> ist der bekannteste kostenlose TLS-Test und zeigt inzwischen auch Post-Quanten-Gruppen an. Wann lohnt sich zusätzlich ein dedizierter Post-Quanten-TLS-Check? Weil beide Werkzeuge unterschiedliche Betriebsfragen beantworten.</p>

<h2>Direkter Vergleich</h2>
<table class="data">
<thead><tr><th>Prüfpunkt</th><th>SSL Labs</th><th>Quantum Aether</th></tr></thead>
<tbody>
<tr><td>Vollständiges einmaliges TLS-Audit</td><td>Ja (60–120 s)</td><td>Fokus auf PQ-Schlüsselaustausch + Zertifikatsübersicht (2–5 s)</td></tr>
<tr><td>X25519MLKEM768 &amp; HelloRetryRequest</td><td>Zeigt Gruppen; PQ-only-Setups können scheitern</td><td>Bietet Hybrid + reines ML-KEM, beantwortet HRR wie Browser</td></tr>
<tr><td>Konsistenz über IPv4 &amp; IPv6</td><td>Alle A/AAAA-IPs</td><td>Bis zu 6 öffentliche IPs, erkennt uneinheitliche CDN-Edges</td></tr>
<tr><td>Tägliche Warnung bei leisem Rückfall</td><td>Nein (manuell)</td><td>Ja (<a href="/monitoring?lang=de">14 Tage kostenlos testen</a>, GitHub Action)</td></tr>
</tbody>
</table>

<h2>Wann SSL Labs und wann ein PQ-Check passt</h2>
<ul>
<li><strong>SSL Labs</strong> eignet sich für ein tiefes Einzel-Audit aller Cipher-Suites, Zertifikatsketten und historischen Schwachstellen.</li>
<li><strong>Quantum Aether</strong> prüft in wenigen Sekunden gezielt, ob ein Browser heute <code>X25519MLKEM768</code> aushandelt, unterstützt PQ-only-Server (bei denen F5 <a href="https://my.f5.com/manage/s/article/K000161411" rel="noopener">Probleme mit SSL Labs</a> dokumentiert) und überwacht Änderungen täglich.</li>
</ul>

<h2>Grenzen beider Tests</h2>
<p>Beide sehen nur den öffentlichen HTTPS-Endpunkt (oft ein CDN), nicht die Verbindung zum Origin-Server oder interne Dienste. Klassische RSA/ECDSA-Zertifikate sind 2026 weiterhin normal, weil Browser noch keine ML-DSA-Zertifikate akzeptieren. <a href="/?lang=de">Domain jetzt kostenlos prüfen</a>.</p>
""",
        },
    },
    "gulf-banks-post-quantum-cryptography-requirements": {
        "updated": "2026-11-21",
        "en": {
            "title": "Gulf banks PQC rules: SAMA & UAE (2026)",
            "description": "SAMA circular 482021280 deadlines, Saudi National Cryptographic Standards (NCS-2) clauses and UAE National Encryption Policy rules for Gulf banks.",
            "body": """
<p>As of November 2026, Saudi Arabia is the only Gulf state with a binding post-quantum requirement aimed at banks: a SAMA circular that sets deadlines for a cryptographic inventory and a quantum risk assessment. The UAE requires migration plans from government entities. We found no published post-quantum requirement for banks from the central banks of Qatar, Bahrain, Oman or Kuwait.</p>

<h2>Saudi Arabia: SAMA circular 482021280</h2>
<p>On 27 August 2026 (14/03/1448 AH) the Saudi Central Bank issued circular No. 482021280, <em>Enhancement of Operational Resilience to Address Quantum Computing Risks</em>, to the financial institutions it supervises. The SAMA Rulebook lists it as in force. It requires:</p>
<ol>
<li><strong>By the end of Q4 2026 (31 December 2026):</strong> accurate and comprehensive procedures to identify and classify all cryptographic assets, classify the related data, systems and services by sensitivity and migration priority, and assess the cryptographic resilience of priority assets, including constraints and third-party dependencies.</li>
<li><strong>By the end of Q1 2027 (31 March 2027):</strong> an enterprise-level assessment of quantum computing risks within enterprise risk management, with action plans.</li>
<li><strong>No date set:</strong> plans to reach the required cryptographic resilience, or appropriate alternatives, for all priority assets.</li>
<li><strong>No date set:</strong> quantum risk as a standing item for the Information Security Supervisory Committee and the Risk Committee, with reporting to the board.</li>
</ol>
<p>The circular does not name algorithms and does not set a date for completing the migration. The signed text is in Arabic; the English version in the rulebook has no legal effect.</p>

<h2>Saudi Arabia: National Cryptographic Standards (NCA)</h2>
<p>The version published on the NCA website today is still <strong>NCS-1:2020</strong>, which only says that post-quantum cryptography "will be considered" in later versions. The updated <strong>NCS-2:2025</strong> was published for public consultation (closed 25 December 2025). It applies to "national entities" and contains a section on post-quantum algorithms:</p>
<ul>
<li><strong>2-5-1:</strong> ML-KEM (FIPS 203): ML-KEM-512 and ML-KEM-768 for the MODERATE level, ML-KEM-1024 for ADVANCED.</li>
<li><strong>2-5-3 and 2-5-4:</strong> ML-DSA (FIPS 204) and SLH-DSA (FIPS 205) for signatures; 2-5-2 also accepts Classic McEliece.</li>
<li><strong>2-5-5-1:</strong> "A post-quantum cryptosystem must be used in hybrid with approved classical cryptosystems."</li>
<li><strong>2-5-5-2:</strong> "All cryptographic systems or solutions must support PQC algorithms."</li>
</ul>
<p>The hybrid group that browsers use today, <code>X25519MLKEM768</code>, combines Curve25519 (accepted for MODERATE in 2-4-3-1) with ML-KEM-768, so it matches both clauses. Check the NCA website for the final status before citing NCS-2 in an audit.</p>

<h2>United Arab Emirates</h2>
<ul>
<li><strong>National Encryption Policy</strong> (UAE Cyber Security Council, approval announced 27 November 2025): government entities must prepare officially approved plans to move from classical public-key cryptography (RSA, ECC) to post-quantum cryptography, keep an automated inventory of cryptographic assets and design new systems to be crypto-agile. No submission deadline has been published.</li>
<li><strong>National post-quantum transition programme</strong> (Cyber Security Council and ATRC, announced 11 May 2026): a cryptographic discovery tool, TII cryptographic libraries with post-quantum algorithms, and a quantum key distribution pilot. It names "critical sectors", not banks specifically, and sets no deadline.</li>
<li><strong>Central Bank of the UAE:</strong> its 2026 operational risk regulation covers ICT and cyber risk; we found no post-quantum requirement in public reporting about it.</li>
</ul>

<h2>Qatar, Bahrain, Oman and Kuwait</h2>
<p>We found no published post-quantum requirement for banks from the Qatar Central Bank, the Central Bank of Bahrain, the Central Bank of Oman or the Central Bank of Kuwait as of November 2026. Banks there that are listed abroad or serve EU customers may still face <a href="/guides/nis2-dora-post-quantum-cryptography?lang=en">DORA</a> or partner requirements, and the global timelines are on <a href="/deadlines?lang=en">post-quantum deadlines</a>.</p>

<h2>Where Gulf banks stand today</h2>
<p>Our <a href="/banks/arab-banks-2026-11?lang=en">Arab banks report</a> (measured 12 November 2026) counted the public subdomains of each bank that negotiate a post-quantum key exchange:</p>
<ul>
<li><strong>Qatar:</strong> 74 of 108 responding subdomains (3 banks).</li>
<li><strong>UAE:</strong> 51 of 234 (5 banks).</li>
<li><strong>Kuwait:</strong> 11 of 81 (3 banks).</li>
<li><strong>Saudi Arabia:</strong> 18 of 219 (7 banks), and none of the 6 measured main websites.</li>
</ul>
<p>So the country with the strictest written rules has the lowest share on its public endpoints. Often the cause is not the bank's own servers but a load balancer, WAF or CDN that has not enabled the hybrid group yet.</p>

<h2>What a bank can do before 31 December 2026</h2>
<ol>
<li><strong>Start the inventory with public TLS endpoints.</strong> They are the easiest assets to enumerate and the most exposed to "<a href="/guides/harvest-now-decrypt-later?lang=en">harvest now, decrypt later</a>". For each hostname record the date, TLS version, negotiated group and who terminates TLS (CDN, load balancer or origin).</li>
<li><strong>Mark third-party dependencies.</strong> The SAMA circular asks for them explicitly. A CDN or WAF vendor that does not offer X25519MLKEM768 is a constraint to document, with the vendor's roadmap.</li>
<li><strong>Enable the hybrid key exchange where you control the server.</strong> See the guides for <a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx</a>, <a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=en">Apache, Caddy, HAProxy and Cloudflare</a> and <a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=en">AWS</a>, or the <a href="/tools/pq-tls-config?lang=en">configuration generator</a>.</li>
<li><strong>Keep evidence over time.</strong> One scan shows one day; regular checks show the board committee progress and catch regressions after vendor changes.</li>
</ol>
<p>A free check of one host is on the <a href="/?lang=en">home page</a>; an <a href="/audit?lang=en">estate audit</a> covers all of an organisation's public subdomains.</p>

<h2>What a TLS check does not prove</h2>
<p>A public scan sees one endpoint on port 443 at one moment. It does not cover internal systems, HSMs, card and payment protocols, stored data, certificates or key management, which the SAMA inventory also has to include. It is evidence for one part of the inventory, not a compliance certificate.</p>

<h2>Sources</h2>
<ul>
<li><a href="https://rulebook.sama.gov.sa/en/enhancement-operational-resilience-address-quantum-computing-risks" rel="noopener">SAMA Rulebook: Enhancement of Operational Resilience to Address Quantum Computing Risks</a> (circular 482021280, 27/08/2026)</li>
<li><a href="https://nca.gov.sa/ncs_en.pdf" rel="noopener">NCA: National Cryptographic Standards NCS-1:2020</a> (current version on the NCA site)</li>
<li><a href="https://istitlaa.ncc.gov.sa/en/security/nca/ncs/Documents/NCS-2-en.pdf" rel="noopener">NCA: NCS-2:2025, consultation version</a>, sections 2-4-3, 2-5</li>
<li><a href="https://u.ae/en/about-the-uae/strategies-initiatives-and-awards/policies/cyber-activities/National-Encryption-Policy" rel="noopener">UAE government portal: National Encryption Policy</a></li>
<li><a href="https://www.atrc.gov.ae/news/uae-cyber-security-council-partners-atrc-advance-national-post-quantum-security-transition" rel="noopener">ATRC: Cyber Security Council partners with ATRC on the post-quantum transition</a> (11 May 2026)</li>
</ul>
""",
        },
        "ar": {
            "title": "متطلبات التشفير الكمي لبنوك الخليج (2026)",
            "description": "ما يشترطه تعميم ساما 482021280 والمعايير الوطنية للتشفير في السعودية وسياسة التشفير الوطنية في الإمارات، مع التواريخ ونتائج فحص البنوك الخليجية.",
            "body": """
<p>حتى نوفمبر 2026، السعودية هي الدولة الخليجية الوحيدة التي لديها متطلب مُلزِم للبنوك بشأن التشفير ما بعد الكمومي: تعميم من البنك المركزي السعودي (ساما) يحدد مواعيد لحصر أصول التشفير وتقييم المخاطر الكمومية. أما الإمارات فتشترط خطط انتقال على الجهات الحكومية. ولم نجد متطلباً منشوراً للبنوك من البنوك المركزية في قطر والبحرين وعُمان والكويت.</p>

<h2>السعودية: تعميم ساما رقم 482021280</h2>
<p>أصدر البنك المركزي السعودي في 14/03/1448هـ (27 أغسطس 2026) التعميم رقم 482021280 بعنوان <em>تعزيز المرونة التشغيلية لمواجهة مخاطر الحوسبة الكمومية</em>، موجّهاً إلى المؤسسات المالية الخاضعة لإشرافه، وهو مُدرج في دليل الأنظمة (Rulebook) على أنه ساري المفعول. ويشترط:</p>
<ol>
<li><strong>بنهاية الربع الرابع 2026 (31 ديسمبر 2026):</strong> التأكد من دقة وشمول إجراءات تحديد جميع أصول التشفير وتصنيفها، وتصنيف البيانات والأنظمة والخدمات المرتبطة بها حسب الحساسية وأولوية الانتقال، وتقييم المرونة التشفيرية للأصول ذات الأولوية بما في ذلك القيود والاعتماد على أطراف خارجية.</li>
<li><strong>بنهاية الربع الأول 2027 (31 مارس 2027):</strong> تقييم مخاطر الحوسبة الكمومية على مستوى المؤسسة ضمن إدارة المخاطر، مع خطط عمل لمعالجتها.</li>
<li><strong>دون موعد محدد:</strong> خطط ومبادرات لبلوغ المرونة التشفيرية المطلوبة، أو حلول بديلة مناسبة، لكل الأصول ذات الأولوية.</li>
<li><strong>دون موعد محدد:</strong> إدراج المخاطر الكمومية بنداً دائماً لدى اللجنة الإشرافية لأمن المعلومات ولجنة المخاطر، ورفع التحديات والتوصيات إلى مجلس الإدارة.</li>
</ol>
<p>لا يسمّي التعميم خوارزميات، ولا يحدد موعداً لإكمال الانتقال. والنص المُلزِم هو النص العربي الموقّع.</p>

<h2>السعودية: المعايير الوطنية للتشفير (الهيئة الوطنية للأمن السيبراني)</h2>
<p>الإصدار المنشور اليوم على موقع الهيئة ما زال <strong>NCS-1:2020</strong>، وهو يذكر فقط أن التشفير ما بعد الكمومي "سيؤخذ في الاعتبار" في الإصدارات القادمة. أما الإصدار المحدَّث <strong>NCS-2:2025</strong> فنُشر لاستطلاع الرأي العام (انتهى في 25 ديسمبر 2025)، وينطبق على "الجهات الوطنية"، ويتضمن قسماً لخوارزميات ما بعد الكم:</p>
<ul>
<li><strong>2-5-1:</strong> ML-KEM (FIPS 203): ML-KEM-512 وML-KEM-768 للمستوى المتوسط (MODERATE)، وML-KEM-1024 للمستوى المتقدم (ADVANCED).</li>
<li><strong>2-5-3 و2-5-4:</strong> ML-DSA (FIPS 204) وSLH-DSA (FIPS 205) للتوقيع الرقمي؛ ويقبل البند 2-5-2 أيضاً Classic McEliece.</li>
<li><strong>2-5-5-1:</strong> يجب استخدام نظام التشفير ما بعد الكمومي بشكل هجين مع نظام تقليدي معتمد.</li>
<li><strong>2-5-5-2:</strong> يجب أن تدعم جميع أنظمة وحلول التشفير خوارزميات ما بعد الكم.</li>
</ul>
<p>المجموعة الهجينة التي تستخدمها المتصفحات اليوم، <code dir="ltr">X25519MLKEM768</code>، تجمع Curve25519 (المقبول للمستوى المتوسط في البند 2-4-3-1) مع ML-KEM-768، فهي تحقق البندين معاً. تحقّق من الحالة النهائية على موقع الهيئة قبل الاستناد إلى NCS-2 في أي تدقيق.</p>

<h2>الإمارات العربية المتحدة</h2>
<ul>
<li><strong>سياسة التشفير الوطنية</strong> (مجلس الأمن السيبراني، أُعلن اعتمادها في 27 نوفمبر 2025): على الجهات الحكومية إعداد خطط معتمدة رسمياً للانتقال من التشفير التقليدي بالمفتاح العام (RSA وECC) إلى التشفير ما بعد الكمومي، والاحتفاظ بحصر آلي لأصول التشفير، وتصميم الأنظمة الجديدة بمرونة تسمح بتبديل الخوارزميات. لم يُنشر موعد لتقديم الخطط.</li>
<li><strong>البرنامج الوطني للانتقال إلى أمن ما بعد الكم</strong> (مجلس الأمن السيبراني ومجلس أبحاث التكنولوجيا المتطورة ATRC، أُعلن في 11 مايو 2026): أداة لاكتشاف أصول التشفير، ومكتبات تشفير من معهد الابتكار التكنولوجي TII تشمل خوارزميات ما بعد الكم، وتجربة لتوزيع المفاتيح الكمومي. يذكر "القطاعات الحيوية" دون تسمية البنوك، ودون مواعيد.</li>
<li><strong>مصرف الإمارات المركزي:</strong> لائحته لعام 2026 لإدارة المخاطر التشغيلية تغطي مخاطر تقنية المعلومات والأمن السيبراني، ولم نجد فيما نُشر عنها متطلباً خاصاً بما بعد الكم.</li>
</ul>

<h2>قطر والبحرين وعُمان والكويت</h2>
<p>لم نجد حتى نوفمبر 2026 متطلباً منشوراً للبنوك بشأن التشفير ما بعد الكمومي من مصرف قطر المركزي أو مصرف البحرين المركزي أو البنك المركزي العُماني أو بنك الكويت المركزي. لكن البنوك المدرجة في الخارج أو التي تخدم عملاء في الاتحاد الأوروبي قد تخضع لـ <a href="/guides/nis2-dora-post-quantum-cryptography?lang=ar">DORA</a> أو لاشتراطات الشركاء، والمواعيد العالمية في صفحة <a href="/deadlines?lang=ar">مواعيد الانتقال إلى ما بعد الكم</a>.</p>

<h2>أين تقف البنوك الخليجية اليوم</h2>
<p>أحصى <a href="/banks/arab-banks-2026-11?lang=ar">تقرير البنوك العربية</a> (قياس 12 نوفمبر 2026) النطاقات الفرعية العامة لكل بنك التي تتفاوض على تبادل مفاتيح مقاوم للكم:</p>
<ul>
<li><strong>قطر:</strong> 74 من 108 نطاقات فرعية مستجيبة (3 بنوك).</li>
<li><strong>الإمارات:</strong> 51 من 234 (5 بنوك).</li>
<li><strong>الكويت:</strong> 11 من 81 (3 بنوك).</li>
<li><strong>السعودية:</strong> 18 من 219 (7 بنوك)، ولا شيء من المواقع الرئيسية الستة التي قيست.</li>
</ul>
<p>أي أن الدولة صاحبة أشد المتطلبات المكتوبة هي الأقل نسبة على نقاطها العامة. والسبب غالباً ليس خوادم البنك نفسه، بل موازن تحميل أو جدار حماية تطبيقات (WAF) أو شبكة CDN لم تفعّل المجموعة الهجينة بعد.</p>

<h2>ما يمكن للبنك فعله قبل 31 ديسمبر 2026</h2>
<ol>
<li><strong>ابدأ الحصر بنقاط TLS العامة.</strong> هي أسهل الأصول حصراً وأكثرها تعرضاً لهجوم "<a href="/guides/harvest-now-decrypt-later?lang=ar">اجمع الآن وفُكّ لاحقاً</a>". سجّل لكل نطاق: التاريخ، وإصدار TLS، والمجموعة المتفق عليها، والجهة التي تنهي اتصال TLS (CDN أو موازن التحميل أو الخادم الأصلي).</li>
<li><strong>حدّد الاعتماد على أطراف خارجية.</strong> يطلبه تعميم ساما صراحةً. مزوّد CDN أو WAF لا يدعم X25519MLKEM768 قيدٌ يجب توثيقه مع خارطة طريق المزوّد.</li>
<li><strong>فعّل التبادل الهجين حيث تتحكم بالخادم.</strong> راجع أدلة <a href="/guides/enable-x25519mlkem768-nginx?lang=ar">nginx</a> و<a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=ar">Apache وCaddy وHAProxy وCloudflare</a> و<a href="/guides/aws-alb-cloudfront-post-quantum-tls?lang=ar">AWS</a>، أو <a href="/tools/pq-tls-config?lang=ar">مولّد الإعدادات</a>.</li>
<li><strong>احتفظ بالأدلة عبر الزمن.</strong> الفحص الواحد يُظهر يوماً واحداً؛ أما الفحص المنتظم فيُظهر للجنة المجلس التقدّم، ويكشف التراجع بعد تغييرات المزوّدين.</li>
</ol>
<p>الفحص المجاني لنطاق واحد في <a href="/?lang=ar">الصفحة الرئيسية</a>، و<a href="/audit?lang=ar">تدقيق النطاقات</a> يغطي كل النطاقات الفرعية العامة للمؤسسة.</p>

<h2>ما لا يثبته فحص TLS</h2>
<p>الفحص العام يرى نقطة واحدة على المنفذ 443 في لحظة واحدة. لا يغطي الأنظمة الداخلية، ولا وحدات HSM، ولا بروتوكولات البطاقات والمدفوعات، ولا البيانات المخزّنة أو الشهادات أو إدارة المفاتيح، وهذه كلها يجب أن يشملها حصر ساما أيضاً. هو دليل لجزء من الحصر، لا شهادة امتثال.</p>

<h2>المصادر</h2>
<ul>
<li><a href="https://rulebook.sama.gov.sa/en/enhancement-operational-resilience-address-quantum-computing-risks" rel="noopener">دليل أنظمة ساما: تعزيز المرونة التشغيلية لمواجهة مخاطر الحوسبة الكمومية</a> (التعميم 482021280، 27/08/2026)</li>
<li><a href="https://nca.gov.sa/ncs_en.pdf" rel="noopener">الهيئة الوطنية للأمن السيبراني: المعايير الوطنية للتشفير NCS-1:2020</a> (الإصدار الحالي على موقع الهيئة)</li>
<li><a href="https://istitlaa.ncc.gov.sa/en/security/nca/ncs/Documents/NCS-2-en.pdf" rel="noopener">الهيئة الوطنية للأمن السيبراني: NCS-2:2025، نسخة استطلاع الرأي</a>، البندان 2-4-3 و2-5</li>
<li><a href="https://u.ae/en/about-the-uae/strategies-initiatives-and-awards/policies/cyber-activities/National-Encryption-Policy" rel="noopener">البوابة الرسمية لحكومة الإمارات: سياسة التشفير الوطنية</a></li>
<li><a href="https://www.atrc.gov.ae/news/uae-cyber-security-council-partners-atrc-advance-national-post-quantum-security-transition" rel="noopener">ATRC: شراكة مجلس الأمن السيبراني لدعم الانتقال إلى أمن ما بعد الكم</a> (11 مايو 2026)</li>
</ul>
""",
        },
    },
    "post-quantum-vendor-security-questionnaire": {
        "updated": "2026-11-21",
        "en": {
            "title": "Answering post-quantum questions in customer security questionnaires",
            "description": "How software and payment vendors can answer bank and enterprise questions about post-quantum TLS with dated, checkable evidence instead of promises.",
            "body": """
<p>Banks, insurers and large enterprises have started asking their software and payment vendors about post-quantum readiness, in security questionnaires and supplier due diligence. The question usually sounds like <em>"Do your public endpoints support post-quantum or hybrid key exchange, and what is your migration plan?"</em> This page shows how to answer it with evidence instead of promises.</p>

<h2>Why the question is coming now</h2>
<ul>
<li>NIST published the ML-KEM standard (FIPS 203) in August 2024. Its draft transition guidance (NIST IR 8547) proposes deprecating RSA and elliptic-curve key establishment from 2030 and disallowing it from 2035.</li>
<li>The EU's coordinated post-quantum roadmap (2025) asks member states to start the transition by the end of 2026 and to protect high-risk use cases by 2030.</li>
<li>Chrome, Firefox, Safari and Cloudflare already negotiate the hybrid group <code>X25519MLKEM768</code> by default. Customers can see whether your endpoints do.</li>
<li>The risk they worry about is "harvest now, decrypt later": traffic recorded today can be decrypted once quantum computers are capable enough.</li>
</ul>

<h2>Three honest answers</h2>
<p><strong>If your endpoints already negotiate it:</strong> "Our public endpoints (list) negotiate the hybrid post-quantum key exchange X25519MLKEM768 in TLS 1.3, observed on (date) by an independent external measurement (link). We monitor this daily and are alerted if it regresses."</p>
<p><strong>If some do and some do not:</strong> "X25519MLKEM768 is enabled on (list), observed on (date) (link). The remaining endpoints (list) are terminated by (CDN / load balancer / server) and are scheduled for (quarter). Progress is monitored daily."</p>
<p><strong>If none do yet:</strong> "Our public endpoints currently use classical key exchange (x25519), observed on (date) (link). Enabling the hybrid group requires (component and version); our target date is (quarter). Certificates remain classical industry-wide until post-quantum certificates are available in public PKI."</p>

<h2>Evidence a reviewer can check</h2>
<ol>
<li>One external observation per hostname: date, address, TLS version and negotiated group. A link the reviewer can open is worth more than a screenshot.</li>
<li>A dated history that shows the change, not only today's state. Daily monitoring keeps a log of every check that you can export as CSV.</li>
<li>A public verification link or badge per domain, so the customer can re-check without asking you.</li>
<li>The limits of the measurement: a public probe sees the edge (often a CDN), not the origin, and says nothing about certificates or internal traffic.</li>
</ol>
<p><a href="/?lang=en">Check your endpoints now</a> (free), or see a <a href="/sample-report?lang=en">full sample report</a>.</p>

<h2>Keep the answer true after you send it</h2>
<p>A CDN policy change, a load-balancer migration or a server upgrade can silently remove post-quantum key exchange. If you told a customer it is enabled, re-check it continuously: monitoring re-tests your domains and common subdomains every day and emails you when the key exchange changes.</p>
""",
        },
        "de": {
            "title": "Post-Quanten-Fragen in Sicherheitsfragebögen von Kunden beantworten",
            "description": "Wie Software- und Zahlungsanbieter Fragen von Banken und Großkunden zu Post-Quanten-TLS mit datierten, prüfbaren Nachweisen beantworten.",
            "body": """
<p>Banken, Versicherungen und Großunternehmen fragen ihre Software- und Zahlungsdienstleister inzwischen nach Post-Quanten-Bereitschaft, in Sicherheitsfragebögen und bei der Lieferantenprüfung. Die Frage lautet meist: <em>„Unterstützen Ihre öffentlichen Endpunkte Post-Quanten- bzw. hybriden Schlüsselaustausch, und wie sieht Ihr Migrationsplan aus?“</em> Diese Seite zeigt, wie Sie mit Nachweisen statt mit Versprechen antworten.</p>

<h2>Warum die Frage jetzt kommt</h2>
<ul>
<li>NIST hat ML-KEM (FIPS 203) im August 2024 veröffentlicht. Der Entwurf der Übergangsleitlinie (NIST IR 8547) sieht vor, RSA- und Elliptische-Kurven-Schlüsselaustausch ab 2030 abzukündigen und ab 2035 nicht mehr zuzulassen.</li>
<li>Der koordinierte EU-Fahrplan für Post-Quanten-Kryptografie (2025) sieht vor, dass die Mitgliedstaaten bis Ende 2026 mit der Umstellung beginnen und Hochrisiko-Anwendungen bis 2030 schützen.</li>
<li>Chrome, Firefox, Safari und Cloudflare handeln die hybride Gruppe <code>X25519MLKEM768</code> bereits standardmäßig aus. Ihre Kunden können sehen, ob Ihre Endpunkte es tun.</li>
<li>Das befürchtete Risiko heißt „harvest now, decrypt later“: Heute aufgezeichneter Verkehr kann entschlüsselt werden, sobald Quantencomputer leistungsfähig genug sind.</li>
</ul>

<h2>Drei ehrliche Antworten</h2>
<p><strong>Wenn Ihre Endpunkte es bereits aushandeln:</strong> „Unsere öffentlichen Endpunkte (Liste) handeln in TLS 1.3 den hybriden Post-Quanten-Schlüsselaustausch X25519MLKEM768 aus, beobachtet am (Datum) durch eine unabhängige externe Messung (Link). Wir überwachen das täglich und werden bei einer Verschlechterung alarmiert.“</p>
<p><strong>Wenn es teilweise umgesetzt ist:</strong> „X25519MLKEM768 ist auf (Liste) aktiv, beobachtet am (Datum) (Link). Die übrigen Endpunkte (Liste) terminieren auf (CDN / Load Balancer / Server) und sind für (Quartal) geplant. Der Fortschritt wird täglich überwacht.“</p>
<p><strong>Wenn noch keiner es tut:</strong> „Unsere öffentlichen Endpunkte nutzen derzeit klassischen Schlüsselaustausch (x25519), beobachtet am (Datum) (Link). Für die hybride Gruppe ist (Komponente und Version) nötig; unser Zieltermin ist (Quartal). Zertifikate bleiben branchenweit klassisch, bis Post-Quanten-Zertifikate in der öffentlichen PKI verfügbar sind.“</p>

<h2>Nachweise, die ein Prüfer selbst prüfen kann</h2>
<ol>
<li>Eine externe Beobachtung pro Hostname: Datum, Adresse, TLS-Version und ausgehandelte Gruppe. Ein Link, den der Prüfer öffnen kann, ist mehr wert als ein Screenshot.</li>
<li>Ein datierter Verlauf, der die Änderung zeigt, nicht nur den heutigen Stand. Die tägliche Überwachung protokolliert jede Prüfung, exportierbar als CSV.</li>
<li>Ein öffentlicher Prüflink oder ein Badge pro Domain, damit der Kunde selbst nachprüfen kann.</li>
<li>Die Grenzen der Messung: Eine öffentliche Prüfung sieht den Rand (oft ein CDN), nicht den Ursprungsserver, und sagt nichts über Zertifikate oder internen Verkehr.</li>
</ol>
<p><a href="/?lang=de">Endpunkte jetzt prüfen</a> (kostenlos) oder einen <a href="/sample-report?lang=en">vollständigen Beispielbericht</a> ansehen.</p>

<h2>Damit die Antwort wahr bleibt</h2>
<p>Eine geänderte CDN-Richtlinie, ein Load-Balancer-Umzug oder ein Server-Update kann den Post-Quanten-Schlüsselaustausch unbemerkt entfernen. Wenn Sie einem Kunden zugesagt haben, dass er aktiv ist, prüfen Sie das laufend: Die Überwachung testet Ihre Domains und üblichen Subdomains täglich und mailt Ihnen, wenn sich der Schlüsselaustausch ändert.</p>
""",
        },
        "ar": {
            "title": "كيف تجيب عن أسئلة ما بعد الكم في استبيانات أمن العملاء",
            "description": "كيف يجيب مزوّدو البرمجيات وخدمات الدفع عن أسئلة البنوك والمؤسسات حول TLS ما بعد الكمّي بأدلة مؤرّخة قابلة للتحقق بدل الوعود.",
            "body": """
<p>بدأت البنوك وشركات التأمين والمؤسسات الكبرى تسأل مزوّدي البرمجيات وخدمات الدفع عن جاهزيتهم لما بعد الكم، في استبيانات الأمن وفي تقييم الموردين. يأتي السؤال عادةً بصيغة: <em>«هل تدعم نقاطكم العامة تبادل المفاتيح ما بعد الكمّي أو الهجين، وما خطتكم للانتقال؟»</em> توضّح هذه الصفحة كيف تجيب بأدلة لا بوعود.</p>

<h2>لماذا يأتي السؤال الآن</h2>
<ul>
<li>نشر NIST معيار ML-KEM ‏(FIPS 203) في أغسطس 2024. ومسودة إرشادات الانتقال (NIST IR 8547) تقترح إيقاف اعتماد تبادل المفاتيح بـ RSA والمنحنيات الإهليلجية بدءاً من 2030 ومنعه من 2035.</li>
<li>خارطة الطريق الأوروبية المنسّقة للتشفير ما بعد الكمّي (2025) تطلب من الدول الأعضاء بدء الانتقال بنهاية 2026 وحماية الاستخدامات عالية الخطورة بحلول 2030.</li>
<li>متصفحات Chrome وFirefox وSafari وشبكة Cloudflare تتفاوض أصلاً على المجموعة الهجينة <code>X25519MLKEM768</code> افتراضياً، ويستطيع عملاؤك رؤية هل تفعل نقاطك ذلك.</li>
<li>الخطر الذي يقلقهم: «احصد الآن، فكّ لاحقاً». حركة البيانات المسجّلة اليوم قابلة لفكّ تشفيرها عندما تصبح الحواسيب الكمّية قادرة.</li>
</ul>

<h2>ثلاث إجابات صادقة</h2>
<p><strong>إن كانت نقاطك تتفاوض عليه:</strong> «نقاطنا العامة (القائمة) تتفاوض على تبادل المفاتيح الهجين ما بعد الكمّي X25519MLKEM768 في TLS 1.3، رُصد ذلك في (التاريخ) بقياس خارجي مستقل (الرابط). نراقب ذلك يومياً ونُنبَّه عند أي تراجع.»</p>
<p><strong>إن كان مطبّقاً جزئياً:</strong> «X25519MLKEM768 مفعّل على (القائمة)، رُصد في (التاريخ) (الرابط). النقاط الباقية (القائمة) تنتهي عند (CDN / موازن حمل / خادم) ومجدولة في (الربع). نتابع التقدّم يومياً.»</p>
<p><strong>إن لم تكن أي نقطة تتفاوض عليه بعد:</strong> «نقاطنا العامة تستخدم حالياً تبادل مفاتيح كلاسيكياً (x25519)، رُصد في (التاريخ) (الرابط). تفعيل المجموعة الهجينة يتطلب (المكوّن والإصدار)، وموعدنا المستهدف (الربع). الشهادات ستبقى كلاسيكية في القطاع كله حتى تتوفر شهادات ما بعد كمّية في البنية العامة.»</p>

<h2>أدلة يستطيع المراجع التحقق منها بنفسه</h2>
<ol>
<li>رصد خارجي لكل اسم نطاق: التاريخ، والعنوان، ونسخة TLS، والمجموعة المتفاوض عليها. رابط يفتحه المراجع أقوى من لقطة شاشة.</li>
<li>سجلّ مؤرَّخ يُظهر التغيير، لا الحالة اليوم فقط. المراقبة اليومية تحفظ سجلاً بكل فحص يمكن تصديره CSV.</li>
<li>رابط تحقق عام أو شارة لكل نطاق، ليتحقق العميل بنفسه دون أن يسألك.</li>
<li>حدود القياس: الفحص العام يرى الحافة (غالباً CDN) لا الخادم الأصلي، ولا يقول شيئاً عن الشهادات أو الحركة الداخلية.</li>
</ol>
<p><a href="/?lang=ar">افحص نقاطك الآن</a> مجاناً، أو شاهد <a href="/sample-report?lang=ar">نموذج تقرير كامل</a>.</p>

<h2>لتبقى الإجابة صحيحة بعد إرسالها</h2>
<p>تغيير سياسة الـ CDN أو نقل موازن الحمل أو تحديث الخادم قد يزيل تبادل المفاتيح ما بعد الكمّي دون أن تلاحظ. إن أخبرت عميلاً أنه مفعّل، فتحقق منه باستمرار: المراقبة تعيد فحص نطاقاتك ونطاقاتها الفرعية الشائعة يومياً وتراسلك عند تغيّر تبادل المفاتيح.</p>
""",
        },
    },
    "x25519mlkem768-handshake-latency-performance": {
        "updated": "2026-11-24",
        "en": {
            "title": "X25519MLKEM768 performance: latency & ClientHello size",
            "description": "Real CPU overhead, ClientHello byte size (1,216 B key share) and TCP packet impact of hybrid post-quantum TLS 1.3 (X25519MLKEM768) vs classical X25519.",
            "body": """
<p>Enabling hybrid post-quantum TLS 1.3 (<code>X25519MLKEM768</code>, NIST FIPS 203) adds negligible CPU time on modern servers, typically well under one millisecond per handshake. The operational difference you actually need to plan for is <strong>packet size</strong>, not CPU.</p>

<h2>Wire sizes: X25519 vs X25519MLKEM768</h2>
<table class="data">
<thead><tr><th>Metric</th><th>Classical X25519</th><th>Hybrid X25519MLKEM768</th></tr></thead>
<tbody>
<tr><td>ClientHello key share</td><td>32 bytes</td><td>1,216 bytes (1,184 B ML-KEM-768 + 32 B X25519)</td></tr>
<tr><td>ServerHello key share</td><td>32 bytes</td><td>1,120 bytes (1,088 B ciphertext + 32 B X25519)</td></tr>
<tr><td>Typical ClientHello total</td><td>~300–550 bytes (1 TCP segment)</td><td>~1,500–1,800 bytes (2 TCP segments on 1,500 B MTU)</td></tr>
<tr><td>Extra TLS round trips (1-RTT)</td><td>0</td><td>0 (unless HelloRetryRequest triggers)</td></tr>
<tr><td>CPU cost (modern x86_64/ARM64)</td><td>~50–100 µs</td><td>~150–350 µs (~0.5–2% of a typical WAN RTT)</td></tr>
</tbody>
</table>

<h2>Why CPU is rarely the bottleneck</h2>
<p>ML-KEM-768 key generation, encapsulation and decapsulation use lattice arithmetic (NTT over small integers) that runs in tens to a few hundred microseconds on modern CPUs with AVX2 or NEON. Across a 20–80 ms internet round trip, that CPU delta is invisible to end users, and TLS 1.3 session resumption avoids repeating key exchange on subsequent connections anyway.</p>

<h2>What actually breaks in production: 2-segment ClientHello</h2>
<p>Because a classical ClientHello fits inside a single 1,500-byte Ethernet frame while an <code>X25519MLKEM768</code> ClientHello spans two TCP segments, legacy firewalls, DPI appliances and misconfigured load balancers occasionally drop or stall the handshake. That causes a timeout or a silent fallback, not slow CPU. Check whether your public hosts survive a real hybrid ClientHello with our <a href="/?lang=en">free single-handshake scanner</a>.</p>

<h2>Avoiding an extra HelloRetryRequest round trip</h2>
<p>If your server lists <code>X25519MLKEM768</code> first while a client sends only a classical key share (or vice versa), TLS 1.3 falls back to a <code>HelloRetryRequest</code>, adding one full network round trip (1 RTT). Match Chrome, Firefox and Safari by keeping <code>X25519MLKEM768</code> first in your group preference list, with <code>X25519</code> and <code>prime256v1</code> as fallbacks — see our <a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx guide</a> or <a href="/tools/pq-tls-config?lang=en">config generator</a>.</p>

<h2>Verify and monitor after enabling</h2>
<p>Measure any host now at <a href="/?lang=en">ather-quantum.com</a>, or start a <a href="/monitoring?lang=en#trial-form">14-day free daily monitoring trial</a> (up to 10 domains, no card) to get alerted if a CDN or firewall change silently reverts your endpoints back to classical TLS.</p>
""",
        },
        "ar": {
            "title": "أداء X25519MLKEM768: زمن المصافحة وحجم ClientHello",
            "description": "العبء الحقيقي على المعالج، وحجم رسالة ClientHello (1,216 بايت)، وأثر حزمتي TCP عند تفعيل TLS 1.3 المقاوم للكم X25519MLKEM768 مقارنة بـ X25519.",
            "body": """
<p>تفعيل تبادل المفاتيح الهجين المقاوم للكم في TLS 1.3 (<code>X25519MLKEM768</code>، معيار NIST FIPS 203) يضيف وقتاً ضئيلاً جداً على المعالج في الخوادم الحديثة — عادةً أقل بكثير من مللي ثانية واحدة لكل مصافحة. الأثر التشغيلي الحقيقي الذي يستحق التخطيط هو <strong>حجم الحزمة الشبكية</strong> لا استهلاك المعالج.</p>

<h2>مقارنة الأحجام والأداء: X25519 مقابل X25519MLKEM768</h2>
<table class="data">
<thead><tr><th>المؤشر</th><th>X25519 التقليدي</th><th>X25519MLKEM768 الهجين</th></tr></thead>
<tbody>
<tr><td>مفتاح ClientHello</td><td>32 بايت</td><td>1,216 بايت (1,184 بايت ML-KEM-768 + 32 بايت X25519)</td></tr>
<tr><td>مفتاح ServerHello</td><td>32 بايت</td><td>1,120 بايت (1,088 بايت نص مشفر + 32 بايت X25519)</td></tr>
<tr><td>حجم ClientHello الإجمالي</td><td>~300–550 بايت (حزمة TCP واحدة)</td><td>~1,500–1,800 بايت (حزمتا TCP على MTU 1500)</td></tr>
<tr><td>جولات شبكية إضافية (RTT)</td><td>0</td><td>0 (ما لم يحدث HelloRetryRequest)</td></tr>
<tr><td>زمن المعالج (x86_64/ARM64 حديث)</td><td>~50–100 ميكروثانية</td><td>~150–350 ميكروثانية (~0.5–2% من زمن جولة إنترنت)</td></tr>
</tbody>
</table>

<h2>لماذا لا يشكّل المعالج عنق زجاجة؟</h2>
<p>عمليات توليد المفتاح والتغليف وفك التغليف في ML-KEM-768 تعتمد على حسابات شبكية سريعة جداً تستغرق بضع مئات من الميكروثانية فقط. مقارنة بزمن انتقال شبكي بين 20 و80 مللي ثانية، يظل الفارق غير محسوس للمستخدم، كما أن استئناف الجلسات في TLS 1.3 يتجنب تكرار تبادل المفاتيح في الاتصالات اللاحقة.</p>

<h2>ما قد يتعطل فعلاً في الإنتاج: انقسام ClientHello على حزمتي TCP</h2>
<p>لأن رسالة ClientHello الهجينة تتجاوز حد حزمة Ethernet القياسية (1,500 بايت) وتنقسم إلى حزمتي TCP، فإن بعض الجدران النارية القديمة وأجهزة الفحص العميق (DPI) وموازنات الحمل غير المحدّثة قد تُسقط الاتصال أو تسبب تراجعاً صامتاً. تحقق فوراً من مضيفك عبر <a href="/?lang=ar">الفحص المجاني</a>.</p>

<h2>تجنب جولة HelloRetryRequest الإضافية</h2>
<p>ضع <code>X25519MLKEM768</code> أولاً في قائمة المجموعات متبوعة بـ <code>X25519</code> و<code>prime256v1</code> لتطابق ترتيب المتصفحات الحديثة وتتجنب جولة إضافية. راجع <a href="/guides/enable-x25519mlkem768-nginx?lang=ar">دليل nginx</a> أو <a href="/tools/pq-tls-config?lang=ar">مولّد الإعدادات</a>، ويمكنك بدء <a href="/monitoring?lang=ar#trial-form">تجربة مراقبة يومية مجانية لمدة 14 يوماً</a> (حتى 10 نطاقات بلا بطاقة).</p>
""",
        },
        "de": {
            "title": "X25519MLKEM768 Performance: Latenz & ClientHello-Größe",
            "description": "CPU-Aufwand, ClientHello-Größe (1.216 Byte Key Share) und TCP-Segmentierung von hybridem Post-Quanten-TLS 1.3 (X25519MLKEM768) im Vergleich zu X25519.",
            "body": """
<p>Hybrides Post-Quanten-TLS 1.3 (<code>X25519MLKEM768</code>, NIST FIPS 203) verursacht auf modernen Servern nur minimalen CPU-Aufwand — typischerweise wenige hundert Mikrosekunden pro Handshake. Betrieblich relevant ist vor allem die <strong>Paketgröße des ClientHello</strong>.</p>

<h2>Größen- und Latenzvergleich</h2>
<table class="data">
<thead><tr><th>Kennzahl</th><th>Klassisch X25519</th><th>Hybrid X25519MLKEM768</th></tr></thead>
<tbody>
<tr><td>ClientHello Key Share</td><td>32 Byte</td><td>1.216 Byte (1.184 B ML-KEM-768 + 32 B X25519)</td></tr>
<tr><td>ServerHello Key Share</td><td>32 Byte</td><td>1.120 Byte (1.088 B Ciphertext + 32 B X25519)</td></tr>
<tr><td>ClientHello gesamt</td><td>~300–550 Byte (1 TCP-Segment)</td><td>~1.500–1.800 Byte (2 TCP-Segmente bei 1.500 B MTU)</td></tr>
<tr><td>CPU-Zeit (x86_64/ARM64)</td><td>~50–100 µs</td><td>~150–350 µs (~0,5–2 % einer typischen WAN-RTT)</td></tr>
</tbody>
</table>

<h2>Praxispunkt: 2-Segment-ClientHello und Middleboxes</h2>
<p>Ältere Firewalls, DPI-Appliances oder Load Balancer, die das gesamte TLS-ClientHello in einem einzigen TCP-Paket erwarten, können Verbindungen abbrechen oder verlangsamen. Prüfen Sie Ihre öffentlichen Endpunkte sofort mit dem <a href="/?lang=de">kostenlosen Scan</a> oder richten Sie die <a href="/monitoring?lang=de#trial-form">14-tägige kostenlose Überwachung</a> für bis zu 10 Domains ein.</p>
""",
        },
    },
    "openssl-3-5-curl-test-x25519mlkem768": {
        "updated": "2026-11-24",
        "en": {
            "title": "Test X25519MLKEM768 with OpenSSL 3.5 and curl (CLI)",
            "description": "Exact openssl s_client and curl commands to verify hybrid post-quantum TLS 1.3 (X25519MLKEM768), read server key-exchange groups and debug fallbacks.",
            "body": """
<p>If you want to verify post-quantum TLS from your terminal or CI pipeline, you need a client linked against <strong>OpenSSL 3.5+</strong> (or BoringSSL/AWS-LC with ML-KEM support). Older OpenSSL 3.0–3.4 builds do not recognize <code>X25519MLKEM768</code>.</p>

<h2>1. Check your local OpenSSL and curl versions</h2>
<pre dir="ltr">openssl version
curl --version | head -n 2</pre>
<p>Confirm OpenSSL reports <strong>3.5.0 or newer</strong> (Debian 13, Ubuntu 26.04, Homebrew <code>openssl@3</code>, or Docker <code>alpine:3.22+</code>).</p>

<h2>2. Test X25519MLKEM768 with openssl s_client</h2>
<pre dir="ltr">openssl s_client -connect example.com:443 -servername example.com -tls1_3 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -iE "Protocol|Cipher|Peer Temp Key|Negotiated TLS1.3 group"</pre>
<p>A post-quantum-ready server prints:</p>
<pre dir="ltr">Negotiated TLS1.3 group: X25519MLKEM768</pre>
<p>To test browser-like fallback behaviour (hybrid offered first, classical allowed if unsupported):</p>
<pre dir="ltr">openssl s_client -connect example.com:443 -servername example.com -groups X25519MLKEM768:X25519:prime256v1 &lt;/dev/null 2&gt;/dev/null | grep -i group</pre>

<h2>3. Test with curl (built against OpenSSL 3.5+)</h2>
<pre dir="ltr">curl -Iv --tlsv1.3 --curves X25519MLKEM768 https://example.com 2&gt;&amp;1 | grep -iE "SSL connection|using|group|X25519MLKEM768"</pre>
<p>If curl fails with <code>SSL_CTX_set1_curves_list failed</code> or <code>unsupported curve</code>, your curl binary is linked to an OpenSSL older than 3.5.</p>

<h2>4. Zero-install CLI &amp; automated monitoring</h2>
<p>If your workstation still ships OpenSSL 3.0/3.2, you can run a live external probe without upgrading OpenSSL locally:</p>
<pre dir="ltr">curl -s "https://ather-quantum.com/api/v1/scan?domain=example.com&amp;format=text"</pre>
<p>Or use the <a href="/?lang=en">web scanner</a> and <a href="/monitoring?lang=en#trial-form">14-day free daily monitoring trial</a> to get email alerts if a deployment ever drops <code>X25519MLKEM768</code>.</p>
""",
        },
        "ar": {
            "title": "فحص X25519MLKEM768 عبر OpenSSL 3.5 وcurl من الطرفية",
            "description": "أوامر openssl s_client وcurl الدقيقة للتحقق من تفعيل TLS 1.3 المقاوم للكم (X25519MLKEM768) وقراءة المجموعة المتفاوض عليها واكتشاف التراجع.",
            "body": """
<p>للتحقق من دعم TLS المقاوم للكم من سطر الأوامر أو خط CI، تحتاج إلى عميل مربوط بـ <strong>OpenSSL 3.5 أو أحدث</strong> (أو BoringSSL/AWS-LC). إصدارات OpenSSL 3.0–3.4 لا تتعرف على المجموعة <code>X25519MLKEM768</code>.</p>

<h2>1. تحقق من إصدار OpenSSL وcurl لديك</h2>
<pre dir="ltr">openssl version
curl --version | head -n 2</pre>
<p>تأكد أن OpenSSL هو <strong>3.5.0 أو أحدث</strong> (متوفر في Debian 13 وUbuntu 26.04 وHomebrew <code>openssl@3</code>).</p>

<h2>2. الفحص عبر openssl s_client</h2>
<pre dir="ltr">openssl s_client -connect example.com:443 -servername example.com -tls1_3 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -iE "Protocol|Cipher|Peer Temp Key|Negotiated TLS1.3 group"</pre>
<p>الخادم الجاهز للكم يطبع:</p>
<pre dir="ltr">Negotiated TLS1.3 group: X25519MLKEM768</pre>
<p>ولاخنبار سلوك المتصفحات (تفضيل الهجين مع السماح بالتراجع التقليدي):</p>
<pre dir="ltr">openssl s_client -connect example.com:443 -servername example.com -groups X25519MLKEM768:X25519:prime256v1 &lt;/dev/null 2&gt;/dev/null | grep -i group</pre>

<h2>3. الفحص عبر curl</h2>
<pre dir="ltr">curl -Iv --tlsv1.3 --curves X25519MLKEM768 https://example.com 2&gt;&amp;1 | grep -iE "SSL connection|using|group|X25519MLKEM768"</pre>

<h2>4. الفحص الفوري بدون ترقية OpenSSL محلياً</h2>
<p>إذا كان جهازك لا يزال على OpenSSL 3.0 يمكنك الفحص مباشرة عبر API النصي:</p>
<pre dir="ltr">curl -s "https://ather-quantum.com/api/v1/scan?domain=example.com&amp;format=text"</pre>
<p>أو عبر <a href="/?lang=ar">الفاحص المجاني</a>، مع إمكانية بدء <a href="/monitoring?lang=ar#trial-form">تجربة مراقبة يومية مجانية لمدة 14 يوماً</a> (حتى 10 نطاقات بلا بطاقة).</p>
""",
        },
        "de": {
            "title": "X25519MLKEM768 mit OpenSSL 3.5 und curl testen (CLI)",
            "description": "Konkrete openssl s_client- und curl-Befehle, um hybrides Post-Quanten-TLS 1.3 (X25519MLKEM768) im Terminal oder in CI-Pipelines zu prüfen.",
            "body": """
<p>Für lokale Tests im Terminal oder in CI-Pipelines wird ein Client mit <strong>OpenSSL 3.5 oder neuer</strong> benötigt. Ältere OpenSSL-Versionen (3.0–3.4) kennen <code>X25519MLKEM768</code> noch nicht.</p>

<h2>1. Versionen prüfen</h2>
<pre dir="ltr">openssl version
curl --version | head -n 2</pre>

<h2>2. Mit openssl s_client testen</h2>
<pre dir="ltr">openssl s_client -connect example.com:443 -servername example.com -tls1_3 -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null | grep -iE "Protocol|Cipher|Negotiated TLS1.3 group"</pre>
<p>Erwartete Ausgabe bei Unterstützung: <code>Negotiated TLS1.3 group: X25519MLKEM768</code>.</p>

<h2>3. Mit curl oder ohne lokales OpenSSL 3.5 testen</h2>
<pre dir="ltr">curl -Iv --tlsv1.3 --curves X25519MLKEM768 https://example.com 2&gt;&amp;1 | grep -iE "SSL connection|group|X25519MLKEM768"
curl -s "https://ather-quantum.com/api/v1/scan?domain=example.com&amp;format=text"</pre>
<p>Alternativ direkt im <a href="/?lang=de">Web-Scanner</a> prüfen oder die <a href="/monitoring?lang=de#trial-form">14-tägige kostenlose Überwachung</a> aktivieren.</p>
""",
        },
    },
    "windows-server-iis-dotnet-post-quantum-tls": {
        "updated": "2026-11-24",
        "en": {
            "title": "Post-quantum TLS on Windows Server, IIS & .NET",
            "description": "How Windows Server (Schannel / SymCrypt), IIS and .NET handle ML-KEM post-quantum TLS 1.3, what is supported today, and the fastest production options.",
            "body": """
<p>On Windows Server and IIS, TLS 1.3 key exchange is controlled by the operating system's <strong>Schannel</strong> and <strong>SymCrypt / CNG</strong> stack — not by IIS configuration alone. That means enabling <code>X25519MLKEM768</code> on IIS depends directly on your Windows Server build and updates.</p>

<h2>1. Where Windows Server &amp; .NET stand</h2>
<ul>
<li><strong>Windows Server 2019 &amp; 2022:</strong> Schannel supports TLS 1.3 (on Server 2022) with classical curves (<code>X25519</code>, <code>P-256</code>, <code>P-384</code>), but does <strong>not</strong> negotiate <code>X25519MLKEM768</code> natively.</li>
<li><strong>Windows Server 2025 &amp; newer Insider/update channels:</strong> Microsoft added ML-KEM (FIPS 203) into SymCrypt and Windows CNG, with TLS 1.3 hybrid key-exchange rollout progressing through Windows servicing updates. Always verify your actual endpoint over the wire rather than assuming an OS patch enabled it.</li>
<li><strong>.NET on Linux vs Windows:</strong> ASP.NET Core / Kestrel on Linux delegates TLS to the host's OpenSSL library (so Linux + OpenSSL 3.5+ negotiates <code>X25519MLKEM768</code> immediately), while .NET on Windows delegates to Schannel.</li>
</ul>

<h2>2. Fastest production path for IIS workloads today</h2>
<p>If you run IIS on Windows Server 2019/2022 (or a Server 2025 build whose Schannel does not yet negotiate <code>X25519MLKEM768</code> publicly), terminate public TLS in front of IIS using a post-quantum-capable reverse proxy or CDN:</p>
<ul>
<li><strong>Cloudflare / Azure Front Door / AWS CloudFront:</strong> enable hybrid PQ TLS at the edge while keeping TLS 1.3 between edge and IIS origin.</li>
<li><strong>Caddy, HAProxy or nginx (OpenSSL 3.5+) reverse proxy:</strong> place in front of IIS — see our <a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=en">reverse proxy &amp; CDN guide</a> and <a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx guide</a>.</li>
</ul>

<h2>3. Check your IIS endpoint right now</h2>
<p>Run our <a href="/?lang=en">free public TLS scan</a> against your IIS hostname (and <code>api.</code> / <code>portal.</code> subdomains) to confirm what external browsers actually negotiate today. For ongoing compliance (<a href="/guides/nis2-dora-post-quantum-cryptography?lang=en">NIS2 / DORA</a> or <a href="/guides/gulf-banks-post-quantum-cryptography-requirements?lang=en">SAMA</a>), start a <a href="/monitoring?lang=en#trial-form">14-day free daily monitoring trial</a> (up to 10 domains, no card).</p>
""",
        },
        "ar": {
            "title": "TLS المقاوم للكم على Windows Server وIIS و.NET",
            "description": "كيف يتعامل Windows Server (Schannel / SymCrypt) وIIS و.NET مع ML-KEM في TLS 1.3، وما المدعوم اليوم، وأسرع حلول الإنتاج لخوادم IIS.",
            "body": """
<p>على Windows Server وIIS يتحكم نظام التشغيل عبر <strong>Schannel</strong> و<strong>SymCrypt / CNG</strong> بتبادل مفاتيح TLS 1.3، وليس إعدادات IIS وحدها. لذلك يتوقف تفعيل <code>X25519MLKEM768</code> مباشرةً على إصدار Windows Server وتحديثاته.</p>

<h2>1. الوضع الحالي لـ Windows Server و.NET</h2>
<ul>
<li><strong>Windows Server 2019 و2022:</strong> يدعم Server 2022 بروتوكول TLS 1.3 بالمنحنيات التقليدية (<code>X25519</code>، <code>P-256</code>، <code>P-384</code>) لكنه <strong>لا</strong> يتفاوض على <code>X25519MLKEM768</code> أصلياً.</li>
<li><strong>Windows Server 2025 والتحديثات الأحدث:</strong> أضافت مايكروسوفت خوارزمية ML-KEM (FIPS 203) إلى SymCrypt وWindows CNG مع تفعيل تدريجي لتبادل المفاتيح الهجين في TLS 1.3 عبر التحديثات. افحص نقطتك فعلياً على الشبكة ولا تفترض التفعيل التلقائي.</li>
<li><strong>.NET على Linux مقابل Windows:</strong> تطبيقات ASP.NET Core / Kestrel على Linux تعتمد على OpenSSL (فتدعم <code>X25519MLKEM768</code> فوراً مع OpenSSL 3.5+)، بينما تعتمد على Schannel في Windows.</li>
</ul>

<h2>2. أسرع طريق عملي لخوادم IIS اليوم</h2>
<p>إذا كان لديك IIS على Windows Server 2019/2022 أو بناء لا يتفاوض بعد على <code>X25519MLKEM768</code>، فأنهِ TLS العام أمام IIS عبر وكيل عكسي أو CDN يدعم ما بعد الكم:</p>
<ul>
<li><strong>Cloudflare أو AWS CloudFront أو وكيل Caddy / nginx (OpenSSL 3.5+):</strong> يوفّر الحماية الكمومية للمتصفحات فوراً دون تعديل تطبيقات .NET الداخلية (انظر <a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=ar">دليل الوكلاء وCDN</a>).</li>
</ul>

<h2>3. افحص خادم IIS الآن</h2>
<p>اختبر نطاقك العام الآن عبر <a href="/?lang=ar">الفحص المجاني</a>، وللامتثال المستمر (<a href="/guides/gulf-banks-post-quantum-cryptography-requirements?lang=ar">ساما</a> أو <a href="/guides/nis2-dora-post-quantum-cryptography?lang=ar">NIS2/DORA</a>) ابدأ <a href="/monitoring?lang=ar#trial-form">تجربة المراقبة اليومية المجانية لمدة 14 يوماً</a> (حتى 10 نطاقات بلا بطاقة).</p>
""",
        },
        "de": {
            "title": "Post-Quanten-TLS auf Windows Server, IIS & .NET",
            "description": "Wie Windows Server (Schannel / SymCrypt), IIS und .NET ML-KEM in TLS 1.3 unterstützen und wie Sie IIS-Endpunkte heute schnell absichern.",
            "body": """
<p>Unter Windows Server und IIS steuert das Betriebssystem über <strong>Schannel</strong> und <strong>SymCrypt / CNG</strong> den TLS-1.3-Schlüsselaustausch — nicht allein IIS. Ob <code>X25519MLKEM768</code> ausgehandelt wird, hängt daher direkt von der Windows-Server-Version ab.</p>

<h2>1. Aktueller Stand</h2>
<ul>
<li><strong>Windows Server 2019 &amp; 2022:</strong> Kein natives <code>X25519MLKEM768</code> in Schannel (nur klassisches X25519 / P-256 / P-384).</li>
<li><strong>Windows Server 2025 &amp; neuere Updates:</strong> ML-KEM (FIPS 203) ist in SymCrypt/CNG integriert; prüfen Sie stets per Live-Handshake, ob Ihr Endpunkt die hybride Gruppe bereits extern anbietet.</li>
<li><strong>.NET auf Linux vs. Windows:</strong> ASP.NET Core / Kestrel unter Linux nutzt OpenSSL (mit OpenSSL 3.5+ sofort PQ-fähig), unter Windows dagegen Schannel.</li>
</ul>

<h2>2. Schnellster Produktionsweg für IIS heute</h2>
<p>Terminieren Sie externes TLS vor IIS über einen PQ-fähigen Reverse Proxy (nginx mit OpenSSL 3.5+, Caddy, HAProxy) oder ein CDN wie Cloudflare — siehe unseren <a href="/guides/enable-x25519mlkem768-nginx?lang=de">nginx-Leitfaden</a>. Prüfen Sie Ihren IIS-Endpunkt sofort mit dem <a href="/?lang=de">kostenlosen Scan</a> oder starten Sie die <a href="/monitoring?lang=de#trial-form">14-tägige kostenlose Überwachung</a>.</p>
""",
        },
    },
}
