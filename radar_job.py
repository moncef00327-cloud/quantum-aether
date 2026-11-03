# radar_job.py — يشغّل رادار الاهتمام يومياً (مؤقت systemd: deploy/quantum_radar.timer).
# التشغيل اليدوي: python radar_job.py [عدد الأيام للخلف، افتراضياً 3]
import datetime as dt
import logging
import os
import sys

import quantum_saas_app
import radar
import sales_db

log = logging.getLogger("quantum_saas.radar_job")


def run(app, days=3):
    conn = sales_db.connect(os.path.join(app.config["DATA_DIR"], "quantum_saas.db"))
    try:
        radar.init(conn)
        since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
        outcome = radar.run(conn, app.extensions["mailer"], app.config["OWNER_EMAIL"], since)
        log.info("radar: %d fetched, %d new, digest sent=%s, %d source errors",
                 outcome["found"], outcome["new"], outcome["sent"], len(outcome["errors"]))
        for err in outcome["errors"]:
            log.warning("radar source error: %s", err)
        return outcome
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    run(quantum_saas_app.create_app(), days=int(sys.argv[1]) if len(sys.argv) > 1 else 3)
