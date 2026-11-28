"""Owner-only Real-Time Agent Operations Dashboard (/admin/agents-live & /admin/agents-live/feed).

Protected by the exact same owner authentication as /admin (HTTP Basic Auth against
ADMIN_PASSWORD_HASH or valid ADMIN_COOKIE). Sets X-Robots-Tag: noindex, nofollow and
Cache-Control: no-store. Never reads or exposes credentials or private keys.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess

from flask import Response, abort, current_app, jsonify, render_template, request
from werkzeug.security import check_password_hash

import a2ui_cards
import agent_discovery
import ucp_commerce

TIMER_META = {
    "quantum_x_autopost.timer": ("X Autopost (3x/يوم)", "التسويق", "x_autopost.paused"),
    "quantum_x_mentions.timer": ("X Mentions (كل ساعة)", "التسويق", "x_autopost.paused"),
    "quantum_agent_platforms.timer": ("Moltbook + Agentboard", "التسويق", "agent_platforms.paused"),
    "quantum_a2a_outreach.timer": ("A2A Outreach", "التسويق", "a2a_outreach.paused"),
    "quantum_msp_radar.timer": ("رادار MSP الألماني", "المبيعات B2B", ""),
    "quantum_msp_wave5.timer": ("دفعة MSP Wave-5", "المبيعات B2B", "msp_outreach.paused"),
    "quantum_marketing_desk.timer": ("موجز التسويق الصباحي", "التسويق", ""),
    "quantum_mcp_index.timer": ("مؤشر خوادم MCP", "الأبحاث", ""),
    "quantum_monitor.timer": ("مراقبة العملاء", "المنتج", ""),
    "quantum_radar.timer": ("رادار النقاشات الساخنة", "الأبحاث", ""),
    "quantum_adoption.timer": ("مؤشر التبنّي الأسبوعي", "الأبحاث", ""),
    "quantum_adoption_monthly.timer": ("لقطة التبنّي الشهرية", "الأبحاث", ""),
    "quantum_scorecard.timer": ("بطاقة الأداء الأسبوعية", "التقارير", ""),
    "quantum_exposure_anchor.timer": ("تثبيت أدلة التعرض", "الأبحاث", ""),
    "quantum_exposure_upgrade.timer": ("ترقيات التعرض", "الأبحاث", ""),
    "quantum_family_dns.timer": ("تنظيف DNS العائلي", "العمليات", ""),
    "quantum_uptime.timer": ("حارس التوفر (5 دقائق)", "العمليات", ""),
    "quantum_indexnow_retry.timer": ("دفع IndexNow", "SEO", ""),
    "quantum_daily_report.timer": ("التقرير اليومي", "التقارير", ""),
    "quantum_cleanup.timer": ("تنظيف القرص", "العمليات", ""),
    "quantum_backup.timer": ("النسخ الاحتياطي المحلي", "العمليات", ""),
    "quantum_telegram_backup.timer": ("النسخ الاحتياطي Telegram", "العمليات", ""),
}

MCP_TOOL_TIERS = {
    "batch_scan_tls": ("x402", "$0.10 USDC"),
    "get_live_cbom": ("x402", "$0.25 USDC"),
    "get_sector_snapshot": ("x402", "$0.50 USDC"),
    "get_tls_attestation": ("x402", "$5.00 USDC"),
    "get_full_report": ("x402", "$49 / x402"),
    "create_full_report_order": ("commerce", "Polygon USDT"),
    "verify_full_report_payment": ("commerce", "Polygon USDT"),
    "register_agent_affiliate": ("commerce", "30% عمولة"),
}

TWEET_ID_RE = re.compile(r"tweet_id=(\d+)")


def _query_systemd_timers(data_dir: str) -> list[dict]:
    """Read live systemd timer schedules safely (read-only); returns [] cleanly in test sandboxes."""
    try:
        out = subprocess.check_output(
            ["systemctl", "list-timers", "--all", "quantum*", "--no-pager", "--plain", "--no-legend", "--full"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
    except Exception:
        return []

    rows: list[dict] = []
    for raw in out.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        unit = next((p for p in parts if p.endswith(".timer")), "")
        if not unit:
            continue
        idx = parts.index(unit)
        prefix = " ".join(parts[:idx])
        tokens = re.findall(r"(?:[A-Z][a-z]{2}\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+\S+)|(?:-\s)|(?:\S+(?:\s+\S+)?\s+ago)", prefix)
        next_at = tokens[0] if len(tokens) >= 1 and not tokens[0].startswith("-") else "—"
        last_at = ""
        for tk in tokens[1:]:
            if re.match(r"^[A-Z][a-z]{2}\s+\d{4}-", tk):
                last_at = tk
                break
        left_m = re.search(r"CET\s+(.+?)\s+(?:[A-Z][a-z]{2}\s+\d{4}-|-\s+-?$)", prefix)
        if not left_m:
            left_m = re.search(r"CEST\s+(.+?)\s+(?:[A-Z][a-z]{2}\s+\d{4}-|-\s+-?$)", prefix)
        left_str = left_m.group(1).strip() if left_m else ""
        passed_m = re.search(r"(\d+\S*(?:\s+\d+\S*)?\s+ago)$", prefix)
        passed_str = passed_m.group(1).strip() if passed_m else "—"

        label, group, pause_name = TIMER_META.get(unit, (unit.removesuffix(".timer"), "أخرى", ""))
        paused = bool(pause_name and os.path.exists(os.path.join(data_dir, pause_name)))
        rows.append({
            "unit": unit,
            "label": label,
            "group": group,
            "state": "paused" if paused else "active",
            "next_at": next_at,
            "left": left_str or "—",
            "last_at": last_at or "—",
            "passed": passed_str,
        })
    return rows


def _service_active() -> bool:
    try:
        out = subprocess.check_output(
            ["systemctl", "is-active", "quantum_saas.service"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()
        return out == "active"
    except Exception:
        return True


def _safe_fetchall(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list:
    try:
        return conn.execute(sql, params).fetchall()
    except sqlite3.Error:
        return []


def _safe_scalar(conn: sqlite3.Connection, sql: str, params: tuple = (), default=0):
    try:
        row = conn.execute(sql, params).fetchone()
        return row[0] if row and row[0] is not None else default
    except sqlite3.Error:
        return default


def _build_protocol_agents(
    *,
    app_active: bool,
    proto_24h: dict[str, int],
    x402_paid: int,
    receipts_24h: int,
    ucp_count: int,
    mcp_tool_count: int,
    mcp_res_count: int,
    mcp_prompt_count: int,
) -> list[dict]:
    st = "active" if app_active else "paused"
    return [
        {
            "id": "mcp",
            "name": f"خادم MCP الرئيسي (v{agent_discovery.VERSION})",
            "badge": "MCP",
            "version": agent_discovery.VERSION,
            "state": st,
            "role": "المركز الرئيسي · 18 أداة + 7 موارد + 5 قوالب",
            "detail": f"{mcp_tool_count} أداة · {mcp_res_count} موارد · {mcp_prompt_count} قوالب · /mcp و /mcp/free",
            "calls_24h": int(proto_24h.get("mcp", 0)),
            "endpoint": "/.well-known/mcp/server-card.json",
            "secondary_url": "/mcp-index",
            "secondary_label": "مؤشر MCP",
        },
        {
            "id": "ucp",
            "name": f"تجارة UCP ({ucp_commerce.UCP_VERSION})",
            "badge": "UCP",
            "version": ucp_commerce.UCP_VERSION,
            "state": st,
            "role": "توافق رسمي 2026-08-25 · /ucp/mcp (8 أدوات) + REST",
            "detail": f"{ucp_count} منتجات/SKUs · /.well-known/ucp · /ucp/mcp · /api/v1/ucp",
            "calls_24h": int(proto_24h.get("ucp", 0)),
            "endpoint": "/.well-known/ucp",
            "secondary_url": "/ucp/handlers/x402.json",
            "secondary_label": "Handler x402",
        },
        {
            "id": "a2ui",
            "name": f"واجهات A2UI (v{a2ui_cards.A2UI_VERSION} · Flutter GenUI)",
            "badge": "A2UI",
            "version": a2ui_cards.A2UI_VERSION,
            "state": st,
            "role": "بطاقات واجهة تفاعلية تصريحية لتطبيقات Flutter وعملاء A2A",
            "detail": "surfaceUpdate · dataModelUpdate · beginRendering · ar/en/de",
            "calls_24h": int(proto_24h.get("a2ui", 0)),
            "endpoint": "/api/v1/a2ui/evidence/cloudflare.com?lang=ar",
            "secondary_url": "/api/v1/a2ui/evidence/cloudflare.com?format=jsonl",
            "secondary_label": "JSONL",
        },
        {
            "id": "x402",
            "name": "مدفوعات x402 v2 (Base USDC)",
            "badge": "x402",
            "version": "2.0",
            "state": st,
            "role": "بيع خدمات الوكلاء بالدفع لكل طلب ($0.10 – $49 USDC)",
            "detail": f"5 أدوات مدفوعة داخل MCP + HTTP · مدفوعات مسجّلة: {x402_paid}",
            "calls_24h": int(x402_paid),
            "endpoint": "/.well-known/x402",
            "secondary_url": "/openapi.json",
            "secondary_label": "OpenAPI 3.1",
        },
        {
            "id": "a2a",
            "name": "وكيل A2A الموقّع (0.3.0 + EdDSA)",
            "badge": "A2A",
            "version": "0.3.0",
            "state": st,
            "role": "تخاطب وكيل-لوكيل مع 7 مهارات وامتداد A2UI v0.8",
            "detail": "message/send · tasks/get · tasks/cancel · بطاقة موقّعة بـ Ed25519",
            "calls_24h": int(proto_24h.get("a2a", 0)),
            "endpoint": "/.well-known/agent-card.json",
            "secondary_url": "/a2a",
            "secondary_label": "بطاقة /a2a",
        },
        {
            "id": "acp",
            "name": "بروتوكول ACP (REST / BeeAI)",
            "badge": "ACP",
            "version": "0.1",
            "state": st,
            "role": "توافق REST لوكلاء Linux Foundation / ChatGPT / BeeAI",
            "detail": "GET /acp/agents · POST /acp/runs · إيصالات موقّعة مرفقة",
            "calls_24h": int(proto_24h.get("acp", 0)),
            "endpoint": "/acp/agents",
            "secondary_url": "/.well-known/api-catalog",
            "secondary_label": "API Catalog",
        },
        {
            "id": "receipts",
            "name": "إيصالات Ed25519 الموقّعة (v1 JWS)",
            "badge": "JWKS",
            "version": "1.0",
            "state": st,
            "role": "توقيع رقمي قابل للتحقق دون اتصال عبر /.well-known/jwks.json",
            "detail": f"إيصالات مُصدرة آخر 24س: {receipts_24h} · سياسة qa-pqc-transport 1.0",
            "calls_24h": int(receipts_24h),
            "endpoint": "/.well-known/jwks.json",
            "secondary_url": "/.well-known/qa-receipt-configuration",
            "secondary_label": "إعدادات الإيصال",
        },
    ]


def collect_snapshot(conn: sqlite3.Connection, data_dir: str, *, base_url: str = "", cfg=None) -> dict:
    now_utc = dt.datetime.now(dt.timezone.utc)
    today = now_utc.strftime("%Y-%m-%d")
    yesterday = (now_utc.date() - dt.timedelta(days=1)).isoformat()
    cfg = cfg if cfg is not None else current_app.config
    b = (base_url or cfg.get("PUBLIC_URL") or "https://ather-quantum.com").rstrip("/")

    # 1) KPIs
    human_today = _safe_scalar(
        conn, "SELECT COUNT(DISTINCT visitor) FROM pageviews WHERE day = ? AND is_bot = 0 AND is_test = 0", (today,), 0
    )
    human_pvs_today = _safe_scalar(
        conn, "SELECT COUNT(*) FROM pageviews WHERE day = ? AND is_bot = 0 AND is_test = 0", (today,), 0
    )
    human_yesterday = _safe_scalar(
        conn, "SELECT COUNT(DISTINCT visitor) FROM pageviews WHERE day = ? AND is_bot = 0 AND is_test = 0", (yesterday,), 0
    )
    scans_24h = _safe_scalar(
        conn, "SELECT COUNT(*) FROM scans WHERE created_at >= datetime('now', '-24 hours')", (), 0
    )
    receipts_24h = _safe_scalar(
        conn, "SELECT COUNT(*) FROM receipts WHERE iat >= strftime('%s', 'now', '-24 hours')", (), 0
    )
    mcp_calls_24h = _safe_scalar(
        conn, "SELECT COUNT(*) FROM agent_calls WHERE ts >= datetime('now', '-24 hours')", (), 0
    )

    proto_24h: dict[str, int] = {}
    for proto, cnt in _safe_fetchall(
        conn,
        "SELECT lower(COALESCE(protocol, 'mcp')), COUNT(*) FROM agent_calls "
        "WHERE ts >= datetime('now', '-24 hours') GROUP BY lower(COALESCE(protocol, 'mcp'))",
    ):
        proto_24h[str(proto)] = int(cnt)

    tool_calls_24h: dict[str, int] = {}
    for act, cnt in _safe_fetchall(
        conn,
        "SELECT action, COUNT(*) FROM agent_calls "
        "WHERE lower(COALESCE(protocol, '')) = 'mcp' AND ts >= datetime('now', '-24 hours') GROUP BY action",
    ):
        tool_calls_24h[str(act)] = int(cnt)

    a2a_total = _safe_scalar(conn, "SELECT COUNT(*) FROM a2a_outreach_sent", (), 0)
    a2a_ok = _safe_scalar(conn, "SELECT COUNT(*) FROM a2a_outreach_sent WHERE http_status = 200", (), 0)
    msp_sent_14d = _safe_scalar(
        conn,
        "SELECT COUNT(*) FROM outreach_sent WHERE sent_at >= datetime('now', '-14 days') AND (lang = 'de' OR subject LIKE '%Pilot%')",
        (),
        0,
    )
    paid_orders = _safe_scalar(conn, "SELECT COUNT(*) FROM orders WHERE status = 'PAID' AND is_test = 0", (), 0)
    x402_paid = _safe_scalar(conn, "SELECT COUNT(*) FROM x402_payments", (), 0)
    active_trials = _safe_scalar(conn, "SELECT COUNT(*) FROM monitor_accounts", (), 0)

    platform_counts = {}
    for plat, kind, cnt in _safe_fetchall(
        conn,
        "SELECT platform, kind, COUNT(*) FROM agent_platform_activity GROUP BY platform, kind",
    ):
        platform_counts.setdefault(plat, {})[kind] = int(cnt)

    # MCP Index live file
    mcp_summary = {"measured": 0, "pq_hybrid": 0, "pq_pct": 0.0, "classical": 0, "tls12": 0, "updated_at": ""}
    idx_path = Path(data_dir) / "mcp_index.json"
    if idx_path.exists():
        try:
            doc = json.loads(idx_path.read_text(encoding="utf-8"))
            if isinstance(doc.get("summary"), dict):
                mcp_summary.update(doc["summary"])
        except Exception:
            pass

    # 2) Build dedicated inventories: MCP tools (18), MCP resources/prompts, UCP catalog (9), A2UI showcase, Protocols (7)
    mcp_tools_list = []
    for t in agent_discovery.TOOLS:
        name = t["name"]
        in_free = name in agent_discovery.FREE_TOOLS
        tier_key, price_lbl = MCP_TOOL_TIERS.get(name, ("free", "مجانية"))
        ro = bool((t.get("annotations") or {}).get("readOnlyHint"))
        mcp_tools_list.append({
            "name": name,
            "title": t.get("title") or name,
            "tier": tier_key,
            "price_label": price_lbl,
            "in_free_endpoint": in_free,
            "read_only": ro,
            "calls_24h": int(tool_calls_24h.get(name, 0)),
        })

    mcp_resources_list = [
        {"uri": r["uri"], "name": r["name"], "kind": "resource", "mime": r.get("mimeType", "application/json")}
        for r in agent_discovery.MCP_RESOURCES
    ] + [
        {"uri": r["uriTemplate"], "name": r["name"], "kind": "template", "mime": r.get("mimeType", "application/json")}
        for r in agent_discovery.MCP_RESOURCE_TEMPLATES
    ]
    mcp_prompts_list = [
        {"name": p["name"], "title": p.get("title") or p["name"], "args": [a["name"] for a in (p.get("arguments") or [])]}
        for p in agent_discovery.MCP_PROMPTS
    ]

    ucp_catalog = ucp_commerce.catalog_items(b, cfg)

    recent_domains = []
    seen_doms = set()
    for (dom,) in _safe_fetchall(conn, "SELECT domain FROM scans ORDER BY rowid DESC LIMIT 24"):
        d = (dom or "").strip().lower()
        if d and d not in seen_doms:
            seen_doms.add(d)
            recent_domains.append(d)
        if len(recent_domains) >= 6:
            break
    for fallback_dom in ("cloudflare.com", "github.com", "google.com"):
        if len(recent_domains) < 6 and fallback_dom not in seen_doms:
            seen_doms.add(fallback_dom)
            recent_domains.append(fallback_dom)

    a2ui_info = {
        "version": a2ui_cards.A2UI_VERSION,
        "extension_uri": a2ui_cards.A2UI_EXTENSION_URI,
        "catalog_id": a2ui_cards.A2UI_CATALOG_ID,
        "mime_type": a2ui_cards.A2UI_MIME,
        "mcp_tool": "get_a2ui_card",
        "resource_template": "qa://a2ui/evidence/{domain}",
        "calls_24h": int(proto_24h.get("a2ui", 0)) + int(tool_calls_24h.get("get_a2ui_card", 0)),
        "sample_domains": [
            {
                "domain": dom,
                "json_ar": f"/api/v1/a2ui/evidence/{dom}?lang=ar",
                "json_en": f"/api/v1/a2ui/evidence/{dom}?lang=en",
                "jsonl": f"/api/v1/a2ui/evidence/{dom}?format=jsonl",
            }
            for dom in recent_domains
        ],
    }

    # 3) Unified Live Activity Feed (expanded to 100 events across ALL agents & protocols)
    events: list[dict] = []

    for plat, kind, ref_key, summary, ts in _safe_fetchall(
        conn,
        "SELECT platform, kind, ref_key, summary, created_at FROM agent_platform_activity ORDER BY id DESC LIMIT 35",
    ):
        url = ""
        m = TWEET_ID_RE.search(summary or "")
        if plat == "x" and m:
            url = f"https://x.com/i/web/status/{m.group(1)}"
        elif plat == "moltbook":
            url = "https://www.moltbook.com/u/quantumaether"
        elif plat == "agentboard":
            url = "https://www.agentboard.ai/a/quantum-aether"
        kind_ar = {
            "daily_post": "نشر تغريدة آلية",
            "manual_post": "نشر تغريدة",
            "mention_reply": "رد على تعليق",
            "daily_digest": "نشر ملخّص يومي",
            "series": "نشر مقال سلسلة",
            "comment_reply": "رد على تعليق",
            "reply": "رد بفحص حي",
            "follow": "متابعة وكيل",
            "intro": "منشور تعريفي",
        }.get(kind, kind)
        events.append({
            "ts": ts or "",
            "channel": plat,
            "badge": plat.upper(),
            "title": kind_ar,
            "detail": f"{ref_key} · {summary}".strip(" ·"),
            "url": url,
            "ok": "skip" not in (summary or "").lower(),
        })

    for ts, host, name, st_code, excerpt in _safe_fetchall(
        conn,
        "SELECT sent_at, host, agent_name, http_status, substr(COALESCE(task_reply, reply_excerpt, ''), 1, 110) "
        "FROM a2a_outreach_sent ORDER BY sent_at DESC LIMIT 18",
    ):
        events.append({
            "ts": ts or "",
            "channel": "a2a",
            "badge": "A2A",
            "title": f"تواصل مع {name or host}",
            "detail": f"{host} · HTTP {st_code} · {(excerpt or '').replace(chr(10), ' ')[:85]}",
            "url": "",
            "ok": int(st_code or 0) == 200,
        })

    for ts, dom, kex, kcls, subj in _safe_fetchall(
        conn,
        "SELECT sent_at, domain, kex_group, kex_class, subject FROM outreach_sent ORDER BY sent_at DESC LIMIT 18",
    ):
        events.append({
            "ts": ts or "",
            "channel": "msp",
            "badge": "MSP B2B",
            "title": f"بريد MSP إلى {dom}",
            "detail": f"{kex or kcls or 'TLS'} · {(subj or '')[:70]}",
            "url": f"https://ather-quantum.com/?domain={dom}&lang=de",
            "ok": True,
        })

    for ts, proto, action, client, dom, st in _safe_fetchall(
        conn,
        "SELECT ts, protocol, action, client_name, domain, status FROM agent_calls ORDER BY id DESC LIMIT 35",
    ):
        p_low = (proto or "mcp").lower()
        ch = p_low if p_low in ("mcp", "ucp", "a2ui", "a2a", "acp", "x402") else "mcp"
        events.append({
            "ts": ts or "",
            "channel": ch,
            "badge": ch.upper(),
            "title": f"{client or 'agent'} → {action}",
            "detail": f"{dom or 'handshake'} · {st}",
            "url": "",
            "ok": (st or "").lower() in ("ok", "200", "paid"),
        })

    for ts, dom, grade, src in _safe_fetchall(
        conn,
        "SELECT created_at, domain, grade, source FROM scans ORDER BY rowid DESC LIMIT 20",
    ):
        events.append({
            "ts": ts or "",
            "channel": "scan",
            "badge": "SCAN",
            "title": f"فحص حيّ: {dom} (Grade {grade or '?'})",
            "detail": f"المصدر: {src or 'direct'}",
            "url": f"https://ather-quantum.com/verify/{dom}",
            "ok": True,
        })

    for ts, sender, subj in _safe_fetchall(
        conn,
        "SELECT received_at, sender, subject FROM inbound_mail ORDER BY received_at DESC LIMIT 10",
    ):
        events.append({
            "ts": ts or "",
            "channel": "mail",
            "badge": "INBOUND",
            "title": f"بريد وارد من {sender}",
            "detail": (subj or "")[:100],
            "url": "",
            "ok": True,
        })

    events.sort(key=lambda e: e.get("ts") or "", reverse=True)
    app_active = _service_active()
    timers = _query_systemd_timers(data_dir)
    active_timers = sum(1 for t in timers if t["state"] == "active")

    protocols = _build_protocol_agents(
        app_active=app_active,
        proto_24h=proto_24h,
        x402_paid=int(x402_paid),
        receipts_24h=int(receipts_24h),
        ucp_count=len(ucp_catalog),
        mcp_tool_count=len(mcp_tools_list),
        mcp_res_count=len(mcp_resources_list),
        mcp_prompt_count=len(mcp_prompts_list),
    )
    live_protocol_count = sum(1 for p in protocols if p["state"] == "active")

    return {
        "server_time_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "app_active": app_active,
        "kpis": {
            "active_agents": active_timers + live_protocol_count,
            "active_timers": active_timers,
            "live_protocols": live_protocol_count,
            "timers_total": len(timers),
            "mcp_tools_total": len(mcp_tools_list),
            "mcp_free_tools": sum(1 for t in mcp_tools_list if t["in_free_endpoint"]),
            "mcp_x402_tools": sum(1 for t in mcp_tools_list if t["tier"] == "x402"),
            "mcp_resources_total": len(mcp_resources_list),
            "mcp_prompts_total": len(mcp_prompts_list),
            "ucp_skus_total": len(ucp_catalog),
            "ucp_calls_24h": int(proto_24h.get("ucp", 0)),
            "a2ui_calls_24h": a2ui_info["calls_24h"],
            "human_today": int(human_today),
            "human_pvs_today": int(human_pvs_today),
            "human_yesterday": int(human_yesterday),
            "scans_24h": int(scans_24h),
            "receipts_24h": int(receipts_24h),
            "mcp_calls_24h": int(mcp_calls_24h),
            "a2a_total": int(a2a_total),
            "a2a_ok": int(a2a_ok),
            "msp_sent_14d": int(msp_sent_14d),
            "paid_orders": int(paid_orders),
            "x402_paid": int(x402_paid),
            "active_trials": int(active_trials),
            "platform_counts": platform_counts,
            "mcp_index": mcp_summary,
        },
        "protocols": protocols,
        "mcp_tools": mcp_tools_list,
        "mcp_resources": mcp_resources_list,
        "mcp_prompts": mcp_prompts_list,
        "ucp_catalog": ucp_catalog,
        "a2ui": a2ui_info,
        "timers": timers,
        "events": events[:100],
    }


def register(bp, deps):
    """deps: db, is_admin_visitor, admin_cookie_name, admin_cookie_value."""
    db = deps["db"]
    is_admin_visitor = deps["is_admin_visitor"]
    admin_cookie_name = deps["admin_cookie_name"]
    admin_cookie_value = deps["admin_cookie_value"]

    def _require_owner():
        if is_admin_visitor():
            return None, False
        password_hash = current_app.config.get("ADMIN_PASSWORD_HASH")
        if not password_hash:
            abort(404)
        auth = request.authorization
        if auth and auth.username == "admin" and check_password_hash(password_hash, auth.password or ""):
            return None, True
        return Response(
            status=401,
            headers={
                "WWW-Authenticate": 'Basic realm="Quantum Aether admin", charset="UTF-8"',
                "Cache-Control": "no-store",
                "X-Robots-Tag": "noindex, nofollow",
            },
        ), False

    @bp.get("/admin/agents-live")
    def admin_agents_live():
        deny, set_cookie = _require_owner()
        if deny is not None:
            return deny
        snap = collect_snapshot(db(), current_app.config["DATA_DIR"])
        resp = current_app.make_response(render_template("agents_live.html", snap=snap))
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        if set_cookie:
            resp.set_cookie(
                admin_cookie_name,
                admin_cookie_value(),
                max_age=365 * 24 * 3600,
                httponly=True,
                secure=request.is_secure,
                samesite="Lax",
            )
        return resp

    @bp.get("/admin/agents-live/feed")
    def admin_agents_live_feed():
        deny, set_cookie = _require_owner()
        if deny is not None:
            return deny
        snap = collect_snapshot(db(), current_app.config["DATA_DIR"])
        resp = jsonify(snap)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        if set_cookie:
            resp.set_cookie(
                admin_cookie_name,
                admin_cookie_value(),
                max_age=365 * 24 * 3600,
                httponly=True,
                secure=request.is_secure,
                samesite="Lax",
            )
        return resp
