"""Search-result length limits for <title> and meta description.

Google cuts titles at roughly 600 px (about 60 characters) and descriptions at
about 155-160 characters. Long titles first lose the trailing brand segment; a
few pages whose title is long even without the brand get a shorter SERP title
here. The visible <h1> and JSON-LD names are not changed.
"""
import re

TITLE_MAX = 60
DESCRIPTION_MAX = 155
BRANDS = ("Quantum Aether", "الأثير الكمومي")

# (path, lang) -> title used only in <title>/og:title when the page title is too long.
TITLE_OVERRIDES = {
    ("/deadlines", "ar"): "مواعيد التشفير ما بعد الكمومي: NIST وCNSA 2.0 وأوروبا",
    ("/deadlines", "de"): "Post-Quanten-Fristen: NIST, CNSA 2.0, EU und UK",
    ("/index", "en"): "PQ-TLS Index: banks, telecoms and governments",
    ("/index", "ar"): "مؤشر PQ-TLS: البنوك والاتصالات والجهات الحكومية",
    ("/index", "de"): "PQ-TLS-Index: Banken, Telcos und Behörden",
    ("/exposure", "en"): "Quantum Exposure Registry · Quantum Aether",
    ("/exposure", "ar"): "سجل التعرّض الكمّي · الأثير الكمومي",
    ("/guides/nis2-dora-post-quantum-cryptography", "en"): "NIS2 and DORA: cryptography and post-quantum TLS",
    ("/guides/nis2-dora-post-quantum-cryptography", "de"): "NIS2 und DORA: Kryptografie und Post-Quanten-TLS",
    ("/guides/python-post-quantum-tls-x25519mlkem768", "en"): "Post-quantum TLS in Python: ssl, requests, httpx",
    ("/guides/python-post-quantum-tls-x25519mlkem768", "ar"): "TLS المقاوم للكم في Python: ssl وrequests وhttpx",
    ("/guides/nodejs-post-quantum-tls-x25519mlkem768", "en"): "Post-quantum TLS in Node.js (X25519MLKEM768)",
    ("/guides/nodejs-post-quantum-tls-x25519mlkem768", "ar"): "TLS المقاوم للكم في Node.js ‏(X25519MLKEM768)",
    ("/guides/go-post-quantum-tls-x25519mlkem768", "en"): "Post-quantum TLS in Go: X25519MLKEM768 and go.mod",
    ("/guides/aws-alb-cloudfront-post-quantum-tls", "en"): "Post-quantum TLS on AWS: ALB, NLB and CloudFront",
    ("/guides/post-quantum-vendor-security-questionnaire", "en"): "Post-quantum answers for security questionnaires",
    ("/guides/post-quantum-vendor-security-questionnaire", "de"): "Post-Quanten-Fragen in Sicherheitsfragebögen",
    ("/guides/check-website-post-quantum-tls", "en"): "How to check a website for post-quantum TLS",
    ("/adoption/dach-hosting", "de"): "Post-Quanten-TLS bei Hostern in DACH",
    ("/adoption/dach-hosting", "ar"): "التشفير المقاوم للكم لدى الاستضافة في DACH",
    ("/adoption/arab-africa-hosting", "en"): "Post-quantum TLS at Arab and African hosts",
    ("/adoption/arab-africa-hosting", "ar"): "TLS ما بعد الكمّي لدى الاستضافة العربية والأفريقية",
    ("/adoption/hosting", "ar"): "أي شركات الاستضافة وCDN تدعم TLS المقاوم للكم؟",
    ("/partners", "en"): "Partner programme: 30% on post-quantum TLS monitoring",
    ("/partners", "de"): "Partnerprogramm: 30 % für Post-Quanten-TLS-Empfehlungen",
    ("/study/top-1000-post-quantum-tls", "en"): "Are the top 1,000 websites ready for post-quantum TLS?",
    ("/study/top-1000-post-quantum-tls", "de"): "Top-1.000-Websites: bereit für Post-Quanten-TLS?",
    ("/prooflab", "en"): "ProofLab: test a post-quantum TLS change first",
}

_SPACE = re.compile(r"\s+")


def _clean(text):
    return _SPACE.sub(" ", str(text or "")).strip()


def title(text, path="", lang="en", limit=TITLE_MAX):
    text = _clean(text)
    if len(text) <= limit:
        return text
    override = TITLE_OVERRIDES.get((path, lang))
    if override:
        return override
    # Arabic titles carry "الأثير الكمومي (Quantum Aether)" for brand searches (commit 072fb47); keep the Arabic name.
    shorter = text.replace(" (Quantum Aether)", "")
    if shorter != text and len(shorter) <= limit:
        return shorter
    head, sep, tail = text.rpartition(" · ")
    if sep and any(brand in tail for brand in BRANDS):
        return head
    return text


def description(text, limit=DESCRIPTION_MAX):
    text = _clean(text)
    if len(text) <= limit:
        return text
    cut = text[:limit - 1]
    space = cut.rfind(" ")
    if space > limit // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:·—-–") + "…"
