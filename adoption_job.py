# adoption_job.py
# مهمة صفحة /adoption. أسبوعياً: أكبر 10 آلاف نطاق وقوائم المراقبة. شهرياً: أكبر 100 ألف (لجدول المزوّدين).
# التشغيل: python adoption_job.py [weekly|monthly]   (مؤقتا systemd: quantum_adoption.timer و quantum_adoption_monthly.timer)
# الفحص كفحص الزائر: اتصالان بالمنفذ 443 لكل نطاق عام، بلا محتوى ولا أي محاولة اختراق.
import datetime as dt
import logging
import os
import sys

import adoption
import asn
import quantum_saas_app
import sales_db

log = logging.getLogger("quantum_saas.adoption_job")


def asn_lookup_for(app):
    """قاعدة IP→ASN في مجلد البيانات؛ تُنزَّل أو تُحدَّث عند الحاجة. فشلها لا يوقف الفحص."""
    path = os.path.join(app.config["DATA_DIR"], "ip2asn-v4.tsv.gz")
    try:
        asn.ensure_database(path)
        return asn.AsnLookup(path).lookup
    except Exception as exc:
        log.warning("ASN database unavailable, providers will be skipped this run: %s", exc)
        return None


def run(app, mode="weekly", day=None, workers=None, asn_lookup="auto"):
    conn = sales_db.connect(os.path.join(app.config["DATA_DIR"], "quantum_saas.db"))
    try:
        lookup = asn_lookup_for(app) if asn_lookup == "auto" else asn_lookup
        if mode == "monthly":
            targets = adoption.load_targets(limit=adoption.MONTHLY_TOP, watchlists={})
            outcome = adoption.run_month(conn, app.extensions["scanner"], targets, day=day or dt.date.today(),
                                         workers=workers or 32, asn_lookup=lookup)
            log.info("adoption month %s: %d targets, %d answered", outcome["month"], outcome["targets"], outcome["answered"])
        else:
            seeded = adoption.seed_from_study(conn)
            if seeded:
                log.info("seeded %d rows from the published study", seeded)
            targets = adoption.load_targets(limit=adoption.WEEKLY_TOP)
            outcome = adoption.run_week(conn, app.extensions["scanner"], targets, day=day or dt.date.today(),
                                        workers=workers or 24, asn_lookup=lookup)
            log.info("adoption week %s: %d targets, %d answered", outcome["week"], outcome["targets"], outcome["answered"])
        adoption.prune(conn)
        return outcome
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    run(quantum_saas_app.create_app(), mode=sys.argv[1] if len(sys.argv) > 1 else "weekly")
