# radar.py — رادار الاهتمام: يجد النقاشات العامة الجديدة عن TLS المقاوم للكم، ويرسل لصاحب الموقع
# كل صباح قائمة بها مع مسودة ردّ مفيد. الرد ينشره صاحب الموقع بيده؛ الرادار لا ينشر ولا يراسل أحداً.
#
# الخصوصية: واجهات رسمية عامة فقط (HN Algolia، Stack Exchange، GitHub)، بلا تخفٍّ ولا بروكسيات.
# لا نحفظ أسماء ولا حسابات: فقط رابط النقاش وعنوانه ومصدره وتاريخ رؤيته، لمنع التكرار.
import datetime as dt
import html
import json
import re
import urllib.parse
import urllib.request

USER_AGENT = "QuantumAetherRadar/1.0 (+https://ather-quantum.com)"
BASE = "https://ather-quantum.com"

QUERIES = ["X25519MLKEM768", "MLKEM768", "ML-KEM TLS", "post-quantum TLS", "post quantum nginx",
           "hybrid key exchange TLS"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS radar_seen (
    url       TEXT PRIMARY KEY,
    source    TEXT NOT NULL,
    title     TEXT,
    topic     TEXT,
    found_at  TEXT NOT NULL
);
"""

CORE = re.compile(r"x25519mlkem768|mlkem|ml-kem|kyber|post[- ]?quantum|pqc|harvest now", re.I)
CONTEXT = re.compile(r"\btls\b|https|ssl|nginx|apache|caddy|haproxy|cloudflare|openssl|certificate|key exchange|web ?server", re.I)
NOISE = re.compile(r"^(bump|build\(deps|chore|update dependency|\[snyk\]|release v?\d)", re.I)
QUESTION = re.compile(r"\?|\bhow\b|\benable\b|\bsupport\b|\berror\b|\bfail|\bnot work|\bwhy\b|\bconfigure", re.I)
# في GitHub نريد من يشغّل خادماً ويسأل عن تفعيله، لا نقاشات داخلية لمطوّري المكتبات
WEBSERVER = re.compile(r"nginx|apache|httpd|caddy|haproxy|cloudflare|traefik|envoy|web ?server|reverse proxy|ingress", re.I)

TOPICS = [("nginx", re.compile(r"nginx", re.I)), ("apache", re.compile(r"apache|httpd", re.I)),
          ("caddy", re.compile(r"caddy", re.I)), ("haproxy", re.compile(r"haproxy", re.I)),
          ("cloudflare", re.compile(r"cloudflare", re.I)), ("openssl", re.compile(r"openssl", re.I))]

GUIDES = {
    "nginx": f"{BASE}/guides/enable-x25519mlkem768-nginx",
    "openssl": f"{BASE}/guides/enable-x25519mlkem768-nginx",
    "apache": f"{BASE}/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare",
    "caddy": f"{BASE}/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare",
    "haproxy": f"{BASE}/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare",
    "cloudflare": f"{BASE}/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare",
    "general": f"{BASE}/guides/harvest-now-decrypt-later",
}

HINTS = {
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
    names = {"serverfault": "Server Fault", "stackoverflow": "Stack Overflow", "security": "Security SE"}
    return [{"source": names.get(site, site), "url": i["link"], "title": _clean(i.get("title")),
             "text": " ".join(i.get("tags", [])), "created": dt.datetime.fromtimestamp(i["creation_date"], dt.timezone.utc).isoformat()}
            for i in data.get("items", [])]


def fetch_github(query, since, get=_get_json):
    q = f'"{query}" is:issue created:>{since.date().isoformat()}'
    data = get("https://api.github.com/search/issues?" + urllib.parse.urlencode({"q": q, "sort": "created", "per_page": 30}))
    return [{"source": "GitHub", "url": i["html_url"], "title": _clean(i.get("title")),
             "text": _clean(i.get("body"))[:600], "created": i.get("created_at", "")}
            for i in data.get("items", [])]


def collect(since, get=_get_json):
    """يجمع من كل المصادر. فشل مصدر واحد لا يوقف الباقي."""
    items, errors = [], []
    for n, query in enumerate(QUERIES):
        sources = [("hn", lambda q: fetch_hn(q, since, get)),
                   ("serverfault", lambda q: fetch_stackexchange(q, since, "serverfault", get)),
                   ("stackoverflow", lambda q: fetch_stackexchange(q, since, "stackoverflow", get))]
        if n < 2:  # GitHub: استعلامان يومياً فقط، حدّه بلا تسجيل دخول 10 طلبات بالدقيقة
            sources.append(("github", lambda q: fetch_github(q, since, get)))
        for name, fn in sources:
            try:
                items.extend(fn(query))
            except Exception as exc:  # الشبكة/الحدّ: نكمل بالباقي
                errors.append(f"{name}:{query}: {exc}")
    return items, errors


# ---------------------------------------------------------------- الفرز وصياغة المسودة

def relevant(item):
    """نقاش عن TLS المقاوم للكم فعلاً، وليس تحديث مكتبة آلياً."""
    blob = f"{item['title']} {item['text']}"
    if NOISE.search(item["title"]):
        return False
    if not (CORE.search(blob) and CONTEXT.search(blob)):
        return False
    if item["source"] == "GitHub" and not (QUESTION.search(blob) and WEBSERVER.search(blob)):
        return False
    # في HN: الموضوع في العنوان، أو تعليق يسأل عنه صراحةً (لا ذكراً عابراً في نقاش آخر)
    if item["source"] == "Hacker News" and not (CORE.search(item["title"]) or
                                                (CORE.search(item["text"]) and QUESTION.search(item["text"]))):
        return False
    return True


def topic_of(item):
    blob = f"{item['title']} {item['text']}"
    for name, rx in TOPICS:
        if rx.search(blob):
            return name
    return "general"


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
        picked.add(item["url"])
        fresh.append(dict(item, topic=topic, draft=draft_reply(item, topic)))
    with conn:
        conn.executemany("INSERT OR IGNORE INTO radar_seen (url, source, title, topic, found_at) VALUES (?, ?, ?, ?, ?)",
                         [(i["url"], i["source"], i["title"], i["topic"], now.isoformat(timespec="seconds")) for i in fresh])
    return fresh


def digest(fresh):
    lines = [f"رادار الاهتمام: {len(fresh)} نقاش جديد عن TLS المقاوم للكم", "",
             "راجع كل نقاش، وانشر الرد بنفسك فقط إن كان يفيد السائل فعلاً. أجب عن سؤاله أولاً.", ""]
    for n, i in enumerate(fresh, 1):
        lines += [f"{n}. [{i['source']}] {i['title'] or '(comment)'}", f"   {i['url']}",
                  f"   الموضوع: {i['topic']}", "   مسودة رد:", *["      " + l for l in i["draft"].splitlines()], ""]
    return f"Quantum Aether radar: {len(fresh)} new discussion(s)", "\n".join(lines)


def run(conn, mailer, owner, since, get=_get_json, now=None):
    items, errors = collect(since, get)
    fresh = find_new(conn, items, now)
    sent = False
    if fresh and owner and mailer.enabled:
        subject, text = digest(fresh)
        sent = mailer.send(owner, subject, text)
    return {"found": len(items), "new": len(fresh), "sent": sent, "errors": errors}
