# discovery.py
# كشف النطاقات الفرعية: أسماء من سجلات شفافية الشهادات (crt.sh، ثم Cert Spotter احتياطاً) ثم فحص تبادل المفاتيح لكل اسم يعمل.
# الصفحة العامة تعرض الأعداد فقط. القائمة الكاملة لا تُعرض إلا بعد تأكيد بريد على النطاق نفسه (يثبت الانتماء للجهة)
# لأن أسماء مثل test/soap/vpn خريطة مفيدة للمهاجمين. النتائج تُخزَّن 24 ساعة لكل نطاق أساسي.
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import secrets
import threading

import adoption
import quantum_vuln_scanner as qs

MAX_HOSTS = 200            # أقصى عدد أسماء نفحصها لكل نطاق
PROBE_TIMEOUT = 4.0
PROBE_WORKERS = 16
CACHE_HOURS = 24
RUN_STALE_MINUTES = 5      # تشغيل «RUNNING» أقدم من هذا يُعتبر فاشلاً (توقف العامل)
RUNS_PER_CLIENT_PER_DAY = 6
GLOBAL_RUNNING_MAX = 3     # تشغيلات متزامنة على الخادم كله
REQUESTS_PER_CLIENT_PER_DAY = 5
CONFIRMATIONS_PER_EMAIL_PER_DAY = 3
REQUEST_TTL_DAYS = 7
HTTP_TIMEOUT = 25

SCHEMA = """
CREATE TABLE IF NOT EXISTS discoveries (
    base        TEXT PRIMARY KEY,
    status      TEXT NOT NULL,              -- RUNNING / DONE / FAILED
    source      TEXT,
    names       INTEGER, responding INTEGER, pq INTEGER, not_pq INTEGER, unknown INTEGER,
    hosts_json  TEXT,
    error       TEXT,
    client_hash TEXT,
    started_at  TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS discovery_runs (client_hash TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS discovery_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    email        TEXT NOT NULL,
    base         TEXT NOT NULL,
    lang         TEXT NOT NULL DEFAULT 'en',
    token_hash   TEXT NOT NULL UNIQUE,
    status       TEXT NOT NULL DEFAULT 'PENDING',   -- PENDING / CONFIRMED
    client_hash  TEXT,
    consent_at   TEXT NOT NULL,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    confirmed_at TEXT
);
"""

_running = threading.BoundedSemaphore(2)  # لكل عامل gunicorn


def init(conn):
    conn.executescript(SCHEMA)


def _now(delta=None):
    t = dt.datetime.now(dt.timezone.utc) + (delta or dt.timedelta())
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def base_domain(domain):
    """النطاق الذي نبحث تحته: نحذف www. فقط (لا نخمّن النطاق القابل للتسجيل)."""
    d = domain.lower().rstrip(".")
    return d[4:] if d.startswith("www.") and d.count(".") >= 2 else d


def email_matches(email, base):
    """البريد على النطاق نفسه أو نطاق أب/فرعي منه: you@dkb.de يصلح لـ dkb.de و business.dkb.de."""
    host = email.rsplit("@", 1)[-1].lower().rstrip(".")
    return host == base or base.endswith("." + host) or host.endswith("." + base)


# ---------------------------------------------------------------- مصادر الأسماء

def _clean(names, base):
    out = set()
    for n in names:
        n = (n or "").strip().lower().rstrip(".")
        if not n or n.startswith("*.") or "*" in n or " " in n:
            continue
        if n == base or n.endswith("." + base):
            out.add(n)
    return out


def ct_names_crtsh(base, http):
    r = http.get("https://crt.sh/", params={"q": "%." + base, "output": "json", "exclude": "expired"},
                 timeout=HTTP_TIMEOUT, headers={"User-Agent": "QuantumAether-Discovery/1.0"})
    r.raise_for_status()
    names = []
    for e in r.json():
        names.extend((e.get("name_value") or "").split("\n"))
        names.append(e.get("common_name") or "")
    return _clean(names, base)


def ct_names_certspotter(base, http):
    r = http.get("https://api.certspotter.com/v1/issuances",
                 params={"domain": base, "include_subdomains": "true", "expand": "dns_names"},
                 timeout=HTTP_TIMEOUT, headers={"User-Agent": "QuantumAether-Discovery/1.0"})
    r.raise_for_status()
    names = []
    for e in r.json():
        names.extend(e.get("dns_names") or [])
    return _clean(names, base)


