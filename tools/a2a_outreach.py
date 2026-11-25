#!/usr/bin/env python3
"""Recurring, ethical B2B-grade A2A outreach campaign (owner-approved 2026-11-25).

Mirrors tools/outreach_send.py discipline for Agent-to-Agent (A2A) endpoints:
  python3 tools/a2a_outreach.py --sync                      refresh qualified open A2A targets from public registries
  python3 tools/a2a_outreach.py --dry-run [--limit 3]       run live TLS check + render payloads, send nothing, write nothing
  python3 tools/a2a_outreach.py --send [--limit 10]         send up to --daily-cap (default 10) per 24h with 60s pause

Guardrails:
  * One message per A2A host/endpoint, EVER (tracked in SQLite a2a_outreach_sent).
  * Respects a2a_outreach_suppress, outreach_suppress, and adoption_optout.
  * Instant kill-switch: touch /var/lib/quantum_saas/a2a_outreach.paused (or outreach.paused).
  * Only contacts open (auth_required=False), healthy, relevant security/compliance/x402/M2M/enterprise/agent-network
    endpoints; runs ONE live TLS 1.3 ClientHello to <host>:443 so every message delivers genuine, verifiable PQ-TLS value.
  * Preserves quantum:quantum ownership on quantum_saas.db (-wal/-shm).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import pwd
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import a2a_client  # noqa: E402
from tools import outreach_send  # noqa: E402

DATA_DIR = os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas")
DB_PATH = os.path.join(DATA_DIR, "quantum_saas.db")
TARGETS_PATH = "/root/outreach/a2a_targets.json"
PAUSE_FILES = [
    os.path.join(DATA_DIR, "a2a_outreach.paused"),
    os.path.join(DATA_DIR, "outreach.paused"),
]
SITE = "https://ather-quantum.com"
OUR_CARD = f"{SITE}/.well-known/agent-card.json"
USER_AGENT = f"QuantumAetherA2A/1.0 (+{OUR_CARD})"

RELEVANT_RE = re.compile(
    r"\b(security|cyber|tls|ssl|cert|pqc|quantum|audit|compliance|nis2|dora|soc2|iso27001|gdpr|privacy|"
    r"x402|usdc|m2m|clearinghouse|marketplace|directory|registry|discovery|network|coordina|acquisition|"
    r"devops|cloud|infra|enterprise|b2b|fintech|bank|payment|saas|api|mcp|a2a|trust|verify|osint|recon|scanner)\b",
    re.I,
)
SKIP_RE = re.compile(
    r"\b(nsfw|porn|adult|casino|gambl|weather|horoscope|astrology|joke|meme|trivia|recipe|dating|tarot|localhost|127\.0\.0\.1)\b",
    re.I,
)
OPT_OUT_RE = re.compile(r"\b(stop|unsubscribe|opt[- ]?out|do not contact|remove us|blacklist|blocked|unauthorized)\b", re.I)
PAID_BOT_RE = re.compile(
    r"\b(x402|pay[- ]?per[- ]?call|http\s*402|paid tools|paid operations|prepaid credits|tollbooth|storefront|"
    r"per image|per call|autonomous purchase|solana usdc)\b",
    re.I,
)
TEAM_CONTACT_RE = re.compile(
    r"\b(message[- ]?team|contact|join|coordina|human|owner|partner|directory|registry|inquiry|submit|list[- ]?agent)\b",
    re.I,
)
TASK_ID_TEXT_RE = re.compile(r"tasks/get\s+([a-zA-Z0-9_-]{8,80})")

SCHEMA = """
CREATE TABLE IF NOT EXISTS a2a_outreach_sent (
    endpoint      TEXT PRIMARY KEY,
    host          TEXT NOT NULL,
    agent_name    TEXT,
    card_url      TEXT,
    tls_version   TEXT,
    kex_group     TEXT,
    kex_class     TEXT,
    http_status   INTEGER,
    reply_excerpt TEXT,
    sent_at       TEXT NOT NULL,
    task_id       TEXT,
    task_state    TEXT,
    task_reply    TEXT
);
CREATE INDEX IF NOT EXISTS a2a_outreach_sent_host ON a2a_outreach_sent (host);
CREATE INDEX IF NOT EXISTS a2a_outreach_sent_at ON a2a_outreach_sent (sent_at);

