# monitor_job.py
# المهمة اليومية: يتحقق من حالة كل اشتراك في PayPal، ثم يفحص نطاقات المشتركين الفعّالين ويرسل التنبيهات.
# التشغيل: python monitor_job.py   (يشغله مؤقت systemd: deploy/quantum_monitor.timer)
import datetime as dt
import logging
import os
import sys

import requests

import analytics_db
import discovery
import free_alerts
import monitor
import monitor_db
import quantum_saas_app
import sales_db
from paypal_client import SUBSCRIPTION_LIVE_STATUSES, PayPalError

log = logging.getLogger("quantum_saas.monitor_job")


def sync_subscriptions(conn, paypal, mailer=None, owner="", base_url="https://ather-quantum.com"):
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
                if new_status in ("CANCELLED", "EXPIRED"):  # إلغاء نهائي: أكّد للعميل بلغته
                    subj, body = monitor.cancel_email(account, f"{base_url}/monitoring?lang={account.get('lang') or 'en'}")
                    mailer.send(account["email"], subj, body)
                monitor.notify_owner(mailer, owner, f"Subscription {new_status.lower()} in PayPal", account,
                                     f"PayPal status: {status}")


def handle_trials(conn, mailer, owner="", base_url="https://ather-quantum.com", now=None):
    """تذكير واحد قبل نهاية التجربة بثلاثة أيام، ثم إيقافها عند النهاية (النطاقات تبقى محفوظة)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    for account in monitor_db.trial_accounts(conn):
        login_url = f"{base_url}/monitoring?lang={account.get('lang') or 'en'}#login"
        left = monitor.trial_days_left(account, now)
        end = dt.datetime.strptime(account["trial_ends_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        if end <= now:
            monitor_db.set_status(conn, account["id"], "TRIAL_ENDED")
            log.info("account %s: trial ended", account["id"])
            if mailer is not None and mailer.enabled:
                mailer.send(account["email"], *monitor.trial_ended_email(account, login_url))
                monitor.notify_owner(mailer, owner, "Free trial ended", dict(account, status="TRIAL_ENDED"),
                                     f"Domains: {', '.join(d['domain'] for d in monitor_db.list_domains(conn, account['id']))}")
        elif left <= monitor.TRIAL_REMIND_DAYS and not account["trial_notice"]:
            if mailer is not None and mailer.enabled and mailer.send(account["email"], *monitor.trial_reminder_email(account, left, login_url)):
                monitor_db.mark_trial_notice(conn, account["id"])
    cutoff = (now - dt.timedelta(days=monitor.TRIAL_RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    purged = monitor_db.purge_ended_trials(conn, cutoff)
    if purged:
        log.info("deleted %d ended trials past retention", purged)


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
        base_url = cfg["PUBLIC_URL"] or "https://ather-quantum.com"
        sync_subscriptions(conn, app.extensions["paypal"], app.extensions["mailer"], cfg["OWNER_EMAIL"], base_url)
        handle_trials(conn, app.extensions["mailer"], cfg["OWNER_EMAIL"], base_url)
        accounts = conn.execute("SELECT * FROM monitor_accounts WHERE status IN ('ACTIVE', 'TRIAL')").fetchall()
        total_domains = total_alerts = 0
        for row in accounts:
            account = dict(row)
            total_domains += monitor.check_account(conn, account, scanner=app.extensions["scanner"])
            total_alerts += send_alerts(conn, account, app.extensions["mailer"], base_url)
        free_checked, free_sent = free_alerts.run(conn, app.extensions["scanner"], app.extensions["mailer"], base_url)
        discovery.prune(conn)
        log.info("free alerts: checked %d, emailed %d", free_checked, free_sent)
        analytics_db.prune(conn, (dt.date.today() - dt.timedelta(days=180)).isoformat())  # نحتفظ بستة أشهر
        log.info("checked %d accounts, %d domains, %d alerts", len(accounts), total_domains, total_alerts)
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)
    run(quantum_saas_app.create_app())
