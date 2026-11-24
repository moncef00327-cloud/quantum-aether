#!/usr/bin/env python3
"""marketing_desk.py — غرفة عمليات التسويق الآلية (5 موظفي تسويق أخلاقيين 24/7).

قراءة فقط من قاعدة البيانات + تحديث تغذية أخبار PQC في DATA_DIR + توليد حزمة تسويق يومية جاهزة للنشر
في /var/lib/quantum_saas/marketing_briefs/YYYY-MM-DD.md وإرسالها للمالك فقط.
يحفظ سجل العناصر المعروضة في marketing_briefs/history.json لمنع تكرار نفس روابط الرادار أو النطاقات
أو المنشورات يوماً بعد يوم. لا يرسل أي بريد لعملاء خارجيين ولا ينشر سباماً على أي منصة خارجية أبداً.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys

import crawler_log
import generate_pqc_news
from mailer import Mailer, with_team_from

log = logging.getLogger("quantum_saas.marketing_desk")

SITE = "https://ather-quantum.com"

mail_from_with_team_name = with_team_from

HISTORY_TTL_DAYS = 60

PAY_SECTORS = (
    "banks-mena", "banks-dach", "banks-europe", "banks-americas-apac",
    "finance-worldwide", "payments-fintech", "crypto-exchanges",
    "health-insurance-dach", "global-insurance-healthcare",
    "telecom", "enterprise-saas-b2b", "cloud-security", "companies-dach",
)
SECTOR_LABELS = {
    "banks-mena": ("بنوك الشرق الأوسط وشمال إفريقيا", "MENA banks", "MENA-Banken"),
    "banks-dach": ("بنوك ألمانيا والنمسا وسويسرا (DACH)", "DACH banks", "DACH-Banken"),
    "banks-europe": ("البنوك الأوروبية", "European banks", "Europäische Banken"),
    "banks-americas-apac": ("بنوك الأمريكتين وآسيا", "Americas & APAC banks", "Banken Amerika & APAC"),
    "health-insurance-dach": ("التأمين الصحي في DACH", "DACH health insurers", "Krankenkassen DACH"),
    "telecom": ("شركات الاتصالات", "telecom operators", "Telekommunikationsanbieter"),
    "finance-worldwide": ("المؤسسات المالية العالمية", "global financial institutions", "Globale Finanzinstitute"),
    "payments-fintech": ("المدفوعات والتقنية المالية", "payments & fintech", "Zahlungsdienstleister & FinTech"),
    "enterprise-saas-b2b": ("منصات SaaS للشركات", "B2B enterprise SaaS", "B2B-Enterprise-SaaS"),
    "cloud-security": ("مزوّدو السحابة والأمن", "cloud & security providers", "Cloud- & Sicherheitsanbieter"),
    "companies-dach": ("الشركات الكبرى في DACH", "major DACH enterprises", "Großunternehmen DACH"),
    "global-insurance-healthcare": ("التأمين والرعاية الصحية العالمية", "global insurance & healthcare", "Versicherung & Gesundheit"),
    "crypto-exchanges": ("منصات تداول الأصول الرقمية", "crypto exchanges", "Krypto-Börsen"),
}

# Daily rotating featured landing pages/guides so each day's posts link to fresh pages
DAILY_SPOTLIGHTS = (
    ("/tools/post-quantum-tls-checker", "أداة فحص جاهزية TLS لما بعد الكم", "Free Post-Quantum TLS Checker", "Kostenloser Post-Quanten-TLS-Checker"),
    ("/guides/tls-clienthello-middlebox-fragmentation", "دليل تعثّر ClientHello مع الجدران النارية", "ClientHello Fragmentation & Middlebox Guide", "Leitfaden: ClientHello-Fragmentierung & Firewalls"),
    ("/guides/bsi-tr-02102-2-post-quantum-tls", "دليل متطلبات BSI TR-02102-2 وNIS2/DORA", "BSI TR-02102-2 & NIS2/DORA PQC TLS Guide", "BSI TR-02102-2 & NIS2/DORA Praxis-Leitfaden"),
    ("/policies/qa-pqc-transport/1.0", "مواصفة الإيصالات الموقّعة Ed25519 (qa-pqc-transport 1.0)", "Signed Ed25519 TLS Receipts (qa-pqc-transport 1.0)", "Signierte Ed25519-TLS-Prüfbelege (v1.0)"),
    ("/partners", "برنامج البايلوت لشركاء ومزوّدي خدمات IT (290 €)", "MSP Partner Pilot (up to 50 hostnames, 290 €)", "IT-Dienstleister-Pilot (bis zu 50 Hostnamen, 290 €)"),
    ("/guides/openssl-3-5-curl-x25519mlkem768", "دليل OpenSSL 3.5 وcurl لتفعيل X25519MLKEM768", "OpenSSL 3.5 & curl X25519MLKEM768 Cookbook", "OpenSSL 3.5 & curl X25519MLKEM768 Anleitung"),
    ("/guides/securing-mcp-a2a-acp-agents-post-quantum-tls", "دليل تأمين وكلاء MCP وA2A بـ PQ-TLS", "Securing MCP, A2A & ACP Agents with PQ-TLS", "MCP-, A2A- & ACP-Agenten mit PQ-TLS absichern"),
)


def conn_ro(db_path: str) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


# ---------------------------------------------------------------- Anti-repetition history store
def _history_path(data_dir: str) -> Path:
    return Path(data_dir) / "marketing_briefs" / "history.json"


def load_history(data_dir: str, today: dt.date) -> dict:
    """Load previously shown URLs/domains and drop entries older than HISTORY_TTL_DAYS (except permanent URL buckets)."""
    empty = {
        "radar_urls": {},
        "news_urls": {},
        "shoutout_domains": {},
        "priority_cf_domains": {},
        "regression_keys": {},
    }
    path = _history_path(data_dir)
    if not path.exists():
        return empty
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return empty
    except Exception:
        return empty

    cutoff = (today - dt.timedelta(days=HISTORY_TTL_DAYS)).isoformat()
    out = {}
    for bucket in empty:
        entries = raw.get(bucket)
        if not isinstance(entries, dict):
            out[bucket] = {}
            continue
        if bucket in ("radar_urls", "news_urls", "regression_keys"):
            # Never re-show an already-briefed radar discussion, news link, or same-week regression
            out[bucket] = {str(k): str(v) for k, v in entries.items()}
        else:
            out[bucket] = {str(k): str(v) for k, v in entries.items() if str(v) >= cutoff}
    return out


def save_history(data_dir: str, history: dict) -> None:
    path = _history_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(history, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------- Employee 1: Intent Radar Reply Drafter
def employee_radar_replies(
    c: sqlite3.Connection,
    limit: int = 4,
    seen_urls: set[str] | None = None,
) -> list[dict]:
    """يقرأ أعلى النقاشات الساخنة الجديدة غير المعروضة سابقاً من radar_seen ويجهّز لكل منها مسودة رد تقني."""
    already = seen_urls or set()
    try:
        rows = c.execute(
            "SELECT url, source, title, topic, intent, stack, score, found_at "
            "FROM radar_seen ORDER BY found_at DESC, score DESC LIMIT ?",
            (max(limit * 10, 50),),
        ).fetchall()
    except sqlite3.Error:
        return []
    drafts = []
    for r in rows:
        url = r["url"]
        if not url or url in already:
            continue
        intent = (r["intent"] or "discussion").lower()
        stack = (r["stack"] or "general").lower()
        title = r["title"] or ""
        if stack == "clienthello" or "clienthello" in title.lower():
            guide = f"{SITE}/guides/tls-clienthello-middlebox-fragmentation"
            reply = (
                "We have been seeing this across enterprise middleboxes/firewalls whenever clients advertise "
                "X25519MLKEM768 (~1.2 KB ClientHello spanning two TCP segments). "
                "Quick way to verify whether an upstream endpoint actually completes the hybrid PQ handshake "
                f"(or triggers a silent fallback/hang): {SITE}/ (free single-handshake check, no login) — "
                f"and diagnostic notes on middlebox fragmentation: {guide}"
            )
        elif intent == "question":
            reply = (
                "If you want to verify whether your public TLS endpoints actually negotiate hybrid "
                "post-quantum key exchange (X25519MLKEM768) vs falling back to classical X25519/P-256, "
                f"you can run a quick one-handshake check here (free, no signup): {SITE}/ — "
                f"and we publish weekly sector benchmarks across 11,000+ domains at {SITE}/adoption"
            )
        else:
            reply = (
                "Great thread. We track live hybrid post-quantum TLS (X25519MLKEM768) adoption weekly across "
                f"11,000+ public domains and banking/telecom/government watchlists ({SITE}/adoption). "
                f"Happy to share any server-specific data or you can test any hostname directly at {SITE}/"
            )
        drafts.append({
            "source": r["source"],
            "score": r["score"],
            "title": title,
            "url": url,
            "intent": intent,
            "reply": reply,
        })
        if len(drafts) >= limit:
            break
    return drafts


# ---------------------------------------------------------------- Employee 2: Data Journalist & Content Studio
def employee_data_journalist(
    c: sqlite3.Connection,
    today: dt.date | None = None,
    shown_regressions: set[str] | None = None,
) -> dict:
    """يحلل أحدث مسح أسبوعي ويدوّر زاوية القصة والقطاع والصفحة المميّزة يومياً لمنع التكرار."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    day_idx = today.toordinal()
    seen_reg = shown_regressions or set()

    weeks = [r[0] for r in c.execute("SELECT DISTINCT week FROM adoption_results ORDER BY week DESC LIMIT 2")]
    if not weeks:
        return {"week": None}
    wk = weeks[0]
    prev_wk = weeks[1] if len(weeks) > 1 else None

    ov = c.execute(
        "SELECT COUNT(*) AS total, SUM(CASE WHEN ok=1 THEN 1 ELSE 0 END) AS ok_n, "
        "SUM(CASE WHEN ok=1 AND pq=1 THEN 1 ELSE 0 END) AS pq_n, "
        "SUM(CASE WHEN ok=1 AND grade IN ('C','F') THEN 1 ELSE 0 END) AS cf_n "
        "FROM adoption_results WHERE week=?",
        (wk,),
    ).fetchone()
    ok_n = ov["ok_n"] or 0
    pq_n = ov["pq_n"] or 0
    pq_pct = round(100.0 * pq_n / ok_n, 1) if ok_n else 0.0

    ph = ",".join("?" for _ in PAY_SECTORS)
    sectors = []
    for r in c.execute(
        f"SELECT sector, COUNT(*) AS total, SUM(CASE WHEN ok=1 THEN 1 ELSE 0 END) AS ok_n, "
        f"SUM(CASE WHEN ok=1 AND pq=1 THEN 1 ELSE 0 END) AS pq_n, "
        f"SUM(CASE WHEN ok=1 AND grade IN ('C','F') THEN 1 ELSE 0 END) AS cf_n "
        f"FROM adoption_results WHERE week=? AND sector IN ({ph}) GROUP BY sector",
        (wk, *PAY_SECTORS),
    ):
        sok = r["ok_n"] or 0
        spq = r["pq_n"] or 0
        if sok < 10:
            continue
        pct = round(100.0 * spq / sok, 1)
        sectors.append({
            "sector": r["sector"], "ok": sok, "pq": spq, "pct": pct,
            "not_pq_pct": round(100.0 - pct, 1), "cf": r["cf_n"] or 0,
        })
    sectors.sort(key=lambda x: (x["pct"], -x["cf"]))

    all_regressions, fresh_regressions, upgrades = [], [], []
    if prev_wk:
        for r in c.execute(
            "SELECT cur.domain, cur.sector, prev.grade AS old_g, cur.grade AS new_g "
            "FROM adoption_results cur JOIN adoption_results prev "
            "ON cur.domain = prev.domain AND prev.week = ? "
            "WHERE cur.week = ? AND cur.ok = 1 AND prev.ok = 1 AND cur.unsure = 0 AND prev.unsure = 0 "
            "AND prev.pq = 1 AND cur.pq = 0 ORDER BY cur.sector IS NULL, cur.domain LIMIT 50",
            (prev_wk, wk),
        ):
            item = dict(r)
            all_regressions.append(item)
            reg_key = f"{wk}:{item['domain']}"
            if reg_key not in seen_reg:
                fresh_regressions.append(item)
        for r in c.execute(
            "SELECT cur.domain, cur.sector, prev.grade AS old_g, cur.grade AS new_g "
            "FROM adoption_results cur JOIN adoption_results prev "
            "ON cur.domain = prev.domain AND prev.week = ? "
            "WHERE cur.week = ? AND cur.ok = 1 AND prev.ok = 1 AND cur.unsure = 0 AND prev.unsure = 0 "
            "AND prev.pq = 0 AND cur.pq = 1 ORDER BY cur.sector IS NULL, cur.domain LIMIT 100",
            (prev_wk, wk),
        ):
            upgrades.append(dict(r))

    # Rotate featured spotlight page & featured sector each day so drafts vary cleanly
    spot_path, spot_ar, spot_en, spot_de = DAILY_SPOTLIGHTS[day_idx % len(DAILY_SPOTLIGHTS)]
    spot_url_ar = f"{SITE}{spot_path}" + ("&lang=ar" if "?" in spot_path else "?lang=ar")
    spot_url_en = f"{SITE}{spot_path}" + ("&lang=en" if "?" in spot_path else "?lang=en")
    spot_url_de = f"{SITE}{spot_path}" + ("&lang=de" if "?" in spot_path else "?lang=de")

    ar_pool = [s for s in sectors if s["sector"] in ("banks-mena", "telecom", "payments-fintech", "finance-worldwide", "crypto-exchanges")] or sectors
    de_pool = [s for s in sectors if s["sector"] in ("health-insurance-dach", "banks-dach", "companies-dach", "banks-europe", "enterprise-saas-b2b")] or sectors
    ar_focus = ar_pool[day_idx % len(ar_pool)] if ar_pool else None
    de_focus = de_pool[day_idx % len(de_pool)] if de_pool else None

    # Rotate 3-sector slice for EN/X posts across available sectors
    if len(sectors) > 3:
        start = (day_idx * 2) % len(sectors)
        en_slice = [sectors[(start + i) % len(sectors)] for i in range(3)]
    else:
        en_slice = sectors[:3]

    ar_post = ""
    if ar_focus:
        ar_label = SECTOR_LABELS.get(ar_focus["sector"], (ar_focus["sector"], ar_focus["sector"], ar_focus["sector"]))[0]
        sector_hub_ar = f"{SITE}/adoption/sector/{ar_focus['sector']}?lang=ar"
        ar_post = (
            f"📊 لقطة قطاعية من مسح {ok_n:,} موقعًا عالميًا ({wk} · {today.isoformat()}):\n"
            f"• في قطاع {ar_label}: {ar_focus['not_pq_pct']}% ما زالت على التشفير التقليدي فقط "
            f"(جاهزية PQ: {ar_focus['pct']}%، ومنها {ar_focus['cf']} مؤسسة بدرجة C أو F).\n"
            f"• المتوسط العالمي لتبني X25519MLKEM768 وصل إلى {pq_pct}%.\n\n"
            f"صفحة القطاع: {sector_hub_ar}\n"
            f"{spot_ar}: {spot_url_ar}\n"
            "#الأمن_السيبراني #التشفير_ما_بعد_الكم #ساما #PQC #TLS"
        )

    en_lines = "\n".join(
        f"- {SECTOR_LABELS.get(s['sector'], (s['sector'], s['sector'], s['sector']))[1]}: "
        f"{s['pct']}% PQ-ready ({s['not_pq_pct']}% classical, {s['cf']} Grade C/F)"
        for s in en_slice
    )
    en_post = (
        f"Post-Quantum TLS sector spotlight ({wk} · {today.isoformat()}, {ok_n:,} public hosts):\n\n"
        f"Global X25519MLKEM768 adoption is {pq_pct}%. Today's sector comparison:\n"
        f"{en_lines}\n\n"
        + (f"Silent regressions tracked this week: {len(all_regressions)} hosts dropped from hybrid PQ back to classical.\n\n" if all_regressions else "")
        + f"{spot_en}: {spot_url_en}\n"
        f"Full weekly tracker: {SITE}/adoption\n"
        "#PostQuantum #TLS #InfoSec #DORA #NIS2 #MLKEM"
    )

    de_post = ""
    if de_focus:
        de_label = SECTOR_LABELS.get(de_focus["sector"], ("", "", de_focus["sector"]))[2]
        sector_hub_de = f"{SITE}/adoption/sector/{de_focus['sector']}?lang=de"
        de_post = (
            f"📊 Post-Quanten-TLS-Update ({wk} · {today.isoformat()}, {ok_n:,} geprüfte Hosts):\n"
            f"• Global nutzen bereits {pq_pct}% X25519MLKEM768.\n"
            f"• Fokus heute — {de_label}: erst {de_focus['pct']}% PQ-fähig "
            f"({de_focus['not_pq_pct']}% noch klassisch, {de_focus['cf']}× Note C/F — relevant für NIS2 & DORA).\n\n"
            f"Branchenübersicht: {sector_hub_de}\n"
            f"{spot_de}: {spot_url_de}\n"
            "#PostQuantum #Cybersicherheit #NIS2 #DORA #TLS"
        )

    x_thread = [
        f"1/ {wk} Post-Quantum TLS spotlight ({today.isoformat()}): {pq_pct}% of {ok_n:,} public hosts negotiate hybrid X25519MLKEM768.",
        "2/ Sector breakdown today:\n" + "\n".join(
            f"• {SECTOR_LABELS.get(s['sector'], (s['sector'], s['sector'], s['sector']))[1]}: {s['pct']}% PQ ({s['cf']} C/F)"
            for s in en_slice
        ),
        f"3/ {spot_en}: {spot_url_en}",
    ]

    return {
        "week": wk, "prev_week": prev_wk, "ok": ok_n, "pq": pq_n, "pq_pct": pq_pct, "cf": ov["cf_n"] or 0,
        "weakest_sectors": sectors[:5], "regressions": fresh_regressions[:10], "all_regressions_count": len(all_regressions),
        "upgrades": upgrades, "spotlight": {"path": spot_path, "en": spot_en, "ar": spot_ar, "de": spot_de},
        "drafts": {"linkedin_ar": ar_post, "linkedin_en": en_post, "linkedin_de": de_post, "x_thread": x_thread},
    }


