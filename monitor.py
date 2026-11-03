# monitor.py
# منطق المراقبة الشهرية: الخطط، فحص نطاقات الحساب، اكتشاف التغيرات، ونصوص التنبيهات والرسائل.
import concurrent.futures as cf
import logging

import monitor_db
import quantum_vuln_scanner

log = logging.getLogger("quantum_saas.monitor")

PLANS = {
    "starter": {"price": "29.00", "domains": 10, "env": "PAYPAL_PLAN_STARTER", "name": "Starter"},
    "business": {"price": "99.00", "domains": 100, "env": "PAYPAL_PLAN_BUSINESS", "name": "Business"},
}

CERT_WARN_DAYS = (14, 3)  # ننبّه مرة عند عبور كل حد

ALERT_TEXT = {
    "GRADE_CHANGED": {
        "en": "{domain}: grade changed from {old} to {new}",
        "ar": "{domain}: تغيّرت الدرجة من {old} إلى {new}",
    },
    "PQ_LOST": {
        "en": "{domain}: post-quantum key exchange is no longer negotiated (now {group})",
        "ar": "{domain}: لم يعد الخادم يتفق على تبادل المفاتيح المقاوم للكم (الآن {group})",
    },
    "PQ_GAINED": {
        "en": "{domain}: post-quantum key exchange is now enabled ({group})",
        "ar": "{domain}: أصبح تبادل المفاتيح المقاوم للكم مفعّلاً ({group})",
    },
    "CERT_EXPIRING": {
        "en": "{domain}: certificate expires in {days} days",
        "ar": "{domain}: تنتهي الشهادة خلال {days} يوماً",
    },
    "UNREACHABLE": {
        "en": "{domain}: scan failed ({error})",
        "ar": "{domain}: فشل الفحص ({error})",
    },
    "RECOVERED": {
        "en": "{domain}: reachable again, grade {new}",
        "ar": "{domain}: عاد يعمل، الدرجة {new}",
    },
}


def alert_text(alert, lang):
    params = dict(alert["params"], domain=alert["domain"])
    return ALERT_TEXT[alert["kind"]][lang if lang in ("en", "ar") else "en"].format(**params)


def diff(previous, result):
    """يقارن آخر حالة محفوظة بنتيجة جديدة ويعيد قائمة (النوع، المعاملات)."""
    alerts = []
    kx, cert = result["key_exchange"], result["certificate"]
    group = kx.get("group") or "?"
    if previous.get("error") and previous.get("grade") is not None:
        alerts.append(("RECOVERED", {"new": result["grade"]}))
    if previous.get("grade") is None:
        return alerts  # أول فحص: لا شيء نقارن به
    if previous["grade"] != result["grade"]:
        alerts.append(("GRADE_CHANGED", {"old": previous["grade"], "new": result["grade"]}))
    if previous.get("pq") and not kx.get("pq"):
        alerts.append(("PQ_LOST", {"group": group}))
    elif previous.get("pq") == 0 and kx.get("pq"):
        alerts.append(("PQ_GAINED", {"group": group}))
    days, old_days = cert.get("days_left"), previous.get("days_left")
    if days is not None:
        for limit in CERT_WARN_DAYS:
            if days <= limit and (old_days is None or old_days > limit):
                alerts.append(("CERT_EXPIRING", {"days": days}))
                break
    return alerts


def record_outcome(conn, account_id, row, result=None, error=None):
    """يحفظ نتيجة فحص نطاق (أو خطأه) ويسجل التنبيهات الناتجة عن المقارنة بالحالة السابقة."""
    if result is None:
        message = (str(error) or type(error).__name__)[:200]
        if not row.get("error") and row.get("grade") is not None:
            monitor_db.add_alert(conn, account_id, row["domain"], "UNREACHABLE", {"error": message})
        monitor_db.save_check(conn, row["id"], error=message)
        return
    for kind, params in diff(row, result):
        monitor_db.add_alert(conn, account_id, row["domain"], kind, params)
    monitor_db.save_check(conn, row["id"], result=result)


def check_account(conn, account, scanner=quantum_vuln_scanner.scan, workers=8):
    """يفحص كل نطاقات الحساب بالتوازي، ثم يكتب النتائج في القاعدة من خيط واحد. يعيد عدد النطاقات."""
    rows = monitor_db.list_domains(conn, account["id"])

    def run(row):
        try:
            return row, scanner(row["domain"]), None
        except Exception as exc:  # فشل نطاق لا يوقف البقية
            return row, None, exc

    with cf.ThreadPoolExecutor(max(1, min(workers, len(rows) or 1))) as pool:
        outcomes = list(pool.map(run, rows))
    for row, result, exc in outcomes:
        record_outcome(conn, account["id"], row, result, exc)
    return len(rows)


def alert_email(account, alerts, dashboard_url):
    # dashboard_url هنا رابط طلب الدخول، لأن الرمز السري لا يُحفظ إلا كبصمة.
    lang = account.get("lang") or "en"
    lines = [f"- {alert_text(a, lang)}" for a in alerts]
    if lang == "ar":
        subject = f"الأثير الكمومي: {len(alerts)} تنبيه لنطاقاتك"
        text = "\n".join(["تغيّرات في نطاقاتك المراقبة:", "", *lines, "", "رابط لوحة التحكم في رسالة الترحيب، أو اطلبه من جديد هنا:", dashboard_url])
    else:
        subject = f"Quantum Aether: {len(alerts)} alert(s) for your domains"
        text = "\n".join(["Changes on your monitored domains:", "", *lines, "", "Your dashboard link is in your welcome email, or request it again here:", dashboard_url])
    return subject, text


def welcome_email(account, dashboard_url):
    plan = PLANS[account["plan"]]
    if account.get("lang") == "ar":
        return ("الأثير الكمومي: اشتراك المراقبة فعّال",
                f"تم تفعيل خطة {plan['name']} (حتى {plan['domains']} نطاقاً).\n\n"
                f"لوحة التحكم (احفظ هذا الرابط، فهو مفتاح حسابك):\n{dashboard_url}\n\n"
                "أضف نطاقاتك من اللوحة. نفحصها يومياً ونراسلك عند أي تغيّر.")
    return ("Quantum Aether: your monitoring subscription is active",
            f"Your {plan['name']} plan is active (up to {plan['domains']} domains).\n\n"
            f"Dashboard (keep this link private, it is the key to your account):\n{dashboard_url}\n\n"
            "Add your domains there. We scan them daily and email you when anything changes.")


def normalize(raw):
    return quantum_vuln_scanner.normalize_domain(raw)
