#!/usr/bin/env python3
"""marketing_desk.py — غرفة عمليات التسويق الآلية (5 موظفي تسويق أخلاقيين 24/7).

قراءة فقط من قاعدة البيانات + تحديث تغذية أخبار PQC في DATA_DIR + توليد حزمة تسويق يومية جاهزة للنشر
في /var/lib/quantum_saas/marketing_briefs/YYYY-MM-DD.md وإرسالها للمالك فقط.
لا يرسل أي بريد لعملاء خارجيين ولا ينشر سباماً على أي منصة خارجية أبداً.
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
from mailer import Mailer

log = logging.getLogger("quantum_saas.marketing_desk")

SITE = "https://ather-quantum.com"

TEAM_FROM_NAME = "Quantum Aether Team"


def mail_from_with_team_name(raw: str) -> str:
    """Keep the address from QS_MAIL_FROM; set the display name to Quantum Aether Team."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if "<" in raw and ">" in raw:
        addr = raw.split("<", 1)[1].rsplit(">", 1)[0].strip()
    else:
        addr = raw
    return f"{TEAM_FROM_NAME} <{addr}>" if addr else ""


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


def conn_ro(db_path: str) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


# ---------------------------------------------------------------- Employee 1: Intent Radar Reply Drafter
def employee_radar_replies(c: sqlite3.Connection, limit: int = 4) -> list[dict]:
    """يقرأ أعلى النقاشات الساخنة من radar_seen ويجهّز لكل منها مسودة رد تقني مفيد وجاهز للنسخ."""
    try:
        rows = c.execute(
            "SELECT url, source, title, topic, intent, stack, score, found_at "
            "FROM radar_seen ORDER BY found_at DESC, score DESC LIMIT ?",
            (limit,),
        ).fetchall()
    except sqlite3.Error:
        return []
    drafts = []
    for r in rows:
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
            "url": r["url"],
            "intent": intent,
            "reply": reply,
        })
    return drafts


