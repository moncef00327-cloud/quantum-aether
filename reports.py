# reports.py
# التقرير الشهري «حالة TLS ما بعد الكمومي»: لقطة مجمّدة من بيانات المتتبّع (لا تتغير بعد النشر، حتى يبقى الاقتباس صحيحاً).
# build() يحسب الأرقام من قاعدة البيانات، وtools/build_report.py يحفظها في data/reports/<id>.json.
# الصفحات تقرأ الملف فقط. الرسوم SVG تُولَّد من الملف نفسه (قابلة للتحميل، CC BY 4.0).
import json
import os
from html import escape

import adoption
import countries
import search_indexing

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "reports")
PROVIDER_MIN = 100
SPOTLIGHT_TOP = 10000


_TLD = {v[3]: k for k, v in countries.COUNTRIES.items()}  # ISO -> ccTLD (GB -> uk)


def _pct(pq, n):
    return round(100 * pq / n, 1) if n else 0.0


def top1000_breakdown(conn, week):
    """Why fewer than 1,000 sites count: excluded hosts, no HTTPS answer on 443, undetermined."""
    rows, ok, unsure = conn.execute("SELECT COUNT(*), COALESCE(SUM(ok),0), COALESCE(SUM(ok AND unsure),0) FROM adoption_results "
                                    "WHERE week = ? AND rank <= 1000", (week,)).fetchone()
    return {"ranks": 1000, "excluded": 1000 - rows, "no_answer": rows - ok, "unsure": unsure, "counted": ok - unsure}


def build(conn, report_id, published):
    snap = adoption.snapshot(conn)
    board = countries.leaderboard(conn)
    if not snap:
        raise RuntimeError("no adoption data")
    tl = snap["timeline"]
    sectors = []
    for s in snap["sectors"]:
        measured = [r for r in s["rows"] if adoption.measured(r)]
        sectors.append({"key": s["key"], "labels": s["labels"], "measured": len(measured),
                        "pq": sum(1 for r in measured if r["pq"]), "pct": _pct(sum(1 for r in measured if r["pq"]), len(measured)),
                        "classical": sorted(r["domain"] for r in measured if not r["pq"])})
    prov = [r for r in (snap["providers"] or {}).get("rows", []) if r["reachable"] >= PROVIDER_MIN]
    ok = lambda r: r["rank"] is not None and r["rank"] <= SPOTLIGHT_TOP and not search_indexing.is_excluded(r["domain"])
    ch = snap["changes"] or {"adopted": [], "dropped": []}
    pick = lambda rows: [{"domain": r["domain"], "rank": r["rank"]} for r in sorted(filter(ok, rows), key=lambda r: r["rank"])[:10]]
    entries = (board or {}).get("entries", [])
    return {
        "id": report_id, "published": published, "week": snap["week"], "week_start": snap["week_start"],
        "previous_week": snap["previous_week"],
        "top1000": tl[-1] if tl else None, "top1000_previous": tl[-2] if len(tl) > 1 else None,
        "top1000_breakdown": top1000_breakdown(conn, snap["week"]),
        "top10k": snap["top10k"],
        "sectors": sectors,
        "providers": [{"asn": r["asn"], "name": r["name"], "sites": r["reachable"], "pq": r["pq"], "pct": r["pct"]} for r in prov],
        "providers_period": (snap["providers"] or {}).get("period"),
        "countries_top": [dict(code=e["iso"], measured=e["measured"], pct=e["pct"]) for e in entries[:5]],
        "countries_bottom": [dict(code=e["iso"], measured=e["measured"], pct=e["pct"]) for e in entries[-5:]],
        "countries_min_sites": (board or {}).get("min_sites"),
        "adopted_count": len(ch["adopted"]), "dropped_count": len(ch["dropped"]),
        "adopted": pick(ch["adopted"]), "dropped": pick(ch["dropped"]),
    }


