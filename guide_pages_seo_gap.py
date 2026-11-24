"""SEO-gap guides added 2026-11-24: OpenSSL 3.5 cookbook and BSI TR-02102-2.

Imported at the end of guides.py and guide_faq.py so the large existing modules
stay easy to merge with concurrent edits. Do not import guides or guide_faq here.
"""

UPDATED = "2026-11-24"

GUIDES = {
    "openssl-3-5-x25519mlkem768": {
        "updated": UPDATED,
        "en": {
            "title": "Test X25519MLKEM768 with OpenSSL 3.5",
            "description": "Verify hybrid post-quantum TLS with OpenSSL 3.5 s_client: read Negotiated TLS1.3 group, avoid Peer Temp Key traps, and understand alert 40.",
            "body": """
<p>This is the cookbook for testing <code>X25519MLKEM768</code> yourself with <strong>OpenSSL 3.5 <code>s_client</code></strong>. It covers the flags, how to read the output, and the failures that look like “the server is broken” when the client is simply too old. If you want a one-click confirmation instead, use the <a href="/tools/post-quantum-tls-checker?lang=en">post-quantum TLS checker</a> (a port-443 handshake only).</p>

<h2>1. Confirm you are on OpenSSL 3.5 or newer</h2>
<pre dir="ltr">openssl version</pre>
<p>You need <strong>3.5.0 or newer</strong>. Debian 13, Ubuntu 25.10/26.04, Homebrew <code>openssl@3</code> (once it has 3.5) and container images such as <code>alpine:3.22+</code> typically ship it. An <code>openssl version</code> of 3.0.x through 3.4.x cannot test this group: the name is unknown, and the output tells you nothing about ML-KEM.</p>
<p>Check the binary you will actually run, not a different one earlier in <code>$PATH</code>:</p>
<pre dir="ltr">which openssl
openssl version -a | head</pre>

<h2>2. Default offer versus forcing the hybrid group</h2>
<p>Two different commands answer two different questions.</p>
<p><strong>Browser-like offer</strong> (hybrid first, classical allowed). On OpenSSL 3.5 the default already includes <code>X25519MLKEM768</code>. You can also list the groups yourself:</p>
<pre dir="ltr">openssl s_client -connect example.com:443 -servername example.com -tls1_3 \\
  -groups X25519MLKEM768:X25519:prime256v1 &lt;/dev/null 2&gt;/dev/null \\
  | grep -iE "Protocol|Cipher|Peer Temp Key|Server Temp Key|Negotiated TLS1.3 group"</pre>
<p>This handshake will usually succeed even if the server is classical: it just negotiates X25519. <strong>Success is not evidence of post-quantum support.</strong> Read the negotiated group (next section).</p>
<p><strong>Hybrid only.</strong> The client offers just <code>X25519MLKEM768</code>, so a classical-only server fails instead of falling back silently:</p>
<pre dir="ltr">openssl s_client -connect example.com:443 -servername example.com -tls1_3 \\
  -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null \\
  | grep -iE "Protocol|Cipher|Peer Temp Key|Server Temp Key|Negotiated TLS1.3 group|alert|error"</pre>
<p>Always pass <code>-servername</code> (SNI). Without it you may test the default certificate/vhost, not the hostname you care about. The scan is on <strong>port 443</strong>.</p>

<h2>3. How to read the output</h2>
<p>The line that matters is:</p>
<pre dir="ltr">Negotiated TLS1.3 group: X25519MLKEM768</pre>
<p>That is a post-quantum hybrid key exchange. Other acceptable post-quantum lines include <code>SecP256r1MLKEM768</code>, <code>SecP384r1MLKEM1024</code>, <code>ML-KEM-768</code> or <code>ML-KEM-1024</code>, depending on the server.</p>
<p><strong>Do not stop at <code>Peer Temp Key: X25519</code> or <code>Server Temp Key: X25519</code>.</strong> OpenSSL may still print the classical X25519 half of a hybrid handshake on that line. A result that only shows X25519 in the temp-key field, without reading <code>Negotiated TLS1.3 group</code>, can be a false classical reading of a successful hybrid exchange — or genuinely classical. The negotiated-group line is the one to trust. If that line says <code>X25519</code> or <code>secp256r1</code>, the server did not select a post-quantum group.</p>

<h2>4. Handshake failure and alert 40</h2>
<p>When you force <code>-groups X25519MLKEM768</code> and the server does not accept it, <code>s_client</code> typically fails with a TLS <strong>alert 40</strong> (<code>handshake_failure</code>), “no suitable key share”, or a generic certificate/handshake error. That usually means:</p>
<ul>
<li>the server (or the CDN edge you reached) does not offer <code>X25519MLKEM768</code>; or</li>
<li>a middlebox stalled a large ClientHello (the hybrid key share is 1,216 bytes and often spans two TCP segments). See the <a href="/guides/x25519mlkem768-handshake-latency-performance?lang=en">handshake size and latency guide</a>.</li>
</ul>
<p>Retry without forcing a single group, and compare with the <a href="/tools/post-quantum-tls-checker?lang=en">online checker</a>, which uses a current client and records the selected group.</p>

<h2>5. Why an OpenSSL 3.0 or 3.4 client proves nothing</h2>
<p>OpenSSL 3.0–3.4 does not implement ML-KEM or the IANA name <code>X25519MLKEM768</code>. Typical symptoms:</p>
<ul>
<li><code>SSL_CTX_set1_groups_list</code> / <code>unknown group</code> if you pass <code>-groups X25519MLKEM768</code>;</li>
<li>a handshake that quietly uses X25519 if you do not pass the group, with no ML-KEM information in the output.</li>
</ul>
<p>Neither result says whether the <em>server</em> is post-quantum ready. Upgrade the client, run the command inside a newer container (<code>debian:trixie</code> or <code>alpine:3.22</code>), or skip the local flags and use the <a href="/tools/post-quantum-tls-checker?lang=en">checker</a> or the text API:</p>
<pre dir="ltr">curl -s "https://ather-quantum.com/api/v1/scan?domain=example.com&amp;format=text"</pre>
<p>A shorter CLI listing, including curl, is in <a href="/guides/openssl-3-5-curl-test-x25519mlkem768?lang=en">Test X25519MLKEM768 with OpenSSL 3.5 and curl</a>.</p>

<h2>6. If the server is not ready</h2>
<p>Enable the hybrid group on the stack that terminates public TLS:</p>
<ul>
<li><a href="/guides/enable-x25519mlkem768-nginx?lang=en">nginx with OpenSSL 3.5</a></li>
<li><a href="/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=en">Ubuntu still on OpenSSL 3.0</a></li>
<li><a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=en">Apache, Caddy, HAProxy and Cloudflare</a></li>
</ul>

<h2>7. Keep the result from drifting</h2>
<p>A one-off <code>s_client</code> run is a snapshot. Load-balancer and CDN changes can silently drop the hybrid group. <a href="/monitoring?lang=en">Continuous monitoring</a> re-checks public endpoints daily: <strong>29 € / 99 €</strong> per month (Starter 10 domains, Business 100), with a 14-day trial. For a dated evidence pack across an organisation's public hostnames, the <a href="/audit?lang=en">PQC Audit is 490 €</a>. DACH operators mapping this to BSI's guideline should also read <a href="/guides/bsi-tr-02102-2-post-quantum-tls?lang=en">BSI TR-02102-2: Post-Quantum TLS</a> and the <a href="/index?lang=en">PQ-TLS Index</a>.</p>
""",
        },
        "ar": {
            "title": "اختبار X25519MLKEM768 باستخدام OpenSSL 3.5",
            "description": "تحقق من TLS الهجين المقاوم للكم عبر OpenSSL 3.5 s_client: اقرأ Negotiated TLS1.3 group، وتجنّب فخ Peer Temp Key، وافهم التنبيه 40.",
            "body": """
<p>هذا الدليل العملي لاختبار <code>X25519MLKEM768</code> بنفسك عبر <strong>OpenSSL 3.5 و<code>s_client</code></strong>. يشرح الأعلام، وكيفية قراءة الناتج، والإخفاقات التي تبدو عطلاً في الخادم بينما العميل فقط قديم. وللتأكيد بنقرة واحدة استخدم <a href="/tools/post-quantum-tls-checker?lang=ar">فاحص TLS المقاوم للكم</a> (مصافحة على المنفذ 443 فقط).</p>

<h2>1. تأكد أنك على OpenSSL 3.5 أو أحدث</h2>
<pre dir="ltr">openssl version</pre>
<p>تحتاج <strong>3.5.0 أو أحدث</strong>. إصدارات 3.0 إلى 3.4 لا تعرف اسم <code>X25519MLKEM768</code> وناتجها لا يقول شيئاً عن ML-KEM.</p>

<h2>2. العرض الافتراضي مقابل فرض المجموعة الهجينة</h2>
<p><strong>عرض يشبه المتصفح</strong> (الهجين أولاً مع السماح بالتقليدي) قد ينجح حتى لو كان الخادم كلاسيكياً. النجاح وحده ليس دليلاً؛ اقرأ المجموعة المتفاوض عليها.</p>
<pre dir="ltr">openssl s_client -connect example.com:443 -servername example.com -tls1_3 \\
  -groups X25519MLKEM768:X25519:prime256v1 &lt;/dev/null 2&gt;/dev/null \\
  | grep -iE "Protocol|Cipher|Peer Temp Key|Server Temp Key|Negotiated TLS1.3 group"</pre>
<p><strong>الهجين فقط</strong> — إن لم يقبل الخادم المجموعة تفشل المصافحة بدل التراجع الصامت:</p>
<pre dir="ltr">openssl s_client -connect example.com:443 -servername example.com -tls1_3 \\
  -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null \\
  | grep -iE "Protocol|Cipher|Peer Temp Key|Server Temp Key|Negotiated TLS1.3 group|alert|error"</pre>
<p>مرّر دائماً <code>-servername</code> (SNI). الفحص على <strong>المنفذ 443</strong>.</p>

<h2>3. كيف تقرأ الناتج</h2>
<p>السطر المهم هو <code>Negotiated TLS1.3 group: X25519MLKEM768</code>. لا تتوقف عند <code>Peer Temp Key: X25519</code> أو <code>Server Temp Key: X25519</code>؛ قد يطبع OpenSSL نصف X25519 من مصافحة هجينة ناجحة. سطر المجموعة المتفاوض عليها هو المرجع.</p>

<h2>4. فشل المصافحة والتنبيه 40</h2>
<p>عند فرض المجموعة وحدها وفشل الخادم في قبولها، يظهر غالباً <strong>التنبيه 40</strong> (<code>handshake_failure</code>) أو «no suitable key share». السبب عادة أن الخادم (أو طرف CDN) لا يعرض المجموعة، أو أن جهازاً وسيطاً تعثر في ClientHello الكبير (1,216 بايت).</p>

<h2>5. لماذا لا يثبت عميل OpenSSL 3.0 أو 3.4 شيئاً</h2>
<p>هذه الإصدارات لا تنفّذ ML-KEM. إن ظهر «unknown group» أو اكتملت مصافحة X25519 بهدوء، فهذا يصف العميل لا الخادم. رقِّ العميل، أو استخدم حاوية أحدث، أو <a href="/tools/post-quantum-tls-checker?lang=ar">الفاحص</a>:</p>
<pre dir="ltr">curl -s "https://ather-quantum.com/api/v1/scan?domain=example.com&amp;format=text"</pre>
<p>قائمة أوامر أقصر، بما فيها curl، في <a href="/guides/openssl-3-5-curl-test-x25519mlkem768?lang=ar">فحص X25519MLKEM768 عبر OpenSSL 3.5 وcurl</a>.</p>

<h2>6. إذا لم يكن الخادم جاهزاً</h2>
<ul>
<li><a href="/guides/enable-x25519mlkem768-nginx?lang=ar">nginx مع OpenSSL 3.5</a></li>
<li><a href="/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=ar">Ubuntu على OpenSSL 3.0</a></li>
<li><a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=ar">Apache وCaddy وHAProxy وCloudflare</a></li>
</ul>

<h2>7. حتى لا تضيع النتيجة لاحقاً</h2>
<p><a href="/monitoring?lang=ar">المراقبة المستمرة</a> تعيد الفحص يومياً: <strong>29 € / 99 €</strong> شهرياً (Starter لعشرة نطاقات، Business لمئة)، مع تجربة 14 يوماً. ولحزمة أدلة مؤرخة عبر أسماء المؤسسة العامة، <a href="/audit?lang=ar">تدقيق PQC بسعر 490 €</a>. وللأطر التنظيمية في ألمانيا راجع <a href="/guides/bsi-tr-02102-2-post-quantum-tls?lang=ar">BSI TR-02102-2</a> و<a href="/index?lang=ar">مؤشر PQ-TLS</a>.</p>
""",
        },
        "de": {
            "title": "X25519MLKEM768 mit OpenSSL 3.5 prüfen",
            "description": "Hybrides Post-Quanten-TLS mit OpenSSL 3.5 s_client prüfen: Negotiated TLS1.3 group lesen, Peer-Temp-Key-Fallen vermeiden, Alert 40 einordnen.",
            "body": """
<p>Dieses Kochbuch zeigt, wie Sie <code>X25519MLKEM768</code> selbst mit <strong>OpenSSL 3.5 <code>s_client</code></strong> prüfen: Flags, Ausgabe, und Fehler, die nach einem defekten Server aussehen, obwohl nur der Client zu alt ist. Zur Bestätigung mit einem Klick nutzen Sie den <a href="/tools/post-quantum-tls-checker?lang=de">Post-Quanten-TLS-Checker</a> (nur Handshake auf Port 443).</p>

<h2>1. OpenSSL 3.5 oder neuer bestätigen</h2>
<pre dir="ltr">openssl version</pre>
<p>Sie brauchen <strong>mindestens 3.5.0</strong>. OpenSSL 3.0 bis 3.4 kennt den Namen <code>X25519MLKEM768</code> nicht; die Ausgabe sagt nichts über ML-KEM.</p>

<h2>2. Standardangebot gegen erzwungene hybride Gruppe</h2>
<p>Ein <strong>browserähnliches Angebot</strong> (Hybrid zuerst, klassisch erlaubt) gelingt oft auch bei einem klassischen Server — Erfolg ist kein Nachweis. Lesen Sie die ausgehandelte Gruppe. Mit <strong>nur</strong> <code>-groups X25519MLKEM768</code> schlägt ein klassischer Server fehl, statt still auf X25519 zu fallen:</p>
<pre dir="ltr">openssl s_client -connect example.com:443 -servername example.com -tls1_3 \\
  -groups X25519MLKEM768 &lt;/dev/null 2&gt;/dev/null \\
  | grep -iE "Protocol|Cipher|Peer Temp Key|Server Temp Key|Negotiated TLS1.3 group|alert|error"</pre>
<p>Übergeben Sie stets <code>-servername</code> (SNI). Die Prüfung läuft auf <strong>Port 443</strong>.</p>

<h2>3. Die Ausgabe lesen</h2>
<p>Maßgeblich ist die Zeile <code>Negotiated TLS1.3 group: X25519MLKEM768</code>. Bleiben Sie nicht bei <code>Peer Temp Key: X25519</code> oder <code>Server Temp Key: X25519</code> stehen: OpenSSL kann dort die klassische X25519-Hälfte eines erfolgreichen Hybrid-Handshakes drucken. Vertrauen Sie der Zeile zur ausgehandelten Gruppe.</p>

<h2>4. Handshake-Fehler und Alert 40</h2>
<p>Erzwingen Sie nur die hybride Gruppe und akzeptiert der Server sie nicht, erscheint typischerweise <strong>Alert 40</strong> (<code>handshake_failure</code>) oder „no suitable key share“. Meist bietet der Server (oder der erreichte CDN-Rand) die Gruppe nicht an, oder eine Middlebox stolpert über das 1.216 Byte große ClientHello.</p>

<h2>5. Warum ein OpenSSL-3.0- oder -3.4-Client nichts beweist</h2>
<p>Diese Versionen implementieren ML-KEM nicht. „Unknown group“ oder ein stiller X25519-Handshake beschreiben den Client, nicht den Server. Aktualisieren Sie den Client, nutzen Sie ein neueres Container-Image oder den <a href="/tools/post-quantum-tls-checker?lang=de">Checker</a>:</p>
<pre dir="ltr">curl -s "https://ather-quantum.com/api/v1/scan?domain=example.com&amp;format=text"</pre>
<p>Eine kürzere Befehlsübersicht inklusive curl steht in <a href="/guides/openssl-3-5-curl-test-x25519mlkem768?lang=de">X25519MLKEM768 mit OpenSSL 3.5 und curl testen</a>.</p>

<h2>6. Wenn der Server nicht bereit ist</h2>
<ul>
<li><a href="/guides/enable-x25519mlkem768-nginx?lang=de">nginx mit OpenSSL 3.5</a></li>
<li><a href="/guides/ubuntu-openssl-3-0-post-quantum-tls?lang=en">Ubuntu mit OpenSSL 3.0</a> (Englisch)</li>
<li><a href="/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare?lang=en">Apache, Caddy, HAProxy und Cloudflare</a> (Englisch)</li>
</ul>

<h2>7. Damit das Ergebnis nicht wieder verschwindet</h2>
<p>Die <a href="/monitoring?lang=de">kontinuierliche Überwachung</a> prüft öffentliche Endpunkte täglich: <strong>29 € / 99 €</strong> pro Monat (Starter 10 Domains, Business 100), mit 14-tägiger Testphase. Für ein datiertes Evidence Pack über die öffentlichen Hostnamen einer Organisation kostet das <a href="/audit?lang=de">PQC-Audit 490 €</a>. Zur Einordnung in die BSI-Vorgaben siehe <a href="/guides/bsi-tr-02102-2-post-quantum-tls?lang=de">BSI TR-02102-2: Post-Quanten-TLS</a> und den <a href="/index?lang=de">PQ-TLS-Index</a>.</p>
""",
        },
    },
    "bsi-tr-02102-2-post-quantum-tls": {
        "updated": UPDATED,
        "en": {
            "title": "BSI TR-02102-2: Post-Quantum TLS",
            "description": "What BSI TR-02102-2 (2026-01) allows for post-quantum TLS: hybrid groups including X25519MLKEM768, classical (EC)DHE only through 2031, and what a port-443 handshake can prove.",
            "body": """
<p>Germany's Federal Office for Information Security publishes <strong>BSI TR-02102-2</strong>, “Cryptographic Mechanisms: Recommendations and Key Lengths — Use of Transport Layer Security (TLS)”. Version <strong>2026-01</strong> is the text operators in the DACH region should map a public TLS rollout against. This page summarises the post-quantum parts, the 2031/2032 dates, and how far a port-443 handshake can take you as evidence.</p>

<h2>What TR-02102-2 (2026-01) says about post-quantum TLS</h2>
<p>The official BSI note on the current version, after IETF <a href="https://www.rfc-editor.org/rfc/rfc10024.html" rel="noopener">RFC 10024</a> was published as a Proposed Standard, is:</p>
<ul>
<li><code>SecP256r1MLKEM768</code> and <code>SecP384r1MLKEM1024</code> can already be used in a TR-compliant way in TLS 1.3, and will be recommended in the next version of TR-02102-2.</li>
<li>In addition to those two groups, <code>X25519MLKEM768</code> can also be used.</li>
</ul>
<p>So hybrid key agreement is permitted now. The formally upcoming recommended pair is the NIST-curve hybrids; <code>X25519MLKEM768</code> (the group most browsers offer first) is also usable under the current BSI note. Always prefer the wording on the <a href="https://www.bsi.bund.de/EN/Themen/Unternehmen-und-Organisationen/Standards-und-Zertifizierung/Technische-Richtlinien/TR-nach-Thema-sortiert/tr02102/tr02102_node.html" rel="noopener">BSI TR-02102 page</a> if a later version supersedes this summary.</p>

<h2>Timelines: 2031 and 2032</h2>
<p>From TR-02102-2 version 2026-01:</p>
<ul>
<li><strong>TLS 1.3</strong> is the preferred protocol and is recommended for use into <strong>2032+</strong>.</li>
<li><strong>TLS 1.2</strong> is recommended only until the <strong>end of 2031</strong>, because no quantum-safe key agreement is expected to be standardised for TLS 1.2.</li>
<li>The <strong>sole use of classical key agreement</strong> ((EC)DHE groups such as secp256r1, secp384r1, X25519 is a classical mechanism in the same sense) is recommended only until the <strong>end of 2031</strong>. From 2032, the BSI direction is hybrid use: a classical group together with a quantum-safe mechanism, not classical (EC)DHE alone.</li>
</ul>
<p>The practical reading for a public HTTPS estate is: enable a hybrid group <em>now</em> (browsers already offer <code>X25519MLKEM768</code>), keep a classical fallback for older clients through 2031, and treat classical-only key exchange as something that should be gone by 2032.</p>

<h2>What a port-443 handshake can and cannot prove</h2>
<p>A public TLS handshake on port 443 shows the key-exchange group a given hostname negotiated <em>at that moment</em> on the IP address the probe reached. That is useful <strong>endpoint posture</strong>: it answers “does this public name already speak a TR-usable hybrid group?”</p>
<p>It is <strong>not</strong> a BSI certification, a TR-02102-2 audit, or a statement that the organisation meets the rest of TR-02102 (algorithms for signatures, certificates, keys at rest, or internal links). It does not cover the CDN-to-origin hop, other ports, or a complete subdomain inventory. State that limit clearly in any evidence you keep.</p>
<p>To see a hostname now, use the <a href="/tools/post-quantum-tls-checker?lang=en">post-quantum TLS checker</a>. To reproduce the handshake locally, follow <a href="/guides/openssl-3-5-x25519mlkem768?lang=en">Test X25519MLKEM768 with OpenSSL 3.5</a>.</p>

<h2>How this sits next to NIS2 and DORA</h2>
<p>TR-02102-2 is a technical recommendation, not a substitute for legal obligations under NIS2 or DORA. Germany's NIS2 implementation refers, in <a href="https://www.gesetze-im-internet.de/bsig_2025/__30.html" rel="noopener">§ 30 BSIG</a>, to the state of the art and to concepts for the use of cryptographic mechanisms. TR-02102 is the usual BSI reference for that state of the art in TLS. Our <a href="/guides/nis2-dora-post-quantum-cryptography?lang=en">NIS2 and DORA guide</a> covers the legal texts; this page covers the TLS technical guideline.</p>

<h2>Keep a dated record</h2>
<p>If you need to show that public DACH hostnames kept hybrid key exchange over time, <a href="/monitoring?lang=en">continuous monitoring</a> re-checks them daily at <strong>29 € / 99 €</strong> per month (Starter 10 domains, Business 100), with a 14-day trial. For a one-off dated evidence pack across an organisation's public hostnames, the <a href="/audit?lang=en">PQC Audit is 490 €</a>. Compare names against the <a href="/index?lang=en">PQ-TLS Index</a>.</p>

<h2>Sources</h2>
<ul>
<li><a href="https://www.bsi.bund.de/EN/Themen/Unternehmen-und-Organisationen/Standards-und-Zertifizierung/Technische-Richtlinien/TR-nach-Thema-sortiert/tr02102/tr02102_node.html" rel="noopener">BSI TR-02102 overview</a> (note on TLS 1.3 hybrids after RFC 10024, version 2026-01)</li>
<li><a href="https://www.bsi.bund.de/SharedDocs/Downloads/EN/BSI/Publications/TechGuidelines/TG02102/BSI-TR-02102-2.pdf?__blob=publicationFile" rel="noopener">BSI TR-02102-2 PDF</a> (version 2026-01): periods of use, TLS 1.3 / 1.2, classical (EC)DHE until the end of 2031</li>
<li><a href="https://www.rfc-editor.org/rfc/rfc10024.html" rel="noopener">RFC 10024</a> — PQ/T hybrid key agreement for TLS 1.3 (<code>X25519MLKEM768</code>, <code>SecP256r1MLKEM768</code>, <code>SecP384r1MLKEM1024</code>)</li>
</ul>
""",
        },
        "ar": {
            "title": "BSI TR-02102-2: TLS المقاوم للكم",
            "description": "ماذا يسمح به BSI TR-02102-2 (2026-01) لـ TLS المقاوم للكم: المجموعات الهجينة بما فيها X25519MLKEM768، و(EC)DHE التقليدي حتى نهاية 2031، وما تثبته مصافحة المنفذ 443.",
            "body": """
<p>ينشر المكتب الاتحادي الألماني لأمن المعلومات دليل <strong>BSI TR-02102-2</strong> لتوصيات TLS. الإصدار <strong>2026-01</strong> هو النص الذي يقيس عليه المشغّلون في منطقة DACH نشر TLS العام. تلخّص هذه الصفحة الجزء المقاوم للكم، وتواريخ 2031/2032، وحدود مصافحة المنفذ 443 كدليل.</p>

<h2>ماذا يقول الإصدار 2026-01 عن TLS المقاوم للكم</h2>
<p>بعد نشر <a href="https://www.rfc-editor.org/rfc/rfc10024.html" rel="noopener">RFC 10024</a>، توضّح ملاحظة BSI الرسمية:</p>
<ul>
<li>يمكن استخدام <code>SecP256r1MLKEM768</code> و<code>SecP384r1MLKEM1024</code> اليوم بما يتوافق مع الدليل، وستُوصى بهما النسخة التالية من TR-02102-2.</li>
<li>بالإضافة إلى هاتين المجموعتين، يمكن أيضاً استخدام <code>X25519MLKEM768</code>.</li>
</ul>
<p>إذن الاتفاق الهجين مسموح به الآن. الزوج الموصى به رسمياً في النسخة القادمة هو هجين منحنيات NIST، و<code>X25519MLKEM768</code> (ما تعرضه المتصفحات أولاً) قابل للاستخدام أيضاً وفق ملاحظة BSI الحالية. راجع دائماً <a href="https://www.bsi.bund.de/EN/Themen/Unternehmen-und-Organisationen/Standards-und-Zertifizierung/Technische-Richtlinien/TR-nach-Thema-sortiert/tr02102/tr02102_node.html" rel="noopener">صفحة BSI</a> إذا صدر إصدار أحدث.</p>

<h2>الجداول الزمنية: 2031 و2032</h2>
<ul>
<li><strong>TLS 1.3</strong> هو البروتوكول المفضّل ويُوصى به حتى <strong>2032+</strong>.</li>
<li><strong>TLS 1.2</strong> موصى به فقط حتى <strong>نهاية 2031</strong>.</li>
<li><strong>استخدام الاتفاق التقليدي وحده</strong> ((EC)DHE) موصى به فقط حتى <strong>نهاية 2031</strong>. اعتباراً من 2032 تتجه توصية BSI إلى الاستخدام الهجين، لا (EC)DHE وحده.</li>
</ul>
<p>القراءة العملية: فعّل مجموعة هجينة الآن، وأبقِ تراجعاً تقليدياً للعملاء القدامى حتى 2031، واجعل التبادل التقليدي وحده في طريقه إلى الاختفاء بحلول 2032.</p>

<h2>ماذا تثبت مصافحة المنفذ 443 وما لا تثبته</h2>
<p>تُظهر مصافحة TLS العامة على المنفذ 443 مجموعة تبادل المفاتيح التي تفاوض عليها اسم معيّن في تلك اللحظة. هذا دليل على <strong>وضع نقطة النهاية</strong>، وليس شهادة BSI ولا تدقيقاً كاملاً وفق TR-02102-2، ولا يغطي التوقيعات أو الشهادات أو البيانات المخزنة أو المسار بين CDN والأصل. صرّح بهذا الحد في أي دليل تحتفظ به.</p>
<p>افحص اسماً الآن عبر <a href="/tools/post-quantum-tls-checker?lang=ar">فاحص TLS المقاوم للكم</a>، أو أعد المصافحة محلياً وفق <a href="/guides/openssl-3-5-x25519mlkem768?lang=ar">اختبار X25519MLKEM768 باستخدام OpenSSL 3.5</a>.</p>

<h2>صلته بـ NIS2 وDORA</h2>
<p>TR-02102-2 توصية تقنية، وليست بديلاً عن الالتزامات القانونية. يشير تنفيذ NIS2 في ألمانيا عبر <a href="https://www.gesetze-im-internet.de/bsig_2025/__30.html" rel="noopener">المادة 30 من BSIG</a> إلى حالة التقنية. دليلنا عن <a href="/guides/nis2-dora-post-quantum-cryptography?lang=ar">NIS2 وDORA</a> يغطي النصوص القانونية؛ وهذه الصفحة تغطي الدليل التقني لـ TLS.</p>

<h2>احتفظ بسجل مؤرخ</h2>
<p><a href="/monitoring?lang=ar">المراقبة المستمرة</a> تعيد الفحص يومياً بسعر <strong>29 € / 99 €</strong> شهرياً، مع تجربة 14 يوماً. ولحزمة أدلة مؤرخة عبر الأسماء العامة، <a href="/audit?lang=ar">تدقيق PQC بسعر 490 €</a>. قارن الأسماء مع <a href="/index?lang=ar">مؤشر PQ-TLS</a>.</p>

<h2>المصادر</h2>
<ul>
<li><a href="https://www.bsi.bund.de/EN/Themen/Unternehmen-und-Organisationen/Standards-und-Zertifizierung/Technische-Richtlinien/TR-nach-Thema-sortiert/tr02102/tr02102_node.html" rel="noopener">صفحة BSI لـ TR-02102</a> (ملاحظة TLS 1.3 بعد RFC 10024، الإصدار 2026-01)</li>
<li><a href="https://www.bsi.bund.de/SharedDocs/Downloads/EN/BSI/Publications/TechGuidelines/TG02102/BSI-TR-02102-2.pdf?__blob=publicationFile" rel="noopener">ملف PDF لـ TR-02102-2</a></li>
<li><a href="https://www.rfc-editor.org/rfc/rfc10024.html" rel="noopener">RFC 10024</a></li>
</ul>
""",
        },
        "de": {
            "title": "BSI TR-02102-2: Post-Quanten-TLS",
            "description": "Was BSI TR-02102-2 (2026-01) für Post-Quanten-TLS erlaubt: hybride Gruppen einschließlich X25519MLKEM768, klassisches (EC)DHE nur bis Ende 2031, und was ein Handshake auf Port 443 belegt.",
            "body": """
<p>Das Bundesamt für Sicherheit in der Informationstechnik veröffentlicht <strong>BSI TR-02102-2</strong>, „Kryptographische Verfahren: Empfehlungen und Schlüssellängen — Verwendung von Transport Layer Security (TLS)“. Die Fassung <strong>2026-01</strong> ist der Text, an dem Betreiber im DACH-Raum eine öffentliche TLS-Einführung ausrichten sollten. Diese Seite fasst die Post-Quanten-Teile, die Daten 2031/2032 und die Reichweite eines Handshakes auf Port 443 als Nachweis zusammen.</p>

<h2>Was TR-02102-2 (2026-01) zu Post-Quanten-TLS sagt</h2>
<p>Nach der Veröffentlichung von <a href="https://www.rfc-editor.org/rfc/rfc10024.html" rel="noopener">RFC 10024</a> als Proposed Standard lautet die offizielle BSI-Hinweis zur geltenden Fassung:</p>
<ul>
<li><code>SecP256r1MLKEM768</code> und <code>SecP384r1MLKEM1024</code> können in TLS 1.3 bereits TR-konform eingesetzt werden und werden in der nächsten Fassung von TR-02102-2 empfohlen.</li>
<li>Zusätzlich zu diesen beiden Gruppen kann auch <code>X25519MLKEM768</code> eingesetzt werden.</li>
</ul>
<p>Hybride Schlüsselvereinbarung ist also bereits zulässig. Das formal als Nächstes empfohlene Paar sind die NIST-Kurven-Hybride; <code>X25519MLKEM768</code> (die Gruppe, die die meisten Browser zuerst anbieten) ist laut aktuellem BSI-Hinweis ebenfalls verwendbar. Maßgeblich bleibt der Wortlaut auf der <a href="https://www.bsi.bund.de/DE/Themen/Unternehmen-und-Organisationen/Standards-und-Zertifizierung/Technische-Richtlinien/TR-nach-Thema-sortiert/tr02102/tr02102_node.html" rel="noopener">BSI-Seite zu TR-02102</a>, falls eine spätere Fassung diesen Stand ersetzt.</p>

<h2>Fristen: 2031 und 2032</h2>
<p>Aus TR-02102-2, Fassung 2026-01:</p>
<ul>
<li><strong>TLS 1.3</strong> ist das bevorzugte Protokoll und wird bis <strong>2032+</strong> empfohlen.</li>
<li><strong>TLS 1.2</strong> wird nur bis <strong>Ende 2031</strong> empfohlen, weil für TLS 1.2 keine quantensichere Schlüsselvereinbarung standardisiert werden soll.</li>
<li>Die <strong>alleinige Verwendung klassischer Schlüsselvereinbarung</strong> ((EC)DHE) wird nur bis <strong>Ende 2031</strong> empfohlen. Ab 2032 zielt die BSI-Linie auf die hybride Verwendung: eine klassische Gruppe zusammen mit einem quantensicheren Mechanismus, nicht (EC)DHE allein.</li>
</ul>
<p>Für eine öffentliche HTTPS-Landschaft heißt das praktisch: eine hybride Gruppe <em>jetzt</em> aktivieren (Browser bieten bereits <code>X25519MLKEM768</code> an), bis 2031 einen klassischen Rückfall für ältere Clients behalten und klassischen Schlüsselaustausch allein bis 2032 ablösen.</p>

<h2>Was ein Handshake auf Port 443 belegen kann — und was nicht</h2>
<p>Ein öffentlicher TLS-Handshake auf Port 443 zeigt die Schlüsselaustauschgruppe, die ein Hostname <em>in diesem Moment</em> auf der erreichten IP ausgehandelt hat. Das ist nützliche <strong>Endpunkt-Haltung</strong>: „Spricht dieser öffentliche Name bereits eine TR-verwendbare hybride Gruppe?“</p>
<p>Es ist <strong>keine</strong> BSI-Zertifizierung, keine TR-02102-2-Prüfung und keine Aussage über den Rest der Richtlinie (Signaturen, Zertifikate, Schlüssel im Ruhezustand, interne Verbindungen). Der Weg vom CDN zum Origin, andere Ports und ein vollständiges Subdomain-Inventar sind nicht erfasst. Halten Sie diese Grenze in jedem Nachweis fest.</p>
<p>Prüfen Sie einen Hostnamen jetzt mit dem <a href="/tools/post-quantum-tls-checker?lang=de">Post-Quanten-TLS-Checker</a>. Den Handshake lokal nachstellen können Sie mit <a href="/guides/openssl-3-5-x25519mlkem768?lang=de">X25519MLKEM768 mit OpenSSL 3.5 prüfen</a>.</p>

<h2>Verhältnis zu NIS2 und DORA</h2>
<p>TR-02102-2 ist eine technische Empfehlung, kein Ersatz für rechtliche Pflichten nach NIS2 oder DORA. Die deutsche NIS2-Umsetzung verweist in <a href="https://www.gesetze-im-internet.de/bsig_2025/__30.html" rel="noopener">§ 30 BSIG</a> auf den Stand der Technik und auf Konzepte für den Einsatz kryptographischer Verfahren. TR-02102 ist die übliche BSI-Referenz dafür im TLS. Unser <a href="/guides/nis2-dora-post-quantum-cryptography?lang=de">Leitfaden zu NIS2 und DORA</a> behandelt die Rechtstexte; diese Seite behandelt die technische TLS-Richtlinie.</p>

<h2>Ein datiertes Protokoll führen</h2>
<p>Wenn Sie zeigen müssen, dass öffentliche DACH-Hostnamen den hybriden Schlüsselaustausch über die Zeit behalten, prüft die <a href="/monitoring?lang=de">kontinuierliche Überwachung</a> sie täglich für <strong>29 € / 99 €</strong> pro Monat (Starter 10 Domains, Business 100), mit 14-tägiger Testphase. Für ein einmaliges datiertes Evidence Pack über die öffentlichen Hostnamen einer Organisation kostet das <a href="/audit?lang=de">PQC-Audit 490 €</a>. Vergleichen Sie Namen mit dem <a href="/index?lang=de">PQ-TLS-Index</a>.</p>

<h2>Quellen</h2>
<ul>
<li><a href="https://www.bsi.bund.de/DE/Themen/Unternehmen-und-Organisationen/Standards-und-Zertifizierung/Technische-Richtlinien/TR-nach-Thema-sortiert/tr02102/tr02102_node.html" rel="noopener">BSI-Übersicht zu TR-02102</a> (Hinweis zu TLS-1.3-Hybriden nach RFC 10024, Fassung 2026-01)</li>
<li><a href="https://www.bsi.bund.de/SharedDocs/Downloads/DE/BSI/Publikationen/TechnischeRichtlinien/TR02102/BSI-TR-02102-2.pdf?__blob=publicationFile" rel="noopener">BSI TR-02102-2 (PDF, deutsch)</a></li>
<li><a href="https://www.rfc-editor.org/rfc/rfc10024.html" rel="noopener">RFC 10024</a> — hybride PQ/T-Schlüsselvereinbarung für TLS 1.3</li>
</ul>
""",
        },
    },
}

