# scorecard.py
# «الواقع مقابل المحاكاة»: يقارن أرقام كل أسبوع منذ الإطلاق بالسيناريوهات الثلاثة التي حُسبت في 2026-11-04
# (محاكاة مونت كارلو لـ 12 شهراً). يجيب عن سؤال واحد: أي سيناريو نعيشه فعلاً؟
import datetime as dt
import math

LAUNCH = dt.date(2026, 11, 3)          # أول يوم بزوار حقيقيين
WEEKS_PER_MONTH = 4.345
COST_PER_MONTH = 63.0                   # تقدير: خادم + نطاق. عدّله حين تصل فاتورة Vultr الفعلية.

# visitors_m1, monthly growth, visitor→scan, scan→report, scan→subscription
SCENARIOS = {
    "pessimistic": {"label": "Pessimistic", "label_ar": "متشائم", "visitors": 300, "growth": 1.10,
                    "scan": 0.05, "report": 0.002, "sub": 0.001, "net_12m": -710},
    "realistic": {"label": "Realistic", "label_ar": "واقعي", "visitors": 1500, "growth": 1.20,
                  "scan": 0.15, "report": 0.004, "sub": 0.003, "net_12m": 4587},
    "optimistic": {"label": "Optimistic", "label_ar": "متفائل", "visitors": 5000, "growth": 1.25,
                   "scan": 0.20, "report": 0.008, "sub": 0.005, "net_12m": 55564},
}


def expected_week(scenario, week_index):
    """المتوقع لأسبوع (0 = أسبوع الإطلاق) حسب سيناريو."""
    month = week_index / WEEKS_PER_MONTH
    visitors = scenario["visitors"] * scenario["growth"] ** month / WEEKS_PER_MONTH
    scans = visitors * scenario["scan"]
    return {"visitors": visitors, "scans": scans, "reports": scans * scenario["report"], "subs": scans * scenario["sub"]}


def actual_weeks(conn, owner_email="", today=None):
    """أرقام حقيقية لكل أسبوع (7 أيام تبدأ من يوم الإطلاق)، دون الروبوتات وزيارات/طلبات المالك."""
    today = today or dt.date.today()
    weeks = []
    start = LAUNCH
    index = 0
    while start <= today:
        end = start + dt.timedelta(days=7)
        a, b = start.isoformat(), end.isoformat()
        one = lambda sql, *args: conn.execute(sql, args).fetchone()[0] or 0
        weeks.append({
            "index": index, "start": a, "partial_days": min(7, (today - start).days + 1),
            "visitors": one("SELECT COUNT(DISTINCT visitor || day) FROM pageviews WHERE is_bot = 0 AND is_test = 0 "
                            "AND day >= ? AND day < ?", a, b),
            "scans": one("SELECT COUNT(*) FROM scans WHERE is_test = 0 AND created_at >= ? AND created_at < ?", a, b),
            "reports": one("SELECT COUNT(*) FROM orders WHERE is_test = 0 AND status = 'COMPLETED' "
                           "AND created_at >= ? AND created_at < ?", a, b),
            "revenue": one("SELECT SUM(CAST(amount AS REAL)) FROM orders WHERE is_test = 0 AND status = 'COMPLETED' "
                           "AND created_at >= ? AND created_at < ?", a, b),
            "subs": one("SELECT COUNT(*) FROM monitor_accounts WHERE status = 'ACTIVE' AND lower(email) <> lower(?) "
                        "AND created_at >= ? AND created_at < ?", owner_email, a, b),
        })
        start, index = end, index + 1
    return weeks


def closest_scenario(actual_visitors, week_index, fraction=1.0):
    """السيناريو الأقرب لعدد الزوار (مسافة لوغاريتمية: 300 مقابل 1500 فرق نسبي لا مطلق)."""
    best, best_dist = None, None
    for key, sc in SCENARIOS.items():
        exp = expected_week(sc, week_index)["visitors"] * fraction
        dist = abs(math.log((actual_visitors + 1) / (exp + 1)))
        if best_dist is None or dist < best_dist:
            best, best_dist = key, dist
    return best


