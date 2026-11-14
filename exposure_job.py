# exposure_job.py — البصمة الأسبوعية لسجل التعرّض الكمّي.
# التشغيل: python exposure_job.py anchor   (أسبوعياً: يبصم كل أسبوع منتهٍ لم يُبصم بعد ويرسله إلى OpenTimestamps)
#          python exposure_job.py upgrade  (يومياً: يحدّث الإثباتات المعلّقة إلى إثبات كتلة بيتكوين)
# مؤقتا systemd: quantum_exposure_anchor.timer و quantum_exposure_upgrade.timer. لا يفحص أي نطاق.
import logging
import os
import sys

import data_access
import exposure
import sales_db

log = logging.getLogger("quantum_saas.exposure_job")


def data_dir():
    return os.environ.get("QS_DATA_DIR") or "/var/lib/quantum_saas"


def run(mode="anchor", directory=None):
    directory = directory or data_dir()
    conn = sales_db.connect(os.path.join(directory, "quantum_saas.db"))
    try:
        done = []
        if mode == "anchor":
            for week in exposure.settled_weeks(conn):
                if exposure.load_anchor(directory, week):
                    continue
                rec = exposure.anchor_week(conn, directory, week)
                log.info("anchored %s: %d rows, sha256 %s, status %s", week, rec["rows"], rec["manifest_sha256"], rec["status"])
                done.append(week)
        changed = exposure.upgrade_anchors(directory)
        if mode == "upgrade":
            try:
                log.info("bot ranges: %s", data_access.refresh_ranges(directory))
                retired = data_access.recheck_canaries(conn)
                active = data_access.generate_canaries(conn)
                log.info("canaries: %d active, retired now: %s", active, retired)
            except Exception:
                log.exception("bot range / canary maintenance failed")
        for week in changed:
            log.info("anchor %s upgraded", week)
        return {"anchored": done, "upgraded": changed}
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    print(run(sys.argv[1] if len(sys.argv) > 1 else "anchor"))
