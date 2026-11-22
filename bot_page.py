"""/bot: the page QuantumAetherBot links to from its User-Agent, for admins who see it in their logs."""

UA = "Mozilla/5.0 (compatible; QuantumAetherBot/1.0; +https://ather-quantum.com/bot)"
SOURCE_IP = "95.179.195.150"

COPY = {
    "en": {
        "title": "QuantumAetherBot visited your site",
        "meta": "What QuantumAetherBot checked on your site (security.txt and one TLS handshake), your post-quantum TLS result, and how to opt out.",
        "lead": "You found QuantumAetherBot in your logs. It is the measurement bot of Quantum Aether, a public tracker of "
                "post-quantum TLS adoption. It did two small things and nothing else.",
        "did_title": "What it did",
        "did": ["Read /.well-known/security.txt (RFC 9116), to find where your security team wants to be contacted.",
                "Made one TLS handshake to see which key exchange your server negotiates (X25519MLKEM768 or classical)."],
        "not_title": "What it did not do",
        "not": "No crawling, no forms, no logins, no vulnerability probing, no load. At most a few requests per domain per month.",
        "result_title": "See your result",
        "result": "Enter your domain for the free result: grade, negotiated key exchange and how to enable post-quantum TLS.",
        "optout_title": "Opt out",
        "optout": "To exclude your domain from all our measurements and emails, publish the DNS record on the opt-out page, "
                  "or write to",
        "optout_link": "Opt-out page",
        "source": "Requests come from",
    },
    "ar": {
        "title": "زار QuantumAetherBot موقعك",
        "meta": "ما الذي فحصه QuantumAetherBot في موقعك (ملف security.txt ومصافحة TLS واحدة)، ونتيجة موقعك، وطريقة الاستبعاد.",
        "lead": "وجدت QuantumAetherBot في سجلات موقعك. هو روبوت القياس لدى Quantum Aether، وهو متتبع عام لانتشار TLS "
                "المقاوم للحوسبة الكمومية. فعل شيئين صغيرين فقط.",
        "did_title": "ما الذي فعله",
        "did": ["قرأ الملف ‎/.well-known/security.txt (المعيار RFC 9116) ليعرف أين يريد فريق الأمن عندكم أن يُراسَل.",
                "أجرى مصافحة TLS واحدة ليعرف تبادل المفاتيح الذي يتفاوض عليه خادمكم (X25519MLKEM768 أو التقليدي)."],
        "not_title": "ما الذي لم يفعله",
        "not": "لا زحف على الصفحات، ولا نماذج، ولا تسجيل دخول، ولا فحص ثغرات، ولا أي حمل على الخادم. بضعة طلبات على الأكثر لكل نطاق في الشهر.",
        "result_title": "اعرف نتيجة موقعك",
        "result": "اكتب نطاقك لترى النتيجة مجانًا: الدرجة، وتبادل المفاتيح، وطريقة تفعيل TLS المقاوم للكم.",
        "optout_title": "الاستبعاد",
        "optout": "لاستبعاد نطاقك من كل قياساتنا ورسائلنا، انشر سجل DNS الموضح في صفحة الاستبعاد، أو راسلنا على",
        "optout_link": "صفحة الاستبعاد",
        "source": "تصدر الطلبات من",
    },
}