# ---------------------------------------------------------------- Employee 2: Data Journalist & Content Studio
def employee_data_journalist(c: sqlite3.Connection) -> dict:
    """يحلل أحدث مسح أسبوعي ويستخرج القصص الإخبارية (أضعف القطاعات، التراجعات الصامتة، الترقيات الجديدة)."""
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

    regressions, upgrades = [], []
    if prev_wk:
        for r in c.execute(
            "SELECT cur.domain, cur.sector, prev.grade AS old_g, cur.grade AS new_g "
            "FROM adoption_results cur JOIN adoption_results prev "
            "ON cur.domain = prev.domain AND prev.week = ? "
            "WHERE cur.week = ? AND cur.ok = 1 AND prev.ok = 1 AND cur.unsure = 0 AND prev.unsure = 0 "
            "AND prev.pq = 1 AND cur.pq = 0 ORDER BY cur.sector IS NULL, cur.domain LIMIT 10",
            (prev_wk, wk),
        ):
            regressions.append(dict(r))
        for r in c.execute(
            "SELECT cur.domain, cur.sector, prev.grade AS old_g, cur.grade AS new_g "
            "FROM adoption_results cur JOIN adoption_results prev "
            "ON cur.domain = prev.domain AND prev.week = ? "
            "WHERE cur.week = ? AND cur.ok = 1 AND prev.ok = 1 AND cur.unsure = 0 AND prev.unsure = 0 "
            "AND prev.pq = 0 AND cur.pq = 1 ORDER BY cur.sector IS NULL, cur.domain LIMIT 10",
            (prev_wk, wk),
        ):
            upgrades.append(dict(r))

    # Build ready-to-post social drafts
    mena = next((s for s in sectors if s["sector"] == "banks-mena"), sectors[0] if sectors else None)
    dach_ins = next((s for s in sectors if s["sector"] == "health-insurance-dach"), sectors[0] if sectors else None)
    weak3 = sectors[:3]

    ar_post = ""
    if mena:
        ar_post = (
            f"📊 بيانات جديدة من مسح {ok_n:,} موقعًا عالميًا ({wk}):\n"
            f"• {mena['not_pq_pct']}% من بنوك الشرق الأوسط وشمال إفريقيا ما زالت تستخدم التشفير التقليدي فقط "
            f"(منها {mena['cf']} بنكًا بدرجة C أو F) — قبل أسابيع من موعد تعميم البنك المركزي السعودي (ساما) في 31 ديسمبر 2026.\n"
            f"• عالميًا وصل تبني X25519MLKEM768 إلى {pq_pct}%.\n\n"
            f"هل نطاق مؤسستك ونطاقاتها الفرعية جاهزة؟ فحص فوري مجاني (بدون تسجيل):\n"
            f"{SITE}/?lang=ar\n"
            f"تقرير التبني الكامل: {SITE}/adoption?lang=ar\n"
            "#الأمن_السيبراني #التشفير_ما_بعد_الكم #ساما #PQC #TLS"
        )

    weak_lines_en = "\n".join(
        f"- {SECTOR_LABELS.get(s['sector'], (s['sector'], s['sector'], s['sector']))[1]}: "
        f"{s['pct']}% PQ-ready ({s['not_pq_pct']}% still classical, {s['cf']} Grade C/F)"
        for s in weak3
    )
    en_post = (
        f"New weekly Post-Quantum TLS telemetry ({wk}, {ok_n:,} public hosts measured):\n\n"
        f"Global X25519MLKEM768 adoption is now {pq_pct}%, yet regulated sectors still lag behind:\n"
        f"{weak_lines_en}\n\n"
        + (f"We also detected {len(regressions)} silent PQ-TLS regressions this week (domains that dropped from hybrid PQ back to classical).\n\n" if regressions else "")
        + f"Check your primary domain free (1 handshake, no signup): {SITE}/\n"
        f"Full open dataset + weekly tracker: {SITE}/adoption\n"
        "#PostQuantum #TLS #InfoSec #DORA #NIS2 #MLKEM"
    )

    de_post = ""
    if dach_ins:
        de_post = (
            f"📊 Neue Messdaten zur Post-Quanten-TLS-Bereitschaft ({wk}, {ok_n:,} geprüfte Hosts):\n"
            f"• Global nutzen bereits {pq_pct}% X25519MLKEM768.\n"
            f"• Bei den {SECTOR_LABELS.get(dach_ins['sector'], ('', '', dach_ins['sector']))[2]} liegt die Quote erst bei {dach_ins['pct']}% "
            f"({dach_ins['not_pq_pct']}% noch rein klassisch — relevant für NIS2 & DORA).\n\n"
            f"Kostenloser Schnellcheck ohne Registrierung: {SITE}/?lang=de\n"
            f"Wöchentlicher Tracker: {SITE}/adoption?lang=de\n"
            "#PostQuantum #Cybersicherheit #NIS2 #DORA #TLS"
        )

    x_thread = [
        f"1/ We just finished our {wk} Post-Quantum TLS scan across {ok_n:,} public hosts: {pq_pct}% now negotiate hybrid X25519MLKEM768. Full open tracker: {SITE}/adoption",
        "2/ The biggest gaps are in regulated paying sectors:\n" + "\n".join(
            f"• {SECTOR_LABELS.get(s['sector'], (s['sector'], s['sector'], s['sector']))[1]}: {s['pct']}% PQ ({s['cf']} C/F)"
            for s in weak3
        ),
        f"3/ Even teams that enabled PQ can silently regress after a CDN/load-balancer change. Test your domain free (no login) or start a 14-day daily monitor: {SITE}/monitoring",
    ]

    return {
        "week": wk, "prev_week": prev_wk, "ok": ok_n, "pq": pq_n, "pq_pct": pq_pct, "cf": ov["cf_n"] or 0,
        "weakest_sectors": sectors[:5], "regressions": regressions, "upgrades": upgrades,
        "drafts": {"linkedin_ar": ar_post, "linkedin_en": en_post, "linkedin_de": de_post, "x_thread": x_thread},
    }


