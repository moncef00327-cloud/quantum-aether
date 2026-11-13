# monitor.py
# منطق المراقبة الشهرية: الخطط، فحص نطاقات الحساب، اكتشاف التغيرات، ونصوص التنبيهات والرسائل.
import concurrent.futures as cf
import datetime as dt
import logging
import adoption

import monitor_db
import quantum_vuln_scanner

log = logging.getLogger("quantum_saas.monitor")

PLANS = {
    "starter": {"price": "29.00", "domains": 10, "env": "PAYPAL_PLAN_STARTER", "name": "Starter"},
    "business": {"price": "99.00", "domains": 100, "env": "PAYPAL_PLAN_BUSINESS", "name": "Business"},
}

TRIAL_DAYS = 14          # تجربة مجانية للشركات بلا دفع
TRIAL_DOMAINS = 10       # حد النطاقات أثناء التجربة مهما كانت الخطة المختارة لاحقاً
TRIAL_REMIND_DAYS = 3    # تذكير واحد قبل النهاية بهذه المدة
CHECK_RETENTION_DAYS = 400  # سجل الفحوص: أكثر من سنة كاملة لدورات التدقيق السنوية
TRIAL_RETENTION_DAYS = 90  # بعدها تُحذف بيانات التجربة المنتهية بلا اشتراك (سياسة الخصوصية)
LIVE_STATUSES = ("ACTIVE", "TRIAL")  # الحسابات التي نفحص نطاقاتها ويمكنها الإضافة والفحص اليدوي


def is_live(account):
    return account["status"] in LIVE_STATUSES


def domain_limit(account):
    return TRIAL_DOMAINS if account["status"] == "TRIAL" else PLANS[account["plan"]]["domains"]


