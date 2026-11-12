# adoption.py
# متتبّع التبنّي: كل أسبوع نعيد فحص أكبر 10 آلاف نطاق في Tranco وقوائم المراقبة (DACH)، وكل شهر أكبر 100 ألف.
# نحفظ نتيجة كل نطاق مع الشبكة المشغّلة له (ASN)، ونحسب من انتقل إلى تبادل المفاتيح الهجين ومن فقده،
# ونسبة الجاهزية لكل مزوّد استضافة/CDN. لا يعتمد على sales_db (حتى لا يحدث استيراد دائري).
import concurrent.futures as cf
import csv
import datetime as dt
import io
import json
import os

import search_indexing

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_STUDY_FILE = os.path.join(BASE_DIR, "data", "pq_study_top1000_raw.jsonl")
TRANCO_FILE = os.path.join(BASE_DIR, "data", "tranco_GQ38K_top100k.csv")
WATCHLISTS_FILE = os.path.join(BASE_DIR, "data", "adoption_watchlists.json")
OPTOUT_FILE = os.path.join(BASE_DIR, "data", "adoption_optout.txt")
TIMELINE_WEEKS = 26
TIMELINE_RANK = 1000          # الخط الزمني على الأكبر 1000 فقط، فيبقى قابلاً للمقارنة مع الدراسة وعبر الأسابيع
WEEKLY_TOP = 10000
MONTHLY_TOP = 100000
KEEP_WEEKS = 52
KEEP_MONTHS = 6
PROVIDER_MIN_SITES = 20       # لا نعرض مزوّداً بأقل من 20 موقعاً مُجيباً: العيّنة أصغر من أن تُقارن

SCHEMA = """
CREATE TABLE IF NOT EXISTS adoption_results (
    week        TEXT NOT NULL,          -- أسبوع ISO مثل 2026-W45
    domain      TEXT NOT NULL,
    rank        INTEGER,                -- ترتيب Tranco؛ فارغ لنطاقات قوائم المراقبة خارج القائمة
    sector      TEXT,                   -- مفتاح قائمة المراقبة إن وُجد
    ok          INTEGER NOT NULL,       -- 1 إن أجاب على HTTPS
    grade       TEXT,
    grp         TEXT,                   -- مجموعة تبادل المفاتيح المتفق عليها
    tls         TEXT,
    pq          INTEGER NOT NULL DEFAULT 0,
    scanned_at  TEXT NOT NULL,
    PRIMARY KEY (week, domain)
);
CREATE INDEX IF NOT EXISTS adoption_by_domain ON adoption_results(domain, week);
CREATE INDEX IF NOT EXISTS adoption_by_week_rank ON adoption_results(week, rank);

CREATE TABLE IF NOT EXISTS adoption_monthly (
    month       TEXT NOT NULL,          -- مثل 2026-11
    domain      TEXT NOT NULL,
    rank        INTEGER,
    ok          INTEGER NOT NULL,
    grade       TEXT,
    grp         TEXT,
    pq          INTEGER NOT NULL DEFAULT 0,
    asn         INTEGER,
    as_name     TEXT,
    scanned_at  TEXT NOT NULL,
    PRIMARY KEY (month, domain)
);
CREATE TABLE IF NOT EXISTS adoption_optout (
    domain      TEXT PRIMARY KEY,
    verified_at TEXT NOT NULL,
    method      TEXT NOT NULL
);
"""


def init(conn):
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(adoption_results)")}
    with conn:
        for name, kind in (("ip", "TEXT"), ("asn", "INTEGER"), ("as_name", "TEXT"),
                           ("unsure", "INTEGER NOT NULL DEFAULT 0")):
            if name not in cols:
                conn.execute(f"ALTER TABLE adoption_results ADD COLUMN {name} {kind}")
        conn.execute("CREATE INDEX IF NOT EXISTS adoption_by_week_network ON adoption_results(week, as_name, rank)")
        mcols = {r[1] for r in conn.execute("PRAGMA table_info(adoption_monthly)")}
        if "unsure" not in mcols:
            conn.execute("ALTER TABLE adoption_monthly ADD COLUMN unsure INTEGER NOT NULL DEFAULT 0")