def save(report):
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with open(os.path.join(REPORTS_DIR, report["id"] + ".json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)


def ids():
    if not os.path.isdir(REPORTS_DIR):
        return []
    return sorted((f[:-5] for f in os.listdir(REPORTS_DIR) if f.endswith(".json")), reverse=True)


def load(report_id):
    if report_id not in ids():
        return None
    with open(os.path.join(REPORTS_DIR, report_id + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def sector(report, key):
    return next((s for s in report["sectors"] if s["key"] == key), None)


def provider(report, asn):
    return next((p for p in report["providers"] if p["asn"] == asn), None)


# ---------------------------------------------------------------- النتائج النصية (بثلاث لغات)

def findings(r, lang):
    """جمل جاهزة للاقتباس، كل رقم من التقرير نفسه."""
    out = []
    t, p = r["top1000"], r["top1000_previous"]
    if t:
        d = round(t["pct"] - p["pct"], 1) if p else None
        out.append({
            "en": f"{t['pct']}% of the 1,000 most visited websites negotiate hybrid post-quantum key exchange (X25519MLKEM768)" + (f", {'up' if d >= 0 else 'down'} {abs(d)} points from the previous week." if d is not None else "."),
            "ar": f"{t['pct']}% من أكثر 1000 موقع زيارةً تتفاوض على تبادل مفاتيح هجين ما بعد كمومي (X25519MLKEM768)" + (f"، بتغيّر {d:+} نقطة عن الأسبوع السابق." if d is not None else "."),
            "de": f"{t['pct']} % der 1.000 meistbesuchten Websites handeln hybriden Post-Quanten-Schlüsselaustausch (X25519MLKEM768) aus" + (f", {d:+} Prozentpunkte gegenüber der Vorwoche." if d is not None else "."),
        }[lang])
    k = r["top10k"]
    if k:
        out.append({"en": f"Across the top 10,000 the share is {k['pct']}% ({k['pq']:,} of {k['reachable']:,} measured sites).",
                    "ar": f"وعلى مستوى أكبر 10,000 موقع النسبة {k['pct']}% ({k['pq']:,} من {k['reachable']:,} موقعاً مقيساً).",
                    "de": f"Unter den Top 10.000 liegt der Anteil bei {k['pct']} % ({k['pq']:,} von {k['reachable']:,} gemessenen Websites)."}[lang])
    eu, dach = sector(r, "banks-europe"), sector(r, "banks-dach")
    if eu and eu["measured"]:
        n = len(eu["classical"])
        out.append({"en": f"{n} of {eu['measured']} European banks and central banks outside Germany, Austria and Switzerland still use classical key exchange only ({round(100 - eu['pct'], 1)}%).",
                    "ar": f"{n} من {eu['measured']} بنكاً وبنكاً مركزياً أوروبياً خارج ألمانيا والنمسا وسويسرا ما زالت تستخدم تبادل مفاتيح تقليدياً فقط ({round(100 - eu['pct'], 1)}%).",
                    "de": f"{n} von {eu['measured']} europäischen Banken und Zentralbanken außerhalb der DACH-Region nutzen weiterhin nur klassischen Schlüsselaustausch ({round(100 - eu['pct'], 1)} %)."}[lang])
    if dach and dach["measured"]:
        n = len(dach["classical"])
        out.append({"en": f"In the DACH region, {n} of {dach['measured']} measured banks and central banks are classical-only.",
                    "ar": f"وفي ألمانيا والنمسا وسويسرا، {n} من {dach['measured']} بنكاً مقيساً تقليدية فقط.",
                    "de": f"In der DACH-Region sind {n} von {dach['measured']} gemessenen Banken und Zentralbanken rein klassisch."}[lang])
    ec2, aws_edge = provider(r, 14618), provider(r, 16509)
    if ec2 and aws_edge:
        out.append({"en": f"Hosting decides more than size: on Amazon's EC2 network (AS14618) only {ec2['pct']}% of sites are post-quantum ready, against {aws_edge['pct']}% on AS16509, where CloudFront and AWS load balancers live.",
                    "ar": f"الاستضافة تحسم أكثر من حجم الموقع: على شبكة EC2 من Amazon (AS14618) فقط {ec2['pct']}% من المواقع جاهزة، مقابل {aws_edge['pct']}% على AS16509 حيث CloudFront وموازنات حمل AWS.",
                    "de": f"Das Hosting entscheidet mehr als die Größe: Im EC2-Netz von Amazon (AS14618) sind nur {ec2['pct']} % der Websites Post-Quanten-fähig, gegenüber {aws_edge['pct']} % in AS16509, wo CloudFront und die AWS Load Balancer liegen."}[lang])
    if r["adopted_count"]:
        names = ", ".join(a["domain"] for a in r["adopted"][:4])
        out.append({"en": f"{r['adopted_count']} sites switched to post-quantum key exchange this week, including {names}; {r['dropped_count']} switched back.",
                    "ar": f"{r['adopted_count']} موقعاً انتقل إلى تبادل المفاتيح ما بعد الكمومي هذا الأسبوع، منها {names}؛ و{r['dropped_count']} عاد إلى التقليدي.",
                    "de": f"{r['adopted_count']} Websites sind diese Woche auf Post-Quanten-Schlüsselaustausch umgestiegen, darunter {names}; {r['dropped_count']} sind zurückgefallen."}[lang])
    return out


# ---------------------------------------------------------------- رسوم SVG

def bar_svg(title, rows, source):
    """rows = [(label, pct)]. رسم أفقي بسيط بخطوط النظام، خلفية فاتحة (يعمل في الطباعة والعروض)."""
    w, row_h, top, left = 780, 30, 56, 300
    h = top + row_h * len(rows) + 44
    bar_w = w - left - 70
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="system-ui,Segoe UI,Arial,sans-serif">',
             f'<rect width="{w}" height="{h}" fill="#ffffff"/>',
             f'<text x="20" y="32" font-size="18" font-weight="600" fill="#18221c">{escape(title)}</text>']
    for i, (label, pct) in enumerate(rows):
        y = top + i * row_h
        parts.append(f'<text x="{left - 10}" y="{y + 19}" font-size="13" fill="#33403a" text-anchor="end">{escape(label)}</text>')
        parts.append(f'<rect x="{left}" y="{y + 6}" width="{bar_w}" height="18" fill="#e8ede9"/>')
        parts.append(f'<rect x="{left}" y="{y + 6}" width="{round(bar_w * pct / 100, 1)}" height="18" fill="#3f7d4e"/>')
        parts.append(f'<text x="{left + bar_w + 8}" y="{y + 19}" font-size="13" fill="#18221c">{pct}%</text>')
    parts.append(f'<text x="20" y="{h - 16}" font-size="11" fill="#5c6b63">{escape(source)}</text></svg>')
    return "\n".join(parts)


def _short(name, n=24):
    name = (name or "").replace(", Inc.", "").replace(", Inc", "").replace(", LLC", "").replace(" B.V.", "").replace(" B.V", "")
    return name if len(name) <= n else name[:n - 1] + "…"


CHARTS = ("sectors", "providers", "countries")
SHORT = {"banks-europe": "Banks, Europe (excl. DACH)", "banks-dach": "Banks, DACH",
         "government-dach": "Government, DACH", "companies-dach": "Companies, DACH"}


def chart(r, name, lang="en"):
    src = f"Quantum Aether · ather-quantum.com/reports/{r['id']} · CC BY 4.0 · week {r['week']}"
    if name == "sectors":
        rows = [(SHORT.get(s["key"]) or s["labels"].get("en") or s["key"], s["pct"]) for s in r["sectors"] if s["measured"]]
        top = [("Top 1,000 websites", r["top1000"]["pct"])] if r["top1000"] else []
        return bar_svg("Post-quantum key exchange by group", top + [(l[:30], p) for l, p in rows], src)
    if name == "providers":
        return bar_svg("Post-quantum key exchange by hosting network",
                       [(f"{_short(p['name'])} (AS{p['asn']})", p["pct"]) for p in r["providers"]], src)
    if name == "countries":
        rows = r["countries_bottom"][::-1] + r["countries_top"][::-1]
        return bar_svg("By country-code domain: lowest 5 first, then highest 5 (sites in brackets)",
                       [(f".{_TLD.get(c['code'], c['code'].lower())} ({c['measured']} sites)", c["pct"]) for c in rows], src)
    return None
