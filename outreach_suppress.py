"""Outreach unsubscribe and suppression (2026-11-23).

  * outreach_suppress: one row per address that must never get outreach again (email, domain, reason, created_at).
    Every outreach sender checks is_suppressed() first; growth_agent.excluded() also reads it, and suppress()
    mirrors the domain into growth_suppress, so both senders see the same opt-outs.
  * outreach_sent: one row per outreach mail actually sent (tools/outreach_send.py), so nobody gets it twice.
  * make_token()/read_token(): HMAC-SHA256 token per recipient address (key derived from QS_HASH_SALT with a
    purpose label; the salt itself never leaves the server). Token = base64url(email) "." base64url(mac[:16]).
  * GET /u/<token>: small trilingual confirmation page with one button. POST /u/<token>: records the opt-out and
    returns 200, also for RFC 8058 one-click (body "List-Unsubscribe=One-Click", no CSRF token by design: the
    signed token is the credential). Idempotent. A bad token is 400 with a generic page. Always noindex/no-store.
"""
import base64
import datetime as dt
import hashlib
import hmac
import re

from flask import make_response, render_template_string, request

PURPOSE = b"quantum-aether outreach-unsubscribe v1"
MAILTO = "reply@mail.ather-quantum.com"
EMAIL_RE = re.compile(r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{4,400}\.[A-Za-z0-9_-]{22}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS outreach_suppress (
  email TEXT PRIMARY KEY,
  domain TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS outreach_suppress_domain ON outreach_suppress (domain);
CREATE TABLE IF NOT EXISTS outreach_sent (
  email TEXT PRIMARY KEY,
  domain TEXT NOT NULL,
  org TEXT NOT NULL DEFAULT '',
  lang TEXT NOT NULL DEFAULT 'en',
  kex_group TEXT NOT NULL DEFAULT '',
  kex_class TEXT NOT NULL DEFAULT '',
  subject TEXT NOT NULL DEFAULT '',
  resend_id TEXT,
  sent_at TEXT NOT NULL,
  last_event TEXT,
  checked_at TEXT);
CREATE INDEX IF NOT EXISTS outreach_sent_domain ON outreach_sent (domain);
CREATE TABLE IF NOT EXISTS growth_suppress (domain TEXT PRIMARY KEY, added_at TEXT, reason TEXT);
"""


def init(conn):
    conn.executescript(SCHEMA)


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize(email):
    email = (email or "").strip().lower()
    if "<" in email:
        email = email.rsplit("<", 1)[-1].rstrip(">").strip()
    return email if len(email) <= 254 and EMAIL_RE.match(email) else ""


def domain_of(email):
    d = email.rpartition("@")[2].strip(".").lower()
    return d[4:] if d.startswith("www.") else d


def _b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _key(secret):
    if not secret:
        raise ValueError("no signing secret configured")
    return hmac.new(secret.encode() if isinstance(secret, str) else secret, PURPOSE, hashlib.sha256).digest()


def _mac(secret, payload):
    return _b64(hmac.new(_key(secret), payload.encode(), hashlib.sha256).digest()[:16])


def make_token(email, secret):
    clean = normalize(email)
    if not clean:
        raise ValueError("invalid email address")
    payload = _b64(clean.encode())
    return f"{payload}.{_mac(secret, payload)}"


def read_token(token, secret):
    """The address the token was minted for, or None (bad shape, bad MAC, no secret, not an address)."""
    if not secret or not isinstance(token, str) or not TOKEN_RE.match(token):
        return None
    payload, sig = token.split(".", 1)
    if not hmac.compare_digest(sig, _mac(secret, payload)):
        return None
    try:
        email = _unb64(payload).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    clean = normalize(email)
    return clean if clean and clean == email else None


def unsubscribe_url(base, email, secret):
    return f"{base.rstrip('/')}/u/{make_token(email, secret)}"


def list_unsubscribe_headers(base, email, secret, mailto=MAILTO):
    """RFC 2369 + RFC 8058 headers for one recipient (Gmail/Yahoo one-click)."""
    return {"List-Unsubscribe": f"<{unsubscribe_url(base, email, secret)}>, <mailto:{mailto}?subject=unsubscribe>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}


def suppress(conn, email, reason, domain=None):
    """Record an opt-out; True when it is new. Mirrors the domain into growth_suppress (domain-level sender)."""
    clean = normalize(email)
    if not clean:
        return False
    dom = (domain or domain_of(clean)).lower()
    init(conn)
    stamp = now_iso()
    with conn:
        cur = conn.execute("INSERT OR IGNORE INTO outreach_suppress (email, domain, reason, created_at) VALUES (?, ?, ?, ?)",
                           (clean, dom, (reason or "")[:40], stamp))
        if dom:
            conn.execute("INSERT OR IGNORE INTO growth_suppress (domain, added_at, reason) VALUES (?, ?, ?)",
                         (dom, stamp, (reason or "")[:40]))
    return bool(cur.rowcount)


def is_suppressed(conn, email=None, domain=None):
    """True if this address, or its organisation's domain, opted out anywhere (outreach_suppress or growth_suppress)."""
    init(conn)
    clean = normalize(email) if email else ""
    doms = {d for d in ((domain or "").lower(), domain_of(clean) if clean else "") if d}
    if clean and conn.execute("SELECT 1 FROM outreach_suppress WHERE email = ?", (clean,)).fetchone():
        return True
    for d in doms:
        if conn.execute("SELECT 1 FROM outreach_suppress WHERE domain = ?", (d,)).fetchone():
            return True
        if conn.execute("SELECT 1 FROM growth_suppress WHERE domain = ?", (d,)).fetchone():
            return True
    return False


def suppressed_domains(conn):
    init(conn)
    return {r[0] for r in conn.execute("SELECT domain FROM outreach_suppress WHERE domain != ''")}


def mask(email):
    local, _, dom = email.partition("@")
    return f"{local[:1]}***@{dom}"


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>{{ t.title }}</title>
<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#0b1020;color:#e8ecf5;margin:0;padding:24px}
main{max-width:560px;margin:40px auto;background:#131a2e;border:1px solid #26304d;border-radius:12px;padding:24px}
h1{font-size:1.25rem;margin:0 0 12px}p{line-height:1.5;margin:8px 0}.ar{direction:rtl;text-align:right}
button{font:inherit;font-weight:600;background:#e8b84a;color:#0b1020;border:0;border-radius:8px;padding:12px 18px;width:100%;cursor:pointer;margin-top:16px}
hr{border:0;border-top:1px solid #26304d;margin:16px 0}small{color:#9aa4bf}</style></head>
<body><main>
{% if state == "invalid" %}
<h1>Link not valid</h1>
<p>This unsubscribe link is not valid. Reply "stop" to the email you received and we will not write again.</p>
<p class="ar" lang="ar" dir="rtl">رابط إلغاء الاشتراك غير صالح. ردّوا بكلمة «إيقاف» على الرسالة ولن نراسلكم مجددًا.</p>
<p lang="de">Dieser Abmeldelink ist ungültig. Antworten Sie mit „stop“ auf die E-Mail, dann schreiben wir nicht mehr.</p>
{% elif state == "done" %}
<h1>You are unsubscribed</h1>
<p>{{ who }} will not receive outreach email from Quantum Aether again.</p>
<p class="ar" lang="ar" dir="rtl">تم إلغاء الاشتراك. لن يصل {{ who }} أي رسائل تواصل من Quantum Aether بعد الآن.</p>
<p lang="de">Abgemeldet. {{ who }} erhält keine Kontakt-E-Mails von Quantum Aether mehr.</p>
{% else %}
<h1>Unsubscribe from Quantum Aether outreach</h1>
<p>Stop all outreach email to {{ who }}.</p>
<p class="ar" lang="ar" dir="rtl">إيقاف كل رسائل التواصل إلى {{ who }}.</p>
<p lang="de">Alle Kontakt-E-Mails an {{ who }} abbestellen.</p>
<form method="post" action=""><button type="submit">Unsubscribe · إلغاء الاشتراك · Abmelden</button></form>
{% endif %}
<hr><small>Quantum Aether Team · <a style="color:#9aa4bf" href="/impressum?lang=en">Impressum</a></small>
</main></body></html>"""


def _page(state, who="", status=200):
    resp = make_response(render_template_string(PAGE, state=state, who=who,
                                                t={"title": "Unsubscribe · Quantum Aether"}), status)
    resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Content-Security-Policy"] = ("default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
                                               "frame-ancestors 'none'; base-uri 'none'")
    return resp


def register(bp, deps):
    """deps: db (callable -> sqlite conn), secret (callable -> signing secret)."""

    @bp.route("/u/<token>", methods=["GET", "POST"])
    def outreach_unsubscribe(token):
        email = read_token(token, deps["secret"]())
        if not email:
            return _page("invalid", status=400)
        if request.method == "POST":
            one_click = "List-Unsubscribe=One-Click" in (request.get_data(as_text=True) or "")[:200]
            suppress(deps["db"](), email, "one-click" if one_click else "unsubscribe-page")
            return _page("done", mask(email))
        return _page("confirm", mask(email))