# ---------------------------------------------------------------- الأسابيع

def week_of(day):
    year, week, _ = day.isocalendar()
    return f"{year}-W{week:02d}"


def week_monday(week):
    year, num = week.split("-W")
    return dt.date.fromisocalendar(int(year), int(num), 1)


# ---------------------------------------------------------------- القوائم

def load_watchlists(path=WATCHLISTS_FILE):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("sectors", {})
    except FileNotFoundError:
        return {}


def load_optout(path=OPTOUT_FILE, conn=None):
    """نطاقات طلب أصحابها استبعادها (سطر لكل نطاق، # للتعليق، بالإضافة إلى الاستبعادات الموثقة عبر DNS TXT في قاعدة البيانات)."""
    out = set()
    try:
        with open(path, encoding="utf-8") as f:
            out.update(line.split("#")[0].strip().lower() for line in f if line.split("#")[0].strip())
    except FileNotFoundError:
        pass
    if conn is not None:
        try:
            rows = conn.execute("SELECT domain FROM adoption_optout").fetchall()
            out.update(r[0].strip().lower() for r in rows if r[0])
        except Exception:
            pass
    return out


def _udp_dns_txt_query(fqdn, nameserver="1.1.1.1", timeout=3.0):
    """استعلام DNS TXT خالص عبر UDP (RFC 1035) لا يحتاج حزماً خارجية."""
    import random, socket, struct
    txid = random.randint(1, 65534)
    header = struct.pack("!HHHHHH", txid, 0x0100, 1, 0, 0, 0)
    qname = b"".join(len(lbl.encode("idna")).to_bytes(1, "big") + lbl.encode("idna") for lbl in fqdn.strip(".").split(".")) + b"\x00"
    packet = header + qname + struct.pack("!HH", 16, 1)  # QTYPE=16 (TXT), QCLASS=1 (IN)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        s.sendto(packet, (nameserver, 53))
        resp, _ = s.recvfrom(4096)
    if len(resp) < 12:
        return []
    r_txid, flags, qdcount, ancount, _, _ = struct.unpack("!HHHHHH", resp[:12])
    if r_txid != txid or (flags & 0x000F) != 0 or ancount == 0:
        return []

    def skip_name(buf, pos):
        while pos < len(buf):
            length = buf[pos]
            if length == 0:
                return pos + 1
            if (length & 0xC0) == 0xC0:
                return pos + 2
            pos += 1 + length
        return pos

    pos = 12
    for _ in range(qdcount):
        pos = skip_name(resp, pos) + 4
    records = []
    for _ in range(ancount):
        if pos >= len(resp):
            break
        pos = skip_name(resp, pos)
        if pos + 10 > len(resp):
            break
        rtype, _, _, rdlength = struct.unpack("!HHIH", resp[pos:pos + 10])
        pos += 10
        rdata = resp[pos:pos + rdlength]
        pos += rdlength
        if rtype == 16:  # TXT
            idx, parts = 0, []
            while idx < len(rdata):
                slen = rdata[idx]
                idx += 1
                parts.append(rdata[idx:idx + slen].decode("utf-8", errors="replace"))
                idx += slen
            records.append("".join(parts))
    return records


def query_txt_records(fqdn, timeout=3.0):
    """يجلب سجلات TXT لاسم النطاق عبر dnspython إن وُجدت، وإلا عبر استعلام UDP مباشر."""
    try:
        import dns.resolver  # type: ignore
        answers = dns.resolver.resolve(fqdn, "TXT", lifetime=timeout)
        return [a.to_text() for a in answers]
    except ImportError:
        pass
    except Exception:
        return []
    for ns in ("1.1.1.1", "8.8.8.8"):
        try:
            recs = _udp_dns_txt_query(fqdn, nameserver=ns, timeout=timeout)
            if recs:
                return recs
        except Exception:
            continue
    return []


