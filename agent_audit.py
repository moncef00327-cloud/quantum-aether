"""Privacy-safe audit trail for inbound AI agent protocol calls (MCP, A2A, ACP).

Records protocol, action/tool/skill, optional declared client name (or UA family), target domain,
and outcome status. Never stores IP addresses, credentials, payment payloads, or raw headers.
"""
import datetime as dt
import re

_CLEAN_RE = re.compile(r"[^a-zA-Z0-9._:/ -]+")


def _clean(value, max_len: int) -> str:
    if not value:
        return ""
    return _CLEAN_RE.sub("", str(value).strip())[:max_len]


def init(conn) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS agent_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            protocol TEXT NOT NULL,
            action TEXT NOT NULL,
            client_name TEXT NOT NULL DEFAULT '',
            domain TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'ok'
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_calls_ts ON agent_calls(ts)")


def client_label(headers, fallback: str = "") -> str:
    """Derive a short, non-PII client identifier from an explicit name or User-Agent product token."""
    if fallback:
        return _clean(fallback, 64)
    ua = (headers.get("User-Agent") or "").strip() if headers else ""
    if not ua:
        return ""
    token = ua.split()[0]
    return _clean(token, 64)


def record(conn, protocol: str, action: str, client_name: str = "", domain: str = "", status: str = "ok") -> None:
    """Best-effort insert into agent_calls; never raises to break an agent request."""
    try:
        init(conn)
        ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "INSERT INTO agent_calls (ts, protocol, action, client_name, domain, status) VALUES (?, ?, ?, ?, ?, ?)",
            (
                ts,
                _clean(protocol, 16) or "unknown",
                _clean(action, 48) or "unknown",
                _clean(client_name, 64),
                _clean(domain, 128),
                _clean(status, 32) or "ok",
            ),
        )
        conn.commit()
    except Exception:
        pass


def summary(conn, days: int = 14, limit: int = 25) -> dict:
    """Aggregated summary for /admin over the last N days, separating real tool/skill calls from liveness/initialize."""
    init(conn)
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = conn.execute(
        """SELECT protocol, action, client_name, status, COUNT(*) AS n, MAX(ts) AS last_ts
           FROM agent_calls
           WHERE ts >= ?
           GROUP BY protocol, action, client_name, status
           ORDER BY CASE WHEN action = 'initialize' THEN 1 ELSE 0 END, n DESC, last_ts DESC
           LIMIT ?""",
        (cutoff, limit),
    ).fetchall()
    proto_rows = conn.execute(
        "SELECT protocol, COUNT(*) AS n FROM agent_calls WHERE ts >= ? AND action != 'initialize' GROUP BY protocol ORDER BY n DESC",
        (cutoff,),
    ).fetchall()
    init_total = conn.execute(
        "SELECT COUNT(*) FROM agent_calls WHERE ts >= ? AND action = 'initialize'",
        (cutoff,),
    ).fetchone()[0]
    by_protocol = {r[0]: r[1] for r in proto_rows}
    total = sum(by_protocol.values())
    formatted = [
        {"protocol": r[0], "action": r[1], "client_name": r[2] or "—", "status": r[3], "n": r[4], "last_ts": r[5],
         "is_handshake": r[1] == "initialize"}
        for r in rows
    ]
    return {"days": days, "total": total, "init_total": init_total, "by_protocol": by_protocol, "rows": formatted}
