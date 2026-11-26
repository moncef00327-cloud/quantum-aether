"""Reverse MCP Security Index: /mcp-index (en/ar/de) and /api/v1/mcp-index (open JSON).

Publishes live post-quantum TLS readiness measurements (including server-preference PQ downgrades)
for public remote HTTPS MCP servers listed in the Official MCP Registry.
"""
from __future__ import annotations

import json
import os

from flask import Response, render_template, url_for

ENDPOINT = "site.mcp_index_page"

T = {
    "en": {
        "title": "MCP Server Post-Quantum TLS Index — Live Remote MCP Leaderboard",
        "meta": "Live post-quantum TLS readiness index of {measured} remote HTTPS MCP servers from the Official MCP Registry: {pq_pct}% negotiate X25519MLKEM768.",
        "kicker": "Reverse MCP Security Radar · Official MCP Registry",
        "h1": "Which remote MCP servers protect AI agent traffic with post-quantum TLS?",
        "lead": "AI agents increasingly send sensitive prompts, tokens, and enterprise records to remote MCP endpoints. We measure public remote HTTPS MCP servers from the Official MCP Registry with one browser-grade TLS 1.3 handshake (offering X25519MLKEM768) and flag both classical endpoints and hidden server-preference downgrades.",
        "kpi_measured": "Remote MCP hosts measured",
        "kpi_pq": "Post-quantum hybrid (X25519MLKEM768)",
        "kpi_classical": "Classical TLS 1.3 only",
        "kpi_misconfig": "Supports PQ, prefers classical",
        "filter_all": "All",
        "filter_pq": "Post-quantum (A)",
        "filter_misconfig": "Preference bug",
        "filter_classical": "Classical (B)",
        "filter_tls12": "TLS 1.2 (C)",
        "search_placeholder": "Filter by MCP server or domain...",
        "col_server": "MCP Server",
        "col_host": "Endpoint Host",
        "col_status": "PQ-TLS Status",
        "col_tls": "TLS / Group",
        "col_action": "Live Proof",
        "st_pq_hybrid": "Post-quantum",
        "st_pq_not_preferred": "PQ supported, classical preferred",
        "st_classical": "Classical only",
        "st_tls12": "TLS 1.2 only",
        "st_unreachable": "Unreachable",
        "btn_scan": "Re-scan ↗",
        "btn_verify": "Badge",
        "updated": "Last measured {ts} UTC · {entries} Official MCP Registry entries inspected · one TLS probe per unique public host.",
        "json_link": "Open JSON API",
        "cta_title": "Run an MCP server or manage customer endpoints?",
        "cta_body": "Check any host live with an offline-verifiable Ed25519 signed TLS receipt, connect our remote MCP server (100/100 on mcptry), or start a free 14-day regression monitoring trial.",
        "cta_scan": "Scan your host",
        "cta_agents": "Connect Quantum Aether MCP",
        "cta_monitor": "14-day free monitoring",
        "empty": "Index snapshot is being generated. Check back in a moment.",
    },
    "ar": {
        "title": "مؤشر أمان خوادم MCP لما بعد الكم — ترتيب حي لخوادم MCP البعيدة",
        "meta": "مؤشر حي لجاهزية التشفير المقاوم للكم لـ {measured} خادم MCP بعيد من السجل الرسمي: {pq_pct}% منها تفاوض X25519MLKEM768.",
        "kicker": "رادار أمان خوادم MCP العكسي · السجل الرسمي للـ MCP",
        "h1": "أيّ خوادم MCP البعيدة تحمي حركة الوكلاء بتشفير TLS مقاوم للكم؟",
        "lead": "ترسل وكلاء الذكاء الاصطناعي بيانات ومفاتيح وسجلات مؤسسية عبر خوادم MCP البعيدة. نفحص النطاقات العامة لخوادم MCP من السجل الرسمي بمصافحة TLS 1.3 معيارية (تعرض X25519MLKEM768) ونكشف الخوادم التقليدية وأخطاء التفضيل الخفية التي تُسقط المتصفحات والوكلاء إلى التشفير الكلاسيكي.",
        "kpi_measured": "خوادم MCP بعيدة تم قياسها",
        "kpi_pq": "هجين مقاوم للكم (X25519MLKEM768)",
        "kpi_classical": "TLS 1.3 تقليدي فقط",
        "kpi_misconfig": "يدعم PQ لكنه يفضّل التقليدي",
        "filter_all": "الكل",
        "filter_pq": "مقاوم للكم (A)",
        "filter_misconfig": "خطأ تفضيل",
        "filter_classical": "تقليدي (B)",
        "filter_tls12": "TLS 1.2 (C)",
        "search_placeholder": "ابحث باسم خادم MCP أو النطاق...",
        "col_server": "خادم MCP",
        "col_host": "نطاق نقطة الاتصال",
        "col_status": "حالة PQ-TLS",
        "col_tls": "الإصدار / المجموعة",
        "col_action": "دليل حي",
        "st_pq_hybrid": "مقاوم للكم",
        "st_pq_not_preferred": "يدعم PQ ويفضّل التقليدي",
        "st_classical": "تقليدي فقط",
        "st_tls12": "TLS 1.2 فقط",
        "st_unreachable": "تعذّر القياس",
        "btn_scan": "أعد الفحص ↗",
        "btn_verify": "الشارة",
        "updated": "آخر قياس {ts} بتوقيت UTC · فُحص {entries} إدخالاً من السجل الرسمي للـ MCP · مصافحة TLS واحدة لكل نطاق عام.",
        "json_link": "واجهة JSON مفتوحة",
        "cta_title": "تُدير خادم MCP أو نطاقات عملاء؟",
        "cta_body": "افحص أي مضيف فورياً مع إيصال Ed25519 موقّع، أو اربط وكيلك بخادم Quantum Aether MCP (تقييم 100/100 على mcptry)، أو ابدأ تجربة المراقبة اليومية المجانية لمدة 14 يوماً.",
        "cta_scan": "افحص نطاقك",
        "cta_agents": "ربط خادم Quantum Aether MCP",
        "cta_monitor": "مراقبة مجانية 14 يوماً",
        "empty": "جارٍ توليد لقطة المؤشر الآن. أعد المحاولة بعد لحظات.",
    },
    "de": {
        "title": "MCP-Server Post-Quanten-TLS-Index — Live-Rangliste öffentlicher MCP-Endpunkte",
        "meta": "Live-Index der Post-Quanten-TLS-Readiness von {measured} Remote-MCP-Servern aus dem offiziellen MCP-Register: {pq_pct}% verhandeln X25519MLKEM768.",
        "kicker": "Reverse MCP Security Radar · Offizielles MCP-Register",
        "h1": "Welche Remote-MCP-Server schützen KI-Agenten-Daten mit Post-Quanten-TLS?",
        "lead": "KI-Agenten senden zunehmend sensible Prompts, Tokens und Unternehmensdaten an Remote-MCP-Endpunkte. Wir messen öffentliche HTTPS-MCP-Server aus dem offiziellen MCP-Register mit einem browserkonformen TLS-1.3-Handshake (X25519MLKEM768) und decken klassische Endpunkte sowie versteckte Präferenz-Fehlkonfigurationen auf.",
        "kpi_measured": "Gemessene Remote-MCP-Hosts",
        "kpi_pq": "Post-Quanten-Hybrid (X25519MLKEM768)",
        "kpi_classical": "Nur klassisches TLS 1.3",
        "kpi_misconfig": "PQ unterstützt, klassisch bevorzugt",
        "filter_all": "Alle",
        "filter_pq": "Post-Quanten (A)",
        "filter_misconfig": "Präferenz-Fehler",
        "filter_classical": "Klassisch (B)",
        "filter_tls12": "TLS 1.2 (C)",
        "search_placeholder": "Nach MCP-Server oder Domain filtern...",
        "col_server": "MCP-Server",
        "col_host": "Endpunkt-Host",
        "col_status": "PQ-TLS-Status",
        "col_tls": "TLS / Gruppe",
        "col_action": "Live-Prüfung",
        "st_pq_hybrid": "Post-Quanten",
        "st_pq_not_preferred": "PQ aktiv, aber klassisch bevorzugt",
        "st_classical": "Nur klassisch",
        "st_tls12": "Nur TLS 1.2",
        "st_unreachable": "Nicht erreichbar",
        "btn_scan": "Neu prüfen ↗",
        "btn_verify": "Badge",
        "updated": "Letzte Messung {ts} UTC · {entries} Einträge im offiziellen MCP-Register geprüft · ein TLS-Handshake pro öffentlichem Host.",
        "json_link": "Offene JSON-API",
        "cta_title": "Betreiben Sie einen MCP-Server oder Kundensysteme?",
        "cta_body": "Prüfen Sie jeden Host live mit signiertem Ed25519-Beleg, verbinden Sie unseren Remote-MCP-Server (100/100 auf mcptry) oder starten Sie das 14-tägige kostenlose Monitoring.",
        "cta_scan": "Host prüfen",
        "cta_agents": "Quantum Aether MCP verbinden",
        "cta_monitor": "14 Tage kostenlos testen",
        "empty": "Der Index-Snapshot wird gerade erstellt. Bitte kurz später erneut öffnen.",
    },
}


