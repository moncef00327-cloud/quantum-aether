# free_alerts.py
# «نبّهني مجاناً»: تنبيه بريدي لنطاق واحد عند تغيّر وضعه (فقدان/كسب تبادل المفاتيح ما بعد الكمومي، تغيّر الدرجة،
# اقتراب انتهاء الشهادة). فحص أسبوعي. تأكيد مزدوج للبريد (DSGVO): لا رسائل قبل الضغط على رابط التأكيد.
# كل رسالة فيها رابط إلغاء بنقرة واحدة. الإلغاء يحذف البريد فوراً. الطلبات غير المؤكدة تُحذف بعد 7 أيام.
import datetime as dt
import hashlib
import secrets

import monitor
import adoption

FREE_DOMAINS_PER_EMAIL = 1  # تأكيد نطاق جديد يستبدل القديم
REQUESTS_PER_CLIENT_PER_DAY = 5
CONFIRMATIONS_PER_EMAIL_PER_DAY = 3
CHECK_EVERY_DAYS = 7
PENDING_TTL_DAYS = 7

SCHEMA = """
CREATE TABLE IF NOT EXISTS free_alerts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL,
    domain        TEXT NOT NULL,
    lang          TEXT NOT NULL DEFAULT 'en',
    token_hash    TEXT NOT NULL UNIQUE,
    status        TEXT NOT NULL DEFAULT 'PENDING',   -- PENDING / ACTIVE
    client_hash   TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    confirmed_at  TEXT,
    consent_at    TEXT NOT NULL,
    last_checked  TEXT,
    last_grade    TEXT,
    last_pq       INTEGER,
    last_days_left INTEGER,
    last_error    TEXT
);
CREATE INDEX IF NOT EXISTS free_alerts_email ON free_alerts (email, status);
"""


def init(conn):
    conn.executescript(SCHEMA)


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def subscribe(conn, email, domain, lang, client_hash):
    """يعيد (token, None) أو (None, سبب الرفض). البريد والنطاق مُتحقق منهما مسبقاً."""
    email = email.strip().lower()
    day_ago = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent = conn.execute("SELECT COUNT(*) FROM free_alerts WHERE client_hash = ? AND created_at >= ?",
                          (client_hash, day_ago)).fetchone()[0]
    to_email = conn.execute("SELECT COUNT(*) FROM free_alerts WHERE email = ? AND status = 'PENDING' AND created_at >= ?",
                            (email, day_ago)).fetchone()[0]
    # حدّان: لكل اتصال، ولكل بريد (حتى لا يُستعمل النموذج لإغراق بريد شخص آخر برسائل التأكيد)
    if recent >= REQUESTS_PER_CLIENT_PER_DAY or to_email >= CONFIRMATIONS_PER_EMAIL_PER_DAY:
        return None, "rate_limited"
    active = conn.execute("SELECT domain FROM free_alerts WHERE email = ? AND status = 'ACTIVE'", (email,)).fetchall()
    if any(d == domain for (d,) in active):
        return None, "already_active"
    token = secrets.token_urlsafe(24)
    with conn:
        conn.execute("INSERT INTO free_alerts (email, domain, lang, token_hash, client_hash, consent_at) VALUES (?, ?, ?, ?, ?, ?)",
                     (email, domain, lang, _hash(token), client_hash, _now()))
    return token, None


def get(conn, token):
    row = conn.execute("SELECT * FROM free_alerts WHERE token_hash = ?", (_hash(token),)).fetchone()
    return dict(row) if row else None


def confirm(conn, token, latest=None):
    """يفعّل التنبيه. latest = آخر نتيجة معروفة للنطاق (لتكون أساس المقارنة الأولى)، أو None."""
    alert = get(conn, token)
    if not alert:
        return None
    if alert["status"] != "ACTIVE":
        with conn:
            # التنبيه المجاني لنطاق واحد: تأكيد نطاق جديد يحلّ محل القديم (لا رفض مزعج)
            conn.execute("DELETE FROM free_alerts WHERE email = ? AND status = 'ACTIVE' AND id <> ?", (alert["email"], alert["id"]))
            conn.execute("DELETE FROM free_alerts WHERE email = ? AND status = 'PENDING' AND id <> ?", (alert["email"], alert["id"]))
            conn.execute("UPDATE free_alerts SET status = 'ACTIVE', confirmed_at = ? WHERE id = ?", (_now(), alert["id"]))
            if latest:
                _store(conn, alert["id"], latest)
    return get(conn, token)


