# data_access.py — حماية بيانات السجل من النسخ الجماعي (الدفعة 5):
#  1) حدود طلبات لكل IP على /exposure/* و /site/* و /adoption.json|csv و /api/v1/* ، مع استثناء زواحف البحث والذكاء
#     الاصطناعي الموثّقة (DNS عكسي + أمامي، أو نطاقات IP المنشورة رسمياً)، وحدود أعلى لمفاتيح API المدفوعة.
#  2) مفاتيح API (تُصدر يدوياً عبر سطر الأوامر؛ لا أسعار هنا) تفتح التاريخ الكامل والتصدير الجماعي.
#  3) نطاقات «كناري» وهمية تُضاف إلى ملفات التصدير فقط، مختلفة لكل مُصدِّر/مفتاح، وتُسجَّل سراً في القاعدة.
# لا يغيّر الأسعار ولا الاشتراكات. أي خطأ في المحدِّد = السماح بالطلب (fail-open) حتى لا يتعطل الموقع.
import concurrent.futures as cf
import datetime as dt
import hashlib
import hmac
import ipaddress
import json
import os
import random
import secrets
import socket
import sqlite3
import struct
import sys
import threading
import time
import urllib.request

# ---------------------------------------------------------------- الحدود (طلبات لكل IP؛ IPv6 لكل ‎/64)
LIMITS = {
    # bucket: {tier: ((window_seconds, max_requests), ...)}
    "pages": {"anon": ((60, 60), (3600, 900)), "declared_bot": ((60, 120), (3600, 2400)), "key": ((60, 600), (3600, 20000))},
    "data": {"anon": ((60, 10), (3600, 60)), "declared_bot": ((60, 10), (3600, 60)), "key": ((60, 120), (3600, 2000))},
    "api": {"anon": ((60, 60), (3600, 1200)), "declared_bot": ((60, 60), (3600, 1200)), "key": ((60, 600), (3600, 20000))},
}
# حد إضافي لكل شبكة IPv4 ‎/24 (أو IPv6 ‎/48) ضد من يدوّر عناوين متجاورة؛ أعلى بكثير من حد العنوان الواحد.
NET_LIMITS = {"pages": ((60, 240), (3600, 4000)), "data": ((60, 30), (3600, 240)), "api": ((60, 240), (3600, 5000))}
EXEMPT_PREFIXES = ("/static/", "/mcp", "/sitemap", "/robots.txt", "/og/", "/favicon")


def bucket_for(path):
    if path in ("/adoption.json", "/adoption.csv") or path.startswith("/exposure/anchors/") or path.startswith("/api/v1/registry/"):
        return "data"
    if path.startswith("/api/v1/"):
        return "api"
    if path.startswith("/exposure/") or path.startswith("/site/"):
        return "pages"
    return None


# ---------------------------------------------------------------- الزواحف
# (اسم، علامات في User-Agent، لواحق DNS العكسي المقبولة، مفاتيح ملف النطاقات المنشورة)
BOTS = [
    ("google", ("googlebot", "google-inspectiontool", "googleother", "adsbot-google", "storebot-google", "google-extended"),
     (".googlebot.com", ".google.com"), ("google",)),
    ("bing", ("bingbot", "msnbot", "bingpreview", "adidxbot"), (".search.msn.com",), ("bing",)),
    ("apple", ("applebot",), (".applebot.apple.com",), ()),
    ("yandex", ("yandexbot", "yandex.com/bots"), (".yandex.ru", ".yandex.net", ".yandex.com"), ()),
    ("duckduckgo", ("duckduckbot", "duckassistbot"), (), ()),
    ("openai", ("gptbot", "oai-searchbot", "chatgpt-user"), (), ("openai",)),
    ("perplexity", ("perplexitybot", "perplexity-user"), (), ("perplexity",)),
    ("anthropic", ("claudebot", "claude-user", "claude-searchbot", "anthropic-ai"), (), ()),
    ("mistral", ("mistralai-user",), (), ()),
]
RANGE_SOURCES = {
    "google": ["https://developers.google.com/static/search/apis/ipranges/googlebot.json",
               "https://developers.google.com/static/crawling/ipranges/common-crawlers.json"],
    "bing": ["https://www.bing.com/toolbox/bingbot.json"],
    "openai": ["https://openai.com/gptbot.json", "https://openai.com/searchbot.json", "https://openai.com/chatgpt-user.json"],
    "perplexity": ["https://www.perplexity.ai/perplexitybot.json", "https://www.perplexity.ai/perplexity-user.json"],
}
VERIFY_TTL = 24 * 3600
_LOCAL = threading.local()
_VERIFY_CACHE = {}
_RANGES = {"loaded_at": 0, "nets": {}}
_DNS_POOL = cf.ThreadPoolExecutor(max_workers=4)