CREATE TABLE IF NOT EXISTS a2a_outreach_suppress (
    host       TEXT PRIMARY KEY,
    reason     TEXT,
    created_at TEXT NOT NULL
);
"""


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def init(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript(SCHEMA)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(a2a_outreach_sent)")}
        for col in ("task_id", "task_state", "task_reply"):
            if col not in cols:
                conn.execute(f"ALTER TABLE a2a_outreach_sent ADD COLUMN {col} TEXT")


def keep_db_owner(db_path: str) -> None:
    try:
        pw = pwd.getpwnam("quantum")
        uid, gid = pw.pw_uid, pw.pw_gid
    except KeyError:
        return
    for suffix in ("", "-wal", "-shm"):
        p = db_path + suffix
        if os.path.exists(p):
            try:
                os.chown(p, uid, gid)
            except OSError:
                pass


def is_paused() -> str | None:
    for p in PAUSE_FILES:
        if os.path.exists(p):
            return p
    return None


def _host_of(url: str) -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlsplit(url.strip())
    return (parsed.hostname or "").lower().removeprefix("www.")


def is_relevant_candidate(name: str, description: str, skills_blob: str, url: str) -> bool:
    host = _host_of(url)
    if not host or "." not in host or "ather-quantum.com" in host or host.endswith((".local", ".internal", ".test", ".example")):
        return False
    blob = f"{name} {description} {skills_blob} {url}"
    if SKIP_RE.search(blob):
        return False
    return bool(RELEVANT_RE.search(blob))


def _get_json(url: str, timeout: float = 15.0) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(500_000).decode("utf-8", "replace"))


def sync_targets(
    out_path: str = TARGETS_PATH,
    *,
    getter=_get_json,
    max_per_registry: int = 300,
) -> list[dict]:
    """Fetch open, healthy, relevant A2A agent candidates from a2aregistry.org and localmark.ai."""
    found: list[dict] = []
    seen_hosts: set[str] = set()

    def add_item(item: dict) -> None:
        host = _host_of(item.get("card_url") or item.get("endpoint") or "")
        if not host or host in seen_hosts:
            return
        if not is_relevant_candidate(
            item.get("name", ""),
            item.get("description", ""),
            item.get("skills_text", ""),
            item.get("endpoint") or item.get("card_url") or "",
        ):
            return
        seen_hosts.add(host)
        item["host"] = host
        found.append(item)

    # 1) a2aregistry.org (paginated up to max_per_registry)
    for offset in range(0, max_per_registry, 100):
        try:
            doc = getter(f"https://a2aregistry.org/api/agents?limit=100&offset={offset}")
        except Exception:
            break
        agents = doc.get("agents") if isinstance(doc, dict) else []
        if not agents:
            break
        for a in agents:
            if not isinstance(a, dict) or not a.get("is_healthy"):
                continue
            if a.get("security") or a.get("securitySchemes"):
                continue
            url = (a.get("url") or "").strip()
            card_url = (a.get("wellKnownURI") or "").strip()
            if not url.startswith("https://") and not card_url.startswith("https://"):
                continue
            skills_text = " ".join(
                f"{s.get('id', '')} {s.get('name', '')} {' '.join(s.get('tags') or [])}"
                for s in (a.get("skills") or [])
                if isinstance(s, dict)
            )
            add_item({
                "source": "a2aregistry.org",
                "name": (a.get("name") or "").strip(),
                "description": (a.get("description") or "")[:300],
                "card_url": card_url,
                "endpoint": url,
                "skills_text": skills_text[:400],
            })
        if len(agents) < 100:
            break

    # 2) localmark.ai (targeted queries for A2A security/compliance/x402/enterprise agents)
    for q in ("security", "compliance", "tls", "x402", "audit", "enterprise", "devops", "agent"):
        try:
            doc = getter(f"https://localmark.ai/api/v1/search?q={urllib.parse.quote(q)}&limit=30")
        except Exception:
            continue
        items = doc.get("items") or doc.get("results") or doc.get("agents") if isinstance(doc, dict) else doc
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            card_url = (it.get("card_url") or "").strip()
            if not card_url.startswith("https://"):
                continue
            add_item({
                "source": "localmark.ai",
                "name": (it.get("name") or "").strip(),
                "description": (it.get("description") or "")[:300],
                "card_url": card_url,
                "endpoint": (it.get("endpoint_url") or it.get("url") or "").strip(),
                "skills_text": q,
            })

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps({"synced_at": now_iso(), "count": len(found), "targets": found}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    os.replace(tmp, out)
    return found


def is_blocked_or_sent(conn: sqlite3.Connection, endpoint: str, host: str) -> bool:
    ep_l = endpoint.rstrip("/").lower()
    h_l = host.lower().removeprefix("www.")
    if conn.execute(
        "SELECT 1 FROM a2a_outreach_sent WHERE lower(rtrim(endpoint,'/')) = ? OR lower(host) = ?",
        (ep_l, h_l),
    ).fetchone():
        return True
    if conn.execute("SELECT 1 FROM a2a_outreach_suppress WHERE lower(host) = ?", (h_l,)).fetchone():
        return True
    for tbl in ("outreach_suppress", "growth_suppress", "adoption_optout"):
        try:
            if conn.execute(f"SELECT 1 FROM {tbl} WHERE lower(domain) = ?", (h_l,)).fetchone():
                return True
        except sqlite3.Error:
            pass
    return False


def sent_last_24h(conn: sqlite3.Connection) -> int:
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return int(conn.execute("SELECT COUNT(*) FROM a2a_outreach_sent WHERE sent_at >= ?", (since,)).fetchone()[0])


def build_a2a_pitch(summary: dict, host: str, obs: dict, *, date_iso: str | None = None, method: str | None = None) -> dict:
    """Build a proof-led A2A JSON-RPC 2.0 payload supporting both A2A 0.3 (message/send) and A2A 1.0 (SendMessage)."""
    today = date_iso or dt.date.today().isoformat()
    name = summary.get("name") or host
    proto = str(summary.get("protocol_version") or "")
    chosen_method = method or ("SendMessage" if proto.startswith("1.") else "message/send")
    tls_v = obs["tls_version"]
    grp = obs["group"]
    if obs["kex_class"] == "hybrid-pq":
        finding = (
            f"On {today}, one public TLS handshake to {host}:443 negotiated {tls_v} with {grp} "
            f"(hybrid post-quantum key exchange — covered). Other endpoints or CDN changes can still silently revert."
        )
    else:
        finding = (
            f"On {today}, one public TLS handshake to {host}:443 negotiated {tls_v} with classical {grp} key exchange "
            f"(not yet hybrid post-quantum X25519MLKEM768)."
        )

    text = (
        f"Hello {name} — one-time A2A interoperability & post-quantum TLS note from Quantum Aether ({OUR_CARD}).\n\n"
        f"{finding}\n\n"
        f"Your agent or team can verify any public hostname via our signed A2A 0.3.0 endpoint ({SITE}/a2a) or "
        f"remote MCP server ({SITE}/mcp — free stored evidence & rate-limited scans with Ed25519 JWS receipts "
        f"verifiable via {SITE}/.well-known/jwks.json). For compliance workflows (NIS2/DORA/BSI), we also offer "
        f"an Auditor-Ready Signed PDF + CycloneDX 1.6 CBOM Attestation ($5.00 USDC on Base via x402; free archived "
        f"sample PDF: {SITE}/api/v1/attestation/sample.pdf) and a 30% recurring AI Agent Affiliate Programme "
        f"(MCP register_agent_affiliate). Free live check for your host: {SITE}/?domain={host}&lang=en\n\n"
        f"One-time message; we will not message this endpoint again. Reply 'stop' to suppress {host}."
    )
    data = {
        "from_agent": "Quantum Aether",
        "agent_card": OUR_CARD,
        "a2a_endpoint": f"{SITE}/a2a",
        "mcp_endpoint": f"{SITE}/mcp",
        "jwks_url": f"{SITE}/.well-known/jwks.json",
        "observed_host": host,
        "observed_date": today,
        "observed_tls": tls_v,
        "observed_group": grp,
        "observed_kex_class": obs["kex_class"],
        "free_check_url": f"{SITE}/?domain={host}&lang=en",
        "free_sample_pdf": f"{SITE}/api/v1/attestation/sample.pdf",
        "attestation_api": f"{SITE}/api/v1/attestation",
        "attestation_price": "5.00 USDC (Base, x402 v2)",
        "affiliate_register": f"{SITE}/api/v1/agent/affiliate/register",
        "one_time_notice": True,
    }
    contact_skill = pick_contact_skill(summary)
    if contact_skill:
        data["skill"] = contact_skill
    if chosen_method == "SendMessage":
        msg = {
            "role": "ROLE_USER",
            "messageId": str(uuid.uuid4()),
            "parts": [
                {"text": text},
                {"data": data},
            ],
        }
    else:
        msg = {
            "kind": "message",
            "role": "user",
            "messageId": str(uuid.uuid4()),
            "parts": [
                {"kind": "text", "text": text},
                {"kind": "data", "data": data},
            ],
        }
    return {
        "jsonrpc": "2.0",
        "id": f"qa-a2a-{uuid.uuid4().hex[:12]}",
        "method": chosen_method,
        "params": {"message": msg},
    }


def is_paid_storefront_only(card: dict) -> bool:
    """Return True for pay-per-call x402 vending-machine bots that don't expose team/contact/coordination skills."""
    if not isinstance(card, dict):
        return False
    skill_ids = " ".join(str(s.get("id") or "") + " " + str(s.get("name") or "") for s in (card.get("skills") or []) if isinstance(s, dict))
    blob = f"{card.get('name') or ''} {card.get('description') or ''} {skill_ids}"
    if TEAM_CONTACT_RE.search(blob):
        return False
    return bool(PAID_BOT_RE.search(blob))


