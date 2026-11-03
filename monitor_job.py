# monitor_job.py
# المهمة اليومية: يتحقق من حالة كل اشتراك في PayPal، ثم يفحص نطاقات المشتركين الفعّالين ويرسل التنبيهات.
# التشغيل: python monitor_job.py   (يشغله مؤقت systemd: deploy/quantum_monitor.timer)
import logging
import os
import sys

import requests

import monitor
import monitor_db
import quantum_saas_app
import sales_db
from paypal_client import SUBSCRIPTION_LIVE_STATUSES, PayPalError

log = logging.getLogger("quantum_saas.monitor_job")


def sync_subscriptions(conn, paypal, mailer=None, owner=""):
    """يوقف الحسابات التي ألغيت أو عُلّقت في PayPal (مثلاً من حساب المشترك أو لفشل الدفع)."""
    if paypal is None:
        return
    for account in monitor_db.accounts_with_subscription(conn):
        try:
            status = paypal.get_subscription(account["subscription_id"]).get("status") or "UNKNOWN"
        except (PayPalError, requests.RequestException) as exc:
            log.warning("could not check subscription of %s: %s", account["id"], exc)
            continue  # لا نوقف أحداً بسبب عطل مؤقت في PayPal
        if status not in SUBSCRIPTION_LIVE_STATUSES:
            log.info("account %s: PayPal status %s, deactivating", account["id"], status)
            new_status = status if status in ("CANCELLED", "SUSPENDED", "EXPIRED") else "SUSPENDED"
            monitor_db.set_status(conn, account["id"], new_status)
            if mailer is not None:
                monitor.notify_owner(mailer, owner, f"Subscription {new_status.lower()} in PayPal", account,
                                     f"PayPal status: {status}")


def send_alerts(conn, account, mailer, base_url):
    alerts = monitor_db.unsent_alerts(conn, account["id"])
    if not alerts or not mailer.enabled:
        return 0
    # الرابط في البريد يحتاج رمزاً صالحاً؛ الرمز الأصلي لا نعرفه (نحفظ بصمته فقط)، فلا نضعه.
    login_url = f"{base_url}/monitoring?lang={account['lang']}#login"
    subject, text = monitor.alert_email(account, alerts, login_url)
    if mailer.send(account["email"], subject, text):
        monitor_db.mark_alerts_sent(conn, [a["id"] for a in alerts])
    return len(alerts)


def run(app):
    cfg = app.config
    conn = sales_db.connect(os.path.join(cfg["DATA_DIR"], "quantum_saas.db"))
    try:
        sync_subscriptions(conn, app.extensions["paypal"], app.extensions["mailer"], cfg["OWNER_EMAIL"])
        accounts = conn.execute("SELECT * FROM monitor_accounts WHERE status = 'ACTIVE'").fetchall()
        base_url = cfg["PUBLIC_URL"] or "https://ather-quatum.cloud"
        total_domains = total_alerts = 0
        for row in accounts:
            account = dict(row)
            total_domains += monitor.check_account(conn, account, scanner=app.extensions["scanner"])
            total_alerts += send_alerts(conn, account, app.extensions["mailer"], base_url)
        log.info("checked %d accounts, %d domains, %d alerts", len(accounts), total_domains, total_alerts)
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    run(quantum_saas_app.create_app())