def verify_dns_optout(domain: str, timeout: float = 3.0) -> dict:
    """
    يتحقق من إثبات ملكية الاستبعاد عبر سجلات DNS TXT:
    يقبل:
      - _ather-optout.<domain> TXT يحتوي على "verify-optout"
      - _qa-optout.<domain>    TXT يحتوي على "qa-optout=1"
    """
    clean = (domain or "").strip().lower().removeprefix("www.")
    if not clean or "." not in clean:
        return {"domain": clean, "verified": False, "records": [], "note": "invalid domain"}
    all_records = []
    for prefix in ("_ather-optout", "_qa-optout"):
        fqdn = f"{prefix}.{clean}"
        recs = query_txt_records(fqdn, timeout=timeout)
        all_records.extend(recs)
        for val in recs:
            low = val.lower()
            if "verify-optout" in low or "qa-optout=1" in low:
                return {
                    "domain": clean,
                    "verified": True,
                    "records": all_records,
                    "note": f"exclusion verified via {fqdn} TXT record",
                }
    return {
        "domain": clean,
        "verified": False,
        "records": all_records,
        "note": "no opt-out TXT token found (_ather-optout.<domain> = verify-optout or _qa-optout.<domain> = qa-optout=1)",
    }


def opted_out(domain, optout=None, check_dns=False):
    clean = (domain or "").strip().lower()
    if not clean:
        return False
    optout = load_optout() if optout is None else optout
    parts = clean.split(".")
    if any(".".join(parts[i:]) in optout for i in range(len(parts) - 1)):
        return True
    if check_dns and verify_dns_optout(clean)["verified"]:
        return True
    return False


def is_opted_out(domain: str, optout=None, check_dns: bool = False) -> bool:
    """واجهة متوافقة للتحقق من استبعاد النطاق محلياً أو عبر DNS TXT."""
    return opted_out(domain, optout=optout, check_dns=check_dns)


def record_optout(conn, domain: str, method: str = "dns_txt"):
    """يسجّل استبعاد النطاق الموثّق في قاعدة البيانات ويحذف نتائجه المنشورة (شاملاً النطاقات الفرعية)."""
    clean = (domain or "").strip().lower().removeprefix("www.")
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO adoption_optout (domain, verified_at, method) VALUES (?, ?, ?)",
            (clean, now, method),
        )
        conn.execute("DELETE FROM adoption_results WHERE domain = ? OR domain LIKE ?", (clean, f"%.{clean}"))
        conn.execute("DELETE FROM adoption_monthly WHERE domain = ? OR domain LIKE ?", (clean, f"%.{clean}"))
    return clean


def _raw_study_rows(path=RAW_STUDY_FILE):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_tranco(limit, path=TRANCO_FILE):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            rank, _, domain = line.strip().partition(",")
            if domain:
                rows.append((int(rank), domain.lower()))
            if len(rows) >= limit:
                break
    return rows


def load_targets(limit=WEEKLY_TOP, watchlists=None, optout=None, tranco_path=TRANCO_FILE):
    """أكبر N نطاق في Tranco (بما فيها التي لم تُجب سابقاً، فقد تجيب لاحقاً) ثم نطاقات قوائم المراقبة."""
    watchlists = load_watchlists() if watchlists is None else watchlists
    optout = load_optout() if optout is None else optout
    sector_of = {}
    for key, sector in watchlists.items():
        for domain in sector.get("domains", []):
            sector_of.setdefault(domain.lower(), key)
    targets, seen = [], set()
    # Excluded content (pornographic, gambling) is not scanned. Its place is taken by the watch-list sectors
    # "finance-worldwide" and "government-worldwide" (the highest-ranked such sites beyond the top `limit`),
    # so "top N" statistics only ever cover real Tranco ranks.
    for rank, domain in load_tranco(limit, tranco_path):
        if domain in seen or opted_out(domain, optout) or search_indexing.is_excluded(domain):
            continue
        targets.append({"domain": domain, "rank": rank, "sector": sector_of.get(domain)})
        seen.add(domain)
    for domain, key in sector_of.items():
        if domain not in seen and not opted_out(domain, optout) and not search_indexing.is_excluded(domain):
            targets.append({"domain": domain, "rank": None, "sector": key})
            seen.add(domain)
    return targets


# ---------------------------------------------------------------- التسجيل

