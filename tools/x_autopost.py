#!/usr/bin/env python3
"""Official X (Twitter) API v2 autoposter & smart mention responder for Quantum Aether.

Uses zero external dependencies (pure stdlib RFC 5849 OAuth 1.0a HMAC-SHA1 -> api.x.com/2/*).
Credentials live strictly outside git at /etc/quantum-aether/x_api.json (chmod 0600):
  {"api_key": "...", "api_secret": "...", "access_token": "...", "access_token_secret": "..."}

Guardrails:
  * Daily post cap: 3 rotating telemetry posts/day across peak slots (09:30, 15:30, 21:30 Europe/Berlin).
  * Hourly mention responder: uses cached user_id + since_id to minimize Pay-Per-Use cost,
    hard-capped at 10 replies/day and max 1 reply per author per 24h (anti-bot-loop protection).
  * Instant kill-switch: touch /var/lib/quantum_saas/x_autopost.paused
  * Cleanly exits 0 (no-op) if /etc/quantum-aether/x_api.json is not configured yet.
  * Preserves quantum:quantum ownership on quantum_saas.db (-wal/-shm).

Usage:
  python3 tools/x_autopost.py --dry-run
  python3 tools/x_autopost.py --post
  python3 tools/x_autopost.py --reply-mentions
  python3 tools/x_autopost.py --post --text "Custom tweet <= 280 chars" [--reply-to TWEET_ID]
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DATA_DIR = os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas")
DB_PATH = os.path.join(DATA_DIR, "quantum_saas.db")
MCP_INDEX_PATH = os.path.join(DATA_DIR, "mcp_index.json")
PAUSE_FILE = os.path.join(DATA_DIR, "x_autopost.paused")
CRED_PATH = "/etc/quantum-aether/x_api.json"
TWEETS_URL = "https://api.x.com/2/tweets"
X402SCAN_URL = "https://www.x402scan.com/server/2b8f5869-118f-4389-ad32-20989ffee2ca"
USER_AGENT = "QuantumAetherXBot/2.1 (+https://ather-quantum.com)"

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_platform_activity (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    platform   TEXT NOT NULL,
    kind       TEXT NOT NULL,
    ref_key    TEXT NOT NULL,
    summary    TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(platform, kind, ref_key)
);
CREATE TABLE IF NOT EXISTS x_bot_kv (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def now_iso() -> str:
    return now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def init_db(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript(SCHEMA)


def keep_db_owner(db_path: str) -> None:
    try:
        pw = pwd.getpwnam("quantum")
        uid, gid = pw.pw_uid, pw.pw_gid
    except KeyError:
        return
    for suffix in ("", "-wal", "-shm", "-journal"):
        p = db_path + suffix
        if os.path.exists(p):
            try:
                os.chown(p, uid, gid)
            except OSError:
                pass


def kv_get(conn: sqlite3.Connection, key: str) -> str:
    row = conn.execute("SELECT v FROM x_bot_kv WHERE k = ?", (key,)).fetchone()
    return str(row[0]) if row else ""


def kv_set(conn: sqlite3.Connection, key: str, value: str) -> None:
    with conn:
        conn.execute(
            "INSERT INTO x_bot_kv (k, v, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(k) DO UPDATE SET v = excluded.v, updated_at = excluded.updated_at",
            (key, str(value), now_iso()),
        )


def current_slot(now: dt.datetime | None = None) -> int:
    """Map UTC hour to 3 daily slots: 0 (morning EU), 1 (EU/US peak), 2 (US/APAC evening)."""
    h = (now or now_utc()).hour
    if h < 12:
        return 0
    if h < 18:
        return 1
    return 2


def already_posted_today(conn: sqlite3.Connection, day: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM agent_platform_activity WHERE platform = 'x' AND kind = 'daily_post' AND ref_key = ?",
        (day,),
    ).fetchone())


def already_posted_slot(conn: sqlite3.Connection, day: str, slot: int) -> bool:
    ref = f"{day}-slot{slot}"
    if slot == 0 and already_posted_today(conn, day):
        return True
    return bool(conn.execute(
        "SELECT 1 FROM agent_platform_activity WHERE platform = 'x' AND kind = 'daily_post' AND ref_key = ?",
        (ref,),
    ).fetchone())


def posts_today_count(conn: sqlite3.Connection, day: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM agent_platform_activity WHERE platform = 'x' AND kind = 'daily_post' "
        "AND (ref_key = ? OR ref_key LIKE ?)",
        (day, f"{day}-slot%"),
    ).fetchone()
    return int(row[0] or 0) if row else 0


def record_post(conn: sqlite3.Connection, kind: str, ref_key: str, summary: str) -> None:
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO agent_platform_activity (platform, kind, ref_key, summary, created_at) "
            "VALUES ('x', ?, ?, ?, ?)",
            (kind, ref_key, summary[:240], now_iso()),
        )


def load_mcp_summary(path: str = MCP_INDEX_PATH) -> dict:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        s = doc.get("summary")
        if isinstance(s, dict) and s.get("measured"):
            return s
    except (OSError, ValueError):
        pass
    return {"measured": 152, "pq_hybrid": 120, "pq_pct": 78.9, "classical": 28, "tls12": 4, "pq_not_preferred": 0}


def build_daily_tweet(summary: dict, day: dt.date | None = None, slot: int = 0) -> str:
    d = day or now_utc().date()
    m = summary.get("measured", 152)
    pq_n = summary.get("pq_hybrid", 120)
    pq_pct = summary.get("pq_pct", 78.9)
    cls = summary.get("classical", 28)
    t12 = summary.get("tls12", 4)
    exposed = cls + t12
    day_str = d.isoformat()

    variants = [
        (
            f"Daily Remote MCP PQ-TLS Index ({day_str}):\n"
            f"Measured {m} live MCP servers:\n"
            f"• {pq_n} ({pq_pct}%) X25519MLKEM768\n"
            f"• {exposed} classical/TLS 1.2\n\n"
            f"Live index + 1-click Grade A README badge:\n"
            f"https://ather-quantum.com/mcp-index #MCP #AIAgents #PQC"
        ),
        (
            f"TLS 1.3 trap most teams miss: servers pass SSL Labs PQC checks yet rank X25519 first—silently "
            f"downgrading Chrome, Firefox & Safari.\n\n"
            f"Verify live + get an Ed25519 signed receipt:\n"
            f"https://ather-quantum.com #PQC #TLS #InfoSec #AIAgents"
        ),
        (
            f"Give Claude Code, Cursor, Codex or OpenClaw live PQ-TLS audits + Nginx/Cloudflare fixes "
            f"(zero API key):\n\n"
            f"npx skills add moncef00327-cloud/quantum-aether\n\n"
            f"MCP setup (100/100 mcptry): https://ather-quantum.com/agents #AIAgents #OpenClaw #MCP"
        ),
        (
            f"Autonomous #Base USDC #x402 endpoints live on x402scan (6/6):\n"
            f"• $0.10 batch-scan (10 domains, Ed25519 receipts)\n"
            f"• $0.25 live CycloneDX 1.6 CBOM JSON\n\n"
            f"{X402SCAN_URL}\n"
            f"https://ather-quantum.com/.well-known/x402 #AIAgents #MCP"
        ),
        (
            f"Why trust a static README security badge?\n"
            f"Every Quantum Aether scan issues an Ed25519 signed JWS receipt (iat/exp, negotiated group, cert SPKI hash) "
            f"agents verify offline via JWKS:\n\n"
            f"https://ather-quantum.com/.well-known/jwks.json #AIAgents #PQC #MCP"
        ),
        (
            f"{exposed} of {m} Official Registry MCP servers still run classical TLS—meaning recorded traffic can be "
            f"decrypted later (HNDL).\n\n"
            f"Free live check + copy-paste Nginx/Cloudflare config:\n"
            f"https://ather-quantum.com/mcp-index #MCP #AIAgents #InfoSec"
        ),
    ]
    return variants[(d.toordinal() * 3 + int(slot)) % len(variants)]


def _pct(s: str) -> str:
    return urllib.parse.quote(str(s), safe="~-._")


def oauth1_header(method: str, url: str, creds: dict, *, nonce: str | None = None, timestamp: str | None = None) -> str:
    """Build an RFC 5849 OAuth 1.0a Authorization header (HMAC-SHA1) for X API v2 JSON requests."""
    oauth_params = {
        "oauth_consumer_key": creds["api_key"],
        "oauth_nonce": nonce or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": timestamp or str(int(time.time())),
        "oauth_token": creds["access_token"],
        "oauth_version": "1.0",
    }
    parsed = urllib.parse.urlsplit(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    all_params = sorted([(_pct(k), _pct(v)) for k, v in list(oauth_params.items()) + query_pairs])
    param_str = "&".join(f"{k}={v}" for k, v in all_params)
    sig_base = "&".join([method.upper(), _pct(base_url), _pct(param_str)])
    signing_key = f"{_pct(creds['api_secret'])}&{_pct(creds['access_token_secret'])}".encode("ascii")
    sig = base64.b64encode(hmac.new(signing_key, sig_base.encode("ascii"), hashlib.sha1).digest()).decode("ascii")
    oauth_params["oauth_signature"] = sig
    header_parts = ", ".join(f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(oauth_params.items()))
    return f"OAuth {header_parts}"


def load_credentials(path: str = CRED_PATH) -> dict | None:
    if not os.path.exists(path):
        return None
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    required = ("api_key", "api_secret", "access_token", "access_token_secret")
    if not isinstance(doc, dict) or not all(str(doc.get(k) or "").strip() for k in required):
        return None
    return {k: str(doc[k]).strip() for k in required}


URL_RE = re.compile(r"https?://[^\s<>()]+")


def extract_urls(text: str) -> list[str]:
    return [m.group(0).rstrip(".,;:!?)") for m in URL_RE.finditer(text or "")]


def verify_urls_ok(text: str, timeout: float = 8.0) -> tuple[bool, list[str]]:
    """Pre-publish health gate: every URL in a tweet/reply must return HTTP 200 on browser GET."""
    failures: list[str] = []
    for url in extract_urls(text):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status != 200:
                    failures.append(f"{url} -> HTTP {resp.status}")
        except urllib.error.HTTPError as exc:
            failures.append(f"{url} -> HTTP {exc.code}")
        except Exception as exc:
            failures.append(f"{url} -> {exc}")
    return (len(failures) == 0), failures


def post_tweet(
    text: str,
    creds: dict,
    *,
    reply_to: str = "",
    timeout: float = 20.0,
    check_urls: bool = True,
) -> tuple[int, dict | str]:
    if check_urls:
        ok, failures = verify_urls_ok(text)
        if not ok:
            return 0, f"pre-publish link check failed: {'; '.join(failures)}"
    auth = oauth1_header("POST", TWEETS_URL, creds)
    payload: dict = {"text": text}
    if reply_to:
        payload["reply"] = {"in_reply_to_tweet_id": str(reply_to)}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        TWEETS_URL,
        data=body,
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(200_000).decode("utf-8", "replace")
            return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read(200_000).decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw


def _oauth_get(url: str, creds: dict, timeout: float = 20.0) -> tuple[int, dict | str]:
    req = urllib.request.Request(
        url,
        headers={"Authorization": oauth1_header("GET", url, creds), "User-Agent": USER_AGENT},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(200_000).decode("utf-8", "replace")
            return resp.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read(200_000).decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw


def already_replied_mention(conn: sqlite3.Connection, mention_id: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM agent_platform_activity WHERE platform = 'x' AND kind = 'mention_reply' AND ref_key = ?",
        (str(mention_id),),
    ).fetchone())


def replied_author_recently(conn: sqlite3.Connection, author_id: str, username: str, hours: int = 24) -> bool:
    cutoff = (now_utc() - dt.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    uname = username.strip().lstrip("@").lower()
    rows = conn.execute(
        "SELECT summary FROM agent_platform_activity "
        "WHERE platform = 'x' AND kind = 'mention_reply' AND created_at >= ?",
        (cutoff,),
    ).fetchall()
    for (s,) in rows:
        sl = (s or "").lower()
        if f"author_id={author_id}" in sl or (uname and f"@{uname}" in sl):
            return True
    return False


def replies_today_count(conn: sqlite3.Connection, day: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM agent_platform_activity WHERE platform = 'x' AND kind = 'mention_reply' AND created_at LIKE ?",
        (f"{day}%",),
    ).fetchone()
    return int(row[0] or 0) if row else 0


def build_mention_reply(username: str, text: str) -> str | None:
    raw = text or ""
    low = raw.lower()
    if any(w in low for w in ("stop", "unsubscribe", "spam", "scam", "airdrop", "giveaway", "crypto pump", "dm me for promo")):
        return None
    if any(w in low for w in ("receipt", "jwks", "signed", "verify", "stale", "badge", "timestamp")):
        reply = (
            "Every scan issues an Ed25519 signed JWS receipt (iat/exp, negotiated group, cert SPKI hash) "
            "verifiable offline via JWKS:\n\n"
            "https://ather-quantum.com/.well-known/jwks.json\n"
            "https://ather-quantum.com/agents #AIAgents #MCP #PQC"
        )
    elif any(w in low for w in ("x402", "usdc", "wallet", "pay", "batch", "cbom", "base")):
        reply = (
            "Any agent with a Base USDC wallet can call our x402 endpoints directly "
            "($0.10 10-domain batch-scan / $0.25 live CBOM):\n\n"
            "https://ather-quantum.com/.well-known/x402\n"
            "npx skills add moncef00327-cloud/quantum-aether #x402 #AIAgents"
        )
    elif any(w in low for w in ("mcp", "skill", "claude", "cursor", "openclaw", "codex", "agent")):
        reply = (
            "Connect our free remote MCP server (100/100 on mcptry) or install our agent skills:\n\n"
            "npx skills add moncef00327-cloud/quantum-aether\n"
            "https://ather-quantum.com/agents #MCP #AIAgents #PQC"
        )
    elif any(w in raw for w in ("关注", "亮眼", "不错", "厉害", "支持")) or any(
        w in low for w in ("follow", "followed", "impressive", "awesome", "great work", "cool", "nice")
    ):
        zh = " 感谢关注！" if any("\u4e00" <= ch <= "\u9fff" for ch in raw) else ""
        reply = (
            f"Thanks for the follow!{zh} We track live post-quantum TLS (X25519MLKEM768) across "
            f"Official Registry MCP servers daily—try a free scan anytime:\n\n"
            f"https://ather-quantum.com/mcp-index #AIAgents #MCP #PQC"
        )
    else:
        reply = (
            "You can test any domain live for real X25519MLKEM768 negotiation + Ed25519 signed receipt "
            "(free, zero API key):\n\n"
            "https://ather-quantum.com/mcp-index #PQC #AIAgents #MCP"
        )
    return reply if len(reply) <= 280 else reply[:280]


def get_self_user_id(conn: sqlite3.Connection, creds: dict) -> str:
    cached = kv_get(conn, "self_user_id")
    if cached:
        return cached
    # Access tokens begin with "<user_id>-..." on X OAuth 1.0a; verify via /2/users/me once and cache.
    st, me = _oauth_get("https://api.x.com/2/users/me", creds)
    if st == 200 and isinstance(me, dict):
        uid = str((me.get("data") or {}).get("id") or "")
        if uid:
            kv_set(conn, "self_user_id", uid)
            return uid
    prefix = creds["access_token"].split("-", 1)[0]
    if prefix.isdigit():
        kv_set(conn, "self_user_id", prefix)
        return prefix
    return ""


def process_mentions(conn: sqlite3.Connection, creds: dict, *, max_replies_per_day: int = 10) -> int:
    day = now_utc().date().isoformat()
    if replies_today_count(conn, day) >= max_replies_per_day:
        print(f"mentions: daily reply cap reached ({max_replies_per_day})")
        return 0
    uid = get_self_user_id(conn, creds)
    if not uid:
        print("mentions: could not resolve self user id", file=sys.stderr)
        return 0
    since_id = kv_get(conn, "mentions_since_id")
    url = (
        f"https://api.x.com/2/users/{uid}/mentions"
        f"?max_results=10&tweet.fields=author_id,created_at&expansions=author_id&user.fields=username"
    )
    if since_id:
        url += f"&since_id={since_id}"
    st, doc = _oauth_get(url, creds)
    if st != 200 or not isinstance(doc, dict):
        print(f"mentions: failed mentions fetch HTTP {st}: {str(doc)[:200]}", file=sys.stderr)
        return 0
    items = doc.get("data") or []
    newest_id = (doc.get("meta") or {}).get("newest_id")
    if newest_id:
        kv_set(conn, "mentions_since_id", str(newest_id))
    if not items:
        print("mentions: no new mentions")
        return 0

    users = {u["id"]: u.get("username", "") for u in (doc.get("includes") or {}).get("users", [])}
    sent = 0
    # Process oldest -> newest
    for item in reversed(items):
        mid = str(item.get("id") or "")
        author_id = str(item.get("author_id") or "")
        if not mid or author_id == str(uid) or already_replied_mention(conn, mid):
            continue
        if replies_today_count(conn, day) >= max_replies_per_day:
            break
        username = users.get(author_id) or ""
        if not username:
            continue
        if replied_author_recently(conn, author_id, username, hours=24):
            record_post(conn, "mention_reply", mid, f"anti_loop_skip @{username} author_id={author_id}")
            print(f"mentions: anti-loop skip @{username} ({mid})")
            continue
        reply_text = build_mention_reply(username, item.get("text") or "")
        if not reply_text:
            record_post(conn, "mention_reply", mid, f"skipped @{username} author_id={author_id}")
            continue
        rst, rres = post_tweet(reply_text, creds, reply_to=mid)
        if rst in (200, 201):
            rtid = (rres.get("data") or {}).get("id") if isinstance(rres, dict) else ""
            record_post(conn, "mention_reply", mid, f"replied @{username} author_id={author_id} tweet_id={rtid}")
            print(f"replied to @{username} ({mid}) -> tweet_id={rtid} (HTTP {rst})")
            sent += 1
        else:
            print(f"reply error to @{username} ({mid}) HTTP {rst}: {str(rres)[:240]}", file=sys.stderr)
    return sent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="render current slot tweet and length without posting")
    mode.add_argument("--post", action="store_true", help="publish tweet via X API v2 (up to --max-posts/day unless --text)")
    mode.add_argument("--reply-mentions", action="store_true", help="check new mentions and reply once per author/24h")
    ap.add_argument("--text", default="", help="optional custom tweet text (<= 280 chars)")
    ap.add_argument("--reply-to", default="", help="optional tweet ID to reply to (requires --text)")
    ap.add_argument("--slot", type=int, default=-1, help="override slot 0..2 (default derived from UTC hour)")
    ap.add_argument("--max-posts", type=int, default=3, help="max scheduled posts per UTC day (default 3)")
    ap.add_argument("--max-replies", type=int, default=10, help="max automated mention replies per UTC day (default 10)")
    ap.add_argument("--check-mentions", action="store_true", help="also check & reply to new mentions after --post")
    ap.add_argument("--creds", default=CRED_PATH)
    ap.add_argument("--db", default=DB_PATH)
    a = ap.parse_args(argv)

    summary = load_mcp_summary()
    now = now_utc()
    today = now.date()
    slot = a.slot if a.slot in (0, 1, 2) else current_slot(now)
    tweet = a.text.strip() if a.text.strip() else build_daily_tweet(summary, today, slot=slot)
    if not a.reply_mentions and len(tweet) > 280:
        sys.exit(f"tweet too long: {len(tweet)} > 280 chars")

    if a.dry_run:
        print(f"[DRY-RUN] slot={slot} chars={len(tweet)}/280\n---\n{tweet}\n---")
        return 0

    if os.path.exists(PAUSE_FILE):
        print(f"paused: {PAUSE_FILE} exists")
        return 0

    creds = load_credentials(a.creds)
    if not creds:
        print(f"waiting_for_credentials: {a.creds} not configured yet (no-op)")
        return 0

    conn = sqlite3.connect(a.db, timeout=30)
    init_db(conn)
    keep_db_owner(a.db)
    try:
        if a.reply_mentions:
            process_mentions(conn, creds, max_replies_per_day=a.max_replies)
            return 0
        day_key = today.isoformat()
        if a.reply_to and not a.text.strip():
            sys.exit("--reply-to requires --text")
        if a.text.strip():
            st, res = post_tweet(tweet, creds, reply_to=a.reply_to.strip())
            if st in (200, 201):
                tid = (res.get("data") or {}).get("id") if isinstance(res, dict) else ""
                if a.reply_to.strip():
                    record_post(conn, "mention_reply", a.reply_to.strip(), f"manual_reply tweet_id={tid}")
                else:
                    record_post(conn, "manual_post", f"manual-{tid or now_iso()}", f"tweet_id={tid}")
                print(f"posted X tweet id={tid} (HTTP {st})")
            else:
                print(f"X API error HTTP {st}: {str(res)[:400]}", file=sys.stderr)
                return 1
        elif posts_today_count(conn, day_key) >= a.max_posts:
            print(f"daily post cap reached ({a.max_posts}) for {day_key}")
        elif already_posted_slot(conn, day_key, slot):
            print(f"already posted slot {slot} today ({day_key})")
        else:
            st, res = post_tweet(tweet, creds)
            if st in (200, 201):
                tid = (res.get("data") or {}).get("id") if isinstance(res, dict) else ""
                ref = f"{day_key}-slot{slot}"
                record_post(conn, "daily_post", ref, f"tweet_id={tid}")
                print(f"posted X tweet id={tid} slot={slot} (HTTP {st})")
            else:
                print(f"X API error HTTP {st}: {str(res)[:400]}", file=sys.stderr)
                return 1
        if a.check_mentions:
            process_mentions(conn, creds, max_replies_per_day=a.max_replies)
        return 0
    finally:
        conn.close()
        keep_db_owner(a.db)


if __name__ == "__main__":
    sys.exit(main())
