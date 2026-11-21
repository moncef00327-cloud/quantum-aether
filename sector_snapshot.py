# sector_snapshot.py — paid weekly sector snapshot (x402, 2026-11-21): every domain of one watch-list sector in the
# latest weekly registry measurement, with grade, key-exchange group, TLS version and post-quantum status.
# Read-only; built from adoption_results. Excluded and opted-out domains are left out, as on the public pages.
import adoption
import search_indexing

DEFAULT_SECTOR = "cyber-agencies-worldwide"


def sectors():
    return adoption.load_watchlists()


def keys():
    return sorted(sectors())


def latest_week(conn):
    weeks = adoption.weeks(conn)
    return weeks[-1] if weeks else None


def build(conn, key, week=None):
    """-> dict, or None when the sector is unknown or there is no measurement yet."""
    sector = sectors().get(key)
    week = week or latest_week(conn)
    if not sector or not week:
        return None
    members = {d.lower() for d in sector.get("domains", [])}
    optout = adoption.load_optout(conn=conn)
    rows = []
    for r in adoption.rows_for(conn, week):
        d = r["domain"]
        if d not in members or search_indexing.is_excluded(d) or adoption.opted_out(d, optout):
            continue
        undetermined = bool(r.get("unsure"))
        rows.append({"domain": d, "reachable": bool(r["ok"]), "grade": r.get("grade"), "group": r.get("grp"),
                     "tls": r.get("tls"), "post_quantum": None if undetermined or not r["ok"] else bool(r["pq"]),
                     "undetermined": undetermined, "network": r.get("as_name"), "scanned_at": r.get("scanned_at")})
    rows.sort(key=lambda x: (x["post_quantum"] is not True, x["domain"]))
    reachable = [x for x in rows if x["reachable"] and not x["undetermined"]]
    pq = sum(1 for x in reachable if x["post_quantum"])
    labels = sector.get("labels") or {}
    return {
        "sector": key, "label": labels.get("en") or key, "labels": labels, "week": week,
        "summary": {"listed": len(members), "measured": len(rows), "determined": len(reachable), "post_quantum": pq,
                    "post_quantum_pct": round(100 * pq / len(reachable), 1) if reachable else 0.0},
        "domains": rows,
        "method": "One TLS handshake per domain from one location on port 443 during the weekly registry run. "
                  "External observation, not a compliance certification.",
        "license": "Quote individual entries with attribution (Source: Quantum Aether Exposure Registry). "
                   "Bulk redistribution or rebuilding the registry needs a licence: https://ather-quantum.com/data-license",
    }
