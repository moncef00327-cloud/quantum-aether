# يرسل تقريراً يومياً للمالك (quantum_daily_report.timer، 06:00). قراءة فقط من قاعدة البيانات.
# يغطّي يوم أمس (UTC): الزيارات، الفحوصات بالدرجات، قمع التحويل، أثر البريد، التسجيلات الجديدة.
import datetime as dt
import os
import sqlite3
import sys

from mailer import Mailer


def conn_ro():
    db = os.path.join(os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas"), "quantum_saas.db")
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def one(c, sql, a=()):
    r = c.execute(sql, a).fetchone()
    return (r[0] if r else 0) or 0


SITE = "https://ather-quantum.com"
PAY_SECTORS = ("banks-europe", "banks-mena", "banks-dach", "finance-worldwide",
               "payments-fintech", "crypto-exchanges", "health-insurance-dach", "telecom")


def prospects_today(c, day):
    """عملاء محتملون: مؤسسة في قطاع يدفع، درجة C/F، زارت صفحتها عندنا أمس، ولم نراسلها."""
    try:
        wk = c.execute("SELECT MAX(week) FROM adoption_results").fetchone()[0]
        contacted = {r[0] for r in c.execute("SELECT domain FROM contacted_orgs")}
    except Exception:
        return []

    def grade_sector(dom):
        for dd in (dom, "www." + dom):
            r = c.execute("SELECT grade,sector FROM adoption_results WHERE week=? AND domain=?", (wk, dd)).fetchone()
            if r:
                return r[0], r[1]
        return None, None

    views = {}
    for path, n in c.execute("SELECT path,COUNT(*) FROM pageviews WHERE day=? AND is_bot=0 AND is_test=0 "
                             "AND path LIKE '/site/%' GROUP BY path", (day,)):
        dom = path.split("/site/", 1)[1].split("?")[0].strip("/").lower()
        if dom.startswith("www."):
            dom = dom[4:]
        if dom and "." in dom:
            views[dom] = views.get(dom, 0) + n
    out = []
    for dom, v in views.items():
        if dom in contacted or ".gov" in dom:
            continue
        g, sec = grade_sector(dom)
        if g in ("C", "F") and sec in PAY_SECTORS:
            out.append((v, g, dom, sec))
    out.sort(key=lambda x: -x[0])
    return out


def build(c, day):
    y = day
    L = [f"Quantum Aether — التقرير اليومي ليوم {y} (UTC)", "=" * 48, ""]

    # 0) عملاء محتملون اليوم (الأهم)
    prospects = prospects_today(c, y)
    L.append("🎯 عملاء محتملون اليوم (مؤسسة تدفع · C/F · أظهرت اهتماماً · لم نراسلها):")
    if prospects:
        for v, g, dom, sec in prospects:
            L.append(f"    [{g} · {sec} · {v} زيارة] {dom}  →  security@{dom}  ·  {SITE}/site/{dom}")
        L.append("    العرض: ابدأ المراقبة الدائمة (14 يوماً مجاناً). راسِل security@ أو أرفق رابط النتيجة.")
    else:
        L.append("    لا عميل محتمل جديد ضمن المعايير أمس.")
    L.append("")

    # 1) الزيارات والفحوصات
    pv = one(c, "SELECT COUNT(*) FROM pageviews WHERE day=? AND is_bot=0 AND is_test=0", (y,))
    uniq = one(c, "SELECT COUNT(DISTINCT visitor) FROM pageviews WHERE day=? AND is_bot=0 AND is_test=0", (y,))
    scans = one(c, "SELECT COUNT(*) FROM scans WHERE substr(created_at,1,10)=? AND is_test=0", (y,))
    L += ["• الحركة:", f"    زيارات بشرية: {pv}  |  زوّار متفرّدون: {uniq}  |  فحوصات: {scans}"]
    grades = c.execute("SELECT grade,COUNT(*) n FROM scans WHERE substr(created_at,1,10)=? AND is_test=0 "
                       "AND grade IS NOT NULL GROUP BY grade ORDER BY grade", (y,)).fetchall()
    if grades:
        L.append("    حسب الدرجة: " + "  ".join(f"{r['grade']}={r['n']}" for r in grades))
    L.append("")

    # 2) قمع التحويل
    imp = one(c, "SELECT COUNT(*) FROM events WHERE day=? AND name='offer_impression' AND is_bot=0 AND is_test=0", (y,))
    starts = one(c, "SELECT COUNT(*) FROM events WHERE day=? AND name IN ('trial_start','trial_cta_clicked') AND is_bot=0 AND is_test=0", (y,))
    rate = f"{(starts / imp * 100):.0f}%" if imp else "—"
    L += ["• قمع التحويل:", f"    انطباعات العرض: {imp}  →  بدء/نقر تجربة: {starts}  (معدّل: {rate})", ""]

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
    L.append("— تذكير: راجع alerts@ather-quantum.com لردود/ارتدادات حملات البريد.")
    return "\n".join(L)


def main():
    yesterday = (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)).isoformat()
    c = conn_ro()
    text = build(c, yesterday)
    print(text)
    owner = os.environ.get("QS_OWNER_EMAIL", "")
    mailer = Mailer(os.environ.get("RESEND_API_KEY", ""), os.environ.get("QS_MAIL_FROM", ""),
                    fallback_sender=os.environ.get("QS_MAIL_FROM_FALLBACK", ""),
                    site_url=os.environ.get("QS_PUBLIC_URL", ""))
    if owner and mailer.enabled and "--dry-run" not in sys.argv:
        ok = mailer.send(owner, f"[Quantum Aether] تقرير يومي {yesterday}", text)
        print(f"\n[sent={ok} to {owner}]")
    else:
        print(f"\n[dry-run or disabled; owner={owner!r} enabled={mailer.enabled}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