def _summary_of(result, asn_lookup=None):
    kx = result.get("key_exchange") or {}
    cert = result.get("certificate") or {}
    ip = result.get("ip")
    asn, as_name = asn_lookup(ip) if (asn_lookup and ip) else (None, None)
    tls = kx.get("version") or cert.get("negotiated_version")
    return {"ok": 1, "grade": result.get("grade"), "grp": kx.get("group"),
            "tls": tls, "pq": 1 if kx.get("pq") else 0, "unsure": 1 if is_unsure(kx, tls) else 0,
            "ip": ip, "asn": asn, "as_name": as_name}


def is_unsure(kx, tls):
    """True when the key-exchange probe could not tell us the group (e.g. a firewall reset our
    ClientHello) and the server speaks TLS 1.3, so post-quantum support is unknown. TLS 1.2-only
    servers cannot negotiate ML-KEM, so those stay a definite «no»."""
    return bool(kx.get('hrr') or (tls != 'TLSv1.2' and
                (kx.get('error') or (not kx.get('group') and not kx.get('pq')))))


EMPTY = {"ok": 0, "grade": None, "grp": None, "tls": None, "pq": 0, "unsure": 0, "ip": None, "asn": None, "as_name": None}


def measured(row):
    """Answered and with a known post-quantum status: the only rows that count in percentages."""
    return bool(row["ok"]) and not row.get("unsure")


def record(conn, week, target, result, scanned_at, asn_lookup=None):
    """يحفظ نتيجة نطاق لأسبوع. result قاموس نتيجة الفحص، أو None إن لم يُجب. لا يُثبّت المعاملة."""
    s = _summary_of(result, asn_lookup) if result else EMPTY
    conn.execute(
        "INSERT OR REPLACE INTO adoption_results (week, domain, rank, sector, ok, grade, grp, tls, pq, scanned_at, ip, asn, as_name, unsure) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (week, target["domain"], target.get("rank"), target.get("sector"), s["ok"], s["grade"], s["grp"], s["tls"],
         s["pq"], scanned_at, s["ip"], s["asn"], s["as_name"], s["unsure"]))


def seed_from_study(conn, raw_path=RAW_STUDY_FILE):
    """أول أسبوع = بيانات الدراسة المنشورة. لا يفعل شيئاً إن وُجدت بيانات."""
    if conn.execute("SELECT 1 FROM adoption_results LIMIT 1").fetchone():
        return 0
    rows = [r for r in _raw_study_rows(raw_path) if not search_indexing.is_excluded(r["domain"])]
    sector_of = {}
    for key, sector in load_watchlists().items():
        for domain in sector.get("domains", []):
            sector_of.setdefault(domain.lower(), key)
    first_day = next(dt.date.fromisoformat(r["scanned_at"][:10]) for r in rows if r.get("scanned_at"))
    with conn:
        for row in rows:
            scanned_at = row.get("scanned_at") or f"{first_day.isoformat()}T00:00:00+00:00"
            day = dt.date.fromisoformat(scanned_at[:10])
            domain = row["domain"].lower()
            target = {"domain": domain, "rank": row["rank"], "sector": sector_of.get(domain)}
            record(conn, week_of(day), target, row if row.get("ok") else None, scanned_at)
    return len(rows)


def _scan_all(scanner, targets, workers, optout=None):
    optout_set = load_optout() if optout is None else optout

    def one(target):
        if opted_out(target["domain"], optout_set):
            return target, None
        try:
            return target, scanner(target["domain"])
        except Exception:  # أي فشل (لا عنوان، لا HTTPS، مهلة) = لم يُجب
            return target, None
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        yield from pool.map(one, targets)


def run_week(conn, scanner, targets, day=None, workers=16, now=None, asn_lookup=None, batch=200):
    """يفحص كل الأهداف ويحفظها تحت أسبوع اليوم. الفحص في خيوط، والكتابة في الخيط الرئيسي على دفعات."""
    week = week_of(day or dt.date.today())
    optout_set = load_optout(conn=conn)
    active_targets = [t for t in targets if not opted_out(t["domain"], optout_set)]
    answered = done = 0
    for target, result in _scan_all(scanner, active_targets, workers, optout=optout_set):
        stamp = (now or dt.datetime.now(dt.timezone.utc)).isoformat(timespec="seconds")
        record(conn, week, target, result, stamp, asn_lookup)
        answered += 1 if result else 0
        done += 1
        if done % batch == 0:
            conn.commit()
    conn.commit()
    return {"week": week, "targets": len(active_targets), "answered": answered}