def pick_contact_skill(summary: dict) -> str | None:
    """Pick a safe free/contact/coordination skill id if the target agent card advertises one."""
    preferred = ("message-team", "contact", "inquiry", "join", "register", "submit", "hello", "info")
    skills = summary.get("skills") or []
    for want in preferred:
        for s in skills:
            sid = str(s.get("id") or "").strip()
            if sid and want in sid.lower():
                return sid
    return None


def _extract_task_info(resp: dict | str, excerpt: str) -> tuple[str | None, str | None]:
    if isinstance(resp, dict):
        res = resp.get("result")
        if isinstance(res, dict):
            tid = res.get("id") if isinstance(res.get("id"), str) else None
            state = (res.get("status") or {}).get("state") if isinstance(res.get("status"), dict) else None
            if tid and state:
                return tid, str(state)
    m = TASK_ID_TEXT_RE.search(excerpt or "")
    if m:
        return m.group(1), "working"
    return None, None


def _extract_reply_excerpt(resp: dict | str) -> str:
    if isinstance(resp, str):
        return resp.strip()[:400]
    if not isinstance(resp, dict):
        return str(resp)[:400]
    if "error" in resp:
        err = resp["error"]
        return f"JSON-RPC error {err.get('code')}: {err.get('message')}"[:400] if isinstance(err, dict) else str(err)[:400]
    res = resp.get("result")
    if isinstance(res, dict):
        parts = res.get("parts") or (res.get("status") or {}).get("message", {}).get("parts") or []
        texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
        if texts:
            return " ".join(texts).strip()[:400]
        return json.dumps(res, ensure_ascii=False)[:400]
    return json.dumps(resp, ensure_ascii=False)[:400]


