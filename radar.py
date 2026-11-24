# radar.py — رادار الاهتمام: يجد النقاشات العامة الجديدة عن TLS المقاوم للكم، ويرسل لصاحب الموقع
# كل صباح قائمة بها مع مسودة ردّ مفيد. الرد ينشره صاحب الموقع بيده؛ الرادار لا ينشر ولا يراسل أحداً.
#
# الخصوصية: واجهات رسمية عامة فقط (HN Algolia، Stack Exchange، GitHub)، بلا تخفٍّ ولا بروكسيات.
# لا نحفظ أسماء ولا حسابات: فقط رابط النقاش وعنوانه ومصدره وتاريخ رؤيته، لمنع التكرار.
import datetime as dt
import html
import json
import re
import time
import urllib.parse
import urllib.request

USER_AGENT = "QuantumAetherRadar/1.0 (+https://ather-quantum.com)"
BASE = "https://ather-quantum.com"

# HN وStack Exchange: البحث يطلب كل كلمات الاستعلام، فـ "post-quantum" وحدها تلتقط نقاشات TLS التي لا تذكر الكلمة.
QUERIES = ["X25519MLKEM768", "MLKEM768", "ML-KEM TLS", "post-quantum TLS", "post quantum nginx",
           "hybrid key exchange TLS", "post-quantum", "ML-KEM openssl"]
# GitHub بلا تسجيل دخول: 10 طلبات بحث بالدقيقة، فنترك GITHUB_PAUSE ثوانٍ بين الطلبات.
GITHUB_QUERIES = ["X25519MLKEM768", "MLKEM768", "post-quantum TLS", "ClientHello ML-KEM",
                  "ML-KEM openssl", "post-quantum nginx", "post-quantum cloudflare"]
GITHUB_PAUSE = 7

SCHEMA = """
CREATE TABLE IF NOT EXISTS radar_seen (
    url       TEXT PRIMARY KEY,
    source    TEXT NOT NULL,
    title     TEXT,
    topic     TEXT,
    found_at  TEXT NOT NULL,
    intent    TEXT,
    stack     TEXT,
    snippet   TEXT,
    score     INTEGER,
    status    TEXT DEFAULT 'new'
);
"""
# أعمدة التحليل المضافة (intent/stack/snippet/score/status): تُضاف لقواعد قديمة عبر ALTER.
ANALYSIS_COLUMNS = (("intent", "TEXT"), ("stack", "TEXT"), ("snippet", "TEXT"),
                    ("score", "INTEGER"), ("status", "TEXT DEFAULT 'new'"))

CORE = re.compile(r"x25519mlkem768|mlkem|ml-kem|kyber|post[- ]?quantum|pqc|harvest now", re.I)
CONTEXT = re.compile(r"\btls\b|https|ssl|nginx|apache|caddy|haproxy|cloudflare|openssl|certificate|key exchange|web ?server"
                     r"|let'?s encrypt|clienthello|client hello|handshake|key share|middlebox|load balancer|firewall", re.I)
NOISE = re.compile(r"^(bump|build\(deps|chore|update dependency|\[snyk\]|release v?\d)", re.I)
# خارج نطاقنا: أدوات تجاوز الحجب (أصحابها ليسوا مشغّلي مواقع)، وتقارير آلية، وبلوك تشين.
OFF_TOPIC = re.compile(r"vless|\breality\b|xray|v2ray|mihomo|clash|sing-box|hiddify|shadowsocks|trojan|订阅|节点"
                       r"|rustsec-|security advisor|security report|отчёт|briefing|digest|technology radar|findings detected"
                       r"|\bchwg-|\[ioc\]|\[new-research\]|arxiv|blockchain|wallet|testnet|ledger|layer-1|\bl1\b|new release v", re.I)
# عطل توافق حقيقي يسبّبه ML-KEM عند من يشغّل خدمة أو عميلاً، حتى لو لم يذكر اسم خادم ويب.
# يجب أن يجتمع في العنوان نفسه فعل عطل وسبب له، وإلا كثرت نقاشات مطوّري المكتبات الداخلية.
FAILURE = re.compile(r"\bfail|\bhangs?\b|\bdrops?\b|\breset\b|refused|\bclosed?\b|timeout|bypass|\berror\b|schließt"
                     r"|validate|excludes?|broken|not work|does not support", re.I)
