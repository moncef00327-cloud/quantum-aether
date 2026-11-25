#!/usr/bin/env python3
"""Build a verified classical/non-PQ B2B prospect CSV from adoption_results (read-only DB + security.txt lookup).

Produces a CSV compatible with tools/outreach_send.py (--targets ...), prioritizing Grade F -> C -> B
in paying commercial sectors so every target has an authentic, urgent post-quantum TLS gap.
NEVER sends email and NEVER modifies the database.
"""
import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import os
import re
import sqlite3
import sys
import urllib.parse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import outreach_suppress as osup  # noqa: E402

DB_PATH = os.path.join(os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas"), "quantum_saas.db")
OUT_PATH = "/root/outreach/targets_cf_priority.csv"
UA = "Mozilla/5.0 (compatible; QuantumAetherBot/1.0; +https://ather-quantum.com/bot)"

PAY_SECTORS = (
    "banks-mena", "banks-dach", "banks-europe", "banks-americas-apac",
    "finance-worldwide", "payments-fintech", "crypto-exchanges",
    "health-insurance-dach", "global-insurance-healthcare",
    "telecom", "enterprise-saas-b2b", "cloud-security", "companies-dach",
)
ARAB_SECTORS = {"banks-mena"}
EMAIL_RE = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")


def parse_security_txt(text):
    emails = []
    expires = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        kl = k.strip().lower()
        val = v.strip()
        if kl == "contact":
            if val.lower().startswith("mailto:"):
                addr = urllib.parse.unquote(val[7:].split("?")[0]).strip().lower()
                if EMAIL_RE.match(addr) and not any(bad in addr for bad in ("noreply", "no-reply", "example.com", "abuse@", "dnisclosubre")):
                    emails.append(addr)
        elif kl == "expires" and not expires:
            expires = val
    # Skip expired security.txt when ISO timestamp is parseable and in the past
    if expires:
        try:
            exp_dt = dt.datetime.fromisoformat(expires.replace("Z", "+00:00"))
            if exp_dt.tzinfo is None:
                exp_dt = exp_dt.replace(tzinfo=dt.timezone.utc)
            if exp_dt < dt.datetime.now(dt.timezone.utc):
                return [], expires, True
        except ValueError:
            pass
    return list(dict.fromkeys(emails)), expires, False


def fetch_security_txt(domain, timeout=4.0):
    base = domain.lower().removeprefix("www.")
    hosts = [domain] if domain.startswith("www.") else [domain, "www." + domain]
    seen = set()
    urls = []
    for h in hosts:
        for p in ("/.well-known/security.txt", "/security.txt"):
            u = f"https://{h}{p}"
            if u not in seen:
                seen.add(u)
                urls.append(u)
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    for url in urls:
        try:
            r = sess.get(url, timeout=timeout, allow_redirects=True)
            if r.status_code != 200:
                continue
            ctype = (r.headers.get("Content-Type") or "").lower()
            if "html" in ctype or "<html" in r.text[:300].lower():
                continue
            emails, expires, is_expired = parse_security_txt(r.text)
            if is_expired:
                return None
            if emails:
                # Prefer address matching the org's own domain when multiple are listed
                same = [e for e in emails if e.endswith("@" + base) or ("." + base) in e.split("@", 1)[1]]
                chosen = same[0] if same else emails[0]
                return {"contact_email": chosen, "source_url": r.url, "expires": expires}
        except Exception:
            continue
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--out", default=OUT_PATH)
    ap.add_argument("--grades", default="F,C,B", help="comma-separated grades to include (default F,C,B)")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--max-targets", type=int, default=150)
    ap.add_argument("--include-top", action="store_true", default=True,
                    help="also scan unsectored top-ranked commercial domains (F->C->B) after paying sectors")
    ap.add_argument("--no-include-top", dest="include_top", action="store_false")
    a = ap.parse_args()

    grades = tuple(g.strip().upper() for g in a.grades.split(",") if g.strip())
    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    wk = conn.execute("SELECT MAX(week) FROM adoption_results").fetchone()[0]

    # Collect already-sent, suppressed, and opted-out domains/emails
    skip_domains, skip_emails = set(), set()
    for tbl, col in (("outreach_sent", "domain"), ("outreach_suppress", "domain"),
                     ("growth_suppress", "domain"), ("adoption_optout", "domain")):
        try:
            skip_domains |= {(r[0] or "").strip().lower().removeprefix("www.") for r in conn.execute(f"SELECT {col} FROM {tbl}") if r[0]}
        except sqlite3.Error:
            pass
    for tbl, col in (("outreach_sent", "email"), ("outreach_suppress", "email"), ("growth_suppress", "email")):
        try:
            skip_emails |= {osup.normalize(r[0]) for r in conn.execute(f"SELECT {col} FROM {tbl}") if r[0]}
        except sqlite3.Error:
            pass

    ph_s = ",".join("?" for _ in PAY_SECTORS)
    ph_g = ",".join("?" for _ in grades)
    rows = list(conn.execute(f"""
        SELECT domain, sector, grade, grp, tls, rank
        FROM adoption_results
        WHERE week = ? AND ok = 1 AND pq = 0 AND unsure = 0
          AND sector IN ({ph_s}) AND grade IN ({ph_g})
        ORDER BY CASE grade WHEN 'F' THEN 0 WHEN 'C' THEN 1 WHEN 'B' THEN 2 ELSE 3 END,
                 CASE sector WHEN 'banks-mena' THEN 0 WHEN 'banks-dach' THEN 1 WHEN 'banks-europe' THEN 2
                             WHEN 'payments-fintech' THEN 3 WHEN 'telecom' THEN 4 ELSE 5 END,
                 domain
    """, (wk, *PAY_SECTORS, *grades)).fetchall())
    if a.include_top:
        rows += list(conn.execute(f"""
            SELECT domain, COALESCE(NULLIF(sector,''), 'top-commercial') AS sector, grade, grp, tls, rank
            FROM adoption_results
            WHERE week = ? AND ok = 1 AND pq = 0 AND unsure = 0
              AND (sector IS NULL OR sector = '') AND grade IN ({ph_g})
            ORDER BY CASE grade WHEN 'F' THEN 0 WHEN 'C' THEN 1 WHEN 'B' THEN 2 ELSE 3 END,
                     COALESCE(rank, 999999) ASC, domain
        """, (wk, *grades)).fetchall())
    conn.close()

    candidates = []
    seen_base = set()
    skip_tlds = (".gov", ".mil", ".edu", ".ac.uk", ".gob.", ".gouv.")
    for r in rows:
        dom = r["domain"].strip().lower()
        base = dom.removeprefix("www.")
        if base in seen_base or base in skip_domains or any(t in base for t in skip_tlds):
            continue
        seen_base.add(base)
        candidates.append(dict(r, base=base))

    print(f"Week {wk}: {len(candidates)} non-PQ paying-sector candidates (grades={grades})")
    found = []
    today = dt.date.today().isoformat()

    def probe(item):
        hit = fetch_security_txt(item["domain"])
        if not hit:
            return None
        email = osup.normalize(hit["contact_email"])
        if not email or email in skip_emails:
            return None
        region = "Arab world" if item["sector"] in ARAB_SECTORS else ("DACH" if "dach" in item["sector"] else "Global")
        lang = "ar" if region == "Arab world" else "en"
        return {
            "region": region,
            "organization": f"{item['base']} ({item['sector']} · grade {item['grade']})",
            "domain": item["base"],
            "country": item["sector"],
            "contact_email": email,
            "source_url": hit["source_url"],
            "handshake_host": item["domain"],
            "tls_version": item["tls"] or "TLSv1.3",
            "key_exchange": item["grp"] or "X25519",
            "kex_class": "classical",
            "lang": lang,
            "security_txt_expires": hit["expires"],
            "checked_at_vienna": today,
            "_grade": item["grade"],
            "_sector": item["sector"],
        }

    ex = cf.ThreadPoolExecutor(max_workers=a.workers)
    try:
        chunk_size = max(a.workers * 4, 80)
        for i in range(0, len(candidates), chunk_size):
            if len(found) >= a.max_targets:
                break
            batch = candidates[i:i + chunk_size]
            futs = [ex.submit(probe, item) for item in batch]
            for fut in cf.as_completed(futs):
                try:
                    res = fut.result()
                except Exception:
                    res = None
                if res:
                    found.append(res)
                    if len(found) >= a.max_targets:
                        for rem_f in futs:
                            rem_f.cancel()
                        break
    finally:
        ex.shutdown(wait=False, cancel_futures=True)

    # Sort F -> C -> B and deduplicate by contact_email (one row per security inbox)
    rank = {"F": 0, "C": 1, "B": 2}
    found.sort(key=lambda x: (rank.get(x["_grade"], 9), x["_sector"], x["domain"]))
    deduped, seen_emails = [], set()
    for row in found:
        if row["contact_email"] not in seen_emails:
            seen_emails.add(row["contact_email"])
            deduped.append(row)
    found = deduped

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    fields = ["region", "organization", "domain", "country", "contact_email", "source_url",
              "handshake_host", "tls_version", "key_exchange", "kex_class", "lang",
              "security_txt_expires", "checked_at_vienna"]
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in found:
            w.writerow({k: row[k] for k in fields})

    by_grade = {}
    for row in found:
        by_grade[row["_grade"]] = by_grade.get(row["_grade"], 0) + 1
    print(f"Wrote {len(found)} verified classical/non-PQ targets to {a.out} (by grade: {by_grade})")


if __name__ == "__main__":
    main()
