# config_gen.py
# مولّد إعدادات TLS ما بعد الكمومي: لكل خادم/منصة وحالة (إصدار المكتبة) خطوات جاهزة للنسخ.
# كل أمر ونص هنا مأخوذ من الأدلة المُتحقق منها في guides.py (لا معلومات جديدة من الذاكرة).
# الأوامر لغة-محايدة؛ الملاحظات بثلاث لغات (en/ar/de).

VERIFY = "openssl s_client -connect example.com:443 -groups X25519MLKEM768 </dev/null 2>/dev/null | grep -i group"


def _t(en, ar, de):
    return {"en": en, "ar": ar, "de": de}


OLD_OPENSSL = _t(
    "OpenSSL 3.0 to 3.4 cannot negotiate ML-KEM, whatever you put in the configuration. Ubuntu 22.04 and 24.04 ship OpenSSL 3.0; Debian 13 ships 3.5. Options: upgrade the OS, use a build linked against OpenSSL 3.5, or put a post-quantum capable proxy, load balancer or CDN in front.",
    "OpenSSL من 3.0 إلى 3.4 لا يستطيع التفاوض على ML-KEM مهما كتبت في الإعدادات. Ubuntu 22.04 و24.04 يأتيان بـ OpenSSL 3.0، وDebian 13 يأتي بـ 3.5. الخيارات: ترقية النظام، أو نسخة مبنية على OpenSSL 3.5، أو وضع وكيل أو موازن حمل أو CDN يدعم ما بعد الكم أمام الخادم.",
    "OpenSSL 3.0 bis 3.4 kann ML-KEM nicht aushandeln, egal was in der Konfiguration steht. Ubuntu 22.04 und 24.04 liefern OpenSSL 3.0, Debian 13 liefert 3.5. Optionen: Betriebssystem aktualisieren, einen gegen OpenSSL 3.5 gebauten Build verwenden oder einen Post-Quanten-fähigen Proxy, Load Balancer oder CDN davorschalten.")
PIN_WARNING = _t(
    "An explicit group or curve list copied from an old hardening guide silently removes the hybrid group. Delete it, or keep X25519MLKEM768 first as shown.",
    "قائمة مجموعات أو منحنيات صريحة منسوخة من دليل «تقوية» قديم تحذف المجموعة الهجينة دون أي تنبيه. احذفها، أو أبقِ X25519MLKEM768 أولاً كما هو موضح.",
    "Eine explizite Gruppen- oder Kurvenliste aus einer alten Härtungsanleitung entfernt die hybride Gruppe stillschweigend. Löschen Sie sie oder setzen Sie X25519MLKEM768 wie gezeigt an den Anfang.")
PROXY_NOTE = _t(
    "If nginx, a load balancer or a CDN terminates TLS in front of this service, browsers never talk TLS to it directly: configure that layer instead.",
    "إن كان nginx أو موازن حمل أو CDN ينهي اتصال TLS أمام هذه الخدمة، فالمتصفح لا يتصل بها مباشرة: اضبط تلك الطبقة بدلاً منها.",
    "Terminiert nginx, ein Load Balancer oder ein CDN TLS vor diesem Dienst, sprechen Browser nie direkt TLS mit ihm: Konfigurieren Sie stattdessen diese Schicht.")
ORIGIN_NOTE = _t(
    "This covers the connection between visitors and the edge. The hop from the edge to your origin is a separate connection: upgrade the origin too if that link crosses the public internet.",
    "هذا يغطي الاتصال بين الزائر والحافة فقط. الاتصال من الحافة إلى خادمك الأصلي اتصال منفصل: رقِّ الخادم الأصلي أيضاً إن كان هذا الاتصال يمر عبر الإنترنت العام.",
    "Das deckt die Verbindung zwischen Besuchern und Edge ab. Die Strecke vom Edge zu Ihrem Origin ist eine eigene Verbindung: Rüsten Sie auch den Origin um, wenn sie über das öffentliche Internet läuft.")