def load_snapshot(data_dir: str) -> dict | None:
    path = os.path.join(data_dir, "mcp_index.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def register(bp, deps):
    """deps: lang, data_dir (callable), base (callable), open_data, de_pages, de_endpoints."""
    deps["de_pages"].add(ENDPOINT)
    deps["de_endpoints"].add(ENDPOINT)

    @bp.get("/mcp-index")
    def mcp_index_page():
        lang = deps["lang"]()
        d = T.get(lang, T["en"])
        snap = load_snapshot(deps["data_dir"]()) or {
            "summary": {
                "updated_at": "", "registry_entries_checked": 0, "total_hosts": 0,
                "measured": 0, "pq_hybrid": 0, "pq_pct": 0.0, "pq_not_preferred": 0,
                "classical": 0, "tls12": 0, "unreachable": 0, "top_groups": [],
            },
            "results": [],
        }
        return render_template(
            "mcp_index.html",
            d=d,
            summary=snap["summary"],
            results=snap["results"],
            lang_code=lang,
            page_url=deps["base"]() + url_for(ENDPOINT),
        )

    @bp.get("/api/v1/mcp-index")
    def mcp_index_json():
        snap = load_snapshot(deps["data_dir"]()) or {"summary": {"measured": 0}, "results": []}
        body = {
            "source": deps["base"]() + url_for(ENDPOINT),
            "methodology": "Browser-like TLS 1.3 ClientHello offering X25519MLKEM768 + classical curves, plus PQ-only preference check on classical TLS 1.3 hosts.",
            **snap,
        }
        resp = Response(json.dumps(body, ensure_ascii=False), mimetype="application/json")
        resp.headers["Cache-Control"] = "public, max-age=1800"
        return deps["open_data"](resp)
