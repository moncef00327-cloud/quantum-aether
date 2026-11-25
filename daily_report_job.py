# يرسل تقريراً يومياً للمالك (quantum_daily_report.timer، 06:00). قراءة فقط من قاعدة البيانات.
# يغطّي يوم أمس (UTC): الزيارات، الفحوصات بالدرجات، قمع التحويل، أثر البريد، التسجيلات الجديدة.
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
import sys

from mailer import Mailer


def _prospect_history_path():
    return Path(os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas")) / "marketing_briefs" / "daily_report_history.json"


def _load_shown_prospects(day: str, ttl_days: int = 7) -> dict:
    p = _prospect_history_path()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
    except Exception:
        return {}
    cutoff = (dt.date.fromisoformat(day) - dt.timedelta(days=ttl_days)).isoformat()
    return {str(k).lower(): str(v) for k, v in raw.items() if str(v) >= cutoff}


def _save_shown_prospects(shown: dict) -> None:
    try:
        p = _prospect_history_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(shown, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, p)
    except OSError:
        pass


def conn_ro():
    db = os.path.join(os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas"), "quantum_saas.db")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def one(c, sql, a=()):
    r = c.execute(sql, a).fetchone()
    return (r[0] if r else 0) or 0


SITE = "https://ather-quantum.com"
PAY_SECTORS = ("banks-europe", "banks-mena", "banks-dach", "banks-americas-apac", "finance-worldwide",
               "payments-fintech", "crypto-exchanges", "health-insurance-dach", "telecom",
               "enterprise-saas-b2b", "companies-dach", "global-insurance-healthcare", "cloud-security")


def prospects_today(c, day, shown_recently=None):
    """عملاء محتملون جدد: مؤسسة في قطاع يدفع، درجة B/C/F، أظهرت اهتماماً أمس، ولم نراسلها ولم تُعرض آخر 7 أيام."""
    try:
        wk = c.execute("SELECT MAX(week) FROM adoption_results").fetchone()[0]
    except Exception:
        return []
    contacted = set(shown_recently or ())
    for tbl in ("contacted_orgs", "outreach_sent", "outreach_suppress", "adoption_optout"):
        try:
            contacted |= {r[0].lower().removeprefix("www.") for r in c.execute(f"SELECT domain FROM {tbl}") if r[0]}
        except Exception:
            pass

    def grade_sector(dom):
        for dd in (dom, "www." + dom):
            r = c.execute("SELECT grade,sector,pq FROM adoption_results WHERE week=? AND domain=?", (wk, dd)).fetchone()
            if r:
                return r[0], r[1], r[2]
        return None, None, None

    views = {}
    for prefix in ("/site/", "/exposure/", "/executive-brief/"):
        for path, n in c.execute("SELECT path,COUNT(*) FROM pageviews WHERE day=? AND is_bot=0 AND is_test=0 "
                                 "AND path LIKE ? GROUP BY path", (day, prefix + "%")):
            dom = path.split(prefix, 1)[1].split("?")[0].strip("/").lower()
            if dom.startswith("www."):
                dom = dom[4:]
            if dom and "." in dom:
                views[dom] = views.get(dom, 0) + n
    for dom, n in c.execute("SELECT domain,COUNT(*) FROM scans WHERE substr(created_at,1,10)=? AND is_test=0 "
                            "GROUP BY domain", (day,)):
        d = (dom or "").strip().lower()
        if d.startswith("www."):
            d = d[4:]
        if d and "." in d:
            views[d] = views.get(d, 0) + n * 2
    out = []
    for dom, v in views.items():
        if dom in contacted or ".gov" in dom:
            continue
        g, sec, pq = grade_sector(dom)
        if g in ("B", "C", "F") and not pq and sec in PAY_SECTORS:
            out.append((v, g, dom, sec))
    out.sort(key=lambda x: (0 if x[1] in ("F", "C") else 1, -x[0]))
    return out


def build(c, day, shown_recently=None, out_prospects=None):
    y = day
    L = [f"Quantum Aether — التقرير اليومي ليوم {y} (UTC)", "=" * 48, ""]

    # 0) عملاء محتملون اليوم (الأهم — دون تكرار من الأيام الـ 7 السابقة)
    prospects = prospects_today(c, y, shown_recently=shown_recently)
    if out_prospects is not None:
        out_prospects.extend(dom for _, _, dom, _ in prospects)
    L.append("🎯 عملاء محتملون اليوم (مؤسسة تدفع · B/C/F غير جاهزة · أظهرت اهتماماً · لم نراسلها):")
    if prospects:
        for v, g, dom, sec in prospects:
            L.append(f"    [{g} · {sec} · {v} تفاعل] {dom}  →  security@{dom}  ·  {SITE}/site/{dom}")
        L.append("    العرض: ابدأ المراقبة الدائمة (14 يوماً مجاناً). راسِل security@ أو أرفق رابط النتيجة.")
    else:
        L.append("    لا عميل محتمل جديد ضمن المعايير أمس.")
    L.append("")

    # 1) الزيارات والفحوصات (مع فصل ضوضاء /scanning عن الزيارات البشرية الصافية)
    pv_all = one(c, "SELECT COUNT(*) FROM pageviews WHERE day=? AND is_bot=0 AND is_test=0", (y,))
    pv_scan_info = one(c, "SELECT COUNT(*) FROM pageviews WHERE day=? AND is_bot=0 AND is_test=0 AND path='/scanning'", (y,))
    pv = pv_all - pv_scan_info
    uniq = one(c, "SELECT COUNT(DISTINCT visitor) FROM pageviews WHERE day=? AND is_bot=0 AND is_test=0 AND path != '/scanning'", (y,))
    scans = one(c, "SELECT COUNT(*) FROM scans WHERE substr(created_at,1,10)=? AND is_test=0", (y,))
    L += ["• الحركة:", f"    زيارات بشرية صافية: {pv}  |  زوّار متفرّدون: {uniq}  |  فحوصات: {scans}  (مستبعد /scanning: {pv_scan_info})"]
    grades = c.execute("SELECT grade,COUNT(*) n FROM scans WHERE substr(created_at,1,10)=? AND is_test=0 "
                       "AND grade IS NOT NULL GROUP BY grade ORDER BY grade", (y,)).fetchall()
    if grades:
        L.append("    حسب الدرجة: " + "  ".join(f"{r['grade']}={r['n']}" for r in grades))
    L.append("")

    # 2) قمع التحويل والمدفوعات
    imp = one(c, "SELECT COUNT(*) FROM events WHERE day=? AND name='offer_impression' AND is_bot=0 AND is_test=0", (y,))
    starts = one(c, "SELECT COUNT(*) FROM events WHERE day=? AND name IN ('trial_start','trial_cta_clicked','trial_created') AND is_bot=0 AND is_test=0", (y,))
    rate = f"{(starts / imp * 100):.0f}%" if imp else "—"
    paid_orders = one(c, "SELECT COUNT(*) FROM orders WHERE substr(created_at,1,10)=? AND is_test=0 AND status IN ('COMPLETED','PAID')", (y,))
    try:
        x402_n = one(c, "SELECT COUNT(*) FROM x402_payments WHERE substr(created_at,1,10)=?", (y,))
    except Exception:
        x402_n = 0
    L += ["• قمع التحويل والمدفوعات:",
          f"    انطباعات العرض: {imp}  →  بدء/نقر تجربة: {starts}  (معدّل: {rate})",
          f"    طلبات مدفوعة مكتملة: {paid_orders}  |  مدفوعات x402: {x402_n}", ""]

    # 3) أثر حملات البريد (زيارات واردة من روابط البريد)
    em = c.execute("SELECT path,COUNT(*) n FROM pageviews WHERE day=? AND is_test=0 "
                   "AND (referrer LIKE 'utm:email%' OR referrer LIKE '%email%') GROUP BY path ORDER BY n DESC LIMIT 8", (y,)).fetchall()
    L.append("• أثر البريد (زيارات من روابط حملاتنا):")
    if em:
        for r in em:
            L.append(f"    {r['n']:>2}× {r['path']}")
    else:
        L.append("    لا زيارات من البريد اليوم.")
    L.append("")

    # 4) تسجيلات/طلبات جديدة
    mon = c.execute("SELECT email,plan,status FROM monitor_accounts WHERE substr(created_at,1,10)=?", (y,)).fetchall()
    aud = c.execute("SELECT org,domain,email FROM audit_requests WHERE substr(created_at,1,10)=? AND is_test=0", (y,)).fetchall()
    L.append("• تسجيلات جديدة:")
    if mon:
        for r in mon:
            L.append(f"    [مراقبة/{r['plan']}·{r['status']}] {r['email']}")
    if aud:
        for r in aud:
            L.append(f"    [طلب تدقيق] {r['org'] or ''} {r['domain'] or ''} — {r['email']}")
    if not mon and not aud:
        L.append("    لا تسجيلات جديدة اليوم.")
    L.append("")

    # 5) أعلى صفحات /site زيارةً أمس
    top = c.execute("SELECT path,COUNT(*) n FROM pageviews WHERE day=? AND is_bot=0 AND is_test=0 "
                    "AND path LIKE '/site/%' GROUP BY path ORDER BY n DESC LIMIT 8", (y,)).fetchall()
    L.append("• أكثر النطاقات اهتماماً أمس (/site):")
    if top:
        for r in top:
            L.append(f"    {r['n']:>2}× {r['path'].split('/site/')[-1]}")
    else:
        L.append("    لا زيارات لصفحات النطاقات أمس.")
    L.append("")

    # 6) اتجاه 7 أيام (زيارات/فحوصات)
    L.append("• اتجاه 7 أيام (زيارات بشرية | فحوصات):")
    trend = []
    for i in range(6, -1, -1):
        d = (dt.date.fromisoformat(y) - dt.timedelta(days=i)).isoformat()
        p = one(c, "SELECT COUNT(*) FROM pageviews WHERE day=? AND is_bot=0 AND is_test=0", (d,))
        s = one(c, "SELECT COUNT(*) FROM scans WHERE substr(created_at,1,10)=? AND is_test=0", (d,))
        trend.append((d, p, s))
    peak = max((p for _, p, _ in trend), default=0) or 1
    for d, p, s in trend:
        bar = "█" * (round(30 * p / peak) if p else 0)
        L.append(f"    {d}  {p:>4} | {s:>3}  {bar}")
    L.append("")
    # 7) نشاط المراسلات والوارد والإيصالات الموقّعة أمس
    try:
        sent_y = one(c, "SELECT COUNT(*) FROM outreach_sent WHERE substr(sent_at,1,10)=?", (y,))
        bounced_y = one(c, "SELECT COUNT(*) FROM outreach_sent WHERE substr(sent_at,1,10)=? AND last_event='bounced'", (y,))
    except Exception:
        sent_y = bounced_y = 0
    try:
        inbound_rows = c.execute("SELECT subject FROM inbound_mail WHERE substr(received_at,1,10)=? ORDER BY received_at DESC LIMIT 5", (y,)).fetchall()
    except Exception:
        inbound_rows = []
    try:
        rcpt_y = one(c, "SELECT COUNT(*) FROM receipts WHERE date(iat,'unixepoch')=?", (y,))
    except Exception:
        rcpt_y = 0
    try:
        a2a_y = one(c, "SELECT COUNT(*) FROM a2a_outreach_sent WHERE substr(sent_at,1,10)=? AND http_status BETWEEN 200 AND 299", (y,))
        a2a_all = one(c, "SELECT COUNT(*) FROM a2a_outreach_sent WHERE http_status BETWEEN 200 AND 299")
        a2a_replies = c.execute(
            "SELECT agent_name, host, reply_excerpt FROM a2a_outreach_sent "
            "WHERE substr(sent_at,1,10)=? AND http_status BETWEEN 200 AND 299 AND reply_excerpt != '' "
            "ORDER BY sent_at DESC LIMIT 3",
            (y,),
        ).fetchall()
    except Exception:
        a2a_y = a2a_all = 0
        a2a_replies = []
    L += ["• المراسلات والإيصالات الموقّعة أمس:",
          f"    رسائل outreach مرسلة: {sent_y} (ارتداد: {bounced_y})  |  حملة A2A: {a2a_y} (الإجمالي: {a2a_all})  |  إيصالات موقّعة v1: {rcpt_y}  |  ردود بريد: {len(inbound_rows)}"]
    for ir in inbound_rows:
        L.append(f"    ↩ {(ir['subject'] or '(بدون عنوان)')[:90]}")
    for ar in a2a_replies:
        L.append(f"    🤖 [{ar['agent_name'] or ar['host']}] {(ar['reply_excerpt'] or '')[:90]}")
    L.append("")

    # 8) شهادات التدقيق المدفوعة والشركاء وطلبات البايلوت (قراءة فقط من SQLite)
    try:
        att_y = one(c, "SELECT COUNT(*) FROM x402_attestations WHERE substr(issued_at,1,10)=?", (y,))
        att_all = one(c, "SELECT COUNT(*) FROM x402_attestations")
    except Exception:
        att_y = att_all = 0
    try:
        p_clicks = c.execute("SELECT code, n FROM partner_clicks WHERE day=? ORDER BY n DESC, code LIMIT 10", (y,)).fetchall()
    except Exception:
        p_clicks = []
    try:
        p_new = one(c, "SELECT COUNT(*) FROM partners WHERE substr(created_at,1,10)=?", (y,))
        p_active = one(c, "SELECT COUNT(*) FROM partners WHERE status='ACTIVE'")
    except Exception:
        p_new = p_active = 0
    try:
        pilot_y = one(c, "SELECT COUNT(*) FROM pilot_leads WHERE substr(created_at,1,10)=?", (y,))
        pilot_all = one(c, "SELECT COUNT(*) FROM pilot_leads")
    except Exception:
        pilot_y = pilot_all = 0
    clicks_str = " · ".join(f"{r['code']}={r['n']}" for r in p_clicks) if p_clicks else "لا نقرات"
    L += [
        "• شهادات التدقيق والشركاء (أمس):",
        f"    شهادات Attestation (5 USDC): {att_y} (الإجمالي: {att_all})  |  طلبات MSP Pilot (290 €): {pilot_y} (الإجمالي: {pilot_all})",
        f"    شركاء جدد: {p_new} (نشطون: {p_active})  |  نقرات روابط الشركاء: {clicks_str}",
        "",
    ]
    L.append("— تذكير: راجع الردود الواردة على reply@mail.ather-quantum.com أو في /admin.")
    return "\n".join(L)


def main():
    yesterday = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
    c = conn_ro()
    dry_run = "--dry-run" in sys.argv
    shown = _load_shown_prospects(yesterday)
    picked = []
    text = build(c, yesterday, shown_recently=set(shown), out_prospects=picked)
    print(text)
    owner = os.environ.get("QS_OWNER_EMAIL", "")
    mailer = Mailer(os.environ.get("RESEND_API_KEY", ""), os.environ.get("QS_MAIL_FROM", ""),
                    fallback_sender=os.environ.get("QS_MAIL_FROM_FALLBACK", ""),
                    site_url=os.environ.get("QS_PUBLIC_URL", ""))
    if owner and mailer.enabled and not dry_run:
        ok = mailer.send(owner, f"[Quantum Aether] تقرير يومي {yesterday}", text)
        print(f"\n[sent={ok} to {owner}]")
        if ok and picked:
            for dom in picked:
                shown[dom.lower()] = yesterday
            _save_shown_prospects(shown)
    else:
        print(f"\n[dry-run or disabled; owner={owner!r} enabled={mailer.enabled}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
