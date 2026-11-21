# exposure.py — سجل التعرّض الكمّي (Quantum Exposure Registry).
# لكل نطاق: متى رأيناه أول مرة، ومتى بدأ يتفاوض على تبادل مفاتيح ما بعد كمّي، وكم أسبوعاً رأيناه كلاسيكياً قبل ذلك
# (نافذة «احصد الآن، فكّ لاحقاً»). كل أسبوع تُبصَم نتائج المتتبّع (sha256) وتُرسَّخ في OpenTimestamps (بيتكوين)،
# فلا يستطيع أحد — ولا نحن — إعادة كتابة التاريخ لاحقاً. ملاحظة خارجية فقط، لا شهادة امتثال. لا يُجري أي فحص.
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import subprocess

import adoption
import badge_evidence
import search_indexing

INDEX_MAX_RANK = search_indexing.INDEX_MAX_RANK  # نفس سياسة /site/ (100 منذ 2026-11-20؛ كانت 1000)
PUBLIC_WEEKS = 26            # الصفحات العامة والواجهة بلا مفتاح: آخر 26 أسبوعاً (مثل /site/)؛ التاريخ الكامل بمفتاح API
INDEX_MIN_WEEKS = 4            # ... أو نطاق له 4 قياسات أسبوعية حقيقية على الأقل؛ ما عداه noindex وخارج خريطة الموقع
MANIFEST_HEADER = "quantum-aether-weekly-anchor-v1"
DOMAIN_KEY_PREFIX = "quantum-aether-domain-v1|"
WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")
OTS_BIN = os.environ.get("QS_OTS_BIN", "/opt/ots-venv/bin/ots")
SETTLE_HOURS = 6               # لا نبصم أسبوعاً ما زال فحصه جارياً
CLAIM_PREFIX = "_ather-claim"

SCHEMA = """
CREATE TABLE IF NOT EXISTS exposure_claims (
    domain      TEXT PRIMARY KEY,
    verified_at TEXT NOT NULL,
    method      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS exposure_claim_attempts (
    domain      TEXT PRIMARY KEY,
    tried_at    TEXT NOT NULL
);
"""


def init(conn):
    conn.executescript(SCHEMA)


# ---------------------------------------------------------------- البصمة الأسبوعية

def state_of(row):
    if not row["ok"]:
        return "unreachable"
    if row["unsure"]:
        return "undetermined"
    return "observed_pq" if row["pq"] else "observed_classical"


def leaf_hash(row):
    """بصمة صف واحد = badge_evidence.attestation_hash (نفس صيغة الشارات)، مع حالة unreachable للنطاق الذي لم يُجب."""
    return badge_evidence.attestation_hash(row["domain"], state_of(row), row["grade"], row["tls"], row["grp"],
                                           row["scanned_at"])


def domain_key(domain):
    """اسم النطاق لا يُكتب في الملف العام: يكفي أن يحسب أي شخص sha256 لاسم النطاق ليجد سطره."""
    return hashlib.sha256((DOMAIN_KEY_PREFIX + domain.lower()).encode("utf-8")).hexdigest()


def manifest_bytes(conn, week):
    cur = conn.execute("SELECT domain, ok, unsure, pq, grade, tls, grp, scanned_at FROM adoption_results "
                       "WHERE week = ? ORDER BY domain", (week,))
    lines = []
    for r in cur:
        leaf = leaf_hash(r)
        if leaf:
            lines.append(f"{domain_key(r['domain'])} {leaf}")
    lines.sort()
    head = f"{MANIFEST_HEADER} week={week} rows={len(lines)} leaf=sha256(quantum-aether-v1|domain|state|grade|tls|group|checked_at) key=sha256({DOMAIN_KEY_PREFIX}domain)"
    return ("\n".join([head] + lines) + "\n").encode("utf-8"), len(lines)


def anchor_dir(data_dir):
    path = os.path.join(data_dir, "anchors")
    os.makedirs(path, exist_ok=True)
    return path


def _paths(data_dir, week):
    base = os.path.join(anchor_dir(data_dir), week)
    return {"json": base + ".json", "manifest": base + ".manifest.txt", "ots": base + ".manifest.txt.ots"}