def ct_names(base, http):
    """يعيد (الأسماء، المصدر). crt.sh يفشل أحياناً (502): محاولتان ثم Cert Spotter."""
    errors = []
    for source, fn, tries in (("crt.sh", ct_names_crtsh, 2), ("certspotter", ct_names_certspotter, 1)):
        for _ in range(tries):
            try:
                return fn(base, http), source
            except Exception as exc:  # noqa: BLE001 — أي فشل ينتقل للمصدر التالي
                errors.append(f"{source}: {type(exc).__name__}")
    raise RuntimeError("; ".join(errors))


# ---------------------------------------------------------------- الفحص

def classify(kx):
    if kx.get("pq"):
        return "pq"
    if adoption.is_unsure(kx, kx.get("version")):
        return "unknown"
    return "not_pq"


def probe_host(host):
    try:
        ip = qs.resolve_public_ip(host)
    except qs.ScanError:
        return None  # لا DNS أو عنوان داخلي: لا يُعدّ
    try:
        kx = qs.probe_key_exchange(ip, host, timeout=PROBE_TIMEOUT)
    except Exception:  # noqa: BLE001
        return None    # لا يرد على 443
    if kx.get("error") and not kx.get("version") and not kx.get("group"):
        return None
    return {"host": host, "status": classify(kx), "group": kx.get("group"), "version": kx.get("version")}


def run_discovery(base, http, probe=probe_host, optout=None):
    names, source = ct_names(base, http)
    optout = adoption.load_optout() if optout is None else optout
    names = sorted(n for n in names if not adoption.opted_out(n, optout))
    total = len(names)
    names = names[:MAX_HOSTS]
    with cf.ThreadPoolExecutor(PROBE_WORKERS) as ex:
        hosts = [h for h in ex.map(probe, names) if h]
    hosts.sort(key=lambda h: ({"not_pq": 0, "unknown": 1, "pq": 2}[h["status"]], h["host"]))
    count = lambda s: sum(1 for h in hosts if h["status"] == s)
    return {"source": source, "names": total, "responding": len(hosts),
            "pq": count("pq"), "not_pq": count("not_pq"), "unknown": count("unknown"), "hosts": hosts}


# ---------------------------------------------------------------- التخزين والتشغيل

def get(conn, base):
    row = conn.execute("SELECT * FROM discoveries WHERE base = ?", (base,)).fetchone()
    if not row:
        return None
    d = dict(row)
    if d["status"] == "RUNNING" and d["started_at"] < _now(dt.timedelta(minutes=-RUN_STALE_MINUTES)):
        d["status"] = "FAILED"
    d["hosts"] = json.loads(d.pop("hosts_json") or "[]")
    return d


def public_summary(d):
    """ما يُعرض علناً: أعداد فقط، بلا أسماء."""
    if not d:
        return {"status": "NONE"}
    keys = ("status", "names", "responding", "pq", "not_pq", "unknown", "finished_at")
    return {k: d.get(k) for k in keys}


def fresh(d):
    return d and d["status"] == "DONE" and (d["finished_at"] or "") >= _now(dt.timedelta(hours=-CACHE_HOURS))


def start(conn, base, client_hash):
    """يحجز تشغيلاً. يعيد 'cached' أو 'running' أو 'started' أو 'rate_limited' أو 'busy'."""
    d = get(conn, base)
    if fresh(d):
        return "cached"
    if d and d["status"] == "RUNNING":
        return "running"
    day_ago = _now(dt.timedelta(days=-1))
    if conn.execute("SELECT COUNT(*) FROM discovery_runs WHERE client_hash = ? AND created_at >= ?",
                    (client_hash, day_ago)).fetchone()[0] >= RUNS_PER_CLIENT_PER_DAY:
        return "rate_limited"
    stale = _now(dt.timedelta(minutes=-RUN_STALE_MINUTES))
    if conn.execute("SELECT COUNT(*) FROM discoveries WHERE status = 'RUNNING' AND started_at >= ?",
                    (stale,)).fetchone()[0] >= GLOBAL_RUNNING_MAX:
        return "busy"
    with conn:
        conn.execute("INSERT INTO discovery_runs VALUES (?, ?)", (client_hash, _now()))
        conn.execute("INSERT OR REPLACE INTO discoveries (base, status, client_hash, started_at) VALUES (?, 'RUNNING', ?, ?)",
                     (base, client_hash, _now()))
    return "started"


def finish(conn, base, result=None, error=None):
    with conn:
        if result is not None:
            conn.execute("UPDATE discoveries SET status='DONE', source=?, names=?, responding=?, pq=?, not_pq=?, unknown=?, "
                         "hosts_json=?, error=NULL, finished_at=? WHERE base=?",
                         (result["source"], result["names"], result["responding"], result["pq"], result["not_pq"],
                          result["unknown"], json.dumps(result["hosts"]), _now(), base))
        else:
            conn.execute("UPDATE discoveries SET status='FAILED', error=?, finished_at=? WHERE base=?",
                         (str(error)[:200], _now(), base))