def run_batch(
    *,
    mode: str,
    targets_path: str = TARGETS_PATH,
    db_path: str = DB_PATH,
    limit: int = 10,
    daily_cap: int = 10,
    pause_s: float = 60.0,
    card_fetcher=a2a_client._http_json,
    handshake_fn=outreach_send.handshake,
    sleep_fn=time.sleep,
) -> dict:
    paused = is_paused()
    if mode == "send" and paused:
        return {"mode": mode, "paused": paused, "sent": 0, "skipped": 0, "errors": 0}

    p = Path(targets_path)
    if not p.exists():
        raise FileNotFoundError(f"Targets file not found: {targets_path} (run --sync first)")
    raw = json.loads(p.read_text(encoding="utf-8"))
    targets = raw.get("targets") if isinstance(raw, dict) else raw

    conn = sqlite3.connect(db_path)
    init(conn)
    if mode == "send":
        keep_db_owner(db_path)

    already_24h = sent_last_24h(conn)
    budget = max(0, min(limit, daily_cap - already_24h)) if mode == "send" else limit
    summary_out = {"mode": mode, "budget": budget, "attempts": 0, "sent": 0, "rendered": 0, "skipped": 0, "errors": 0, "items": []}
    consecutive_errors = 0

    try:
        for t in targets:
            if summary_out["attempts" if mode == "send" else "rendered"] >= budget:
                break
            if mode == "send" and is_paused():
                break
            card_hint = (t.get("card_url") or t.get("endpoint") or "").strip()
            host = (t.get("host") or _host_of(card_hint)).strip().lower()
            if not host or is_blocked_or_sent(conn, t.get("endpoint") or card_hint, host):
                summary_out["skipped"] += 1
                continue

            # 1) Live Agent Card verification (must be open, valid https non-root JSON-RPC endpoint, not paid-only bot)
            try:
                card_url, card = a2a_client.fetch_agent_card(card_hint, fetcher=card_fetcher, timeout=10.0)
                info = a2a_client.summarize_card(card_url, card)
            except Exception:
                summary_out["skipped"] += 1
                continue

            if is_paid_storefront_only(card):
                summary_out["skipped"] += 1
                continue

            endpoint = (info.get("endpoint") or "").strip()
            ep_host = _host_of(endpoint) or host
            ep_path = urllib.parse.urlsplit(endpoint).path.strip("/")
            ep_trim = endpoint.rstrip("/")
            if info.get("auth_required") or not endpoint.startswith("https://") or not ep_path or ep_trim.endswith(("/mcp", "/ask")):
                summary_out["skipped"] += 1
                continue
            if is_blocked_or_sent(conn, endpoint, ep_host):
                summary_out["skipped"] += 1
                continue

            # 2) Live single-ClientHello PQ-TLS check on the target agent's own host
            obs = handshake_fn(ep_host)
            if not isinstance(obs, dict) or obs.get("error"):
                summary_out["skipped"] += 1
                continue

            payload = build_a2a_pitch(info, ep_host, obs)

            if mode == "dry-run":
                summary_out["rendered"] += 1
                summary_out["items"].append({
                    "name": info["name"], "host": ep_host, "endpoint": endpoint,
                    "method": payload["method"],
                    "tls": obs["tls_version"], "group": obs["group"], "kex_class": obs["kex_class"],
                    "preview": payload["params"]["message"]["parts"][0]["text"][:260],
                })
                continue

            # 3) Send ONE A2A JSON-RPC 2.0 call (with A2A-Version header + auto-fallback on -32601 / -32009)
            if summary_out["attempts"] > 0 and pause_s > 0:
                sleep_fn(pause_s)

            def _post_with_version(pld):
                hdrs = {"A2A-Version": "1.0"} if pld["method"] == "SendMessage" else {"A2A-Version": "0.3"}
                try:
                    return card_fetcher(endpoint, method="POST", body=pld, timeout=20.0, extra_headers=hdrs)
                except TypeError:
                    return card_fetcher(endpoint, method="POST", body=pld, timeout=20.0)

            try:
                status, resp = _post_with_version(payload)
                err_code = resp.get("error", {}).get("code") if (status == 200 and isinstance(resp, dict) and isinstance(resp.get("error"), dict)) else None
                if err_code in (-32601, -32009):
                    alt = "message/send" if payload["method"] == "SendMessage" else "SendMessage"
                    payload = build_a2a_pitch(info, ep_host, obs, method=alt)
                    status, resp = _post_with_version(payload)
            except Exception:
                summary_out["errors"] += 1
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    break
                continue

            summary_out["attempts"] += 1
            excerpt = _extract_reply_excerpt(resp)
            task_id, task_state = _extract_task_info(resp, excerpt)
            ts = now_iso()
            with conn:
                conn.execute(
                    "INSERT OR REPLACE INTO a2a_outreach_sent "
                    "(endpoint, host, agent_name, card_url, tls_version, kex_group, kex_class, http_status, "
                    "reply_excerpt, sent_at, task_id, task_state) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (endpoint, ep_host, info["name"], card_url, obs["tls_version"], obs["group"], obs["kex_class"],
                     int(status), excerpt, ts, task_id, task_state),
                )
                if status in (401, 403, 429) or OPT_OUT_RE.search(excerpt):
                    conn.execute(
                        "INSERT OR IGNORE INTO a2a_outreach_suppress (host, reason, created_at) VALUES (?, ?, ?)",
                        (ep_host, f"http_{status}_or_optout", ts),
                    )
            keep_db_owner(db_path)

            if 200 <= int(status) < 300:
                consecutive_errors = 0
                summary_out["sent"] += 1
            else:
                summary_out["errors"] += 1
                consecutive_errors += 1
            summary_out["items"].append({
                "name": info["name"], "host": ep_host, "endpoint": endpoint,
                "http_status": status, "task_id": task_id, "reply_excerpt": excerpt[:200],
            })
            if consecutive_errors >= 5:
                break
    finally:
        conn.close()
    return summary_out