FAQ = {
    "openssl-3-5-x25519mlkem768": {
        "en": {
            "short": "<p>Use <strong>OpenSSL 3.5 or newer</strong> and look for <code>Negotiated TLS1.3 group: X25519MLKEM768</code>. Do not trust <code>Peer Temp Key: X25519</code> alone. An OpenSSL 3.0–3.4 client cannot test this group. Or skip the flags and use the <a href=\"/tools/post-quantum-tls-checker?lang=en\">post-quantum TLS checker</a>.</p>",
            "faq": [
                ("Which OpenSSL version do I need to test X25519MLKEM768?",
                 "<p>OpenSSL 3.5.0 or newer. Versions 3.0 to 3.4 do not recognise the group name and cannot prove whether the server supports it.</p>"),
                ("What line in the s_client output should I trust?",
                 "<p><code>Negotiated TLS1.3 group: X25519MLKEM768</code> (or another hybrid / ML-KEM group). <code>Peer Temp Key: X25519</code> can appear even during a successful hybrid handshake because it may show only the X25519 half.</p>"),
                ("What does TLS alert 40 mean in this test?",
                 "<p>Alert 40 is handshake_failure. With <code>-groups X25519MLKEM768</code> it usually means the server did not accept that group, or a middlebox stalled the large ClientHello.</p>"),
                ("Why does a test from OpenSSL 3.0 or 3.4 prove nothing?",
                 "<p>Those releases have no ML-KEM implementation. They either reject the group name or silently finish with classical X25519, regardless of what the server can do.</p>"),
                ("How can I test without upgrading OpenSSL on my machine?",
                 "<p>Use the <a href=\"/tools/post-quantum-tls-checker?lang=en\">online checker</a>, <code>curl https://ather-quantum.com/api/v1/scan?domain=example.com&amp;format=text</code>, or run OpenSSL 3.5 inside a newer container image.</p>"),
            ],
        },
        "ar": {
            "short": "<p>استخدم <strong>OpenSSL 3.5 أو أحدث</strong> وابحث عن <code>Negotiated TLS1.3 group: X25519MLKEM768</code>. لا تعتمد على <code>Peer Temp Key: X25519</code> وحده. عميل 3.0–3.4 لا يستطيع اختبار هذه المجموعة. أو تجاوز الأعلام واستخدم <a href=\"/tools/post-quantum-tls-checker?lang=ar\">الفاحص</a>.</p>",
            "faq": [
                ("ما إصدار OpenSSL المطلوب لاختبار X25519MLKEM768؟",
                 "<p>OpenSSL 3.5.0 أو أحدث. الإصدارات 3.0 إلى 3.4 لا تعرف اسم المجموعة ولا تثبت إن كان الخادم يدعمها.</p>"),
                ("أي سطر في ناتج s_client أثق به؟",
                 "<p><code>Negotiated TLS1.3 group: X25519MLKEM768</code> (أو مجموعة هجينة / ML-KEM أخرى). قد يظهر <code>Peer Temp Key: X25519</code> حتى في مصافحة هجينة ناجحة.</p>"),
                ("ماذا يعني التنبيه 40 في هذا الفحص؟",
                 "<p>التنبيه 40 هو فشل المصافحة. مع فرض المجموعة يعني عادة أن الخادم لم يقبلها، أو أن جهازاً وسيطاً تعثر في ClientHello الكبير.</p>"),
                ("لماذا لا يثبت الفحص من OpenSSL 3.0 أو 3.4 شيئاً؟",
                 "<p>هذه الإصدارات لا تنفّذ ML-KEM. إما ترفض اسم المجموعة أو تكتمل بصمت عبر X25519 التقليدي، بغض النظر عن قدرة الخادم.</p>"),
                ("كيف أفحص دون ترقية OpenSSL على جهازي؟",
                 "<p>عبر <a href=\"/tools/post-quantum-tls-checker?lang=ar\">الفاحص على الموقع</a> أو واجهة النص <code>curl https://ather-quantum.com/api/v1/scan?domain=example.com&amp;format=text</code> أو حاوية أحدث.</p>"),
            ],
        },
        "de": {
            "short": "<p>Nutzen Sie <strong>OpenSSL 3.5 oder neuer</strong> und suchen Sie nach <code>Negotiated TLS1.3 group: X25519MLKEM768</code>. Vertrauen Sie nicht allein auf <code>Peer Temp Key: X25519</code>. Ein Client mit OpenSSL 3.0–3.4 kann diese Gruppe nicht testen. Oder nutzen Sie den <a href=\"/tools/post-quantum-tls-checker?lang=de\">Post-Quanten-TLS-Checker</a>.</p>",
            "faq": [
                ("Welche OpenSSL-Version ist nötig?",
                 "<p>OpenSSL 3.5.0 oder neuer. Die Versionen 3.0 bis 3.4 kennen den Gruppennamen nicht und können die Serverunterstützung nicht belegen.</p>"),
                ("Welcher Zeile in der s_client-Ausgabe soll ich trauen?",
                 "<p><code>Negotiated TLS1.3 group: X25519MLKEM768</code> (oder eine andere hybride / ML-KEM-Gruppe). <code>Peer Temp Key: X25519</code> kann auch bei einem erfolgreichen Hybrid-Handshake erscheinen.</p>"),
                ("Was bedeutet TLS-Alert 40 bei diesem Test?",
                 "<p>Alert 40 ist handshake_failure. Mit <code>-groups X25519MLKEM768</code> heißt das meist: Der Server hat die Gruppe nicht akzeptiert, oder eine Middlebox hat das große ClientHello ausgebremst.</p>"),
                ("Warum beweist ein Test mit OpenSSL 3.0 oder 3.4 nichts?",
                 "<p>Diese Versionen enthalten keine ML-KEM-Implementierung. Sie lehnen den Namen ab oder beenden den Handshake still mit klassischem X25519 — unabhängig vom Server.</p>"),
                ("Wie teste ich ohne lokales OpenSSL 3.5?",
                 "<p>Mit dem <a href=\"/tools/post-quantum-tls-checker?lang=de\">Online-Checker</a>, mit <code>curl https://ather-quantum.com/api/v1/scan?domain=example.com&amp;format=text</code> oder in einem neueren Container-Image.</p>"),
            ],
        },
    },
    "bsi-tr-02102-2-post-quantum-tls": {
        "en": {
            "short": "<p>BSI TR-02102-2 (2026-01) already allows hybrid TLS 1.3 key agreement, including <code>X25519MLKEM768</code> and the SecP* ML-KEM hybrids in RFC 10024. Classical (EC)DHE alone is recommended only until the <strong>end of 2031</strong>; from 2032 the direction is hybrid. A port-443 handshake is endpoint posture, <strong>not</strong> a BSI certification.</p>",
            "faq": [
                ("Does BSI already allow hybrid post-quantum TLS?",
                 "<p>Yes. After RFC 10024, BSI states that SecP256r1MLKEM768 and SecP384r1MLKEM1024 can already be used TR-compliant in TLS 1.3 (and will be recommended in the next TR-02102-2 version), and that X25519MLKEM768 can also be used.</p>"),
                ("Is X25519MLKEM768 TR-compliant?",
                 "<p>The current official BSI note on version 2026-01 says that, in addition to the two SecP* hybrids, X25519MLKEM768 can also be used. Check the BSI TR-02102 page if a later version changes that wording.</p>"),
                ("Until when is classical (EC)DHE still recommended?",
                 "<p>Only until the end of 2031, if used alone. TLS 1.2 is likewise recommended only until the end of 2031. TLS 1.3 is recommended into 2032+.</p>"),
                ("Does a port-443 scan prove BSI compliance?",
                 "<p>No. It is evidence that a public hostname negotiated a hybrid or ML-KEM group at that moment. It is not a BSI certification and does not cover signatures, certificates, keys at rest, origin connections or a full estate.</p>"),
                ("What should a DACH operator do now?",
                 "<p>Enable a hybrid group on public TLS terminators, verify each hostname with a port-443 handshake, keep a dated record (monitoring at 29 € / 99 € per month, or a 490 € audit as an evidence pack), and plan to end classical-only key exchange by 2032.</p>"),
            ],
        },
        "ar": {
            "short": "<p>يسمح BSI TR-02102-2 (2026-01) الآن باتفاق المفاتيح الهجين في TLS 1.3، بما فيه <code>X25519MLKEM768</code> وهجين SecP* في RFC 10024. يُوصى بـ (EC)DHE التقليدي وحده حتى <strong>نهاية 2031</strong> فقط؛ ومن 2032 يتجه الدليل إلى الهجين. مصافحة المنفذ 443 دليل على وضع نقطة النهاية، <strong>وليست</strong> شهادة BSI.</p>",
            "faq": [
                ("هل يسمح BSI أصلاً بـ TLS الهجين المقاوم للكم؟",
                 "<p>نعم. بعد RFC 10024 يوضح BSI أن SecP256r1MLKEM768 وSecP384r1MLKEM1024 يمكن استخدامهما اليوم بما يتوافق مع الدليل، وأن X25519MLKEM768 يمكن استخدامه أيضاً.</p>"),
                ("هل X25519MLKEM768 متوافق مع الدليل؟",
                 "<p>ملاحظة BSI الرسمية على إصدار 2026-01 تقول إنه بالإضافة إلى هجيني SecP* يمكن أيضاً استخدام X25519MLKEM768. راجع صفحة BSI إذا صدر إصدار أحدث.</p>"),
                ("حتى متى يُوصى بـ (EC)DHE التقليدي؟",
                 "<p>حتى نهاية 2031 فقط إذا استُخدم وحده. كذلك TLS 1.2 حتى نهاية 2031. أما TLS 1.3 فيُوصى به حتى 2032+.</p>"),
                ("هل يثبت فحص المنفذ 443 الامتثال لـ BSI؟",
                 "<p>لا. هو دليل على أن اسماً عاماً تفاوض على مجموعة هجينة أو ML-KEM في تلك اللحظة، وليس شهادة BSI ولا يغطي التوقيعات أو الشهادات أو الأصل أو المؤسسة بالكامل.</p>"),
                ("ماذا يفعل المشغّل في منطقة DACH الآن؟",
                 "<p>فعّل مجموعة هجينة على من ينهي TLS العام، وتحقق من كل اسم بمصافحة على المنفذ 443، واحتفظ بسجل مؤرخ (مراقبة بـ 29 € / 99 € شهرياً، أو تدقيق بـ 490 € كحزمة أدلة)، وخطّط لإنهاء التبادل التقليدي وحده بحلول 2032.</p>"),
            ],
        },
        "de": {
            "short": "<p>BSI TR-02102-2 (2026-01) erlaubt bereits die hybride TLS-1.3-Schlüsselvereinbarung, einschließlich <code>X25519MLKEM768</code> und der SecP*-ML-KEM-Hybride aus RFC 10024. Klassisches (EC)DHE allein wird nur bis <strong>Ende 2031</strong> empfohlen; ab 2032 zielt die Linie auf hybrid. Ein Handshake auf Port 443 ist Endpunkt-Haltung, <strong>keine</strong> BSI-Zertifizierung.</p>",
            "faq": [
                ("Erlaubt das BSI bereits hybrides Post-Quanten-TLS?",
                 "<p>Ja. Nach RFC 10024 können SecP256r1MLKEM768 und SecP384r1MLKEM1024 in TLS 1.3 bereits TR-konform eingesetzt werden (und werden in der nächsten Fassung empfohlen); zusätzlich kann X25519MLKEM768 eingesetzt werden.</p>"),
                ("Ist X25519MLKEM768 TR-konform?",
                 "<p>Der aktuelle offizielle BSI-Hinweis zur Fassung 2026-01 sagt, dass neben den beiden SecP*-Hybriden auch X25519MLKEM768 verwendet werden kann. Prüfen Sie die BSI-Seite, falls eine spätere Fassung den Wortlaut ändert.</p>"),
                ("Bis wann wird klassisches (EC)DHE noch empfohlen?",
                 "<p>Nur bis Ende 2031, wenn es allein verwendet wird. TLS 1.2 ebenfalls nur bis Ende 2031. TLS 1.3 wird bis 2032+ empfohlen.</p>"),
                ("Beweist ein Scan auf Port 443 die BSI-Konformität?",
                 "<p>Nein. Er belegt, dass ein öffentlicher Hostname in diesem Moment eine hybride oder ML-KEM-Gruppe ausgehandelt hat. Das ist keine BSI-Zertifizierung und umfasst keine Signaturen, Zertifikate, Origin-Verbindungen oder die gesamte Landschaft.</p>"),
                ("Was sollte ein DACH-Betreiber jetzt tun?",
                 "<p>Eine hybride Gruppe an den öffentlichen TLS-Terminatoren aktivieren, jeden Hostnamen per Handshake auf Port 443 prüfen, ein datiertes Protokoll führen (Monitoring für 29 € / 99 € im Monat oder ein Audit für 490 € als Evidence Pack) und klassischen Schlüsselaustausch allein bis 2032 ablösen.</p>"),
            ],
        },
    },
}