# ---------------------------------------------------------------- Employee 3: Viral Grade-A Badge Shoutouts
def employee_badge_shoutouts(c: sqlite3.Connection, week: str, upgrades: list[dict], limit: int = 5) -> list[dict]:
    """يختار مؤسسات حاصلة على الدرجة A (يفضّل الترقيات الجديدة) لتجهيز منشورات تهنئة مع شارة A المجانية."""
    chosen = []
    seen = set()
    for u in upgrades:
        if u.get("new_g") == "A" and u["domain"] not in seen:
            seen.add(u["domain"])
            chosen.append((u["domain"], u.get("sector") or "newly-upgraded", True))
            if len(chosen) >= limit:
                break
    if len(chosen) < limit and week:
        ph = ",".join("?" for _ in PAY_SECTORS)
        for r in c.execute(
            f"SELECT domain, sector FROM adoption_results "
            f"WHERE week=? AND ok=1 AND pq=1 AND grade='A' AND sector IN ({ph}) "
            f"ORDER BY RANDOM() LIMIT ?",
            (week, *PAY_SECTORS, limit - len(chosen)),
        ):
            if r["domain"] not in seen:
                seen.add(r["domain"])
                chosen.append((r["domain"], r["sector"], False))
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
def employee_b2b_leads(c: sqlite3.Connection, week: str, day: str, limit: int = 8) -> dict:
    """يلتقط العملاء الساخنين (زيارة/فحص أمس) + أعلى أهداف C/F غير المراسَلة من القطاعات المدفوعة."""
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

    # 2) Top priority uncontacted C/F domains in paying sectors
    ph = ",".join("?" for _ in PAY_SECTORS)
    priority = []
    if week:
        for r in c.execute(
            f"SELECT domain, sector, grade, grp, tls FROM adoption_results "
            f"WHERE week=? AND ok=1 AND pq=0 AND unsure=0 AND grade IN ('F','C') AND sector IN ({ph}) "
            f"ORDER BY CASE grade WHEN 'F' THEN 0 ELSE 1 END, "
            f"CASE sector WHEN 'banks-mena' THEN 0 WHEN 'banks-dach' THEN 1 WHEN 'banks-europe' THEN 2 "
            f"WHEN 'telecom' THEN 3 ELSE 4 END, domain LIMIT ?",
            (week, *PAY_SECTORS, limit * 2),
        ):
            base = r["domain"].lower().removeprefix("www.")
            if base in skip or ".gov" in base:
                continue
            skip.add(base)
            priority.append({
                "domain": base, "grade": r["grade"], "sector": r["sector"],
                "tls": r["tls"], "group": r["grp"],
                "site_url": f"{SITE}/site/{base}", "brief_url": f"{SITE}/executive-brief/{base}",
            })
            if len(priority) >= limit:
                break
    return {"inbound_hot": inbound, "priority_cf": priority}


# ---------------------------------------------------------------- Employee 5: GEO / AI Search Freshness
def employee_geo_freshness(data_dir: str, refresh_news: bool = True) -> dict:
    """يحدّث تغذية أخبار PQC في DATA_DIR لتبقى الصفحات متجددة لزواحف Google/OpenAI ويلخص حركة الزواحف."""
    news_status = {"updated": False, "items": 0, "error": None}
    if refresh_news:
        try:
            out_path = Path(data_dir) / "news_feed.json"
            prev_out = generate_pqc_news.OUTPUT
            generate_pqc_news.OUTPUT = out_path
            try:
                rc = generate_pqc_news.main()
            finally:
                generate_pqc_news.OUTPUT = prev_out
            if rc == 0 and out_path.exists():
                doc = json.loads(out_path.read_text(encoding="utf-8"))
                news_status = {"updated": True, "items": len(doc.get("items", [])), "updated_at": doc.get("updated_at"), "error": None}
            else:
                news_status["error"] = f"feed_refresh_rc_{rc}"
        except Exception as exc:
            news_status["error"] = f"{type(exc).__name__}: {exc}"[:140]
            log.warning("PQC news refresh failed: %s", news_status["error"])
    crawlers = crawler_log.summary(data_dir, days=7)
    return {"news": news_status, "crawlers": crawlers}