def bot_family(user_agent):
    ua = (user_agent or "").lower()
    for name, marks, _suffixes, _ranges in BOTS:
        if any(m in ua for m in marks):
            return name
    return None


def _load_ranges(data_dir):
    path = os.path.join(data_dir, "bot_ranges.json")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return _RANGES["nets"]
    if mtime != _RANGES["loaded_at"]:
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            _RANGES["nets"] = {fam: [ipaddress.ip_network(p, strict=False) for p in prefixes]
                               for fam, prefixes in raw.get("families", {}).items()}
            _RANGES["loaded_at"] = mtime
        except (OSError, ValueError):
            pass
    return _RANGES["nets"]


def refresh_ranges(data_dir, fetch=None):
    """ينزّل نطاقات IP المنشورة رسمياً للزواحف (يومياً). يحتفظ بالقديم لعائلة فشل تنزيلها."""
    fetch = fetch or (lambda url: urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "quantum-aether-botcheck/1.0"}), timeout=20).read())
    path = os.path.join(data_dir, "bot_ranges.json")
    try:
        with open(path, encoding="utf-8") as f:
            old = json.load(f).get("families", {})
    except (OSError, ValueError):
        old = {}
    families, report = {}, {}
    for fam, urls in RANGE_SOURCES.items():
        prefixes = []
        try:
            for url in urls:
                data = json.loads(fetch(url))
                for p in data.get("prefixes", []):
                    v = p.get("ipv4Prefix") or p.get("ipv6Prefix")
                    if v:
                        ipaddress.ip_network(v, strict=False)
                        prefixes.append(v)
            families[fam] = sorted(set(prefixes))
            report[fam] = len(families[fam])
        except Exception as exc:  # نحتفظ بالقائمة السابقة
            families[fam] = old.get(fam, [])
            report[fam] = f"kept {len(families[fam])} ({exc.__class__.__name__})"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"updated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "families": families}, f)
    os.replace(tmp, path)
    return report


def _rdns_verified(ip, suffixes, timeout=2.0):
    def work():
        host = socket.gethostbyaddr(ip)[0].lower().rstrip(".")
        if not any(host.endswith(s) for s in suffixes):
            return False
        addrs = {a[4][0] for a in socket.getaddrinfo(host, None)}
        return ip in addrs
    try:
        return _DNS_POOL.submit(work).result(timeout=timeout)
    except Exception:
        return False


def verify_bot(ip, family, data_dir, rdns=None):
    """True إن كان الـ IP فعلاً للزاحف المعلن (نطاقات منشورة أو DNS عكسي ثم أمامي). النتيجة مخزنة يوماً."""
    key = (ip, family)
    hit = _VERIFY_CACHE.get(key)
    now = time.time()
    if hit and now - hit[1] < VERIFY_TTL:
        return hit[0]
    ok = False
    try:
        addr = ipaddress.ip_address(ip)
        nets = _load_ranges(data_dir).get(family, [])
        ok = any(addr in n for n in nets)
    except ValueError:
        addr = None
    if not ok and addr is not None:
        suffixes = next((b[2] for b in BOTS if b[0] == family), ())
        if suffixes:
            ok = (rdns or _rdns_verified)(ip, suffixes)
    _VERIFY_CACHE[key] = (ok, now)
    if len(_VERIFY_CACHE) > 20000:
        _VERIFY_CACHE.clear()
    return ok


# ---------------------------------------------------------------- عدّاد الطلبات (SQLite مشترك بين عمليات gunicorn)