def poll_pending_tasks(*, db_path: str = DB_PATH, card_fetcher=a2a_client._http_json) -> dict:
    """Poll open async A2A tasks (e.g. Braigetori team queue) via tasks/get and store completed human replies."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init(conn)
    out = {"checked": 0, "updated": 0, "items": []}
    try:
        rows = conn.execute(
            "SELECT endpoint, host, agent_name, task_id, task_state FROM a2a_outreach_sent "
            "WHERE task_id IS NOT NULL AND task_id != '' "
            "AND (task_state IS NULL OR task_state IN ('submitted', 'working', 'input-required')) "
            "ORDER BY sent_at DESC LIMIT 25"
        ).fetchall()
        for r in rows:
            out["checked"] += 1
            payload = {"jsonrpc": "2.0", "id": f"qa-poll-{uuid.uuid4().hex[:8]}", "method": "tasks/get", "params": {"id": r["task_id"]}}
            try:
                st, resp = card_fetcher(r["endpoint"], method="POST", body=payload, timeout=15.0)
            except Exception:
                continue
            if st != 200 or not isinstance(resp, dict) or not isinstance(resp.get("result"), dict):
                continue
            res = resp["result"]
            new_state = str((res.get("status") or {}).get("state") or r["task_state"] or "")
            new_reply = _extract_reply_excerpt(resp)
            if new_state != r["task_state"] or (new_reply and new_state == "completed"):
                with conn:
                    conn.execute(
                        "UPDATE a2a_outreach_sent SET task_state=?, task_reply=? WHERE endpoint=?",
                        (new_state, new_reply, r["endpoint"]),
                    )
                keep_db_owner(db_path)
                out["updated"] += 1
            out["items"].append({"host": r["host"], "task_id": r["task_id"], "state": new_state, "reply": new_reply[:200]})
    finally:
        conn.close()
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Controlled recurring B2B-grade A2A outreach campaign.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--sync", action="store_true", help="Refresh qualified open A2A targets from public registries")
    mode.add_argument("--dry-run", action="store_true", help="Render messages with live TLS check; send nothing")
    mode.add_argument("--send", action="store_true", help="Send up to --limit/--daily-cap A2A introductions")
    mode.add_argument("--poll-tasks", action="store_true", help="Poll open async A2A tasks for human team replies")
    ap.add_argument("--targets", default=TARGETS_PATH)
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--daily-cap", type=int, default=10)
    ap.add_argument("--pause", type=float, default=60.0)
    args = ap.parse_args(argv)

    if args.sync:
        items = sync_targets(args.targets)
        print(f"Synced {len(items)} qualified open A2A targets -> {args.targets}")
        return 0
    if args.poll_tasks:
        print(json.dumps(poll_pending_tasks(db_path=args.db), indent=2, ensure_ascii=False))
        return 0

    res = run_batch(
        mode="send" if args.send else "dry-run",
        targets_path=args.targets,
        db_path=args.db,
        limit=args.limit,
        daily_cap=args.daily_cap,
        pause_s=args.pause,
    )
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
