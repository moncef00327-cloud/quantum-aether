# يرسل بطاقة «الواقع مقابل المحاكاة» إلى المالك (كل اثنين، quantum_scorecard.timer).
import os
import sys

import crawler_log
import monitor
import sales_db
import scorecard
import weekly_banks
from mailer import Mailer


def main():
    db_path = os.path.join(os.environ.get("QS_DATA_DIR", "/var/lib/quantum_saas"), "quantum_saas.db")
    owner = os.environ.get("QS_OWNER_EMAIL", "")
    conn = sales_db.connect(db_path)
    card = scorecard.build(conn, owner, monitor.PLANS)
    text = scorecard.as_text(card)
    try:  # ملخص زيارات الزواحف (قياس أثر IndexNow و llms.txt)
        text += "\n\n" + crawler_log.as_text(crawler_log.summary(os.path.dirname(db_path)))
    except Exception as exc:
        text += f"\n\nCrawler summary unavailable: {exc}"
    try:  # weekly bank tracker + ready-to-post LinkedIn texts (the bank sectors are scanned ~03:45 UTC Monday)
        text += "\n\n" + weekly_banks.as_text(weekly_banks.build(conn))
    except Exception as exc:
        text += f"\n\nWeekly bank tracker unavailable: {exc}"
    print(text)
    mailer = Mailer(os.environ.get("RESEND_API_KEY", ""), os.environ.get("QS_MAIL_FROM", ""),
                    fallback_sender=os.environ.get("QS_MAIL_FROM_FALLBACK", ""),
                    site_url=os.environ.get("QS_PUBLIC_URL", ""))
    if owner and mailer.enabled and "--dry-run" not in sys.argv:
        verdict = scorecard.SCENARIOS[card["verdict"]]["label"] if card["verdict"] else "no data"
        mailer.send(owner, f"[Quantum Aether] weekly scorecard: {verdict} scenario", text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