# ---------------------------------------------------------------- Employee 3: Viral Grade-A Badge Shoutouts
def employee_badge_shoutouts(
    c: sqlite3.Connection,
    week: str,
    upgrades: list[dict],
    limit: int = 5,
    shown_domains: set[str] | None = None,
) -> list[dict]:
    """يختار مؤسسات حاصلة على الدرجة A لم تُعرض في الأيام الـ 30 الماضية."""
    already = shown_domains or set()
    chosen = []
    seen = set(already)
    for u in upgrades:
        dom = (u.get("domain") or "").strip().lower()
        if u.get("new_g") == "A" and dom and dom not in seen:
            seen.add(dom)
            chosen.append((u["domain"], u.get("sector") or "newly-upgraded", True))
            if len(chosen) >= limit:
                break
    if len(chosen) < limit and week:
        ph = ",".join("?" for _ in PAY_SECTORS)
        for r in c.execute(
            f"SELECT domain, sector FROM adoption_results "
            f"WHERE week=? AND ok=1 AND pq=1 AND grade='A' AND sector IN ({ph}) "
            f"ORDER BY RANDOM() LIMIT ?",
            (week, *PAY_SECTORS, max((limit - len(chosen)) * 8, 40)),
        ):
            dom = (r["domain"] or "").strip().lower()
            if dom and dom not in seen:
                seen.add(dom)
                chosen.append((r["domain"], r["sector"], False))
                if len(chosen) >= limit:
                    break
    out = []
    for dom, sec, is_new in chosen:
        tag = "upgraded to" if is_new else "verified at"
        out.append({
            "domain": dom,
            "sector": sec,
            "badge_page": f"{SITE}/site/{dom}#badge",
            "shoutout": (
                f"👏 Congrats to {dom} ({sec}) — {tag} Grade A Post-Quantum TLS (X25519MLKEM768)! "
                f"Public verification & embeddable badge: {SITE}/site/{dom}#badge"
            ),
        })
    return out