S_CHECK = "check"
S_CONFIG = "config"
S_RELOAD = "reload"
S_VERIFY = "verify"


def step(kind, code=None, note=None):
    return {"kind": kind, "code": code, "note": note}


SERVERS = {
    "nginx": {
        "name": "nginx", "guide": "enable-x25519mlkem768-nginx",
        "variants": {
            "openssl35": {"label": _t("OpenSSL 3.5 or newer", "OpenSSL 3.5 أو أحدث", "OpenSSL 3.5 oder neuer"), "ok": True, "steps": [
                step(S_CHECK, "nginx -V 2>&1 | grep -o 'OpenSSL [0-9.]*'\nopenssl version"),
                step(S_CONFIG, "server {\n    listen 443 ssl;\n    http2 on;\n    ssl_protocols TLSv1.2 TLSv1.3;\n    ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;\n    # ... certificates and the rest of your config\n}",
                     _t("Also look in included files such as /etc/letsencrypt/options-ssl-nginx.conf for another ssl_ecdh_curve line.",
                        "ابحث أيضاً في الملفات المضمّنة مثل /etc/letsencrypt/options-ssl-nginx.conf عن سطر ssl_ecdh_curve آخر.",
                        "Prüfen Sie auch eingebundene Dateien wie /etc/letsencrypt/options-ssl-nginx.conf auf eine weitere ssl_ecdh_curve-Zeile.")),
                step(S_RELOAD, "nginx -t && systemctl reload nginx"),
                step(S_VERIFY, VERIFY)]},
            "openssl30": {"label": _t("OpenSSL 3.0 to 3.4", "OpenSSL من 3.0 إلى 3.4", "OpenSSL 3.0 bis 3.4"), "ok": False, "steps": [
                step(S_CHECK, "nginx -V 2>&1 | grep -o 'OpenSSL [0-9.]*'", OLD_OPENSSL)]},
        },
    },
    "apache": {
        "name": "Apache httpd", "guide": "post-quantum-tls-apache-caddy-haproxy-cloudflare",
        "variants": {
            "openssl35": {"label": _t("mod_ssl with OpenSSL 3.5+", "mod_ssl مع OpenSSL 3.5 أو أحدث", "mod_ssl mit OpenSSL 3.5+"), "ok": True, "steps": [
                step(S_CHECK, "openssl version\napachectl -V"),
                step(S_CONFIG, "SSLProtocol -all +TLSv1.2 +TLSv1.3\nSSLOpenSSLConfCmd Groups X25519MLKEM768:X25519:prime256v1",
                     _t("With OpenSSL 3.5 the group is on by default; set it explicitly if your config already has a Groups or SSLOpenSSLConfCmd Curves line.",
                        "مع OpenSSL 3.5 المجموعة مفعّلة افتراضياً؛ اضبطها صراحةً إن كان في إعداداتك سطر Groups أو SSLOpenSSLConfCmd Curves.",
                        "Mit OpenSSL 3.5 ist die Gruppe standardmäßig aktiv; setzen Sie sie explizit, wenn Ihre Konfiguration bereits eine Groups- oder SSLOpenSSLConfCmd-Curves-Zeile enthält.")),
                step(S_RELOAD, "apachectl configtest && systemctl reload apache2   # httpd on RHEL"),
                step(S_VERIFY, VERIFY)]},
            "openssl30": {"label": _t("OpenSSL 3.0 to 3.4", "OpenSSL من 3.0 إلى 3.4", "OpenSSL 3.0 bis 3.4"), "ok": False, "steps": [
                step(S_CHECK, "openssl version\napachectl -V", OLD_OPENSSL)]},
        },
    },
    "haproxy": {
        "name": "HAProxy", "guide": "post-quantum-tls-apache-caddy-haproxy-cloudflare",
        "variants": {
            "openssl35": {"label": _t("Built with OpenSSL 3.5+ or AWS-LC", "مبني على OpenSSL 3.5+ أو AWS-LC", "Gebaut mit OpenSSL 3.5+ oder AWS-LC"), "ok": True, "steps": [
                step(S_CHECK, "haproxy -vv | grep -iE 'openssl|aws-lc'"),
                step(S_CONFIG, "bind :443 ssl crt /etc/haproxy/certs/ curves X25519MLKEM768:X25519:P-256"),
                step(S_RELOAD, "haproxy -c -f /etc/haproxy/haproxy.cfg && systemctl reload haproxy"),
                step(S_VERIFY, VERIFY)]},
            "openssl30": {"label": _t("Built with OpenSSL 3.0 to 3.4", "مبني على OpenSSL من 3.0 إلى 3.4", "Gebaut mit OpenSSL 3.0 bis 3.4"), "ok": False, "steps": [
                step(S_CHECK, "haproxy -vv | grep -iE 'openssl|aws-lc'", OLD_OPENSSL)]},
        },
    },
    "caddy": {
        "name": "Caddy", "guide": "post-quantum-tls-apache-caddy-haproxy-cloudflare",
        "variants": {
            "v210": {"label": _t("Caddy 2.10 or newer", "Caddy 2.10 أو أحدث", "Caddy 2.10 oder neuer"), "ok": True, "steps": [
                step(S_CHECK, "caddy version   # 2.10 or newer"),
                step(S_CONFIG, "example.com {\n    reverse_proxy 127.0.0.1:8000\n}",
                     _t("Nothing to add: Caddy 2.10+ is built with Go 1.24+, which enables X25519MLKEM768 by default. Remove any curves option in the tls block, or include the hybrid group in it.",
                        "لا شيء يُضاف: Caddy 2.10+ مبني على Go 1.24+ الذي يفعّل X25519MLKEM768 افتراضياً. احذف أي خيار curves في كتلة tls، أو أضف إليه المجموعة الهجينة.",
                        "Nichts hinzuzufügen: Caddy 2.10+ ist mit Go 1.24+ gebaut, das X25519MLKEM768 standardmäßig aktiviert. Entfernen Sie eine curves-Option im tls-Block oder nehmen Sie die hybride Gruppe auf.")),
                step(S_VERIFY, VERIFY)]},
            "older": {"label": _t("Older than 2.10", "أقدم من 2.10", "Älter als 2.10"), "ok": False, "steps": [
                step(S_CHECK, "caddy version",
                     _t("Upgrade Caddy to 2.10 or newer; that is usually all you need.",
                        "رقِّ Caddy إلى 2.10 أو أحدث؛ هذا عادةً كل ما تحتاجه.",
                        "Aktualisieren Sie Caddy auf 2.10 oder neuer; meist ist das alles."))]},
        },
    },
    "go": {
        "name": "Go (crypto/tls)", "guide": "go-post-quantum-tls-x25519mlkem768",
        "variants": {
            "go124": {"label": _t("go.mod says go 1.24 or newer", "go.mod فيه go 1.24 أو أحدث", "go.mod mit go 1.24 oder neuer"), "ok": True, "steps": [
                step(S_CHECK, "go version\ngrep '^go ' go.mod"),
                step(S_CONFIG, "srv := &http.Server{\n    Addr: \":443\",\n    TLSConfig: &tls.Config{\n        CurvePreferences: []tls.CurveID{\n            tls.X25519MLKEM768, tls.X25519, tls.CurveP256,\n        },\n    },\n}\nlog.Fatal(srv.ListenAndServeTLS(\"cert.pem\", \"key.pem\"))",
                     _t("An empty CurvePreferences already uses the defaults, which include X25519MLKEM768. Also look for GODEBUG=tlsmlkem=0 in Dockerfiles, systemd units and Kubernetes manifests: it turns the defaults off.",
                        "ترك CurvePreferences فارغاً يستخدم الإعدادات الافتراضية التي تشمل X25519MLKEM768. وابحث عن GODEBUG=tlsmlkem=0 في ملفات Docker ووحدات systemd وملفات Kubernetes: فهو يعطّل الافتراضي.",
                        "Ein leeres CurvePreferences nutzt bereits die Standardwerte inklusive X25519MLKEM768. Suchen Sie außerdem nach GODEBUG=tlsmlkem=0 in Dockerfiles, systemd-Units und Kubernetes-Manifesten: Es schaltet die Standardwerte ab.")),
                step(S_VERIFY, "c, err := tls.Dial(\"tcp\", \"example.com:443\", &tls.Config{})\nif err != nil { log.Fatal(err) }\nfmt.Println(c.ConnectionState().CurveID) // X25519MLKEM768")]},
            "go123": {"label": _t("go.mod says go 1.23 or older", "go.mod فيه go 1.23 أو أقدم", "go.mod mit go 1.23 oder älter"), "ok": False, "steps": [
                step(S_CHECK, "grep '^go ' go.mod",
                     _t("The defaults come from the go line of your main module, not from the toolchain: with go 1.23 or older in go.mod, even the newest Go builds a classical-only service. Raise the line, or add the godebug line below to go.mod.",
                        "الإعدادات الافتراضية تأتي من سطر go في الوحدة الرئيسية لا من أداة البناء: مع go 1.23 أو أقدم في go.mod، حتى أحدث Go يبني خدمة تقليدية فقط. ارفع السطر، أو أضف سطر godebug أدناه إلى go.mod.",
                        "Die Standardwerte kommen aus der go-Zeile Ihres Hauptmoduls, nicht aus der Toolchain: Mit go 1.23 oder älter in go.mod baut selbst das neueste Go einen rein klassischen Dienst. Erhöhen Sie die Zeile oder fügen Sie die godebug-Zeile unten in go.mod ein.")),
                step(S_CONFIG, "go mod edit -go=1.24\n# or, if you cannot raise it yet, add to go.mod:\ngodebug tlsmlkem=1")]},
        },
    },
    "node": {
        "name": "Node.js", "guide": "nodejs-post-quantum-tls-x25519mlkem768",
        "variants": {
            "openssl35": {"label": _t("OpenSSL 3.5+ (official Node.js 24 binaries)", "OpenSSL 3.5+ (نسخ Node.js 24 الرسمية)", "OpenSSL 3.5+ (offizielle Node.js-24-Binaries)"), "ok": True, "steps": [
                step(S_CHECK, "node -p process.versions.openssl"),
                step(S_CONFIG, "const https = require('node:https');\nhttps.createServer({\n  key, cert,\n  minVersion: 'TLSv1.2',\n  ecdhCurve: 'X25519MLKEM768:X25519:prime256v1',\n}, app).listen(443);",
                     _t("The default ecdhCurve 'auto' already includes the hybrid group; old snippets like ecdhCurve: 'prime256v1' remove it.",
                        "القيمة الافتراضية ecdhCurve: 'auto' تشمل المجموعة الهجينة؛ مقتطفات قديمة مثل ecdhCurve: 'prime256v1' تحذفها.",
                        "Der Standard ecdhCurve 'auto' enthält die hybride Gruppe bereits; alte Snippets wie ecdhCurve: 'prime256v1' entfernen sie.")),
                step(S_VERIFY, VERIFY, PROXY_NOTE)]},
            "openssl30": {"label": _t("OpenSSL 3.0 to 3.4 (often distribution packages)", "OpenSSL من 3.0 إلى 3.4 (غالباً حزم التوزيعات)", "OpenSSL 3.0 bis 3.4 (oft Distributionspakete)"), "ok": False, "steps": [
                step(S_CHECK, "node -p process.versions.openssl",
                     _t("Node.js packages from Linux distributions are often linked against the system OpenSSL (3.0 on Ubuntu 22.04 and 24.04), which cannot negotiate ML-KEM. Use the official Node.js 24 LTS binaries (OpenSSL 3.5), or terminate TLS in front of Node.js.",
                        "حزم Node.js في توزيعات Linux غالباً مرتبطة بـ OpenSSL النظام (3.0 في Ubuntu 22.04 و24.04) الذي لا يدعم ML-KEM. استخدم نسخ Node.js 24 LTS الرسمية (OpenSSL 3.5)، أو أنهِ TLS أمام Node.js.",
                        "Node.js-Pakete aus Linux-Distributionen nutzen oft das System-OpenSSL (3.0 unter Ubuntu 22.04 und 24.04), das ML-KEM nicht aushandeln kann. Nutzen Sie die offiziellen Node.js-24-LTS-Binaries (OpenSSL 3.5) oder terminieren Sie TLS vor Node.js."))]},
        },
    },
    "java": {
        "name": "Java (JSSE)", "guide": "java-post-quantum-tls-jdk27",
        "variants": {
            "jdk27": {"label": _t("JDK 27", "JDK 27", "JDK 27"), "ok": True, "steps": [
                step(S_CHECK, "java -version",
                     _t("JDK 27 enables X25519MLKEM768 by default (JEP 527) for the standard javax.net.ssl APIs: embedded Tomcat, Jetty or Undertow on JSSE, HttpClient, HttpsURLConnection.",
                        "JDK 27 يفعّل X25519MLKEM768 افتراضياً (JEP 527) لواجهات javax.net.ssl القياسية: Tomcat وJetty وUndertow المضمّنة على JSSE وHttpClient وHttpsURLConnection.",
                        "JDK 27 aktiviert X25519MLKEM768 standardmäßig (JEP 527) für die javax.net.ssl-APIs: eingebettetes Tomcat, Jetty oder Undertow auf JSSE, HttpClient, HttpsURLConnection.")),
                step(S_CONFIG, "-Djdk.tls.namedGroups=X25519MLKEM768,x25519,secp256r1,secp384r1",
                     _t("Only needed if you override the groups: look for jdk.tls.namedGroups in start scripts, JAVA_TOOL_OPTIONS or container env, and SSLParameters.setNamedGroups(...) in code.",
                        "مطلوب فقط إن كنت تغيّر المجموعات: ابحث عن jdk.tls.namedGroups في سكربتات التشغيل أو JAVA_TOOL_OPTIONS أو متغيرات الحاوية، وعن SSLParameters.setNamedGroups(...) في الكود.",
                        "Nur nötig, wenn Sie die Gruppen überschreiben: Suchen Sie jdk.tls.namedGroups in Startskripten, JAVA_TOOL_OPTIONS oder Container-Variablen und SSLParameters.setNamedGroups(...) im Code.")),
                step(S_VERIFY, VERIFY, PROXY_NOTE)]},
            "jdk21": {"label": _t("JDK 21 or 25 (LTS)", "JDK 21 أو 25 (LTS)", "JDK 21 oder 25 (LTS)"), "ok": False, "steps": [
                step(S_CHECK, "java -version",
                     _t("JDK 21 and 25 have no hybrid ML-KEM key exchange in SunJSSE. Terminate TLS in front of the JVM on a component that supports it: nginx with OpenSSL 3.5, a PQ-enabled AWS load balancer or a CDN.",
                        "JDK 21 و25 لا يدعمان تبادل المفاتيح الهجين ML-KEM في SunJSSE. أنهِ TLS أمام JVM على مكوّن يدعمه: nginx مع OpenSSL 3.5، أو موازن حمل AWS بسياسة PQ، أو CDN.",
                        "JDK 21 und 25 haben keinen hybriden ML-KEM-Schlüsselaustausch in SunJSSE. Terminieren Sie TLS vor der JVM auf einer Komponente, die ihn unterstützt: nginx mit OpenSSL 3.5, ein PQ-fähiger AWS Load Balancer oder ein CDN."))]},
        },
    },
    "python": {
        "name": "Python (ssl)", "guide": "python-post-quantum-tls-x25519mlkem768",
        "variants": {
            "openssl35": {"label": _t("ssl.OPENSSL_VERSION 3.5+", "ssl.OPENSSL_VERSION بإصدار 3.5+", "ssl.OPENSSL_VERSION 3.5+"), "ok": True, "steps": [
                step(S_CHECK, "python3 -c \"import ssl; print(ssl.OPENSSL_VERSION)\"",
                     _t("What matters is the OpenSSL Python is linked to, not the Python version. Delete any set_ecdh_curve('prime256v1') call: it removes the hybrid group.",
                        "المهم هو OpenSSL الذي ترتبط به Python، لا إصدار Python. احذف أي استدعاء set_ecdh_curve('prime256v1'): فهو يحذف المجموعة الهجينة.",
                        "Entscheidend ist das OpenSSL, gegen das Python gelinkt ist, nicht die Python-Version. Löschen Sie Aufrufe wie set_ecdh_curve('prime256v1'): Sie entfernen die hybride Gruppe.")),
                step(S_CONFIG, "import ssl, socket\nctx = ssl.create_default_context()\n# optional, Python 3.15+: hybrid first, classical fallback\nctx.set_groups(\"X25519MLKEM768:X25519:prime256v1\")\nwith socket.create_connection((\"example.com\", 443)) as s:\n    with ctx.wrap_socket(s, server_hostname=\"example.com\") as t:\n        print(t.version(), t.group())   # TLSv1.3 X25519MLKEM768",
                     PROXY_NOTE)]},
            "openssl30": {"label": _t("ssl.OPENSSL_VERSION 3.0 to 3.4", "ssl.OPENSSL_VERSION من 3.0 إلى 3.4", "ssl.OPENSSL_VERSION 3.0 bis 3.4"), "ok": False, "steps": [
                step(S_CHECK, "python3 -c \"import ssl; print(ssl.OPENSSL_VERSION)\"",
                     _t("Linux distribution Pythons use the system OpenSSL (3.0 on Ubuntu 22.04 and 24.04), which cannot negotiate ML-KEM. The python.org installers for Windows and macOS and the Pythons that uv installs ship OpenSSL 3.5.",
                        "نسخ Python في توزيعات Linux تستخدم OpenSSL النظام (3.0 في Ubuntu 22.04 و24.04) الذي لا يدعم ML-KEM. مثبّتات python.org لـ Windows وmacOS ونسخ Python التي يثبّتها uv تأتي بـ OpenSSL 3.5.",
                        "Python aus Linux-Distributionen nutzt das System-OpenSSL (3.0 unter Ubuntu 22.04 und 24.04), das ML-KEM nicht aushandeln kann. Die python.org-Installer für Windows und macOS sowie die von uv installierten Pythons bringen OpenSSL 3.5 mit."))]},
        },
    },
    "aws-alb": {
        "name": "AWS ALB / NLB", "guide": "aws-alb-cloudfront-post-quantum-tls",
        "variants": {
            "cli": {"label": _t("AWS CLI, CloudFormation or CDK", "AWS CLI أو CloudFormation أو CDK", "AWS CLI, CloudFormation oder CDK"), "ok": True, "steps": [
                step(S_CHECK, None,
                     _t("Listeners created with the CLI, CloudFormation or the CDK still default to ELBSecurityPolicy-2016-08, which has no post-quantum key exchange. Set a PQ policy explicitly.",
                        "المستمعات المنشأة عبر CLI أو CloudFormation أو CDK ما زالت تستخدم افتراضياً ELBSecurityPolicy-2016-08 بلا تبادل مفاتيح ما بعد كمومي. اضبط سياسة PQ صراحةً.",
                        "Mit CLI, CloudFormation oder CDK erstellte Listener nutzen weiterhin standardmäßig ELBSecurityPolicy-2016-08 ohne Post-Quanten-Schlüsselaustausch. Setzen Sie explizit eine PQ-Policy.")),
                step(S_CONFIG, "aws elbv2 modify-listener \\\n  --listener-arn arn:aws:elasticloadbalancing:...:listener/app/my-alb/... \\\n  --ssl-policy ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09\n# FIPS: ELBSecurityPolicy-TLS13-1-2-Res-FIPS-PQ-2025-09"),
                step(S_VERIFY, VERIFY)]},
            "terraform": {"label": _t("Terraform", "Terraform", "Terraform"), "ok": True, "steps": [
                step(S_CONFIG, "resource \"aws_lb_listener\" \"https\" {\n  # ...\n  protocol   = \"HTTPS\"\n  ssl_policy = \"ELBSecurityPolicy-TLS13-1-2-Res-PQ-2025-09\"\n}"),
                step(S_VERIFY, VERIFY)]},
        },
    },
    "cloudfront": {
        "name": "AWS CloudFront", "guide": "aws-alb-cloudfront-post-quantum-tls",
        "variants": {
            "default": {"label": _t("Any distribution", "أي توزيع", "Jede Distribution"), "ok": True, "steps": [
                step(S_CONFIG, None,
                     _t("Nothing to configure: CloudFront supports X25519MLKEM768 for viewer connections. Hybrid key exchange works only over TLS 1.3.",
                        "لا شيء يُضبط: CloudFront يدعم X25519MLKEM768 لاتصالات الزوار. التبادل الهجين يعمل عبر TLS 1.3 فقط.",
                        "Nichts zu konfigurieren: CloudFront unterstützt X25519MLKEM768 für Viewer-Verbindungen. Hybrider Schlüsselaustausch funktioniert nur mit TLS 1.3.")),
                step(S_VERIFY, VERIFY, ORIGIN_NOTE)]},
        },
    },
    "cloudflare": {
        "name": "Cloudflare", "guide": "post-quantum-tls-apache-caddy-haproxy-cloudflare",
        "variants": {
            "default": {"label": _t("Proxied domain (orange cloud)", "نطاق يمر عبر Cloudflare (السحابة البرتقالية)", "Proxied Domain (orange Wolke)"), "ok": True, "steps": [
                step(S_CONFIG, None,
                     _t("Cloudflare negotiates X25519MLKEM768 with browsers on all plans by default once the domain is proxied. It is the fastest fix for an old server you cannot upgrade.",
                        "Cloudflare يتفاوض على X25519MLKEM768 مع المتصفحات في كل الباقات افتراضياً حين يمر النطاق عبره. وهو أسرع حل لخادم قديم لا تستطيع ترقيته.",
                        "Cloudflare handelt X25519MLKEM768 mit Browsern in allen Tarifen standardmäßig aus, sobald die Domain proxied ist. Der schnellste Weg für einen alten Server, den Sie nicht aktualisieren können.")),
                step(S_VERIFY, VERIFY, ORIGIN_NOTE)]},
        },
    },
}

STEP_TITLES = {
    S_CHECK: _t("1. Check your version", "١. تحقّق من الإصدار", "1. Version prüfen"),
    S_CONFIG: _t("2. Configure", "٢. الإعدادات", "2. Konfigurieren"),
    S_RELOAD: _t("3. Test and reload", "٣. اختبر وأعد التحميل", "3. Testen und neu laden"),
    S_VERIFY: _t("4. Verify", "٤. تحقّق من النتيجة", "4. Prüfen"),
}


def variant(server, key):
    s = SERVERS[server]
    if key not in s["variants"]:
        key = next(iter(s["variants"]))
    return key, s["variants"][key]


_TOKEN = None


def rich(text):
    """يلفّ الرموز التقنية (مسارات، أسماء إعدادات) في <code dir=ltr> حتى لا يقلبها النص العربي. النص مُهرَّب أولاً."""
    global _TOKEN
    import re
    from markupsafe import Markup, escape
    if _TOKEN is None:
        _TOKEN = re.compile(r"[\w./:'()=,-]*[/_=][\w./:'()=,-]*[\w)/]")
    return Markup(_TOKEN.sub(lambda m: f'<code dir="ltr">{m.group(0)}</code>', str(escape(text))))