def run_in_background(connect, base, http, probe=probe_host):
    """يشغّل الكشف في خيط (لا يحجز طلب HTTP). connect() يفتح اتصال قاعدة بيانات جديداً للخيط."""
    def work():
        with _running:
            conn = connect()
            try:
                finish(conn, base, result=run_discovery(base, http, probe))
            except Exception as exc:  # noqa: BLE001
                finish(conn, base, error=exc)
            finally:
                conn.close()
    t = threading.Thread(target=work, name=f"discovery-{base}", daemon=True)
    t.start()
    return t


# ---------------------------------------------------------------- طلب القائمة الكاملة (تأكيد مزدوج)

def request_list(conn, email, base, lang, client_hash):
    email = email.strip().lower()
    day_ago = _now(dt.timedelta(days=-1))
    if (conn.execute("SELECT COUNT(*) FROM discovery_requests WHERE client_hash = ? AND created_at >= ?",
                     (client_hash, day_ago)).fetchone()[0] >= REQUESTS_PER_CLIENT_PER_DAY or
            conn.execute("SELECT COUNT(*) FROM discovery_requests WHERE email = ? AND created_at >= ?",
                         (email, day_ago)).fetchone()[0] >= CONFIRMATIONS_PER_EMAIL_PER_DAY):
        return None, "rate_limited"
    token = secrets.token_urlsafe(24)
    with conn:
        conn.execute("INSERT INTO discovery_requests (email, base, lang, token_hash, client_hash, consent_at) "
                     "VALUES (?, ?, ?, ?, ?, ?)", (email, base, lang, _hash(token), client_hash, _now()))
    return token, None


def get_request(conn, token):
    row = conn.execute("SELECT * FROM discovery_requests WHERE token_hash = ? AND created_at >= ?",
                       (_hash(token), _now(dt.timedelta(days=-REQUEST_TTL_DAYS)))).fetchone()
    return dict(row) if row else None


def confirm_request(conn, token):
    req = get_request(conn, token)
    if req and req["status"] != "CONFIRMED":
        with conn:
            conn.execute("UPDATE discovery_requests SET status='CONFIRMED', confirmed_at=? WHERE id=?", (_now(), req["id"]))
        req = get_request(conn, token)
    return req


def prune(conn):
    """طلبات غير مؤكدة أقدم من 7 أيام تُحذف (لا نحتفظ ببريد لم يؤكده صاحبه)."""
    with conn:
        conn.execute("DELETE FROM discovery_requests WHERE status='PENDING' AND created_at < ?",
                     (_now(dt.timedelta(days=-REQUEST_TTL_DAYS)),))
        conn.execute("DELETE FROM discovery_runs WHERE created_at < ?", (_now(dt.timedelta(days=-2)),))


# ---------------------------------------------------------------- الرسائل

_CONFIRM = {
    "en": ("Your subdomain list for {base}",
           "Hello,\n\nyou asked for the full list of {base} subdomains we checked for post-quantum TLS. "
           "Open it here (link valid 7 days):\n\n{url}\n\nIf you did not ask for this, ignore this email; "
           "the request is deleted after 7 days.\n\nQuantum Aether · {site}"),
    "ar": ("قائمة النطاقات الفرعية لـ {base}",
           "مرحباً،\n\nطلبت القائمة الكاملة لنطاقات {base} الفرعية التي فحصنا دعمها لـ TLS ما بعد الكمومي. "
           "افتحها من هنا (الرابط صالح 7 أيام):\n\n{url}\n\nإن لم تطلب هذا فتجاهل الرسالة؛ يُحذف الطلب بعد 7 أيام.\n\n"
           "الأثير الكمومي · {site}"),
    "de": ("Ihre Subdomain-Liste für {base}",
           "Guten Tag,\n\nSie haben die vollständige Liste der Subdomains von {base} angefordert, die wir auf Post-Quanten-TLS "
           "geprüft haben. Hier öffnen (Link 7 Tage gültig):\n\n{url}\n\nFalls Sie das nicht angefordert haben, ignorieren Sie "
           "diese E-Mail; die Anfrage wird nach 7 Tagen gelöscht.\n\nQuantum Aether · {site}"),
}


def confirm_email(lang, base, url, site):
    subject, body = _CONFIRM[lang if lang in _CONFIRM else "en"]
    return subject.format(base=base), body.format(base=base, url=url, site=site)