# ---------------------------------------------------------------- Employee 4: B2B Lead Researcher
def employee_b2b_leads(
    c: sqlite3.Connection,
    week: str,
    day: str,
    limit: int = 8,
    shown_domains: set[str] | None = None,
    today: dt.date | None = None,
) -> dict:
    """يلتقط العملاء الساخنين (زيارة/فحص أمس) + أهداف C/F جديدة غير مراسَلة ولم تُعرض خلال آخر 30 يوماً."""
    skip = set()
    for tbl in ("outreach_sent", "outreach_suppress", "growth_suppress", "adoption_optout", "contacted_orgs"):
        try:
            skip |= {(r[0] or "").strip().lower().removeprefix("www.") for r in c.execute(f"SELECT domain FROM {tbl}") if r[0]}
        except sqlite3.Error:
            pass

    # 1) Inbound interested prospects (visited or scanned yesterday)
    inbound = []
    seen_in = set()
    for prefix in ("/site/", "/exposure/", "/executive-brief/"):
        try:
            for path, n in c.execute(
                "SELECT path, COUNT(*) FROM pageviews WHERE day=? AND is_bot=0 AND is_test=0 AND path LIKE ? GROUP BY path",
                (day, prefix + "%"),
            ):
                dom = path.split(prefix, 1)[1].split("?")[0].strip("/").lower().removeprefix("www.")
                if not dom or dom in skip or dom in seen_in or ".gov" in dom:
                    continue
                row = c.execute(
                    "SELECT grade, sector, grp FROM adoption_results WHERE week=? AND (domain=? OR domain=?) AND ok=1 AND pq=0",
                    (week, dom, "www." + dom),
                ).fetchone()
                if row and row["sector"] in PAY_SECTORS:
                    seen_in.add(dom)
                    inbound.append({"domain": dom, "grade": row["grade"], "sector": row["sector"],
                                    "group": row["grp"], "hits": n, "brief": f"{SITE}/executive-brief/{dom}"})
        except sqlite3.Error:
            pass

    # 2) Fresh priority uncontacted C/F domains (excluding previously shown domains & rotating sector focus)
    already_shown = shown_domains or set()
    priority_skip = skip | already_shown | seen_in
    today = today or dt.datetime.now(dt.timezone.utc).date()
    rotated_sectors = list(PAY_SECTORS)
    shift = today.toordinal() % len(rotated_sectors)
    rotated_sectors = rotated_sectors[shift:] + rotated_sectors[:shift]
    sector_rank = {sec: i for i, sec in enumerate(rotated_sectors)}

    ph = ",".join("?" for _ in PAY_SECTORS)
    candidates = []
    if week:
        for r in c.execute(
            f"SELECT domain, sector, grade, grp, tls FROM adoption_results "
            f"WHERE week=? AND ok=1 AND pq=0 AND unsure=0 AND grade IN ('F','C') AND sector IN ({ph}) "
            f"ORDER BY CASE grade WHEN 'F' THEN 0 ELSE 1 END, domain LIMIT 400",
            (week, *PAY_SECTORS),
        ):
            base = r["domain"].lower().removeprefix("www.")
            if base in priority_skip or ".gov" in base:
                continue
            priority_skip.add(base)
            candidates.append((
                0 if r["grade"] == "F" else 1,
                sector_rank.get(r["sector"], 99),
                base,
                {
                    "domain": base, "grade": r["grade"], "sector": r["sector"],
                    "tls": r["tls"], "group": r["grp"],
                    "site_url": f"{SITE}/site/{base}", "brief_url": f"{SITE}/executive-brief/{base}",
                },
            ))
    candidates.sort(key=lambda x: (x[0], x[1], x[2]))
    priority = [item for _, _, _, item in candidates[:limit]]
    return {"inbound_hot": inbound, "priority_cf": priority}


