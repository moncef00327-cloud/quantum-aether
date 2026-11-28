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
        # Extract NEXT and LEFT/PASSED human snippets cleanly
        # Typical format: "Sat 2026-11-28 03:10:40 CET 42min Sat 2026-11-28 02:10:58 CET 16min ago"
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


def collect_snapshot(conn: sqlite3.Connection, data_dir: str) -> dict:
    now_utc = dt.datetime.now(dt.timezone.utc)
    today = now_utc.strftime("%Y-%m-%d")
    yesterday = (now_utc.date() - dt.timedelta(days=1)).isoformat()

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

    # 2) Unified Live Activity Feed (most recent events across ALL agents)
    events: list[dict] = []

    for plat, kind, ref_key, summary, ts in _safe_fetchall(
        conn,
        "SELECT platform, kind, ref_key, summary, created_at FROM agent_platform_activity ORDER BY id DESC LIMIT 25",
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
        "FROM a2a_outreach_sent ORDER BY sent_at DESC LIMIT 12",
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
        "SELECT sent_at, domain, kex_group, kex_class, subject FROM outreach_sent ORDER BY sent_at DESC LIMIT 12",
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
        "SELECT ts, protocol, action, client_name, domain, status FROM agent_calls ORDER BY id DESC LIMIT 15",
    ):
        events.append({
            "ts": ts or "",
            "channel": "mcp",
            "badge": (proto or "MCP").upper(),
            "title": f"{client or 'agent'} → {action}",
            "detail": f"{dom or 'handshake'} · {st}",
            "url": "",
            "ok": (st or "").lower() in ("ok", "200", "paid"),
        })

    for ts, dom, grade, src in _safe_fetchall(
        conn,
        "SELECT created_at, domain, grade, source FROM scans ORDER BY rowid DESC LIMIT 12",
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
        "SELECT received_at, sender, subject FROM inbound_mail ORDER BY received_at DESC LIMIT 8",
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
    timers = _query_systemd_timers(data_dir)
    active_timers = sum(1 for t in timers if t["state"] == "active")

    return {
        "server_time_utc": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "app_active": _service_active(),
        "kpis": {
            "active_agents": active_timers + (1 if _service_active() else 0),
            "timers_total": len(timers),
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
        "timers": timers,
        "events": events[:50],
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