def run_month(conn, scanner, targets, day=None, workers=32, asn_lookup=None, batch=500):
    """الفحص الشهري الواسع (أكبر 100 ألف): يُستعمل لجدول مزوّدي الاستضافة."""
    month = (day or dt.date.today()).strftime("%Y-%m")
    optout_set = load_optout(conn=conn)
    active_targets = [t for t in targets if not opted_out(t["domain"], optout_set)]
    answered = done = 0
    for target, result in _scan_all(scanner, active_targets, workers, optout=optout_set):
        s = _summary_of(result, asn_lookup) if result else EMPTY
        conn.execute(
            "INSERT OR REPLACE INTO adoption_monthly (month, domain, rank, ok, grade, grp, pq, asn, as_name, scanned_at, unsure) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (month, target["domain"], target.get("rank"), s["ok"], s["grade"], s["grp"], s["pq"], s["asn"], s["as_name"],
             dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), s["unsure"]))
        answered += 1 if result else 0
        done += 1
        if done % batch == 0:
            conn.commit()
    conn.commit()
    return {"month": month, "targets": len(active_targets), "answered": answered}


def purge_excluded(conn):
    """Removes excluded content (pornographic, gambling) from every stored week and month. Returns rows deleted."""
    hosts = sorted(search_indexing.reviewed_hosts())
    deleted = 0
    with conn:
        for i in range(0, len(hosts), 500):
            chunk = hosts[i:i + 500]
            marks = ",".join("?" * len(chunk))
            deleted += conn.execute(f"DELETE FROM adoption_results WHERE domain IN ({marks})", chunk).rowcount
            deleted += conn.execute(f"DELETE FROM adoption_monthly WHERE domain IN ({marks})", chunk).rowcount
    return deleted


def prune(conn, keep_weeks=KEEP_WEEKS, keep_months=KEEP_MONTHS):
    purge_excluded(conn)
    keep_w = weeks(conn)[-keep_weeks:]
    keep_m = [r[0] for r in conn.execute("SELECT DISTINCT month FROM adoption_monthly ORDER BY month")][-keep_months:]
    with conn:
        if keep_w:
            conn.execute(f"DELETE FROM adoption_results WHERE week NOT IN ({','.join('?' * len(keep_w))})", keep_w)
        if keep_m:
            conn.execute(f"DELETE FROM adoption_monthly WHERE month NOT IN ({','.join('?' * len(keep_m))})", keep_m)


# ---------------------------------------------------------------- القراءة

def weeks(conn):
    return [r[0] for r in conn.execute("SELECT DISTINCT week FROM adoption_results ORDER BY week")]


def rows_for(conn, week):
    cur = conn.execute("SELECT * FROM adoption_results WHERE week = ? ORDER BY rank IS NULL, rank, domain", (week,))
    return [dict(r) for r in cur]


def timeline(conn, limit=TIMELINE_WEEKS):
    """نسبة التبنّي أسبوعياً على الأكبر 1000 وحدها، حتى تبقى الأرقام قابلة للمقارنة."""
    cur = conn.execute(
        "SELECT week, SUM(CASE WHEN ok = 1 AND unsure = 0 THEN 1 ELSE 0 END) AS reachable, "
        "SUM(CASE WHEN ok = 1 AND unsure = 0 AND pq = 1 THEN 1 ELSE 0 END) AS pq "
        "FROM adoption_results WHERE rank IS NOT NULL AND rank <= ? GROUP BY week ORDER BY week", (TIMELINE_RANK,))
    points = []
    for r in cur:
        reachable, pq = r["reachable"] or 0, r["pq"] or 0
        points.append({"week": r["week"], "date": week_monday(r["week"]).isoformat(), "reachable": reachable,
                       "pq": pq, "pct": round(100 * pq / reachable, 1) if reachable else 0.0})
    return points[-limit:]