RELATED_LABELS = {"en": "See also", "ar": "انظر أيضاً", "de": "Siehe auch"}

# Extra related links shown under existing guides (and the new ones).
RELATED = {
    "check-website-post-quantum-tls": [
        ("guide", "openssl-3-5-x25519mlkem768",
         {"en": "Test X25519MLKEM768 with OpenSSL 3.5",
          "ar": "اختبار X25519MLKEM768 باستخدام OpenSSL 3.5",
          "de": "X25519MLKEM768 mit OpenSSL 3.5 prüfen"}),
        ("tool", "/tools/post-quantum-tls-checker",
         {"en": "Post-quantum TLS checker",
          "ar": "فاحص TLS المقاوم للكم",
          "de": "Post-Quanten-TLS-Checker"}),
    ],
    "ubuntu-openssl-3-0-post-quantum-tls": [
        ("guide", "openssl-3-5-x25519mlkem768",
         {"en": "Test X25519MLKEM768 with OpenSSL 3.5",
          "ar": "اختبار X25519MLKEM768 باستخدام OpenSSL 3.5",
          "de": "X25519MLKEM768 mit OpenSSL 3.5 prüfen"}),
        ("tool", "/tools/post-quantum-tls-checker",
         {"en": "Post-quantum TLS checker",
          "ar": "فاحص TLS المقاوم للكم",
          "de": "Post-Quanten-TLS-Checker"}),
    ],
    "nis2-dora-post-quantum-cryptography": [
        ("guide", "bsi-tr-02102-2-post-quantum-tls",
         {"en": "BSI TR-02102-2: Post-Quantum TLS",
          "ar": "BSI TR-02102-2: TLS المقاوم للكم",
          "de": "BSI TR-02102-2: Post-Quanten-TLS"}),
        ("tool", "/tools/post-quantum-tls-checker",
         {"en": "Post-quantum TLS checker",
          "ar": "فاحص TLS المقاوم للكم",
          "de": "Post-Quanten-TLS-Checker"}),
    ],
    "openssl-3-5-curl-test-x25519mlkem768": [
        ("guide", "openssl-3-5-x25519mlkem768",
         {"en": "Test X25519MLKEM768 with OpenSSL 3.5 (full cookbook)",
          "ar": "اختبار X25519MLKEM768 باستخدام OpenSSL 3.5 (الدليل الكامل)",
          "de": "X25519MLKEM768 mit OpenSSL 3.5 prüfen (ausführliches Kochbuch)"}),
        ("tool", "/tools/post-quantum-tls-checker",
         {"en": "Post-quantum TLS checker",
          "ar": "فاحص TLS المقاوم للكم",
          "de": "Post-Quanten-TLS-Checker"}),
    ],
    "ssl-labs-post-quantum-tls-check": [
        ("tool", "/tools/post-quantum-tls-checker",
         {"en": "Post-quantum TLS checker",
          "ar": "فاحص TLS المقاوم للكم",
          "de": "Post-Quanten-TLS-Checker"}),
        ("guide", "openssl-3-5-x25519mlkem768",
         {"en": "Test X25519MLKEM768 with OpenSSL 3.5",
          "ar": "اختبار X25519MLKEM768 باستخدام OpenSSL 3.5",
          "de": "X25519MLKEM768 mit OpenSSL 3.5 prüfen"}),
    ],
    "enable-x25519mlkem768-nginx": [
        ("tool", "/tools/post-quantum-tls-checker",
         {"en": "Post-quantum TLS checker",
          "ar": "فاحص TLS المقاوم للكم",
          "de": "Post-Quanten-TLS-Checker"}),
        ("guide", "openssl-3-5-x25519mlkem768",
         {"en": "Test X25519MLKEM768 with OpenSSL 3.5",
          "ar": "اختبار X25519MLKEM768 باستخدام OpenSSL 3.5",
          "de": "X25519MLKEM768 mit OpenSSL 3.5 prüfen"}),
    ],
    "openssl-3-5-x25519mlkem768": [
        ("tool", "/tools/post-quantum-tls-checker",
         {"en": "Post-quantum TLS checker",
          "ar": "فاحص TLS المقاوم للكم",
          "de": "Post-Quanten-TLS-Checker"}),
        ("guide", "bsi-tr-02102-2-post-quantum-tls",
         {"en": "BSI TR-02102-2: Post-Quantum TLS",
          "ar": "BSI TR-02102-2: TLS المقاوم للكم",
          "de": "BSI TR-02102-2: Post-Quanten-TLS"}),
        ("guide", "openssl-3-5-curl-test-x25519mlkem768",
         {"en": "OpenSSL 3.5 and curl CLI commands",
          "ar": "أوامر OpenSSL 3.5 وcurl",
          "de": "OpenSSL 3.5- und curl-Befehle"}),
    ],
    "bsi-tr-02102-2-post-quantum-tls": [
        ("tool", "/tools/post-quantum-tls-checker",
         {"en": "Post-quantum TLS checker",
          "ar": "فاحص TLS المقاوم للكم",
          "de": "Post-Quanten-TLS-Checker"}),
        ("guide", "openssl-3-5-x25519mlkem768",
         {"en": "Test X25519MLKEM768 with OpenSSL 3.5",
          "ar": "اختبار X25519MLKEM768 باستخدام OpenSSL 3.5",
          "de": "X25519MLKEM768 mit OpenSSL 3.5 prüfen"}),
        ("guide", "nis2-dora-post-quantum-cryptography",
         {"en": "NIS2 and DORA post-quantum requirements",
          "ar": "متطلبات NIS2 وDORA للتشفير المقاوم للكم",
          "de": "NIS2- und DORA-Anforderungen"}),
    ],
}


def related_for(slug, lang):
    items = RELATED.get(slug) or []
    out = []
    for kind, target, titles in items:
        title = titles.get(lang) or titles["en"]
        if kind == "guide":
            href = f"/guides/{target}?lang={lang if lang in titles else 'en'}"
            # German only when the target guide has a 'de' title that we provided;
            # url_for in the template is better, but this is used as a fallback list of dicts.
        else:
            href = f"{target}?lang={lang}"
        out.append({"kind": kind, "target": target, "title": title, "href": href})
    return out