# ---------------------------------------------------------------- Render Daily Markdown Brief
def render_brief(day: str, radar_drafts: list[dict], dj: dict, badges: list[dict], leads: dict, geo: dict) -> str:
    L = [
        f"# Quantum Aether — حزمة موظفي التسويق اليومية ({day})",
        "",
        "> توليد آلي 100% أخلاقي (بدون إرسال خارجي ولا سبام). انسخ وانشر ما يناسبك خلال دقيقتين.",
        "",
        "---",
        "",
        "## 1️⃣ موظف صائد النقاشات الساخنة (GitHub / HN — ردود تقنية جاهزة)",
    ]
    if radar_drafts:
        for i, d in enumerate(radar_drafts, 1):
            L += [
                f"### {i}. [{d['source']} · {d['score']}/100] {d['title']}",
                f"- الرابط: {d['url']}",
                f"- **مسودة الرد المقترح:**",
                f"> {d['reply']}",
                "",
            ]
    else:
        L += ["لا توجد نقاشات جديدة في الرادار اليوم.", ""]

    L += ["---", "", "## 2️⃣ موظف الصحفي البياني (منشورات جاهزة بأرقام الأسبوع)"]
    if dj.get("week"):
        L += [
            f"- **الأسبوع:** `{dj['week']}` | **المفحوص بنجاح:** {dj['ok']:,} | **جاهز للكم (PQ):** {dj['pq']:,} ({dj['pq_pct']}%) | **درجة C/F:** {dj['cf']:,}",
            "",
            "### LinkedIn (عربي — بنوك الخليج / ساما)",
            "```text",
            dj["drafts"]["linkedin_ar"],
            "```",
            "",
            "### LinkedIn (English — EU DORA / NIS2 / Global)",
            "```text",
            dj["drafts"]["linkedin_en"],
            "```",
            "",
            "### LinkedIn (Deutsch — DACH)",
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
            L.append("### ⚠️ تراجعات صامتة مكتشفة هذا الأسبوع (أقوى قصص بيع للمراقبة)")
            for r in dj["regressions"]:
                L.append(f"- `{r['domain']}` ({r['sector'] or 'top'}): هبط من `{r['old_g']}` إلى `{r['new_g']}`")
            L.append("")
    else:
        L += ["لا توجد بيانات أسبوعية بعد.", ""]

    L += ["---", "", "## 3️⃣ موظف الشارات الفيروسية (تهنئة أصحاب الدرجة A لـ Backlinks)"]
    if badges:
        for b in badges:
            L.append(f"- **{b['domain']}** ({b['sector']}): {b['shoutout']}")
    else:
        L.append("لا توجد عناصر اليوم.")
    L.append("")

    L += ["---", "", "## 4️⃣ موظف أبحاث العملاء B2B (أهداف غير جاهزة للكم — بدون إرسال تلقائي)"]
    if leads["inbound_hot"]:
        L.append("### 🔥 زاروا موقعك أو فحصوا أمس (أولوية قصوى):")
        for h in leads["inbound_hot"]:
            L.append(f"- **[{h['grade']} · {h['sector']}] `{h['domain']}`** ({h['hits']} تفاعل) — {h['brief']}")
    else:
        L.append("- لا زيارات واردة من قطاعات مدفوعة (B/C/F) أمس.")
    L.append("")
    L.append("### 🎯 أبرز أهداف C/F غير المراسَلة:")
    for p in leads["priority_cf"]:
        L.append(f"- **[{p['grade']} · {p['sector']}] `{p['domain']}`** (`{p['tls']}` / `{p['group'] or 'classical'}`) — [صفحة النتيجة]({p['site_url']}) · [الملخص التنفيذي]({p['brief_url']})")
    L.append("")

    L += ["---", "", "## 5️⃣ موظف الظهور في البحث والذكاء الاصطناعي (GEO / Crawlers)"]
    news = geo["news"]
    if news["updated"]:
        L.append(f"- ✅ **تغذية أخبار PQC:** حُدّثت بنجاح ({news['items']} خبرًا من NIST/IBM/Google/Cloudflare/arXiv).")
    elif news["error"]:
        L.append(f"- ⚠️ **تغذية أخبار PQC:** تعذّر التحديث ({news['error']}).")
    else:
        L.append("- ℹ️ **تغذية أخبار PQC:** تخطّي التحديث في وضع الاختبار.")
    fams = geo["crawlers"].get("families") or []
    if fams:
        summary_str = " · ".join(f"{f['family']}={f['hits']}" for f in fams[:6])
        L.append(f"- **زواحف البحث/AI الموثّقة (آخر 7 أيام):** {summary_str}")
    else:
        L.append("- **زواحف البحث/AI الموثّقة:** لا بيانات مسجّلة بعد.")
    L.append("")
    L += ["—", "Quantum Aether Team", ""]
    return "\n".join(L)


def run(data_dir: str | None = None, refresh_news: bool = True, send_email: bool = True, today: dt.date | None = None) -> dict:
    data_dir = data_dir or os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas")
    today = today or dt.datetime.now(dt.timezone.utc).date()
    yesterday = (today - dt.timedelta(days=1)).isoformat()
    db_path = os.path.join(data_dir, "quantum_saas.db")

    c = conn_ro(db_path)
    try:
        radar_drafts = employee_radar_replies(c)
        dj = employee_data_journalist(c)
        badges = employee_badge_shoutouts(c, dj.get("week") or "", dj.get("upgrades") or [])
        leads = employee_b2b_leads(c, dj.get("week") or "", yesterday)
    finally:
        c.close()

    geo = employee_geo_freshness(data_dir, refresh_news=refresh_news)
    brief = render_brief(today.isoformat(), radar_drafts, dj, badges, leads, geo)

    out_dir = Path(data_dir) / "marketing_briefs"
    out_dir.mkdir(parents=True, exist_ok=True)
    dated_path = out_dir / f"{today.isoformat()}.md"
    latest_path = out_dir / "latest.md"
    dated_path.write_text(brief, encoding="utf-8")
    latest_path.write_text(brief, encoding="utf-8")

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
            emailed = bool(mailer.send(owner, f"[Quantum Aether] حزمة التسويق اليومية {today.isoformat()}", brief))

    return {
        "day": today.isoformat(),
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
    res = run(refresh_news=not no_news, send_email=not no_email)
    log.info("marketing_desk done: path=%s emailed=%s news=%d radar=%d leads=%d",
             res["path"], res["emailed"], res["news_items"], res["radar_count"], res["priority_leads"])
    if "--print" in argv:
        print(res["brief"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