def load_anchor(data_dir, week):
    if not WEEK_RE.match(week or ""):
        return None
    path = os.path.join(data_dir, "anchors", week + ".json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def anchors(data_dir):
    folder = os.path.join(data_dir, "anchors")
    if not os.path.isdir(folder):
        return []
    out = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".json") and WEEK_RE.match(name[:-5]):
            a = load_anchor(data_dir, name[:-5])
            if a:
                out.append(a)
    return out


def _run(args, timeout=120):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def _write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


def settled_weeks(conn, now=None):
    """أسابيع انتهى فحصها (آخر نتيجة فيها أقدم من SETTLE_HOURS)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    out = []
    for week, last in conn.execute("SELECT week, MAX(scanned_at) FROM adoption_results GROUP BY week ORDER BY week"):
        stamp = badge_evidence.moment(last)
        if stamp and (now - stamp).total_seconds() >= SETTLE_HOURS * 3600:
            out.append(week)
    return out


def anchor_week(conn, data_dir, week, ots_bin=OTS_BIN, now=None, stamp=None):
    """يبصم أسبوعاً مرة واحدة فقط (الملف لا يُعاد كتابته أبداً) ويرسله إلى خوادم OpenTimestamps العامة."""
    paths = _paths(data_dir, week)
    existing = load_anchor(data_dir, week)
    if existing and os.path.exists(paths["manifest"]):
        return existing
    body, rows = manifest_bytes(conn, week)
    with open(paths["manifest"], "wb") as f:
        f.write(body)
    digest = hashlib.sha256(body).hexdigest()
    now = now or dt.datetime.now(dt.timezone.utc)
    record = {"week": week, "rows": rows, "manifest_sha256": digest, "created_at": now.isoformat(timespec="seconds"),
              "method": "OpenTimestamps (Bitcoin) via public calendars",
              "files": {"manifest": os.path.basename(paths["manifest"]), "proof": os.path.basename(paths["ots"])},
              "leaf_hash": "badge_evidence.attestation_hash: sha256('quantum-aether-v1|domain|state|grade|tls|group|checked_at')",
              "domain_key": f"sha256('{DOMAIN_KEY_PREFIX}' + domain)",
              "verify": f"ots verify {os.path.basename(paths['ots'])}  (needs {os.path.basename(paths['manifest'])} next to it)"}
    code, out = (stamp or (lambda p: _run([ots_bin, "stamp", p])))(paths["manifest"])
    record["status"] = "pending" if code == 0 and os.path.exists(paths["ots"]) else "stamp_failed"
    record["stamp_log"] = out.strip()[-800:]
    _write_json(paths["json"], record)
    return record


def upgrade_anchors(data_dir, ots_bin=OTS_BIN, run=None):
    """يحدّث الإثباتات المعلّقة حين يُدرج التقويم البصمة في كتلة بيتكوين (عادة خلال ساعات)."""
    run = run or _run
    changed = []
    for a in anchors(data_dir):
        paths = _paths(data_dir, a["week"])
        if a.get("status") == "stamp_failed" and not os.path.exists(paths["ots"]):
            code, out = run([ots_bin, "stamp", paths["manifest"]])
            if code == 0 and os.path.exists(paths["ots"]):
                a["status"] = "pending"
                a["stamp_log"] = out.strip()[-800:]
                _write_json(paths["json"], a)
                changed.append(a["week"])
            continue
        if a.get("status") != "pending":
            continue
        run([ots_bin, "upgrade", paths["ots"]])
        code, info = run([ots_bin, "info", paths["ots"]])
        heights = re.findall(r"BitcoinBlockHeaderAttestation\((\d+)\)", info)
        if heights:
            a["status"] = "complete"
            a["bitcoin_block"] = int(min(heights, key=int))
            a["upgraded_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            _write_json(paths["json"], a)
            changed.append(a["week"])
    return changed


# ---------------------------------------------------------------- نافذة التعرّض

def _history(conn, domain):
    best = []
    alt = domain[4:] if domain.startswith("www.") else f"www.{domain}"
    for cand in (domain, alt):
        rows = [dict(r) for r in conn.execute(
            "SELECT week, domain, rank, sector, ok, grade, grp, tls, pq, unsure, as_name, asn, scanned_at "
            "FROM adoption_results WHERE domain = ? ORDER BY week", (cand,))]
        if len(rows) > len(best):
            best = rows
    return best


def _monday(week):
    return adoption.week_monday(week).isoformat()


def network_stats(conn, as_name, week):
    if not as_name:
        return None
    total, pq = conn.execute("SELECT COUNT(*), COALESCE(SUM(pq), 0) FROM adoption_results WHERE week = ? AND as_name = ? "
                             "AND ok = 1 AND unsure = 0", (week, as_name)).fetchone()
    return {"as_name": as_name, "measured": total, "pq": pq, "pct": round(100 * pq / total, 1) if total else None}


def is_indexable(domain, rank, measured_weeks, sector=None):
    if (search_indexing.is_excluded(domain)
            or search_indexing.family_dns_blocked(domain)
            or search_indexing.is_infrastructure(domain)):
        return False
    if rank is not None and rank <= INDEX_MAX_RANK:
        return True
    # قطاعات المشترين فقط، وبعد 4 قياسات حقيقية (لا صفحات رقيقة لنطاقات أُضيفت للتو)
    return sector in search_indexing.PRIORITY_SECTORS and measured_weeks >= INDEX_MIN_WEEKS


def window(conn, domain, data_dir=None, peers=True, max_weeks=PUBLIC_WEEKS):
    """كل ما تعرضه صفحة /exposure/<domain> وواجهة exposure_window. None إن لم نرَ النطاق في المتتبّع."""
    rows = _history(conn, domain)
    if not rows:
        return None
    measured = [r for r in rows if r["ok"] and not r["unsure"]]
    last = rows[-1]
    current = measured[-1] if measured else None
    pq_rows = [r for r in measured if r["pq"]]
    first_pq = pq_rows[0]["week"] if pq_rows else None
    first_measured = measured[0]["week"] if measured else None
    regressions = [r["week"] for r in measured if first_pq and r["week"] > first_pq and not r["pq"]]
    if not measured:
        status = "no_measurement"
    elif first_pq is None:
        status = "classical"
    elif first_pq == first_measured:
        status = "pq_since_first_observation"
    else:
        status = "went_pq"
    classical_weeks = [r["week"] for r in measured if not r["pq"]]
    window_start = _monday(first_measured) if first_measured else None
    if status == "went_pq":
        window_end, open_ = _monday(first_pq), False
    elif status == "classical":
        window_end, open_ = current["scanned_at"][:10], True
    else:
        window_end, open_ = None, False
    days = None
    if window_start and window_end:
        days = (dt.date.fromisoformat(window_end) - dt.date.fromisoformat(window_start)).days
    anchor_cache = {}
    timeline = []
    for r in rows:
        if data_dir and r["week"] not in anchor_cache:
            anchor_cache[r["week"]] = load_anchor(data_dir, r["week"])
        a = anchor_cache.get(r["week"])
        timeline.append({"week": r["week"], "week_start": _monday(r["week"]), "state": state_of(r), "grade": r["grade"],
                         "group": r["grp"], "tls": r["tls"], "network": r["as_name"], "checked_at": r["scanned_at"],
                         "leaf_hash": leaf_hash(r),
                         "anchor": ({"manifest_sha256": a["manifest_sha256"], "status": a.get("status"),
                                     "bitcoin_block": a.get("bitcoin_block")} if a else None)})
    truncated = max_weeks is not None and len(timeline) > max_weeks
    if truncated:
        timeline = timeline[-max_weeks:]
    rank = last["rank"]
    out = {
        "history_truncated": truncated, "public_weeks": max_weeks,
        "domain": last["domain"], "rank": rank, "sector": last["sector"],
        "first_observed_week": rows[0]["week"], "first_observed": _monday(rows[0]["week"]),
        "first_measured_week": first_measured,
        "first_pq_week": first_pq, "first_pq_date": _monday(first_pq) if first_pq else None,
        "status": status, "currently_pq": bool(current and current["pq"]),
        "regression_weeks": regressions, "classical_weeks_observed": len(classical_weeks),
        "measured_weeks": len(measured), "observed_weeks": len(rows),
        "exposure_window": {"start": window_start, "end": window_end, "open": open_, "days": days,
                            "lower_bound": True,
                            "note": "Observed lower bound: classical key exchange may have been in use before our first observation."},
        "last_checked": last["scanned_at"], "network": (current or last)["as_name"],
        "timeline": timeline,
        "indexable": is_indexable(last["domain"], rank, len(measured), last["sector"]),
        "disclaimer": "External observation of the public HTTPS endpoint (one TLS handshake per week on port 443). "
                      "Not a compliance certification, audit or legal advice.",
    }
    if peers:
        net = out["network"]
        out["network_stats"] = network_stats(conn, net, last["week"])
        peer_rows = [p for p in adoption.peers(conn, last["domain"], net, last["week"], limit=40)
                     if search_indexing.is_indexable(p["domain"], p["rank"], p["sector"])][:8]
        out["peers"] = [{"domain": p["domain"], "grade": p["grade"], "pq": bool(p["pq"]), "unsure": bool(p["unsure"]),
                         "first_pq_week": _first_pq(conn, p["domain"])} for p in peer_rows]
    return out


def _first_pq(conn, domain):
    return conn.execute("SELECT MIN(week) FROM adoption_results WHERE domain = ? AND ok = 1 AND unsure = 0 AND pq = 1",
                        (domain,)).fetchone()[0]


def sitemap_domains(conn, optout=None):
    """نطاقات /exposure/ المفهرسة فقط: أكبر 1000 في آخر أسبوع، أو 4 أسابيع قياس حقيقية فأكثر."""
    weeks = adoption.weeks(conn)
    if not weeks:
        return []
    latest = weeks[-1]
    out = []
    cur = conn.execute(
        "SELECT domain, SUM(CASE WHEN ok = 1 AND unsure = 0 THEN 1 ELSE 0 END) AS n, MAX(substr(scanned_at, 1, 10)) AS day, "
        "MAX(CASE WHEN week = ? THEN rank END) AS rank, MAX(sector) AS sector FROM adoption_results GROUP BY domain", (latest,))
    for r in cur:
        if not r["n"] or not is_indexable(r["domain"], r["rank"], r["n"], r["sector"]):
            continue
        if optout is not None and adoption.opted_out(r["domain"], optout):
            continue
        out.append((r["domain"], r["day"], r["rank"] if r["rank"] is not None else 10 ** 9))
    out.sort(key=lambda x: (x[2], x[0]))
    return [(d, day) for d, day, _ in out]


# ---------------------------------------------------------------- مطالبة المالك بالصفحة (DNS TXT)

def claim_token(domain, salt):
    mac = hmac.new((salt or "").encode("utf-8"), ("claim|" + domain.lower()).encode("utf-8"), hashlib.sha256)
    return "qa-claim=" + mac.hexdigest()[:24]


def verify_claim(domain, salt, query=None):
    query = query or adoption.query_txt_records
    fqdn = f"{CLAIM_PREFIX}.{domain}"
    token = claim_token(domain, salt)
    records = query(fqdn)
    return {"domain": domain, "record": fqdn, "token": token, "verified": any(token in r for r in records),
            "found": records[:5]}


def claim_of(conn, domain):
    init(conn)
    row = conn.execute("SELECT verified_at FROM exposure_claims WHERE domain = ?", (domain,)).fetchone()
    return row[0] if row else None


def record_claim(conn, domain):
    init(conn)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with conn:
        conn.execute("INSERT OR REPLACE INTO exposure_claims (domain, verified_at, method) VALUES (?, ?, 'dns_txt')",
                     (domain, now))
    return now


def claim_allowed(conn, domain, now=None, seconds=30):
    """حدّ بسيط: محاولة تحقق واحدة لكل نطاق كل 30 ثانية (كل محاولة = استعلام DNS واحد)."""
    init(conn)
    now = now or dt.datetime.now(dt.timezone.utc)
    row = conn.execute("SELECT tried_at FROM exposure_claim_attempts WHERE domain = ?", (domain,)).fetchone()
    if row:
        last = badge_evidence.moment(row[0])
        if last and (now - last).total_seconds() < seconds:
            return False
    with conn:
        conn.execute("INSERT OR REPLACE INTO exposure_claim_attempts (domain, tried_at) VALUES (?, ?)",
                     (domain, now.isoformat(timespec="seconds")))
    return True