# ---------------------------------------------------------------- Employee 5: GEO / AI Search Freshness
def employee_geo_freshness(
    data_dir: str,
    refresh_news: bool = True,
    seen_news_urls: set[str] | None = None,
) -> dict:
    """يحدّث تغذية أخبار PQC في DATA_DIR ويعرض الأخبار الجديدة غير المعروضة سابقاً فقط مع ملخص الزواحف."""
    already = seen_news_urls or set()
    news_status = {"updated": False, "items": 0, "fresh_items": [], "error": None}
    out_path = Path(data_dir) / "news_feed.json"
    if refresh_news:
        try:
            prev_out = generate_pqc_news.OUTPUT
            generate_pqc_news.OUTPUT = out_path
            try:
                rc = generate_pqc_news.main()
            finally:
                generate_pqc_news.OUTPUT = prev_out
            if rc == 0 and out_path.exists():
                doc = json.loads(out_path.read_text(encoding="utf-8"))
                items = doc.get("items") or []
                fresh = [it for it in items if it.get("url") and it["url"] not in already]
                news_status = {
                    "updated": True, "items": len(items), "fresh_items": fresh[:5],
                    "updated_at": doc.get("updated_at"), "error": None,
                }
            else:
                news_status["error"] = f"feed_refresh_rc_{rc}"
        except Exception as exc:
            news_status["error"] = f"{type(exc).__name__}: {exc}"[:140]
            log.warning("PQC news refresh failed: %s", news_status["error"])
    elif out_path.exists():
        try:
            doc = json.loads(out_path.read_text(encoding="utf-8"))
            items = doc.get("items") or []
            fresh = [it for it in items if it.get("url") and it["url"] not in already]
            news_status["items"] = len(items)
            news_status["fresh_items"] = fresh[:5]
        except Exception:
            pass
    crawlers = crawler_log.summary(data_dir, days=7)
    return {"news": news_status, "crawlers": crawlers}