def stop(conn, token):
    """إلغاء بنقرة: نحذف الصف كله (لا نحتفظ بالبريد)."""
    alert = get(conn, token)
    if alert:
        with conn:
            conn.execute("DELETE FROM free_alerts WHERE id = ?", (alert["id"],))
    return alert


def _store(conn, alert_id, result=None, error=None):
    if result is not None:
        kx = result['key_exchange']
        pq = None if adoption.is_unsure(kx, kx.get('version') or result['certificate'].get('negotiated_version')) else int(bool(kx.get('pq')))
        conn.execute("UPDATE free_alerts SET last_checked = ?, last_grade = ?, last_pq = ?, last_days_left = ?, last_error = NULL "
                     "WHERE id = ?", (_now(), result["grade"], pq,
                                      result["certificate"].get("days_left"), alert_id))
    else:
        conn.execute("UPDATE free_alerts SET last_checked = ?, last_error = ? WHERE id = ?", (_now(), str(error)[:200], alert_id))


def due(conn, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    cutoff = (now - dt.timedelta(days=CHECK_EVERY_DAYS) + dt.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cur = conn.execute("SELECT * FROM free_alerts WHERE status = 'ACTIVE' AND (last_checked IS NULL OR last_checked < ?)", (cutoff,))
    return [dict(r) for r in cur]


def prune_pending(conn, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    cutoff = (now - dt.timedelta(days=PENDING_TTL_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with conn:
        return conn.execute("DELETE FROM free_alerts WHERE status = 'PENDING' AND created_at < ?", (cutoff,)).rowcount


def check(conn, alert, scanner):
    """يفحص نطاق تنبيه واحد ويعيد قائمة التغييرات [(النوع، المعاملات)]. فشل الفحص لا يُنبّه (المجاني لا يراقب التوقف)."""
    previous = {"grade": alert["last_grade"], "pq": alert["last_pq"], "days_left": alert["last_days_left"]}
    try:
        result = scanner(alert["domain"])
    except Exception as exc:  # noqa: BLE001 — أي فشل يُسجَّل فقط
        with conn:
            _store(conn, alert["id"], error=exc)
        return []
    changes = monitor.diff(previous, result)
    with conn:
        _store(conn, alert["id"], result)
    return [c for c in changes if c[0] != "RECOVERED"]


# ---------------------------------------------------------------- الرسائل
_CONFIRM = {
    "en": ("Confirm your free alert for {domain}",
           "Hello,\n\nplease confirm that you want an email when the post-quantum TLS status of {domain} changes "
           "(we check it once a week):\n\n{confirm_url}\n\n"
           "Your dynamic PQC readiness badge (stays green while your alert or monitoring is active):\n"
           "[![Post-quantum TLS grade by Quantum Aether]({base}/badge/{domain}.svg)]({base}/verify/{domain})\n\n"
           "If you did not ask for this, ignore this email; "
           "nothing will be sent and the request is deleted after 7 days.\n\nQuantum Aether · {base}"),
    "ar": ("أكّد تنبيهك المجاني لـ {domain}",
           "مرحباً،\n\nأكّد من فضلك أنك تريد رسالة حين يتغيّر وضع TLS ما بعد الكمومي لـ {domain} "
           "(نفحصه مرة كل أسبوع):\n\n{confirm_url}\n\n"
           "شارتك الديناميكية الجاهزة لملف README أو موقعك (تبقى خضراء ونشطة طالما التنبيه أو الاشتراك مفعّل):\n"
           "[![Post-quantum TLS grade by Quantum Aether]({base}/badge/{domain}.svg)]({base}/verify/{domain})\n\n"
           "إن لم تطلب هذا فتجاهل الرسالة؛ لن نرسل شيئاً ويُحذف الطلب بعد 7 أيام.\n\n"
           "الأثير الكمومي · {base}"),
    "de": ("Bestätigen Sie Ihre kostenlose Benachrichtigung für {domain}",
           "Guten Tag,\n\nbitte bestätigen Sie, dass Sie eine E-Mail erhalten möchten, wenn sich der Post-Quanten-TLS-Status von "
           "{domain} ändert (wir prüfen einmal pro Woche):\n\n{confirm_url}\n\n"
           "Ihr dynamisches Post-Quanten-TLS-Badge für README oder Website:\n"
           "[![Post-quantum TLS grade by Quantum Aether]({base}/badge/{domain}.svg)]({base}/verify/{domain})\n\n"
           "Falls Sie das nicht angefordert haben, ignorieren "
           "Sie diese E-Mail; es wird nichts gesendet und die Anfrage nach 7 Tagen gelöscht.\n\nQuantum Aether · {base}"),
}

_ALERT = {
    "en": ("{domain}: post-quantum TLS status changed",
           "Hello,\n\nour weekly check of {domain} found a change:\n\n{changes}\n\nCurrent result: {site_url}\n"
           "Fix steps for nginx, Apache, Caddy and Cloudflare: {guides_url}\n\n"
           "Need this for more domains, every day, with certificate-expiry warnings? Monitoring starts at $29/month: {monitoring_url}\n\n"
           "Stop these emails (one click, deletes your address): {stop_url}"),
    "ar": ("{domain}: تغيّر وضع TLS ما بعد الكمومي",
           "مرحباً،\n\nوجد فحصنا الأسبوعي لـ {domain} تغييراً:\n\n{changes}\n\nالنتيجة الحالية: {site_url}\n"
           "خطوات الإصلاح لـ nginx وApache وCaddy وCloudflare: {guides_url}\n\n"
           "تحتاج هذا لنطاقات أكثر، يومياً، مع تحذير قبل انتهاء الشهادة؟ المراقبة من 29$ شهرياً: {monitoring_url}\n\n"
           "أوقف هذه الرسائل (نقرة واحدة، يحذف بريدك): {stop_url}"),
    "de": ("{domain}: Post-Quanten-TLS-Status geändert",
           "Guten Tag,\n\nunsere wöchentliche Prüfung von {domain} hat eine Änderung festgestellt:\n\n{changes}\n\n"
           "Aktuelles Ergebnis: {site_url}\nAnleitungen für nginx, Apache, Caddy und Cloudflare: {guides_url}\n\n"
           "Mehr Domains, täglich, mit Warnung vor Zertifikatsablauf? Überwachung ab 29 $/Monat: {monitoring_url}\n\n"
           "Diese E-Mails abbestellen (ein Klick, löscht Ihre Adresse): {stop_url}"),
}


def _lang(lang):
    return lang if lang in ("en", "ar", "de") else "en"


def confirm_email(lang, domain, confirm_url, base):
    subject, body = _CONFIRM[_lang(lang)]
    return subject.format(domain=domain), body.format(domain=domain, confirm_url=confirm_url, base=base)


def alert_email(alert, changes, base, stop_url):
    lang = _lang(alert["lang"])
    subject, body = _ALERT[lang]
    lines = "\n".join("- " + monitor.alert_text({"kind": kind, "params": params, "domain": alert["domain"]}, lang)
                      for kind, params in changes)
    q = f"?lang={lang}"
    return subject.format(domain=alert["domain"]), body.format(
        domain=alert["domain"], changes=lines, site_url=f"{base}/site/{alert['domain']}{q}",
        guides_url=f"{base}/guides{q if lang != 'de' else '?lang=en'}", monitoring_url=f"{base}/monitoring{q}", stop_url=stop_url)


def run(conn, scanner, mailer, base):
    """للمهمة اليومية: يحذف الطلبات غير المؤكدة القديمة ويفحص ما حان موعده. يعيد (فُحص، أُرسل)."""
    prune_pending(conn)
    checked = sent = 0
    for alert in due(conn):
        changes = check(conn, alert, scanner)
        checked += 1
        if changes:
            # رمز الإلغاء مخزّن مجزّأً فقط: نصدر رمزاً جديداً لكل رسالة
            token = secrets.token_urlsafe(24)
            with conn:
                conn.execute("UPDATE free_alerts SET token_hash = ? WHERE id = ?", (_hash(token), alert["id"]))
            subject, text = alert_email(alert, changes, base, f"{base}/alerts/stop/{token}")
            if mailer.send(alert["email"], subject, text):
                sent += 1
    return checked, sent