def build(conn, owner_email="", plans=None, today=None):
    weeks = actual_weeks(conn, owner_email, today)
    rows = []
    for w in weeks:
        frac = w["partial_days"] / 7
        exp = {k: {m: round(v * frac, 2) for m, v in expected_week(sc, w["index"]).items()} for k, sc in SCENARIOS.items()}
        rows.append(dict(w, expected=exp, closest=closest_scenario(w["visitors"], w["index"], frac)))
    prices = {k: float(p["price"]) for k, p in (plans or {}).items()}
    active = conn.execute("SELECT plan, COUNT(*) FROM monitor_accounts WHERE status = 'ACTIVE' AND lower(email) <> lower(?) "
                          "GROUP BY plan", (owner_email,)).fetchall()
    mrr = sum(prices.get(plan, 0) * n for plan, n in active)
    totals = {m: sum(w[m] for w in weeks) for m in ("visitors", "scans", "reports", "revenue", "subs")}
    days = max(1, (min(today or dt.date.today(), dt.date.today()) - LAUNCH).days + 1)
    cost_so_far = COST_PER_MONTH * days / 30.4
    full = [r for r in rows if r["partial_days"] == 7]
    latest = (full or rows)[-1] if rows else None
    return {"weeks": rows, "totals": totals, "mrr": mrr, "cost_so_far": round(cost_so_far, 2),
            "net_so_far": round(totals["revenue"] + 0 - cost_so_far, 2), "breakeven_subs": math.ceil(COST_PER_MONTH / 27.06),
            "verdict": latest["closest"] if latest else None, "scenarios": SCENARIOS,
            "conversion": {"scan": round(totals["scans"] / totals["visitors"], 4) if totals["visitors"] else None},
            "conversion_warning": conversion_warning(totals, latest["closest"] if latest else None)}


def conversion_warning(totals, verdict):
    """الحكم بالزوار وحدهم مضلل: 70 زائراً بلا أي فحص ليس «واقعياً». ننبّه إن كان الفحص أقل من نصف المتوقع."""
    if not verdict or totals["visitors"] < 30:
        return None
    expected_rate = SCENARIOS[verdict]["scan"]
    actual_rate = totals["scans"] / totals["visitors"]
    if actual_rate < expected_rate / 2:
        return (f"Traffic matches {SCENARIOS[verdict]['label']}, but visitor→scan is {actual_rate:.1%} vs {expected_rate:.0%} "
                f"assumed: the homepage is not converting; revenue will track Pessimistic until this is fixed.")
    return None


def as_text(card):
    """نص البريد الأسبوعي (إنجليزي/عربي مختصر)."""
    lines = ["Quantum Aether — reality vs simulation", ""]
    lines.append("week start  | visitors (pess/real/opt expected) | scans | reports | new subs | closest")
    for w in card["weeks"]:
        e = w["expected"]
        tag = "" if w["partial_days"] == 7 else f" (partial {w['partial_days']}d)"
        lines.append(f"{w['start']}{tag} | {w['visitors']} ({e['pessimistic']['visitors']:.0f}/{e['realistic']['visitors']:.0f}/"
                     f"{e['optimistic']['visitors']:.0f}) | {w['scans']} (real. {e['realistic']['scans']:.0f}) | "
                     f"{w['reports']} | {w['subs']} | {SCENARIOS[w['closest']]['label']}")
    t = card["totals"]
    lines += ["", f"Since launch: {t['visitors']} visitors, {t['scans']} scans, {t['reports']} reports (${t['revenue']:.2f}), "
                  f"{t['subs']} subscriptions. MRR ${card['mrr']:.2f}.",
              f"Estimated cost so far ${card['cost_so_far']:.2f}; net ${card['net_so_far']:.2f}. "
              f"Break-even: {card['breakeven_subs']} Starter subscriptions.",
              f"Verdict: tracking the {SCENARIOS[card['verdict']]['label'].upper()} scenario "
              f"(الأقرب: {SCENARIOS[card['verdict']]['label_ar']})." if card["verdict"] else "No data yet."]
    if card.get("conversion_warning"):
        lines.append("WARNING: " + card["conversion_warning"])
    return "\n".join(lines)