# ---------------------------------------------------------------- Render Daily Markdown Brief
def render_brief(day: str, radar_drafts: list[dict], dj: dict, badges: list[dict], leads: dict, geo: dict) -> str:
    L = [
        f"# Quantum Aether — حزمة موظفي التسويق اليومية ({day})",
        "",
        "> توليد آلي 100% أخلاقي (بدون إرسال خارجي ولا سبام، ومع منع تكرار الروابط والنطاقات المعروضة سابقاً).",
        "",
        "---",
        "",
        "## 1️⃣ موظف صائد النقاشات الساخنة (GitHub / HN — نقاشات جديدة فقط)",
    ]
    if radar_drafts:
        for i, d in enumerate(radar_drafts, 1):
            L += [
                f"### {i}. [{d['source']} · {d['score']}/100] {d['title']}",
                f"- الرابط: {d['url']}",
                "- **مسودة الرد المقترح:**",
                f"> {d['reply']}",
                "",
            ]
    else:
        L += ["لا توجد نقاشات جديدة غير معروضة في الرادار اليوم (تم إخفاء الروابط التي أُرسلت في أيام سابقة).", ""]

    L += ["---", "", "## 2️⃣ موظف الصحفي البياني (منشورات متجددة يومياً بأرقام الأسبوع)"]
    if dj.get("week"):
        L += [
            f"- **الأسبوع:** `{dj['week']}` | **المفحوص بنجاح:** {dj['ok']:,} | **جاهز للكم (PQ):** {dj['pq']:,} ({dj['pq_pct']}%) | **درجة C/F:** {dj['cf']:,}",
            "",
            "### LinkedIn (عربي — زاوية اليوم)",
            "```text",
            dj["drafts"]["linkedin_ar"],
            "```",
            "",
            "### LinkedIn (English — Today's Sector Spotlight)",
            "```text",
            dj["drafts"]["linkedin_en"],
            "```",
            "",
            "### LinkedIn (Deutsch — Tagesfokus DACH)",
            "```text",
            dj["drafts"]["linkedin_de"],
            "```",
            "",
            "### X / Twitter Thread",
        ]
        for tw in dj["drafts"]["x_thread"]:
            L.append(f"- {tw}")
        L.append("")
        if dj["regressions"]:
            L.append("### ⚠️ تراجعات صامتة جديدة هذا الأسبوع (لم تُعرض سابقاً)")
            for r in dj["regressions"]:
                L.append(f"- `{r['domain']}` ({r['sector'] or 'top'}): هبط من `{r['old_g']}` إلى `{r['new_g']}`")
            L.append("")
    else:
        L += ["لا توجد بيانات أسبوعية بعد.", ""]

    L += ["---", "", "## 3️⃣ موظف الشارات الفيروسية (مؤسسات جديدة بدرجة A لـ Backlinks)"]
    if badges:
        for b in badges:
            L.append(f"- **{b['domain']}** ({b['sector']}): {b['shoutout']}")
    else:
        L.append("لا توجد مؤسسات جديدة غير معروضة اليوم.")
    L.append("")

    L += ["---", "", "## 4️⃣ موظف أبحاث العملاء B2B (أهداف جديدة غير مكررة — بدون إرسال تلقائي)"]
    if leads["inbound_hot"]:
        L.append("### 🔥 زاروا موقعك أو فحصوا أمس (أولوية قصوى):")
        for h in leads["inbound_hot"]:
            L.append(f"- **[{h['grade']} · {h['sector']}] `{h['domain']}`** ({h['hits']} تفاعل) — {h['brief']}")
    else:
        L.append("- لا زيارات واردة من قطاعات مدفوعة (B/C/F) أمس.")
    L.append("")
    L.append("### 🎯 أهداف C/F جديدة غير مراسَلة ولم تُعرض سابقاً:")
    if leads["priority_cf"]:
        for p in leads["priority_cf"]:
            L.append(f"- **[{p['grade']} · {p['sector']}] `{p['domain']}`** (`{p['tls']}` / `{p['group'] or 'classical'}`) — [صفحة النتيجة]({p['site_url']}) · [الملخص التنفيذي]({p['brief_url']})")
    else:
        L.append("- تم عرض جميع أهداف C/F الحالية خلال آخر 30 يوماً.")
    L.append("")

    L += ["---", "", "## 5️⃣ موظف الظهور في البحث والذكاء الاصطناعي (GEO / الأخبار الجديدة)"]
    news = geo["news"]
    if news["updated"]:
        L.append(f"- ✅ **تغذية أخبار PQC:** حُدّثت بنجاح ({news['items']} خبرًا من NIST/IBM/Google/Cloudflare/arXiv).")
    elif news["error"]:
        L.append(f"- ⚠️ **تغذية أخبار PQC:** تعذّر التحديث ({news['error']}).")
    else:
        L.append("- ℹ️ **تغذية أخبار PQC:** تخطّي التحديث في وضع الاختبار.")
    fresh_news = news.get("fresh_items") or []
    if fresh_news:
        L.append("- **أخبار PQC جديدة لم تُعرض سابقاً:**")
        for it in fresh_news:
            L.append(f"  - [{it.get('source', 'PQC')}] {it.get('title', '')} — {it.get('url', '')}")
    fams = geo["crawlers"].get("families") or []
    if fams:
        summary_str = " · ".join(f"{f['family']}={f['hits']}" for f in fams[:6])
        L.append(f"- **زواحف البحث/AI الموثّقة (آخر 7 أيام):** {summary_str}")
    else:
        L.append("- **زواحف البحث/AI الموثّقة:** لا بيانات مسجّلة بعد.")
    L.append("")
    L += ["—", "Quantum Aether Team", ""]
    return "\n".join(L)


