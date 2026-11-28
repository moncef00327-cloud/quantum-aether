"""High-intent factual comparison landing pages (/vs-censys and /vs-securitytrails) in en/de/ar.

Positions Quantum Aether honestly as the specialized Post-Quantum TLS (X25519MLKEM768),
Ed25519 signed receipt (JWKS), remote MCP/A2A/x402, and DACH NIS2/BSI TR-02102-2 layer
that complements internet-wide scanners like Censys and SecurityTrails.
"""
from __future__ import annotations

from flask import render_template, url_for

ENDPOINTS = ("site.vs_censys_page", "site.vs_securitytrails_page")

PAGES = {
    "censys": {
        "slug": "censys",
        "competitor": "Censys",
        "en": {
            "title": "Quantum Aether vs Censys: PQC TLS, Ed25519 & MCP",
            "meta": "Censys maps internet-wide attack surfaces. Quantum Aether adds browser-order X25519MLKEM768 downgrade detection, offline-verifiable Ed25519 TLS receipts, remote MCP/x402, and German NIS2/BSI MSP reporting.",
            "kicker": "Comparison · Post-Quantum TLS & Agent Security Layer",
            "h1": "Censys maps the internet. Quantum Aether verifies Post-Quantum TLS & AI-agent trust.",
            "lead": "You do not need to replace Censys to close the post-quantum gap. Censys excels at internet-wide IP/certificate discovery; Quantum Aether adds the specialized layer for live browser-order X25519MLKEM768 negotiation, hidden server-preference downgrade detection, offline-verifiable Ed25519 receipts, remote MCP/x402, and DACH NIS2/BSI TR-02102-2 compliance.",
            "best_for_us": "Teams & MSPs needing live X25519MLKEM768 proof, Ed25519 signed receipts for NIS2/DORA audits, remote MCP/x402 integration, and predictable European pricing (29 €/mo Starter, 99 €/mo Business, 290 € MSP Pilot).",
            "best_for_them": "Enterprise SOC teams running broad internet-wide IPv4/port/banner discovery and threat hunting across exposed infrastructure.",
            "rows": [
                ("Live browser-order X25519MLKEM768 handshake check", "Yes — detects silent PQ-supported-but-classical-preferred downgrades", "General TLS/certificate telemetry; focused on broad asset inventory"),
                ("Offline-verifiable Ed25519 JWS scan receipts (JWKS)", "Yes — every scan issues a signed receipt (/.well-known/jwks.json)", "Not built around per-scan Ed25519 JWS compliance receipts"),
                ("Remote MCP Server, A2A Card & Base USDC x402 API", "Yes — free remote MCP (100/100 mcptry) + $0.10 batch-scan / $0.25 CBOM", "Traditional enterprise API key model"),
                ("German NIS2 / BSI TR-02102-2 MSP Pilot PDF", "Yes — 290 € one-time pilot (up to 50 hosts, German Ampel PDF)", "Enterprise contracts in English (typically higher annual minimums)"),
                ("Transparent SMB & MSP pricing", "Free scan · 29 €/mo (10 hosts) · 99 €/mo (100 hosts) · 290 € Pilot", "Enterprise sales / higher tier pricing"),
            ],
            "faq": [
                ("Should we cancel Censys to use Quantum Aether?", "No. Most security teams keep Censys for broad attack-surface discovery and add Quantum Aether specifically for continuous post-quantum TLS verification, signed NIS2/DORA audit receipts, and AI-agent MCP/x402 workflows."),
                ("Why can a host look PQ-ready in standard scanners yet fail real browsers?", "Some TLS 1.3 servers support X25519MLKEM768 when offered alone, but enforce a server preference order that ranks classical x25519 first—silently downgrading Chrome, Firefox, and Safari. Quantum Aether explicitly tests both browser-order and PQ-only handshakes."),
            ],
        },
        "de": {
            "title": "Quantum Aether vs. Censys: PQC-TLS & NIS2",
            "meta": "Censys kartiert Angriffsflächen im Internet. Quantum Aether ergänzt gezielt Post-Quanten-TLS (X25519MLKEM768), signierte Ed25519-Prüfbelege, Remote-MCP und deutsche NIS2-/BSI-Berichte ab 29 €/Monat.",
            "kicker": "Vergleich · Post-Quanten-TLS & DACH-Compliance",
            "h1": "Censys kartiert das Internet. Quantum Aether beweist Post-Quanten-TLS für NIS2 & KI-Agenten.",
            "lead": "Sie müssen Censys nicht ablösen. Censys ist stark bei globaler Asset- und Port-Suche; Quantum Aether liefert genau die spezialisierte Schicht für echte Browser-Aushandlung von X25519MLKEM768, versteckte Server-Präferenz-Downgrades, offline prüfbare Ed25519-Belege, Remote-MCP und deutsche IT-Dienstleister-Berichte (BSI TR-02102-2 / NIS2).",
            "best_for_us": "IT-Dienstleister (MSPs) und Sicherheitsteams im DACH-Raum, die prüffähige Ed25519-Nachweise, deutsche Ampel-PDFs (290 € Pilot für 50 Hosts) und tägliches PQC-Monitoring ab 29 €/Monat brauchen.",
            "best_for_them": "Große SOC-Teams mit Fokus auf globale IPv4-/Port-Suche und Threat-Hunting.",
            "rows": [
                ("Live-Prüfung auf X25519MLKEM768 in Browser-Reihenfolge", "Ja — erkennt auch versteckte Präferenz-Downgrades auf x25519", "Fokus auf breite globale Asset- und Zertifikatssuche"),
                ("Offline prüfbare Ed25519-JWS-Prüfbelege (JWKS)", "Ja — jeder Scan erzeugt einen signierten Beleg (/.well-known/jwks.json)", "Kein Fokus auf signierte Einzel-Prüfbelege pro Scan"),
                ("Remote-MCP-Server, A2A-Card & Base-USDC x402", "Ja — kostenloser Remote-MCP + $0.10 Batch-Scan / $0.25 CBOM", "Klassisches Enterprise-API-Modell"),
                ("Deutscher NIS2- / BSI-TR-02102-2-MSP-Pilotbericht", "Ja — 290 € einmalig (bis 50 Hostnamen, deutsches Ampel-PDF)", "Englischsprachige Enterprise-Verträge"),
                ("Transparente KMU- & MSP-Preise", "Gratis-Check · 29 €/Monat (10 Hosts) · 99 €/Monat (100 Hosts)", "Enterprise-Vertrieb / höhere Einstiegspreise"),
            ],
            "faq": [
                ("Müssen wir Censys kündigen, um Quantum Aether zu nutzen?", "Nein. Quantum Aether lässt sich direkt ergänzend einsetzen — speziell für Post-Quanten-TLS-Nachweise, signierte Ed25519-Prüfbelege für NIS2/DORA-Audits und deutsche Kundenberichte."),
                ("Warum fallen manche Server trotz PQ-Unterstützung auf klassisches TLS zurück?", "Wenn ein TLS-1.3-Server klassisches x25519 in der Server-Reihenfolge vor X25519MLKEM768 priorisiert, handeln Chrome, Firefox und Safari klassisch aus. Quantum Aether prüft beide Modi explizit."),
            ],
        },
        "ar": {
            "title": "Quantum Aether مقابل Censys: PQC TLS وMCP",
            "meta": "يركّز Censys على مسح أصول الإنترنت العامة، بينما يضيف Quantum Aether فحص X25519MLKEM768 بترتيب المتصفح، إيصالات Ed25519 الموقّعة، خادم MCP، وتقارير NIS2 بأسعار تبدأ من 29 € شهرياً.",
            "kicker": "مقارنة تقنية · طبقة التشفير المقاوم للكم والوكلاء",
            "h1": "Censys لمسح الإنترنت التقليدي. Quantum Aether لإثبات Post-Quantum TLS وثقة الوكلاء.",
            "lead": "لا تحتاج إلى استبدال Censys؛ يبرع Censys في مسح عناوين IP والمنافذ على مستوى الإنترنت، بينما يضيف Quantum Aether الطبقة المتخصصة في فحص X25519MLKEM768 بترتيب المتصفح الحقيقي، كشف تراجع التفضيل الخفي، إيصالات Ed25519 القابلة للتحقق دون إنترنت، خادم MCP وx402، وتقارير NIS2 للشركات ومزوّدي IT.",
            "best_for_us": "شركات الأمن ومزوّدو خدمات IT (MSPs) وفرق الوكلاء الباحثة عن إثبات X25519MLKEM768 وإيصالات Ed25519 الموقّعة وتكامل MCP بأسعار واضحة (29 €/شهر Starter · 99 €/شهر Business · 290 € بايلوت MSP).",
            "best_for_them": "فرق SOC الكبرى التي تبحث عن مسح شامل للمنافذ والشهادات على نطاق الإنترنت بالكامل.",
            "rows": [
                ("فحص X25519MLKEM768 بترتيب المتصفح الحقيقي", "نعم — يكشف التراجع الصامت حين يفضّل الخادم x25519 الكلاسيكي", "يركّز على جرد الأصول والشهادات العامة"),
                ("إيصالات Ed25519 JWS قابلة للتحقق دون إنترنت (JWKS)", "نعم — كل فحص يصدر إيصالاً موقّعاً (/.well-known/jwks.json)", "غير مبني على إيصالات امتثال موقّعة لكل فحص"),
                ("خادم MCP بعيد وبطاقة A2A ومدفوعات x402", "نعم — خادم MCP مجاني (100/100 على mcptry) + $0.10 فحص جماعي", "نموذج API مؤسسي تقليدي"),
                ("تقرير MSP Pilot بالألمانية/الإنجليزية لـ NIS2", "نعم — 290 € لمرة واحدة (حتى 50 نطاقاً + PDF رسمي)", "عقود مؤسسية سنوية مرتفعة"),
                ("أسعار شفافة للشركات الصغيرة والمتوسطة", "فحص مجاني · 29 €/شهر · 99 €/شهر · 290 € بايلوت", "تسعير مؤسسي مرتفع"),
            ],
            "faq": [
                ("هل نحتاج لإلغاء Censys لاستخدام Quantum Aether؟", "لا. يمكنك استخدام Quantum Aether كطبقة مكمّلة فوق أدواتك الحالية لإثبات جاهزية ما بعد الكم وإصدار إيصالات Ed25519 الموقّعة وتأمين خوادم MCP."),
                ("لماذا تبدو بعض الخوادم جاهزة في ماسحات تقليدية لكنها تفشل مع المتصفحات؟", "لأن بعض خوادم TLS 1.3 تدعم X25519MLKEM768 لكنها ترتّب x25519 الكلاسيكي أولاً، فتسقط متصفحات Chrome وFirefox وSafari تلقائياً إلى التشفير الكلاسيكي. نكشف هذا الخطأ بدقة."),
            ],
        },
    },
    "securitytrails": {
        "slug": "securitytrails",
        "competitor": "SecurityTrails",
        "en": {
            "title": "Quantum Aether vs SecurityTrails: Live PQC TLS & MCP",
            "meta": "Compare Quantum Aether and SecurityTrails: move beyond historical DNS records with live X25519MLKEM768 handshake monitoring, signed Ed25519 receipts, remote MCP, and European NIS2 compliance starting at 29 €/mo.",
            "kicker": "Comparison · Live PQ-TLS Monitoring vs Historical DNS",
            "h1": "SecurityTrails tracks DNS history. Quantum Aether proves live Post-Quantum TLS & agent security.",
            "lead": "SecurityTrails is built for historical DNS and passive domain reconnaissance. Quantum Aether focuses on what compliance auditors and AI agents need next: live TLS 1.3 X25519MLKEM768 verification, continuous regression alerts, offline-verifiable Ed25519 receipts, CycloneDX 1.6 CBOM exports, and native MCP/x402 access.",
            "best_for_us": "DevSecOps teams, AI agent builders, and European MSPs who need live PQ-TLS compliance proof, regression monitoring from 29 €/mo, and native MCP/x402 integration.",
            "best_for_them": "Investigators and threat-intel analysts researching historical DNS/WHOIS ownership timelines.",
            "rows": [
                ("Live Post-Quantum TLS (X25519MLKEM768) verification", "Yes — live handshake + server-preference downgrade detection", "Primarily passive DNS / WHOIS / domain history"),
                ("Signed Ed25519 JWS compliance receipts + CycloneDX 1.6 CBOM", "Yes — verifiable offline via /.well-known/jwks.json", "Not provided as signed PQC cryptographic receipts"),
                ("Native Remote MCP Server & Base USDC x402 endpoints", "Yes — zero API key for free MCP + pay-per-call x402", "Conventional REST API key plans"),
                ("Daily PQ-TLS regression monitoring & cert expiry alerts", "Yes — 14-day free trial, then 29 €/mo (10 hosts) or 99 €/mo (100 hosts)", "Focused on DNS/asset inventory changes"),
                ("DACH MSP Partner Pilot (German Ampel PDF, up to 50 hosts)", "Yes — 290 € one-time pilot with optional partner logo", "Not offered as localized German NIS2/BSI MSP PDF"),
            ],
            "faq": [
                ("Can Quantum Aether replace SecurityTrails for DNS history?", "No — if you need multi-year historical DNS A/MX/WHOIS archives, keep SecurityTrails. Use Quantum Aether for live post-quantum TLS readiness, daily regression monitoring, signed Ed25519 receipts, and MCP/x402 automation."),
                ("How fast can we test our domains?", "Run a free single-domain check right on this page in seconds (no signup), or start a 14-day free monitoring trial for up to 10 hostnames with no credit card."),
            ],
        },
        "de": {
            "title": "Quantum Aether vs. SecurityTrails: PQC-TLS & MCP",
            "meta": "Vergleich Quantum Aether vs. SecurityTrails: Live-Prüfung auf X25519MLKEM768, signierte Ed25519-Prüfbelege, CycloneDX-1.6-CBOM, Remote-MCP und deutsches NIS2-Monitoring ab 29 €/Monat.",
            "kicker": "Vergleich · Live-PQ-TLS-Monitoring vs. DNS-Historie",
            "h1": "SecurityTrails zeigt DNS-Historie. Quantum Aether beweist Live-Post-Quanten-TLS & NIS2-Readiness.",
            "lead": "SecurityTrails ist auf historische DNS- und WHOIS-Daten spezialisiert. Quantum Aether schließt die operative Lücke für 2026–2030: echte X25519MLKEM768-Handshakes, tägliches Regressions-Monitoring, offline prüfbare Ed25519-Belege, CycloneDX-1.6-CBOM und deutsche MSP-Pilotberichte nach BSI TR-02102-2 / NIS2.",
            "best_for_us": "Teams und IT-Dienstleister im DACH-Raum mit Bedarf an täglicher PQC-Überwachung ab 29 €/Monat, signierten Audit-Belegen und Remote-MCP.",
            "best_for_them": "Analysten für historische DNS- und WHOIS-Recherchen.",
            "rows": [
                ("Live-Post-Quanten-TLS-Prüfung (X25519MLKEM768)", "Ja — inkl. Erkennung von Server-Präferenz-Downgrades", "Fokus auf passive DNS-/WHOIS-Historie"),
                ("Signierte Ed25519-Prüfbelege & CycloneDX 1.6 CBOM", "Ja — offline verifizierbar über /.well-known/jwks.json", "Keine signierten PQC-TLS-Auditbelege"),
                ("Remote-MCP-Server & Base-USDC x402 API", "Ja — kostenloser Remote-MCP ohne API-Key + x402", "Klassische REST-API-Tarife"),
                ("Tägliches PQC-Regressions- & Zertifikats-Monitoring", "Ja — 14 Tage gratis, danach 29 €/Monat (10 Hosts) / 99 € (100 Hosts)", "Fokus auf DNS-Änderungen"),
                ("DACH MSP-Pilot (deutsches Ampel-PDF, bis 50 Hosts)", "Ja — 290 € einmalig, optional mit Partner-Logo", "Kein deutschsprachiger NIS2-/BSI-MSP-Bericht"),
            ],
            "faq": [
                ("Ersetzt Quantum Aether SecurityTrails für historische DNS-Daten?", "Nein — für mehrjährige DNS-/WHOIS-Archive bleibt SecurityTrails ideal. Quantum Aether ergänzt die Live-Messung von Post-Quanten-TLS, signierten Ed25519-Nachweisen und NIS2-Berichten."),
                ("Wie schnell können wir unsere Domains testen?", "Sofort kostenlos oben auf dieser Seite ohne Anmeldung — oder 14 Tage kostenloses tägliches Monitoring für bis zu 10 Hosts ohne Kreditkarte."),
            ],
        },
        "ar": {
            "title": "Quantum Aether مقابل SecurityTrails: PQC TLS",
            "meta": "قارن بين Quantum Aether وSecurityTrails: فحص حيّ لـ X25519MLKEM768، إيصالات Ed25519 الموقّعة، تقارير CycloneDX 1.6 CBOM، وخادم MCP ومراقبة يومية تبدأ من 29 €/شهر.",
            "kicker": "مقارنة تقنية · مراقبة PQ-TLS الحية مقابل سجل DNS التاريخي",
            "h1": "SecurityTrails لسجل DNS التاريخي. Quantum Aether لإثبات Post-Quantum TLS الحي والوكلاء.",
            "lead": "يتميّز SecurityTrails بأرشيف DNS التاريخي وبيانات WHOIS. أما Quantum Aether فيركّز على ما يحتاجه المدقّقون ووكلاء الذكاء الاصطناعي اليوم: مصافحة TLS 1.3 حقيقية لـ X25519MLKEM768، مراقبة التراجع اليومية، إيصالات Ed25519 الموقّعة، تقارير CycloneDX 1.6 CBOM، وتكامل MCP/x402.",
            "best_for_us": "فرق الأمن ومطوّرو الوكلاء وشركات MSP الباحثة عن مراقبة PQC يومية بدءاً من 29 €/شهر وإيصالات موقّعة وتقارير تدقيق جاهزة.",
            "best_for_them": "الباحثون الذين يحتاجون أرشيف سجلات DNS وWHOIS لعدة سنوات.",
            "rows": [
                ("فحص X25519MLKEM768 الحيّ وكشف تراجع التفضيل", "نعم — قياس مصافحة TLS حقيقية بترتيب المتصفح", "يركّز أساساً على أرشيف DNS وWHOIS"),
                ("إيصالات Ed25519 الموقّعة + CycloneDX 1.6 CBOM", "نعم — قابلة للتحقق دون إنترنت عبر /.well-known/jwks.json", "غير مخصّص لإيصالات امتثال PQC موقّعة"),
                ("خادم MCP بعيد ومدفوعات Base USDC x402", "نعم — خادم MCP مجاني دون مفتاح API + x402", "خطط REST API تقليدية"),
                ("مراقبة يومية لتراجع التشفير وانتهاء الشهادات", "نعم — تجربة 14 يوماً مجاناً ثم 29 €/شهر (10 نطاقات) أو 99 € (100)", "يركّز على تغيرات سجلات DNS"),
                ("برنامج MSP Pilot (تقرير PDF لـ 50 نطاقاً)", "نعم — 290 € لمرة واحدة مع شعار الشريك اختيارياً", "غير متوفر كباقة تقارير MSP لـ NIS2"),
            ],
            "faq": [
                ("هل يستبدل Quantum Aether أرشيف DNS في SecurityTrails؟", "لا؛ إذا كنت تحتاج أرشيف DNS التاريخي فاحتفظ بـ SecurityTrails، وأضف Quantum Aether للفحص الحي لـ Post-Quantum TLS والمراقبة اليومية وإيصالات Ed25519 وتكامل MCP."),
                ("كم يستغرق اختبار نطاقنا الآن؟", "ثوانٍ معدودة مجاناً من صندوق الفحص في هذه الصفحة بدون تسجيل، أو تجربة مراقبة يومية مجانية لمدة 14 يوماً بدون بطاقة ائتمان."),
            ],
        },
    },
}

