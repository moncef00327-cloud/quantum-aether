#!/usr/bin/env python3
"""Flag adult/malware domains via Cloudflare family DNS (1.1.1.3 -> 0.0.0.0) and
write them to data/family_dns_blocked.json so /site/<domain> is never indexed."""
import concurrent.futures as cf
import datetime as dt
import json
import os
import sqlite3
import subprocess

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "family_dns_blocked.json")
DB = "file:" + os.path.join(os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas"), "quantum_saas.db") + "?mode=ro"


def domains():
    c = sqlite3.connect(DB, uri=True)
    ds = set()
    for (d,) in c.execute("SELECT DISTINCT domain FROM adoption_results WHERE ok=1"):
        d = (d or "").lower().strip()
        if d.startswith("www."):
            d = d[4:]
        if d and "." in d:
            ds.add(d)
    for (p,) in c.execute("SELECT DISTINCT path FROM pageviews WHERE path LIKE '/site/%'"):
        d = p.split("/site/", 1)[1].split("?")[0].strip("/").lower()
        if d.startswith("www."):
            d = d[4:]
        if d and "." in d:
            ds.add(d)
    return sorted(ds)


def blocked(d):
    try:
        out = subprocess.run(["dig", "+short", "+time=3", "+tries=1", "@1.1.1.3", d, "A"],
                             capture_output=True, text=True, timeout=6).stdout
        return d if "0.0.0.0" in out else None
    except Exception:
        return None


def main():
    ds = domains()
    hits = []
    with cf.ThreadPoolExecutor(max_workers=40) as ex:
        for r in ex.map(blocked, ds):
            if r:
                hits.append(r)
    # Merge, never replace: the database may not hold every listed host (server move), and a failed lookup is no all-clear.
    try:
        with open(OUT, encoding="utf-8") as f:
            hits.extend(json.load(f).get("hosts", []))
    except FileNotFoundError:
        pass
    hits = sorted(set(hits))
    json.dump({"hosts": hits, "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "checked": len(ds),
               "note": "Cloudflare family DNS (1.1.1.3) -> 0.0.0.0; de-indexed via search_indexing."},
              open(OUT, "w"), ensure_ascii=False, indent=1)
    print(f"checked {len(ds)} domains, blocked {len(hits)} -> {OUT}")


if __name__ == "__main__":
    main()