def run(
    data_dir: str | None = None,
    refresh_news: bool = True,
    send_email: bool = True,
    today: dt.date | None = None,
    record_history: bool = True,
) -> dict:
    data_dir = data_dir or os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas")
    today = today or dt.datetime.now(dt.timezone.utc).date()
    today_iso = today.isoformat()
    yesterday = (today - dt.timedelta(days=1)).isoformat()
    db_path = os.path.join(data_dir, "quantum_saas.db")

    history = load_history(data_dir, today)

    c = conn_ro(db_path)
    try:
        radar_drafts = employee_radar_replies(c, seen_urls=set(history["radar_urls"]))
        dj = employee_data_journalist(c, today=today, shown_regressions=set(history["regression_keys"]))
        badges = employee_badge_shoutouts(
            c, dj.get("week") or "", dj.get("upgrades") or [],
            shown_domains=set(history["shoutout_domains"]),
        )
        leads = employee_b2b_leads(
            c, dj.get("week") or "", yesterday,
            shown_domains=set(history["priority_cf_domains"]),
            today=today,
        )
    finally:
        c.close()

    geo = employee_geo_freshness(
        data_dir, refresh_news=refresh_news, seen_news_urls=set(history["news_urls"])
    )
    brief = render_brief(today_iso, radar_drafts, dj, badges, leads, geo)

    out_dir = Path(data_dir) / "marketing_briefs"
    out_dir.mkdir(parents=True, exist_ok=True)
    dated_path = out_dir / f"{today_iso}.md"
    latest_path = out_dir / "latest.md"
    dated_path.write_text(brief, encoding="utf-8")
    latest_path.write_text(brief, encoding="utf-8")

    if record_history:
        for d in radar_drafts:
            history["radar_urls"][d["url"]] = today_iso
        for it in geo["news"].get("fresh_items") or []:
            if it.get("url"):
                history["news_urls"][it["url"]] = today_iso
        wk = dj.get("week") or ""
        for r in dj.get("regressions") or []:
            history["regression_keys"][f"{wk}:{r['domain']}"] = today_iso
        for b in badges:
            history["shoutout_domains"][b["domain"].lower()] = today_iso
        for p in leads.get("priority_cf") or []:
            history["priority_cf_domains"][p["domain"].lower()] = today_iso
        save_history(data_dir, history)

    emailed = False
    if send_email:
        owner = os.environ.get("QS_OWNER_EMAIL", "")
        mailer = Mailer(
            os.environ.get("RESEND_API_KEY", ""),
            mail_from_with_team_name(os.environ.get("QS_MAIL_FROM", "")),
            fallback_sender=mail_from_with_team_name(os.environ.get("QS_MAIL_FROM_FALLBACK", "")),
            site_url=os.environ.get("QS_PUBLIC_URL", SITE),
        )
        if owner and mailer.enabled:
            emailed = bool(mailer.send(owner, f"[Quantum Aether] حزمة التسويق اليومية {today_iso}", brief))

    return {
        "day": today_iso,
        "path": str(dated_path),
        "latest": str(latest_path),
        "emailed": emailed,
        "news_items": geo["news"].get("items", 0),
        "radar_count": len(radar_drafts),
        "priority_leads": len(leads["priority_cf"]),
        "brief": brief,
    }


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    no_email = "--no-email" in argv or "--dry-run" in argv
    no_news = "--no-news" in argv
    dry_run = "--dry-run" in argv
    res = run(refresh_news=not no_news, send_email=not no_email, record_history=not dry_run)
    log.info("marketing_desk done: path=%s emailed=%s news=%d radar=%d leads=%d",
             res["path"], res["emailed"], res["news_items"], res["radar_count"], res["priority_leads"])
    if "--print" in argv:
        print(res["brief"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