UI = {
    "en": {
        "col_cap": "Capability",
        "col_us": "Quantum Aether",
        "best_us": "Best fit for Quantum Aether",
        "best_them": "Best fit for",
        "faq_title": "Frequently asked questions",
        "cta_trial": "Start 14-day free monitoring (29 €/mo after)",
        "cta_msp": "MSP Partner Pilot (50 hosts · 290 €) ↗",
        "cta_mcp": "Remote MCP & x402 setup ↗",
        "other_vs": "Also compare:",
    },
    "de": {
        "col_cap": "Funktion",
        "col_us": "Quantum Aether",
        "best_us": "Ideal für Quantum Aether",
        "best_them": "Ideal für",
        "faq_title": "Häufige Fragen",
        "cta_trial": "14 Tage kostenlos testen (ab 29 €/Monat)",
        "cta_msp": "MSP-Partner-Pilot (50 Hosts · 290 €) ↗",
        "cta_mcp": "Remote-MCP & x402 einrichten ↗",
        "other_vs": "Weiterer Vergleich:",
    },
    "ar": {
        "col_cap": "الميزة",
        "col_us": "Quantum Aether",
        "best_us": "الأنسب مع Quantum Aether",
        "best_them": "الأنسب مع",
        "faq_title": "أسئلة شائعة",
        "cta_trial": "ابدأ مراقبة مجانية 14 يوماً (ثم 29 €/شهر)",
        "cta_msp": "برنامج MSP Pilot (50 نطاقاً · 290 €) ↗",
        "cta_mcp": "إعداد خادم MCP وx402 ↗",
        "other_vs": "مقارنة أخرى:",
    },
}


def register(bp, deps):
    """deps: lang, base, de_pages, de_endpoints."""
    for ep in ENDPOINTS:
        deps["de_pages"].add(ep)
        deps["de_endpoints"].add(ep)

    def _render(key: str, ep: str):
        lang = deps["lang"]()
        page = PAGES[key]
        d = page.get(lang, page["en"])
        ui = UI.get(lang, UI["en"])
        other_key = "securitytrails" if key == "censys" else "censys"
        other_ep = "site.vs_securitytrails_page" if key == "censys" else "site.vs_censys_page"
        return render_template(
            "vs_competitor.html",
            slug=page["slug"],
            competitor=page["competitor"],
            other_competitor=PAGES[other_key]["competitor"],
            other_url=url_for(other_ep, lang=lang),
            d=d,
            ui=ui,
            lang_code=lang,
            page_url=deps["base"]() + url_for(ep),
        )

    @bp.get("/vs-censys")
    def vs_censys_page():
        return _render("censys", "site.vs_censys_page")

    @bp.get("/vs-securitytrails")
    def vs_securitytrails_page():
        return _render("securitytrails", "site.vs_securitytrails_page")