def _rl_conn(data_dir):
    path = os.path.join(data_dir, "ratelimit.db")
    conn = getattr(_LOCAL, "conn", None)
    if conn is None or getattr(_LOCAL, "path", None) != path:
        conn = sqlite3.connect(path, timeout=0.5, isolation_level=None, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=OFF")
        conn.execute("CREATE TABLE IF NOT EXISTS hits (k TEXT NOT NULL, w INTEGER NOT NULL, n INTEGER NOT NULL, "
                     "PRIMARY KEY (k, w)) WITHOUT ROWID")
        _LOCAL.conn, _LOCAL.path = conn, path
    return conn


def client_key(ip):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip or "-"
    if addr.version == 6:
        return str(ipaddress.ip_network(f"{ip}/64", strict=False))
    return ip


def network_key(ip):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    return "net:" + str(ipaddress.ip_network(f"{ip}/{24 if addr.version == 4 else 48}", strict=False))


def hit(data_dir, key, bucket, limits, now=None):
    """يزيد العدّادات ويعيد None إن سُمح، وإلا عدد الثواني حتى نهاية النافذة (Retry-After)."""
    now = int(now or time.time())
    conn = _rl_conn(data_dir)
    retry = None
    for window, maximum in limits:
        w = now // window
        n = conn.execute("INSERT INTO hits (k, w, n) VALUES (?, ?, 1) ON CONFLICT(k, w) DO UPDATE SET n = n + 1 RETURNING n",
                         (f"{bucket}|{window}|{key}", w)).fetchone()[0]
        if n > maximum:
            retry = max(retry or 0, (w + 1) * window - now)
    if random.random() < 0.01:
        conn.execute("DELETE FROM hits WHERE w < ? AND k LIKE '%|60|%'", (now // 60 - 5,))
        conn.execute("DELETE FROM hits WHERE w < ? AND k LIKE '%|3600|%'", (now // 3600 - 2,))
    return retry


# ---------------------------------------------------------------- مفاتيح API

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash    TEXT NOT NULL UNIQUE,
    prefix      TEXT NOT NULL,
    label       TEXT NOT NULL,
    tier        TEXT NOT NULL DEFAULT 'data',
    created_at  TEXT NOT NULL,
    revoked_at  TEXT
);
CREATE TABLE IF NOT EXISTS data_canaries (
    domain        TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    last_checked  TEXT,
    status        TEXT NOT NULL DEFAULT 'active'      -- active | retired (بدأ يُحَل في DNS)
);
CREATE TABLE IF NOT EXISTS data_canary_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    export      TEXT NOT NULL,
    week        TEXT,
    canaries    TEXT NOT NULL,
    client_hash TEXT,
    api_key_id  INTEGER,
    user_agent  TEXT,
    UNIQUE (export, week, canaries, client_hash, api_key_id)
);
"""


def init(conn):
    conn.executescript(SCHEMA)


def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def create_key(conn, label, tier="data"):
    init(conn)
    key = "qa_" + secrets.token_urlsafe(30)
    with conn:
        conn.execute("INSERT INTO api_keys (key_hash, prefix, label, tier, created_at) VALUES (?, ?, ?, ?, ?)",
                     (hashlib.sha256(key.encode()).hexdigest(), key[:10], label[:120], tier, _now()))
    return key


def revoke_key(conn, prefix_or_id):
    init(conn)
    with conn:
        return conn.execute("UPDATE api_keys SET revoked_at = ? WHERE (prefix = ? OR id = ?) AND revoked_at IS NULL",
                            (_now(), str(prefix_or_id), str(prefix_or_id))).rowcount


def lookup_key(conn, key):
    if not key or not key.startswith("qa_") or len(key) > 100:
        return None
    init(conn)
    row = conn.execute("SELECT id, label, tier FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
                       (hashlib.sha256(key.encode()).hexdigest(),)).fetchone()
    return {"id": row[0], "label": row[1], "tier": row[2]} if row else None


def key_from_headers(headers):
    auth = headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return (headers.get("X-API-Key") or "").strip() or None


# ---------------------------------------------------------------- نطاقات الكناري
# أسماء شركات معقولة (DACH / الخليج / أوروبا) على نطاقات عليا حقيقية. لا تُستخدم إلا إن أعاد DNS العام NXDOMAIN
# للاسم (غير مسجَّل/غير مفوَّض) من محلِّلَين مختلفين، ويُعاد فحصها يومياً؛ أي اسم يبدأ بالحل يُسحب فوراً من الاستعمال.
CANARY_WORDS_A = ["alpen", "donau", "nordhafen", "kremser", "inntal", "bodensee", "falkenried", "lindgruen", "rheinfeld",
                  "tauern", "wachau", "seewinkel", "almtal", "murtal", "lechfeld", "salzach", "gurktal", "ennstal"]
CANARY_WORDS_B = ["treuhand", "datenwerk", "logistik-gruppe", "privatbank", "versicherung", "netzdienste", "handelshaus",
                  "kapital", "systemhaus", "beteiligungen", "finanzpartner", "it-services", "energiehandel", "verwaltung"]
CANARY_TLDS = ["at", "de", "ch", "eu"]


def _dns_rcode(name, qtype=2, nameserver="1.1.1.1", timeout=3.0):
    qid = random.randint(0, 65535)
    q = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0)
    for label in name.rstrip(".").split("."):
        q += bytes([len(label)]) + label.encode("ascii")
    q += b"\x00" + struct.pack(">HH", qtype, 1)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(q, (nameserver, 53))
        data = s.recv(4096)
    finally:
        s.close()
    flags = struct.unpack(">H", data[2:4])[0]
    return flags & 0x000F  # 3 = NXDOMAIN


def is_unregistered(domain, rcode=None):
    rcode = rcode or _dns_rcode
    try:
        return all(rcode(domain, 2, ns) == 3 for ns in ("1.1.1.1", "8.8.8.8"))
    except Exception:
        return False


def generate_canaries(conn, count=40, rcode=None, rng=None):
    """يملأ مخزون الكناري حتى `count` اسماً نشطاً، كلها NXDOMAIN لحظة الإنشاء."""
    init(conn)
    rng = rng or random.SystemRandom()
    have = conn.execute("SELECT COUNT(*) FROM data_canaries WHERE status = 'active'").fetchone()[0]
    tries = 0
    while have < count and tries < count * 10:
        tries += 1
        name = f"{rng.choice(CANARY_WORDS_A)}-{rng.choice(CANARY_WORDS_B)}.{rng.choice(CANARY_TLDS)}"
        if conn.execute("SELECT 1 FROM data_canaries WHERE domain = ?", (name,)).fetchone():
            continue
        if not is_unregistered(name, rcode):
            continue
        with conn:
            conn.execute("INSERT INTO data_canaries (domain, created_at, last_checked) VALUES (?, ?, ?)", (name, _now(), _now()))
        have += 1
    return have


def recheck_canaries(conn, rcode=None):
    """يومياً: أي كناري صار يُحَل (سُجِّل) يُسحب نهائياً حتى لا نشير أبداً إلى نطاق حقيقي لطرف ثالث."""
    init(conn)
    retired = []
    for (name,) in conn.execute("SELECT domain FROM data_canaries WHERE status = 'active'").fetchall():
        if is_unregistered(name, rcode):
            conn.execute("UPDATE data_canaries SET last_checked = ? WHERE domain = ?", (_now(), name))
        else:
            conn.execute("UPDATE data_canaries SET status = 'retired', last_checked = ? WHERE domain = ?", (_now(), name))
            retired.append(name)
    conn.commit()
    return retired


def active_canaries(conn):
    init(conn)
    return [r[0] for r in conn.execute("SELECT domain FROM data_canaries WHERE status = 'active' ORDER BY domain")]


def is_canary(conn, domain):
    init(conn)
    return bool(conn.execute("SELECT 1 FROM data_canaries WHERE domain = ?", ((domain or "").lower(),)).fetchone())


def pick_canaries(conn, salt, export, week, ident, n=2):
    pool = active_canaries(conn)
    if len(pool) < n:
        return []
    seed = hmac.new((salt or "").encode(), f"{export}|{week}|{ident}".encode(), hashlib.sha256).digest()
    rng = random.Random(seed)
    return rng.sample(pool, n)


def log_canaries(conn, export, week, canaries, client_hash=None, api_key_id=None, user_agent=None):
    init(conn)
    with conn:
        conn.execute("INSERT OR IGNORE INTO data_canary_log (created_at, export, week, canaries, client_hash, api_key_id, user_agent) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)", (_now()[:10], export, week, ",".join(canaries), client_hash or "", api_key_id or 0,
                                                       (user_agent or "")[:200]))


def watermark_rows(rows, canaries, salt, week):
    """يضيف صفاً معقولاً لكل كناري: قيمه منسوخة من صف حقيقي يختاره hash (بلا ترتيب Tranco ولا قطاع)، ثم يعيد الترتيب."""
    real = [r for r in rows if r.get("ok") and r.get("as_name")]
    if not real or not canaries:
        return list(rows)
    out = list(rows)
    for name in canaries:
        idx = int(hmac.new((salt or "").encode(), f"row|{week}|{name}".encode(), hashlib.sha256).hexdigest(), 16) % len(real)
        src = dict(real[idx])
        stamp = str(src.get("scanned_at") or "")
        fake = {k: src.get(k) for k in src}
        fake.update(domain=name, rank=None, sector=None, ip=None)
        fake["scanned_at"] = stamp
        out.append(fake)
    out.sort(key=lambda r: (r.get("week") or "", r.get("rank") is None, r.get("rank") or 0, r.get("domain") or ""))
    return out


# ---------------------------------------------------------------- سطر الأوامر

def _main(argv):
    import sales_db
    data_dir = os.environ.get("QS_DATA_DIR") or "/var/lib/quantum_saas"
    conn = sales_db.connect(os.path.join(data_dir, "quantum_saas.db"))
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "create-key":
        label = argv[2] if len(argv) > 2 else "unnamed"
        tier = argv[3] if len(argv) > 3 else "data"
        print(create_key(conn, label, tier))
    elif cmd == "revoke-key":
        print(revoke_key(conn, argv[2]))
    elif cmd == "list-keys":
        init(conn)
        for r in conn.execute("SELECT id, prefix, label, tier, created_at, revoked_at FROM api_keys"):
            print(tuple(r))
    elif cmd == "refresh-bots":
        print(refresh_ranges(data_dir))
    elif cmd == "canaries":
        print("active:", generate_canaries(conn), "retired now:", recheck_canaries(conn))
    else:
        print("usage: data_access.py create-key LABEL [TIER] | revoke-key PREFIX|ID | list-keys | refresh-bots | canaries")


if __name__ == "__main__":
    _main(sys.argv)