CAUSE = re.compile(r"clienthello|client hello|middlebox|firewall|load balancer|prox(?:y|ies)|fragment|oversized|decode_error"
                   r"|alert \d+|handshake|connect|negotiat|interop|compatib|post-quantum|pqc|ml-kem|x25519mlkem768", re.I)


def _breakage(title):
    return bool(FAILURE.search(title) and CAUSE.search(title))
QUESTION = re.compile(r"\?|\bhow\b|\benable\b|\bsupport\b|\berror\b|\bfail|\bnot work|\bwhy\b|\bconfigure", re.I)
# في GitHub نريد من يشغّل خادماً أو بنية TLS ويسأل عن تفعيله، لا نقاشات داخلية لمطوّري المكتبات
WEBSERVER = re.compile(
    r"nginx|apache|httpd|caddy|haproxy|cloudflare|traefik|envoy|web ?server|reverse proxy|ingress"
    r"|openssl|cloudfront|aws alb|azure|iis|f5|big-ip|fortinet|palo alto|kubernetes|istio|certbot|let'?s encrypt",
    re.I,
)

TOPICS = [("clienthello", re.compile(r"clienthello|client hello|middlebox|firewall|load balancer|fragment|oversized"
                                     r"|decode_error", re.I)),
          ("nginx", re.compile(r"nginx", re.I)), ("apache", re.compile(r"apache|httpd", re.I)),
          ("caddy", re.compile(r"caddy", re.I)), ("haproxy", re.compile(r"haproxy", re.I)),
          ("cloudflare", re.compile(r"cloudflare", re.I)), ("openssl", re.compile(r"openssl", re.I))]

GUIDES = {
    "clienthello": f"{BASE}/guides/enable-x25519mlkem768-nginx",  # قسم "Large ClientHello"
    "nginx": f"{BASE}/guides/enable-x25519mlkem768-nginx",
    "openssl": f"{BASE}/guides/enable-x25519mlkem768-nginx",
    "apache": f"{BASE}/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare",
    "caddy": f"{BASE}/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare",
    "haproxy": f"{BASE}/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare",
    "cloudflare": f"{BASE}/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare",
    "general": f"{BASE}/guides/harvest-now-decrypt-later",
}

HINTS = {
    "clienthello": "The X25519MLKEM768 key share makes the ClientHello about 1.2 KB larger, so it often spans two TCP "
                   "segments or TLS records. Middleboxes, firewalls or parsers that expect it in one packet drop or reset "
                   "the connection; updating that device, or temporarily offering X25519 alone, confirms the cause.",
    "nginx": "nginx needs to be built against OpenSSL 3.5 or newer; then `ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1;` "
             "in the server block enables the hybrid group with a classical fallback.",
    "openssl": "OpenSSL 3.5 ships ML-KEM natively, so X25519MLKEM768 is available as a group without the oqs-provider; "
               "older 3.x builds need the provider or an upgrade.",
    "apache": "Apache httpd uses `SSLOpenSSLConfCmd Groups X25519MLKEM768:X25519:prime256v1` on top of OpenSSL 3.5+.",
    "caddy": "Recent Caddy releases (built with Go 1.24+) negotiate X25519MLKEM768 by default, so updating Caddy is usually enough.",
    "haproxy": "HAProxy built with OpenSSL 3.5+ accepts `curves X25519MLKEM768:X25519:P-256` on the bind line.",
    "cloudflare": "Cloudflare already offers X25519MLKEM768 to browsers on the edge; the origin connection is a separate setting.",
    "general": "Browsers (Chrome, Firefox, Edge) already offer X25519MLKEM768; whether a connection uses it depends on the server "
               "or CDN, and the classical group stays as a fallback.",
}


def init(conn):
    conn.executescript(SCHEMA)
    have = {r[1] for r in conn.execute("PRAGMA table_info(radar_seen)")}
    with conn:
        for col, ddl in ANALYSIS_COLUMNS:
            if col not in have:
                conn.execute(f"ALTER TABLE radar_seen ADD COLUMN {col} {ddl}")


# ---------------------------------------------------------------- الجلب (واجهات رسمية فقط)

