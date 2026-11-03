# adoption_job.py
# المهمة الأسبوعية لصفحة /adoption: تعيد فحص الأكبر 1000 وقوائم المراقبة وتحفظ النتائج.
# التشغيل: python adoption_job.py   (يشغله مؤقت systemd: deploy/quantum_adoption.timer)
# الفحص نفسه كفحص الزائر: اتصالان بالمنفذ 443 لكل نطاق عام، بلا أي محاولة اختراق.
import datetime as dt
import logging
import os
import sys

import adoption
import quantum_saas_app
import sales_db

log = logging.getLogger("quantum_saas.adoption_job")


def run(app, day=None, workers=16):
    conn = sales_db.connect(os.path.join(app.config["DATA_DIR"], "quantum_saas.db"))
    try:
        seeded = adoption.seed_from_study(conn)
        if seeded:
            log.info("seeded %d rows from the published study", seeded)
        targets = adoption.load_targets()
        outcome = adoption.run_week(conn, app.extensions["scanner"], targets, day=day or dt.date.today(),
                                    workers=workers)
        log.info("adoption week %s: %d targets, %d answered", outcome["week"], outcome["targets"], outcome["answered"])
        return outcome
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    run(quantum_saas_app.create_app())