def trial_days_left(account, now):
    """أيام التجربة المتبقية (تقريب للأعلى، لا تقل عن صفر)."""
    if not account.get("trial_ends_at"):
        return None
    end = dt.datetime.strptime(account["trial_ends_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    return max(0, -(-(end - now) // dt.timedelta(days=1)))


CERT_WARN_DAYS = (14, 3)  # ننبّه مرة عند عبور كل حد

ALERT_TEXT = {
    'OBSERVATION_UNDETERMINED': {
        'en': '{domain}: key-exchange measurement is inconclusive; support has not been confirmed or disproved',
        'ar': '{domain}: قياس تبادل المفاتيح غير حاسم؛ لم يُثبت الدعم أو نفيه',
        'de': '{domain}: Schlüsselaustausch unbestimmt; Unterstützung weder bestätigt noch widerlegt',
    },
    "GRADE_CHANGED": {
        "en": "{domain}: grade changed from {old} to {new}",
        "ar": "{domain}: تغيّرت الدرجة من {old} إلى {new}",
        "de": "{domain}: Note geändert von {old} zu {new}",
    },
    "PQ_LOST": {
        "en": "{domain}: SILENT DOWNGRADE — post-quantum key exchange is no longer negotiated after a server/CDN change (now {group})",
        "ar": "{domain}: تنبيه تراجع صامت — توقف الخادم أو الـ CDN عن التفاوض على التشفير المقاوم للكم وتراجع إلى ({group})",
        "de": "{domain}: STILLER RÜCKSCHRITT — Quantenresistenter Schlüsselaustausch wird nicht mehr ausgehandelt (jetzt {group})",
    },
    "PQ_GAINED": {
        "en": "{domain}: post-quantum key exchange is now enabled ({group})",
        "ar": "{domain}: أصبح تبادل المفاتيح المقاوم للكم مفعّلاً ({group})",
        "de": "{domain}: Quantenresistenter Schlüsselaustausch ist jetzt aktiv ({group})",
    },
    "CERT_EXPIRING": {
        "en": "{domain}: certificate expires in {days} days",
        "ar": "{domain}: تنتهي الشهادة خلال {days} يوماً",
        "de": "{domain}: Zertifikat läuft in {days} Tagen ab",
    },
    "UNREACHABLE": {
        "en": "{domain}: scan failed ({error})",
        "ar": "{domain}: فشل الفحص ({error})",
        "de": "{domain}: Prüfung fehlgeschlagen ({error})",
    },
    "ENDPOINTS_MIXED": {
        "en": "{domain}: servers disagree, {pq} of {total} addresses negotiate post-quantum key exchange (classical on {ips})",
        "ar": "{domain}: الخوادم غير متسقة، {pq} من {total} عناوين تتفاوض على التبادل المقاوم للكم (تقليدي على {ips})",
        "de": "{domain}: Server uneinheitlich, {pq} von {total} Adressen mit quantenresistentem Schlüsselaustausch (klassisch auf {ips})",
    },
    "NEW_ASSET": {
        "en": "{domain}: new asset found under {base} and added to monitoring (key exchange {group})",
        "ar": "{domain}: أصل جديد تحت {base} أُضيف للمراقبة (تبادل المفاتيح {group})",
        "de": "{domain}: neues Asset unter {base} gefunden und zur Überwachung hinzugefügt (Schlüsselaustausch {group})",
    },
    "ASSETS_OVER_LIMIT": {
        "en": "{domain}: {count} more live hosts found, but your plan limit of {limit} domains is reached. Upgrade or remove domains to monitor them",
        "ar": "{domain}: وُجد {count} خادماً حياً إضافياً، لكن حد خطتك ({limit} نطاقاً) مكتمل. رقِّ الخطة أو احذف نطاقات لمراقبتها",
        "de": "{domain}: {count} weitere aktive Hosts gefunden, aber Ihr Tariflimit von {limit} Domains ist erreicht. Upgraden oder Domains entfernen",
    },
    "ASSET_RETIRED": {
        "en": "{domain}: removed from monitoring: no answer on {days} consecutive checks and no longer found live under {base}",
        "ar": "{domain}: سُحب من المراقبة: لم يرد في {days} فحوص متتالية ولم يعد يظهر حياً تحت {base}",
        "de": "{domain}: aus der Überwachung entfernt: {days} Prüfungen in Folge keine Antwort und unter {base} nicht mehr aktiv gefunden",
    },
    "RECOVERED": {
        "en": "{domain}: reachable again, grade {new}",
        "ar": "{domain}: عاد يعمل، الدرجة {new}",
        "de": "{domain}: wieder erreichbar, Note {new}",
    },
}


def alert_text(alert, lang):
    params = dict(alert["params"], domain=alert["domain"])
    return ALERT_TEXT[alert["kind"]][lang if lang in ("en", "ar", "de") else "en"].format(**params)


def diff(previous, result):
    """يقارن آخر حالة محفوظة بنتيجة جديدة ويعيد قائمة (النوع، المعاملات)."""
    alerts = []
    kx, cert = result["key_exchange"], result["certificate"]
    group = kx.get("group") or "?"
    uncertain = adoption.is_unsure(kx, kx.get('version') or cert.get('negotiated_version'))
    old_result = previous.get('result') or {}
    old_kx = old_result.get('key_exchange') or {}
    old_tls = old_kx.get('version') or (old_result.get('certificate') or {}).get('negotiated_version')
    old_uncertain = (bool(old_result) and adoption.is_unsure(old_kx, old_tls)) or (
        previous.get('grade') is not None and previous.get('pq') is None)
    if previous.get("error") and previous.get("grade") is not None:
        alerts.append(("RECOVERED", {"new": result["grade"]}))
    if previous.get("grade") is None:
        return alerts  # أول فحص: لا شيء نقارن به
    if uncertain and not old_uncertain:
        alerts.append(('OBSERVATION_UNDETERMINED', {}))
    if not uncertain and not old_uncertain and previous["grade"] != result["grade"]:
        alerts.append(("GRADE_CHANGED", {"old": previous["grade"], "new": result["grade"]}))
    if not uncertain and not old_uncertain and previous.get("pq") and not kx.get("pq"):
        alerts.append(("PQ_LOST", {"group": group}))
    elif not uncertain and not old_uncertain and previous.get("pq") == 0 and kx.get("pq"):
        alerts.append(("PQ_GAINED", {"group": group}))
    mixed = (result.get("endpoint_summary") or {}).get("mixed")
    old_mixed = ((old_result.get("endpoint_summary") or {}).get("mixed"))
    if mixed and not old_mixed:
        s = result["endpoint_summary"]
        classical = [e["ip"] for e in result.get("endpoints", ()) if not e["undetermined"] and not e["pq"]]
        alerts.append(("ENDPOINTS_MIXED", {"pq": s["pq"], "total": s["total"], "ips": ", ".join(classical) or "?"}))
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
    elif lang == "de":
        subject = f"Quantum Aether: {len(alerts)} Hinweis(e) zu Ihren Domains"
        text = "\n".join(["Änderungen an Ihren überwachten Domains:", "", *lines, "", "Ihr Dashboard-Link steht in der Willkommens-E-Mail, oder fordern Sie ihn hier erneut an:", dashboard_url])
    else:
        subject = f"Quantum Aether: {len(alerts)} alert(s) for your domains"
        text = "\n".join(["Changes on your monitored domains:", "", *lines, "", "Your dashboard link is in your welcome email, or request it again here:", dashboard_url])
    return subject, text


def _lang(account):
    l = (account.get("lang") or "en")
    return l if l in ("en", "ar", "de") else "en"


def welcome_email(account, dashboard_url):
    """رسالة شكر وترحيب عند تفعيل الاشتراك، بلغة العميل. خطة الشركات (Business) بنبرة رسمية."""
    plan = PLANS[account["plan"]]
    name, domains = plan["name"], plan["domains"]
    business = account["plan"] == "business"
    lang = _lang(account)
    if business:
        bodies = {
            "ar": ("الأثير الكمومي: اشتراك مراقبة الشركات فعّال",
                   f"نشكر لكم اختيار الأثير الكمومي لحماية نطاقات مؤسستكم. تم تفعيل خطة {name} (حتى {domains} نطاقاً).\n\n"
                   f"لوحة التحكم (شاركوها مع فريق الأمن لديكم فقط؛ هذا الرابط هو مفتاح الحساب):\n{dashboard_url}\n\n"
                   "أضيفوا نطاقات مؤسستكم من اللوحة. نفحصها جميعاً يومياً ونخطر هذا العنوان فور أي تغيّر: "
                   "فقدان التبادل المقاوم للكم، أو انخفاض الدرجة، أو اقتراب انتهاء شهادة.\n\n"
                   "للاستفسارات المتعلقة بالفوترة أو التهيئة، يُرجى الرد على هذه الرسالة."),
            "de": ("Quantum Aether: Ihre Business-Überwachung ist aktiv",
                   f"Vielen Dank, dass Sie Quantum Aether für Ihr Unternehmen gewählt haben. Ihr Tarif {name} ist aktiv (bis zu {domains} Domains).\n\n"
                   f"Dashboard (nur mit Ihrem Sicherheitsteam teilen; dieser Link ist der Schlüssel zum Konto):\n{dashboard_url}\n\n"
                   "Fügen Sie dort die Domains Ihres Unternehmens hinzu. Wir prüfen sie täglich und benachrichtigen diese Adresse sofort "
                   "bei jeder Änderung: Wegfall des quantenresistenten Schlüsselaustauschs, schlechtere Note oder ablaufendes Zertifikat.\n\n"
                   "Bei Fragen zu Abrechnung oder Einrichtung antworten Sie bitte auf diese E-Mail."),
            "en": ("Quantum Aether: your Business monitoring is active",
                   f"Thank you for choosing Quantum Aether for your organization. Your {name} plan is active (up to {domains} domains).\n\n"
                   f"Dashboard (share it only with your security team; this link is the key to the account):\n{dashboard_url}\n\n"
                   "Add your organization's domains there. We scan all of them every day and notify this address the moment anything changes: "
                   "post-quantum key exchange lost, a lower grade, or a certificate nearing expiry.\n\n"
                   "For billing or onboarding questions, please reply to this email."),
        }
        return bodies[lang]
    bodies = {
        "ar": ("الأثير الكمومي: شكراً لك، اشتراك المراقبة فعّال",
               f"شكراً لاشتراكك في الأثير الكمومي. تم تفعيل خطة {name} (حتى {domains} نطاقاً).\n\n"
               f"لوحة التحكم (احفظ هذا الرابط، فهو مفتاح حسابك):\n{dashboard_url}\n\n"
               "أضف نطاقاتك من اللوحة. نفحصها يومياً ونراسلك فور أي تغيّر: فقدان التبادل المقاوم للكم، "
               "أو انخفاض الدرجة، أو اقتراب انتهاء شهادة.\n\n"
               "يمكنك الإلغاء في أي وقت من لوحة التحكم. لأي سؤال، ردّ على هذه الرسالة."),
        "de": ("Quantum Aether: Danke – Ihre Überwachung ist aktiv",
               f"Danke für Ihr Abonnement bei Quantum Aether. Ihr Tarif {name} ist aktiv (bis zu {domains} Domains).\n\n"
               f"Dashboard (bewahren Sie diesen Link privat auf, er ist der Schlüssel zu Ihrem Konto):\n{dashboard_url}\n\n"
               "Fügen Sie dort Ihre Domains hinzu. Wir prüfen sie täglich und mailen Ihnen sofort bei jeder Änderung: "
               "Wegfall des quantenresistenten Schlüsselaustauschs, schlechtere Note oder ablaufendes Zertifikat.\n\n"
               "Sie können jederzeit im Dashboard kündigen. Bei Fragen antworten Sie einfach auf diese E-Mail."),
        "en": ("Quantum Aether: thank you — your monitoring is active",
               f"Thank you for subscribing to Quantum Aether. Your {name} plan is active (up to {domains} domains).\n\n"
               f"Dashboard (keep this link private, it is the key to your account):\n{dashboard_url}\n\n"
               "Add your domains there. We scan them daily and email you the moment anything changes: "
               "post-quantum key exchange lost, a lower grade, or a certificate nearing expiry.\n\n"
               "You can cancel anytime from the dashboard. Any questions, just reply to this email."),
    }
    return bodies[lang]


def trial_welcome_email(lang, domain, dashboard_url):
    """رابط لوحة التجربة: يصل بالبريد فقط."""
    bodies = {
        "ar": ("الأثير الكمومي: بدأت تجربتكم المجانية لمراقبة {d}",
               "بدأت تجربتكم المجانية لمدة {days} يوماً لمراقبة {d}.\n\n"
               "لوحة التحكم (هذا الرابط هو مفتاح الحساب؛ شاركوه مع فريقكم التقني فقط):\n{url}\n\n"
               "أضيفوا حتى {n} نطاقات (الموقع، الـ API، البريد، بوابة العملاء...). نفحصها يومياً ونراسلكم فور أي تراجع: "
               "فقدان التبادل المقاوم للكم، أو انخفاض الدرجة، أو اقتراب انتهاء شهادة.\n\n"
               "لا دفع ولا بطاقة. عند نهاية التجربة تتوقف المراقبة ما لم تشتركوا من اللوحة نفسها، وتبقى نطاقاتكم محفوظة.\n"
               "لأي سؤال، ردّوا على هذه الرسالة."),
        "de": ("Quantum Aether: Ihr kostenloser Test für {d} hat begonnen",
               "Ihr kostenloser {days}-Tage-Test für die Überwachung von {d} hat begonnen.\n\n"
               "Dashboard (dieser Link ist der Schlüssel zum Konto; nur mit Ihrem Technikteam teilen):\n{url}\n\n"
               "Fügen Sie bis zu {n} Domains hinzu (Website, API, Mail, Kundenportal ...). Wir prüfen sie täglich und melden jeden Rückschritt sofort: "
               "Wegfall des quantenresistenten Schlüsselaustauschs, schlechtere Note oder ablaufendes Zertifikat.\n\n"
               "Keine Zahlung, keine Karte. Nach dem Test endet die Überwachung, sofern Sie nicht im Dashboard abonnieren; Ihre Domains bleiben gespeichert.\n"
               "Bei Fragen antworten Sie einfach auf diese E-Mail."),
        "en": ("Quantum Aether: your free trial for {d} has started",
               "Your free {days}-day monitoring trial for {d} has started.\n\n"
               "Dashboard (this link is the key to the account; share it only with your technical team):\n{url}\n\n"
               "Add up to {n} domains (website, API, mail, customer portal...). We scan them daily and email you the moment anything regresses: "
               "post-quantum key exchange lost, a lower grade, or a certificate nearing expiry.\n\n"
               "No payment, no card. When the trial ends, monitoring stops unless you subscribe from the same dashboard; your domains stay saved.\n"
               "Any questions, just reply to this email."),
    }
    subject, body = bodies[lang if lang in bodies else "en"]
    return subject.format(d=domain), body.format(d=domain, url=dashboard_url, days=TRIAL_DAYS, n=TRIAL_DOMAINS)


def trial_reminder_email(account, days_left, login_url):
    bodies = {
        "ar": ("الأثير الكمومي: تنتهي تجربتكم المجانية خلال {k} أيام",
               "تنتهي تجربة المراقبة المجانية خلال {k} أيام. بعدها نتوقف عن فحص نطاقاتكم يومياً ولن تصلكم تنبيهات التراجع.\n\n"
               "للاستمرار، افتحوا لوحة التحكم واختاروا خطة (Starter بـ 29$ أو Business بـ 99$ شهرياً). "
               "نطاقاتكم وسجلّ التنبيهات يبقيان كما هما.\n\n"
               "إن لم يكن رابط اللوحة عندكم، اطلبوه هنا:\n{url}"),
        "de": ("Quantum Aether: Ihr kostenloser Test endet in {k} Tagen",
               "Ihr kostenloser Überwachungstest endet in {k} Tagen. Danach prüfen wir Ihre Domains nicht mehr täglich und Sie erhalten keine Warnungen.\n\n"
               "Um fortzufahren, öffnen Sie Ihr Dashboard und wählen Sie einen Tarif (Starter 29 $ oder Business 99 $ pro Monat). "
               "Ihre Domains und der Warnverlauf bleiben erhalten.\n\n"
               "Dashboard-Link nicht zur Hand? Hier anfordern:\n{url}"),
        "en": ("Quantum Aether: your free trial ends in {k} days",
               "Your free monitoring trial ends in {k} days. After that we stop scanning your domains daily and you won't get regression alerts.\n\n"
               "To keep it running, open your dashboard and pick a plan (Starter $29 or Business $99 per month). "
               "Your domains and alert history stay as they are.\n\n"
               "Don't have the dashboard link at hand? Request it here:\n{url}"),
    }
    subject, body = bodies[_lang(account)]
    return subject.format(k=days_left), body.format(k=days_left, url=login_url)


def trial_ended_email(account, login_url):
    bodies = {
        "ar": ("الأثير الكمومي: انتهت تجربتكم المجانية وتوقفت المراقبة",
               "انتهت تجربة المراقبة المجانية، وتوقف الفحص اليومي لنطاقاتكم.\n\n"
               "نطاقاتكم وآخر النتائج محفوظة. لاستئناف المراقبة اشتركوا من لوحة التحكم (Starter بـ 29$ أو Business بـ 99$ شهرياً).\n\n"
               "اطلبوا رابط اللوحة من هنا:\n{url}\n\nشكراً لتجربتكم الأثير الكمومي."),
        "de": ("Quantum Aether: Ihr kostenloser Test ist beendet",
               "Ihr kostenloser Überwachungstest ist beendet; die tägliche Prüfung Ihrer Domains ist pausiert.\n\n"
               "Ihre Domains und die letzten Ergebnisse sind gespeichert. Abonnieren Sie im Dashboard, um fortzufahren (Starter 29 $ oder Business 99 $ pro Monat).\n\n"
               "Dashboard-Link anfordern:\n{url}\n\nDanke, dass Sie Quantum Aether getestet haben."),
        "en": ("Quantum Aether: your free trial has ended",
               "Your free monitoring trial has ended and daily scanning of your domains is paused.\n\n"
               "Your domains and latest results are saved. Subscribe from the dashboard to resume (Starter $29 or Business $99 per month).\n\n"
               "Request your dashboard link here:\n{url}\n\nThanks for trying Quantum Aether."),
    }
    subject, body = bodies[_lang(account)]
    return subject, body.format(url=login_url)


def cancel_email(account, monitoring_url):
    """رسالة تأكيد الإلغاء وشكر، بلغة العميل."""
    bodies = {
        "ar": ("الأثير الكمومي: تم إلغاء اشتراك المراقبة",
               "تم إلغاء اشتراكك ولن تُحصَّل منك أي رسوم بعد الآن. توقفت المراقبة اليومية لنطاقاتك.\n\n"
               "شكراً لتجربتك الأثير الكمومي. تستطيع العودة والاشتراك في أي وقت من:\n"
               f"{monitoring_url}\n\n"
               "إن كان الإلغاء عن طريق الخطأ، أو لديك ملاحظة تساعدنا على التحسّن، فقط ردّ على هذه الرسالة."),
        "de": ("Quantum Aether: Ihr Überwachungs-Abo wurde gekündigt",
               "Ihr Abonnement wurde gekündigt und es werden keine weiteren Gebühren berechnet. Die tägliche Überwachung wurde beendet.\n\n"
               "Danke, dass Sie Quantum Aether ausprobiert haben. Sie können jederzeit erneut abonnieren:\n"
               f"{monitoring_url}\n\n"
               "War die Kündigung ein Versehen oder haben Sie Feedback für uns? Antworten Sie einfach auf diese E-Mail."),
        "en": ("Quantum Aether: your monitoring subscription is cancelled",
               "Your subscription has been cancelled and you will not be charged again. Daily monitoring has stopped.\n\n"
               "Thank you for trying Quantum Aether. You can resubscribe anytime at:\n"
               f"{monitoring_url}\n\n"
               "If this was a mistake, or you have feedback that would help us improve, just reply to this email."),
    }
    return bodies[_lang(account)]


def report_receipt_email(lang, domain, amount, currency, report_url, order_id):
    """تأكيد/إيصال شراء التقرير على وسيط دائم (§ 7 FAGG)، بلغة المشتري."""
    lang = lang if lang in ("en", "ar", "de") else "en"
    bodies = {
        "ar": (f"الأثير الكمومي: تأكيد شراء تقرير {domain}",
               f"شكراً لشرائك. تم استلام الدفعة: {amount} {currency}.\n\n"
               f"تقريرك الكامل لجاهزية {domain} لما بعد الكم:\n{report_url}\n"
               "(احفظ هذا الرابط؛ هو وصولك إلى التقرير.)\n\n"
               f"رقم العملية: {order_id}\n\n"
               "تؤكّد هذه الرسالة إتمام العقد. لأي سؤال، ردّ عليها."),
        "de": (f"Quantum Aether: Kaufbestätigung – Bericht für {domain}",
               f"Vielen Dank für Ihren Kauf. Zahlung erhalten: {amount} {currency}.\n\n"
               f"Ihr vollständiger Post-Quantum-Bericht für {domain}:\n{report_url}\n"
               "(Bewahren Sie diesen Link auf; er ist Ihr Zugang zum Bericht.)\n\n"
               f"Bestellnummer: {order_id}\n\n"
               "Diese E-Mail bestätigt den Vertragsabschluss. Bei Fragen antworten Sie einfach."),
        "en": (f"Quantum Aether: payment confirmed — report for {domain}",
               f"Thank you for your purchase. Payment received: {amount} {currency}.\n\n"
               f"Your full post-quantum readiness report for {domain}:\n{report_url}\n"
               "(Keep this link; it is your access to the report.)\n\n"
               f"Order: {order_id}\n\n"
               "This email confirms your contract. Any questions, just reply."),
    }
    return bodies[lang]


def owner_email(event, account, detail=""):
    """رسالة لصاحب الموقع عند اشتراك جديد أو إلغاء أو توقف."""
    plan = PLANS[account["plan"]]
    trial = account.get("status") in ("TRIAL", "TRIAL_ENDED")
    subject = (f"[Quantum Aether] {event} — {account['email']}" if trial
               else f"[Quantum Aether] {event}: {plan['name']} ${plan['price']} — {account['email']}")
    text = "\n".join([
        f"Event: {event}",
        f"Customer: {account['email']}",
        f"Plan: {plan['name']} (${plan['price']}/month, up to {plan['domains']} domains)" if account.get("status") not in ("TRIAL", "TRIAL_ENDED")
        else f"Free trial (ends {account.get('trial_ends_at') or '-'}, up to {TRIAL_DOMAINS} domains)",
        f"Account: {account['id']}",
        f"PayPal subscription: {account.get('subscription_id') or '-'}",
        *( [f"Detail: {detail}"] if detail else [] ),
    ])
    return subject, text


def notify_owner(mailer, owner, event, account, detail=""):
    if owner:
        subject, text = owner_email(event, account, detail)
        mailer.send(owner, subject, text)


def normalize(raw):
    return quantum_vuln_scanner.normalize_domain(raw)