def _get_json(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def fetch_hn(query, since, get=_get_json):
    params = urllib.parse.urlencode({"query": query, "tags": "(story,comment)", "hitsPerPage": 30,
                                     "numericFilters": f"created_at_i>{int(since.timestamp())}"})
    data = get("https://hn.algolia.com/api/v1/search_by_date?" + params)
    items = []
    for h in data.get("hits", []):
        title = h.get("title") or h.get("story_title") or ""
        items.append({"source": "Hacker News", "url": f"https://news.ycombinator.com/item?id={h['objectID']}",
                      "title": _clean(title), "text": _clean(h.get("comment_text") or h.get("story_text") or "")[:600],
                      "created": h.get("created_at", "")})
    return items


def fetch_stackexchange(query, since, site, get=_get_json):
    params = urllib.parse.urlencode({"order": "desc", "sort": "creation", "q": query, "site": site,
                                     "fromdate": int(since.timestamp()), "pagesize": 30})
    data = get("https://api.stackexchange.com/2.3/search/advanced?" + params)
    names = {"serverfault": "Server Fault", "stackoverflow": "Stack Overflow", "security": "Security SE",
             "superuser": "Super User", "devops": "DevOps SE"}
    return [{"source": names.get(site, site), "url": i["link"], "title": _clean(i.get("title")),
             "text": " ".join(i.get("tags", [])), "created": dt.datetime.fromtimestamp(i["creation_date"], dt.timezone.utc).isoformat()}
            for i in data.get("items", [])]


def fetch_github(query, since, get=_get_json):
    q = f'"{query}" is:issue created:>{since.date().isoformat()}'
    data = get("https://api.github.com/search/issues?" + urllib.parse.urlencode({"q": q, "sort": "created", "per_page": 30}))
    return [{"source": "GitHub", "url": i["html_url"], "title": _clean(i.get("title")),
             "text": _clean(i.get("body"))[:600], "created": i.get("created_at", "")}
            for i in data.get("items", [])]


def collect(since, get=_get_json, sleep=None):
    """يجمع من كل المصادر. فشل مصدر واحد لا يوقف الباقي."""
    if sleep is None:  # ننتظر فقط مع الشبكة الحقيقية، لا في الاختبارات
        sleep = time.sleep if get is _get_json else (lambda seconds: None)
    se_sites = ("serverfault", "stackoverflow", "security", "devops")
    jobs = [(name, query, fn) for query in QUERIES
            for name, fn in ([("hn", lambda q: fetch_hn(q, since, get))]
                             + [(s, (lambda q, s=s: fetch_stackexchange(q, since, s, get))) for s in se_sites])]
    jobs += [("github", query, lambda q: fetch_github(q, since, get)) for query in GITHUB_QUERIES]
    items, errors, github_calls = [], [], 0
    for name, query, fn in jobs:
        if name == "github":
            if github_calls:
                sleep(GITHUB_PAUSE)
            github_calls += 1
        try:
            items.extend(fn(query))
        except Exception as exc:  # الشبكة/الحدّ: نكمل بالباقي
            errors.append(f"{name}:{query}: {exc}")
    return items, errors


# ---------------------------------------------------------------- الفرز وصياغة المسودة

def relevant(item):
    """نقاش عن TLS المقاوم للكم فعلاً، وليس تحديث مكتبة آلياً."""
    text = re.sub(r"https?://\S+", " ", item["text"])  # "https" داخل رابط ليس نقاشاً عن HTTPS
    blob = f"{item['title']} {text}"
    if NOISE.search(item["title"]) or OFF_TOPIC.search(item["title"]):
        return False
    if not (CORE.search(blob) and CONTEXT.search(blob)):
        return False
    # GitHub: من يشغّل خادماً ويسأل عن تفعيله، أو بلاغ عطل توافق سببه ML-KEM (ClientHello كبير، جدار ناري...)
    if item["source"] == "GitHub" and not ((QUESTION.search(blob) and WEBSERVER.search(blob))
                                           or _breakage(item["title"])):
        return False
    # في HN: الموضوع في العنوان، أو تعليق يسأل عنه صراحةً (لا ذكراً عابراً في نقاش آخر)
    if item["source"] == "Hacker News" and not (CORE.search(item["title"]) or
                                                (CORE.search(text) and CONTEXT.search(text)
                                                 and QUESTION.search(text))):
        return False
    return True


def topic_of(item):
    blob = f"{item['title']} {item['text']}"
    for name, rx in TOPICS:
        if rx.search(blob):
            return name
    return "general"


ANNOUNCE = re.compile(r"announc|releas|now support|now enabled|is now|ships?\b|adds? support|available now|rolled out|we added", re.I)


def intent_of(item):
    """نوع النيّة: عطل توافق، سؤال تفعيل، إعلان، أو نقاش عام."""
    if _breakage(item["title"] or ""):
        return "breakage"
    blob = f"{item['title']} {item['text']}"
    if QUESTION.search(blob):
        return "question"
    if ANNOUNCE.search(blob):
        return "announcement"
    return "discussion"


def score_of(item, intent):
    """درجة قابلية التواصل 0–100: الأعلى = شخص يشغّل خادماً ويسأل/يبلّغ عطلاً (عميل محتمل)."""
    blob = f"{item['title']} {item['text']}"
    s = {"breakage": 80, "question": 65, "discussion": 40, "announcement": 25}.get(intent, 40)
    if WEBSERVER.search(blob):  # يشغّل خادماً فعلاً → عميل قابل للتواصل
        s += 15
    if item["source"] in ("Server Fault", "Stack Overflow", "Security SE"):
        s += 5  # ممارسو تشغيل يطلبون حلّاً
    if CORE.search(item["title"] or ""):
        s += 5  # الموضوع في العنوان لا عابراً
    return max(0, min(100, s))


def draft_reply(item, topic):
    """مسودة تبدأ بالإجابة، والرابط مرجع لا إعلان، مع الإفصاح عن صاحب الأداة."""
    return (f"{HINTS[topic]}\n\n"
            f"Step-by-step guide: {GUIDES[topic]}\n"
            f"To verify from outside (which group the server actually negotiates): {BASE}/?domain=yourdomain\n\n"
            "(Disclosure: I run that scanner; the guide and the check are free.)")


def find_new(conn, items, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    seen = {r[0] for r in conn.execute("SELECT url FROM radar_seen")}
    fresh, picked = [], set()
    for item in items:
        if item["url"] in seen or item["url"] in picked or not relevant(item):
            continue
        topic = topic_of(item)
        intent = intent_of(item)
        picked.add(item["url"])
        fresh.append(dict(item, topic=topic, intent=intent, stack=topic,
                          snippet=(item.get("text") or "")[:240], score=score_of(item, intent),
                          status="new", draft=draft_reply(item, topic)))
    fresh.sort(key=lambda i: -i["score"])  # الأولوية أولاً
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO radar_seen (url, source, title, topic, found_at, intent, stack, snippet, score, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(i["url"], i["source"], i["title"], i["topic"], now.isoformat(timespec="seconds"),
              i["intent"], i["stack"], i["snippet"], i["score"], i["status"]) for i in fresh])
    return fresh


def digest(fresh):
    top = fresh[0]["score"] if fresh else 0
    lines = [f"رادار العملاء: {len(fresh)} سؤال/نقاش جديد عن TLS المقاوم للكم — مرتّبة بالأولوية (أعلى درجة {top}/100).", "",
             "لكل بند ردّ علني جاهز: انشره بنفسك تحت السؤال (ثوانٍ). يجيب أولاً، والرابط مرجع لا إعلان.", ""]
    for n, i in enumerate(fresh, 1):
        lines += [f"{n}. [{i['score']}/100 · {i['intent']} · {i['source']}] {i['title'] or '(comment)'}",
                  f"   {i['url']}",
                  f"   الموضوع: {i['topic']}"]
        if i.get("snippet"):
            lines.append(f"   مقتطف: {i['snippet']}")
        lines += ["   ردّ علني جاهز:", *["      " + l for l in i["draft"].splitlines()], ""]
    return f"Quantum Aether radar: {len(fresh)} lead(s), top {top}/100", "\n".join(lines)


def run(conn, mailer, owner, since, get=_get_json, now=None):
    items, errors = collect(since, get)
    fresh = find_new(conn, items, now)
    sent = False
    if fresh and owner and mailer.enabled:
        subject, text = digest(fresh)
        sent = mailer.send(owner, subject, text)
    return {"found": len(items), "new": len(fresh), "sent": sent, "errors": errors}