def tier_stats(rows, top):
    """نسبة الجاهزية بين الأكبر N في أسبوع واحد (None إن لم يُفحص هذا العدد)."""
    tier = [r for r in rows if r["rank"] is not None and r["rank"] <= top]
    if not tier or max(r["rank"] for r in tier) < top * 0.9:
        return None
    reachable = sum(1 for r in tier if measured(r))
    pq = sum(1 for r in tier if measured(r) and r["pq"])
    return {"top": top, "reachable": reachable, "pq": pq, "pct": round(100 * pq / reachable, 1) if reachable else 0.0}


def providers(conn, min_sites=PROVIDER_MIN_SITES, limit=30):
    """جاهزية كل شبكة (استضافة/CDN): من آخر فحص شهري إن وُجد، وإلا من آخر أسبوع."""
    month = conn.execute("SELECT MAX(month) FROM adoption_monthly").fetchone()[0]
    if month:
        source, label = ("SELECT asn, as_name, pq FROM adoption_monthly WHERE month = ? AND ok = 1 AND unsure = 0 AND asn IS NOT NULL",
                         (month,)), month
    else:
        all_weeks = weeks(conn)
        if not all_weeks:
            return None
        source, label = ("SELECT asn, as_name, pq FROM adoption_results WHERE week = ? AND ok = 1 AND unsure = 0 AND asn IS NOT NULL",
                         (all_weeks[-1],)), all_weeks[-1]
    counts = {}
    for asn, name, pq in conn.execute(*source):
        entry = counts.setdefault(asn, {"asn": asn, "name": name, "reachable": 0, "pq": 0})
        entry["reachable"] += 1
        entry["pq"] += 1 if pq else 0
    rows = [dict(e, pct=round(100 * e["pq"] / e["reachable"], 1)) for e in counts.values() if e["reachable"] >= min_sites]
    rows.sort(key=lambda e: (-e["reachable"], e["name"] or ""))
    sample = sum(e["reachable"] for e in counts.values())
    return {"period": label, "monthly": bool(month), "sites": sample, "rows": rows[:limit]} if rows else None


def first_pq_weeks(conn):
    cur = conn.execute("SELECT domain, MIN(week) FROM adoption_results WHERE ok = 1 AND pq = 1 GROUP BY domain")
    return {domain: week for domain, week in cur}


def changes(previous, current):
    """يقارن أسبوعين. لا يُحسب «فقد» لنطاق لم يُجب هذا الأسبوع: الغياب ليس تراجعاً."""
    prev = {r["domain"]: r for r in previous}
    adopted, dropped, regraded = [], [], []
    for row in current:
        before = prev.get(row["domain"])
        if not before or not measured(before) or not measured(row):
            continue
        if row["pq"] and not before["pq"]:
            adopted.append(dict(row, grade_before=before["grade"], grp_before=before["grp"]))
        elif before["pq"] and not row["pq"]:
            dropped.append(dict(row, grade_before=before["grade"], grp_before=before["grp"]))
        elif row["grade"] != before["grade"]:
            regraded.append(dict(row, grade_before=before["grade"], grp_before=before["grp"]))
    return {"adopted": adopted, "dropped": dropped, "regraded": regraded}


def snapshot(conn, watchlists=None):
    """كل ما تحتاجه الصفحة وملفات JSON/CSV. يعيد None إن لم تكن هناك بيانات بعد."""
    all_weeks = weeks(conn)
    if not all_weeks:
        return None
    week = all_weeks[-1]
    previous_week = all_weeks[-2] if len(all_weeks) > 1 else None
    current = rows_for(conn, week)
    diff = changes(rows_for(conn, previous_week), current) if previous_week else None
    points = timeline(conn)
    now_point = points[-1] if points else {"reachable": 0, "pq": 0, "pct": 0.0}
    prev_point = points[-2] if len(points) > 1 else None
    since = first_pq_weeks(conn)
    watchlists = load_watchlists() if watchlists is None else watchlists
    sectors = []
    for key, sector in watchlists.items():
        members = [dict(r, pq_since=since.get(r["domain"]) if r["pq"] else None)
                   for r in current if r["sector"] == key]
        members.sort(key=lambda r: (not r["ok"], bool(r.get("unsure")), not r["pq"], r["domain"]))
        sectors.append({"key": key, "labels": sector.get("labels", {}), "rows": members,
                        "reachable": sum(1 for r in members if measured(r)),
                        "pq": sum(1 for r in members if measured(r) and r["pq"]),
                        "unsure": sum(1 for r in members if r["ok"] and r.get("unsure"))})
    return {
        "week": week, "week_start": week_monday(week).isoformat(), "previous_week": previous_week,
        "scanned_at": max((r["scanned_at"] for r in current), default=""),
        "reachable": now_point["reachable"], "pq": now_point["pq"], "pct": now_point["pct"],
        "delta_pp": round(now_point["pct"] - prev_point["pct"], 1) if prev_point else None,
        "top10k": tier_stats(current, WEEKLY_TOP), "providers": providers(conn),
        "timeline": points, "changes": diff, "sectors": sectors, "rows": current,
    }


