"""Freeze the Arab banks report: weekly-tracker rows from the DB + subdomain discovery results (JSON files).

    python tools/build_bank_report.py arab-banks-2026-11 2026-11-12 results1.json results2.json [--db PATH]

Discovery JSON files map base domain -> discovery.run_discovery() output (as written by an outreach run).
Host names are dropped; only counts are stored in data/bank_reports/<id>.json.
"""
import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bank_report  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("report_id")
    ap.add_argument("measured_on")
    ap.add_argument("discoveries", nargs="+")
    ap.add_argument("--db", default="/var/lib/quantum_saas/quantum_saas.db")
    ap.add_argument("--week", default=None)
    a = ap.parse_args(argv)
    conn = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    week = a.week or conn.execute("SELECT MAX(week) FROM adoption_results WHERE sector = 'banks-mena'").fetchone()[0]
    weekly = {r["domain"]: dict(r) for r in conn.execute(
        "SELECT * FROM adoption_results WHERE week = ? AND sector = 'banks-mena'", (week,))}
    disc = {}
    for path in a.discoveries:
        with open(path, encoding="utf-8") as f:
            disc.update(json.load(f))
    report = bank_report.build(weekly, disc, a.measured_on, a.report_id)
    report["week"] = week
    os.makedirs(bank_report.DIR, exist_ok=True)
    out = os.path.join(bank_report.DIR, a.report_id + ".json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    missing = [r["domain"] for r in report["rows"] if r["subs"] is None]
    print(out, "rows", len(report["rows"]), "without subdomain data:", missing)


if __name__ == "__main__":
    main()
