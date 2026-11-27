#!/usr/bin/env python3
"""Official X (Twitter) API v2 daily autoposter for Quantum Aether (Free Tier compliant, max 1 post/day).

Uses zero external dependencies (pure stdlib RFC 5849 OAuth 1.0a HMAC-SHA1 -> POST https://api.x.com/2/tweets).
Credentials live strictly outside git at /etc/quantum-aether/x_api.json (chmod 0600):
  {"api_key": "...", "api_secret": "...", "access_token": "...", "access_token_secret": "..."}

Guardrails:
  * Hard cap: 1 automated post per UTC day (tracked in SQLite agent_platform_activity).
  * Instant kill-switch: touch /var/lib/quantum_saas/x_autopost.paused
  * Cleanly exits 0 (no-op) if /etc/quantum-aether/x_api.json is not configured yet.
  * Preserves quantum:quantum ownership on quantum_saas.db (-wal/-shm).

Usage:
  python3 tools/x_autopost.py --dry-run
  python3 tools/x_autopost.py --post
  python3 tools/x_autopost.py --post --text "Custom tweet <= 280 chars"
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
USER_AGENT = "QuantumAetherXBot/2.0 (+https://ather-quantum.com)"

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


def already_posted_today(conn: sqlite3.Connection, day: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM agent_platform_activity WHERE platform = 'x' AND kind = 'daily_post' AND ref_key = ?",
        (day,),
    ).fetchone())


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
    return {"measured": 118, "pq_hybrid": 91, "pq_pct": 77.1, "classical": 24, "tls12": 3, "pq_not_preferred": 0}


def build_daily_tweet(summary: dict, day: dt.date | None = None) -> str:
    d = day or now_utc().date()
    m = summary.get("measured", 118)
    pq_n = summary.get("pq_hybrid", 91)
    pq_pct = summary.get("pq_pct", 77.1)
    cls = summary.get("classical", 24)
    t12 = summary.get("tls12", 3)
    exposed = cls + t12
    day_str = d.isoformat()

    variants = [
        (
            f"Daily Remote MCP PQ-TLS Index ({day_str}):\n"
            f"Measured {m} live MCP servers from the Official Registry:\n"
            f"• {pq_n} ({pq_pct}%) negotiate X25519MLKEM768\n"
            f"• {exposed} still classical/TLS 1.2\n\n"
            f"Check yours + grab a 1-click Grade A README badge:\n"
            f"https://ather-quantum.com/mcp-index #MCP #PQC"
        ),
        (
            f"TLS 1.3 trap most teams miss: a server can pass SSL Labs PQC checks while still ranking X25519 first — "
            f"silently downgrading Chrome, Firefox & Safari to classical TLS.\n\n"
            f"Test any domain live with an Ed25519 signed receipt (free):\n"
            f"https://ather-quantum.com #PQC #TLS #NIS2"
        ),
        (
            f"Give Claude Code, Cursor, Codex or OpenClaw live post-quantum TLS audits + copy-paste Nginx/Cloudflare fixes "
            f"(zero API key):\n\n"
            f"npx skills add moncef00327-cloud/quantum-aether\n\n"
            f"Remote MCP (100/100 on mcptry): https://ather-quantum.com/mcp #OpenClaw #MCP"
        ),
        (
            f"Autonomous #Base USDC #x402 endpoints live on x402scan (6/6):\n"
            f"• $0.10 batch-scan (10 domains, Ed25519 receipts)\n"
            f"• $0.25 live CycloneDX 1.6 CBOM JSON\n\n"
            f"{X402SCAN_URL}\n"
            f"https://ather-quantum.com/.well-known/x402"
        ),
    ]
    return variants[d.toordinal() % len(variants)]


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


def post_tweet(text: str, creds: dict, timeout: float = 20.0) -> tuple[int, dict | str]:
    auth = oauth1_header("POST", TWEETS_URL, creds)
    body = json.dumps({"text": text}).encode("utf-8")
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="render today's tweet and length without posting")
    mode.add_argument("--post", action="store_true", help="publish tweet via X API v2 (max 1/day unless --text)")
    ap.add_argument("--text", default="", help="optional custom tweet text (<= 280 chars)")
    ap.add_argument("--creds", default=CRED_PATH)
    ap.add_argument("--db", default=DB_PATH)
    a = ap.parse_args(argv)

    summary = load_mcp_summary()
    today = now_utc().date()
    tweet = a.text.strip() if a.text.strip() else build_daily_tweet(summary, today)
    if len(tweet) > 280:
        sys.exit(f"tweet too long: {len(tweet)} > 280 chars")

    if a.dry_run:
        print(f"[DRY-RUN] chars={len(tweet)}/280\n---\n{tweet}\n---")
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
        day_key = today.isoformat()
        if not a.text.strip() and already_posted_today(conn, day_key):
            print(f"already posted today ({day_key})")
            return 0
        st, res = post_tweet(tweet, creds)
        if st in (200, 201):
            tid = (res.get("data") or {}).get("id") if isinstance(res, dict) else ""
            kind = "manual_post" if a.text.strip() else "daily_post"
            ref = f"manual-{tid or now_iso()}" if a.text.strip() else day_key
            record_post(conn, kind, ref, f"tweet_id={tid}")
            print(f"posted X tweet id={tid} (HTTP {st})")
            return 0
        print(f"X API error HTTP {st}: {str(res)[:400]}", file=sys.stderr)
        return 1
    finally:
        conn.close()
        keep_db_owner(a.db)


if __name__ == "__main__":
    sys.exit(main())