EXPORT_FIELDS = ["week", "domain", "rank", "sector", "ok", "grade", "grp", "tls", "pq", "unsure", "asn", "as_name", "scanned_at"]


def to_csv(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=EXPORT_FIELDS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k) for k in EXPORT_FIELDS})
    return out.getvalue()


# ---------------------------------------------------------------- صفحات النطاقات العامة (/site/<domain>)
def domain_history(conn, domain, limit=TIMELINE_WEEKS):
    """نتائج النطاق أسبوعاً بأسبوع (الأحدث أخيراً): ما يجعل كل صفحة نطاق فريدة وقابلة للاستشهاد."""
    cur = conn.execute("SELECT week, rank, ok, grade, grp, tls, pq, unsure, as_name, scanned_at FROM adoption_results "
                       "WHERE domain = ? ORDER BY week DESC LIMIT ?", (domain, limit))
    return [dict(r) for r in cur][::-1]


def latest_for(conn, domain):
    """آخر نتيجة أسبوعية أجاب فيها النطاق، أو None."""
    row = conn.execute("SELECT * FROM adoption_results WHERE domain = ? AND ok = 1 ORDER BY week DESC LIMIT 1",
                       (domain,)).fetchone()
    return dict(row) if row else None


def peers(conn, domain, as_name, week, limit=6):
    """نطاقات على الشبكة نفسها في الأسبوع نفسه (روابط داخلية ذات صلة)، الأعلى ترتيباً أولاً."""
    if not as_name:
        return []
    cur = conn.execute("SELECT domain, rank, sector, grade, pq, unsure FROM adoption_results WHERE week = ? "
                       "AND as_name = ? AND ok = 1 AND domain <> ? AND (rank IS NOT NULL OR sector IS NOT NULL) "
                       "ORDER BY rank IS NULL, rank LIMIT ?", (week, as_name, domain, limit))
    return [dict(r) for r in cur]


def rank_neighbors(conn, rank, week, domain, limit=6):
    """نطاقات قريبة في ترتيب Tranco: تربط كل صفحة بجيرانها فيصل الزاحف إلى كل الصفحات."""
    if rank is None:
        return []
    span = 4 * limit + 10  # نافذة صغيرة حول الترتيب فيُستعمل الفهرس بدل مسح الأسبوع كله
    cur = conn.execute("SELECT domain, grade, pq, unsure FROM adoption_results WHERE week = ? AND rank BETWEEN ? AND ? "
                       "AND ok = 1 AND domain <> ? ORDER BY ABS(rank - ?) LIMIT ?",
                       (week, rank - span, rank + span, domain, rank, limit))
    return [dict(r) for r in cur]


def site_domains(conn):
    """كل النطاقات التي أجابت في آخر أسبوع مع تاريخ فحصها، مرتبة حسب الترتيب (لخريطة الموقع)."""
    all_weeks = weeks(conn)
    if not all_weeks:
        return []
    cur = conn.execute("SELECT domain, substr(scanned_at, 1, 10), rank, sector FROM adoption_results "
                       "WHERE week = ? AND ok = 1 ORDER BY rank IS NULL, rank, domain", (all_weeks[-1],))
    return [tuple(r) for r in cur]
