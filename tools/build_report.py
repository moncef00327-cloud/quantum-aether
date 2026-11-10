"""Freeze the monthly 'State of post-quantum TLS' report from the live tracker data.

Usage (as the service user, with the service env loaded):
    python tools/build_report.py 2026-11 2026-11-10
Writes data/reports/<id>.json. Published reports are never rebuilt silently: pass --force to overwrite.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import quantum_saas_app  # noqa: E402
import reports  # noqa: E402
import sales_db  # noqa: E402


def main(argv):
    report_id, published = argv[1], argv[2]
    if reports.load(report_id) and "--force" not in argv:
        sys.exit(f"report {report_id} already exists (use --force)")
    app = quantum_saas_app.create_app()
    conn = sales_db.connect(os.path.join(app.config["DATA_DIR"], "quantum_saas.db"))
    try:
        report = reports.build(conn, report_id, published)
    finally:
        conn.close()
    out = [a for a in argv[3:] if a != "--force"]  # optional output directory (default data/reports)
    if out:
        reports.REPORTS_DIR = out[0]
    reports.save(report)
    print(os.path.join(reports.REPORTS_DIR, report_id + ".json"))


if __name__ == "__main__":
    main(sys.argv)
