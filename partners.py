"""Partner (affiliate) programme, 2026-11-21.

Terms (owner decision): 30% of monitoring payments for 12 months from the customer's start, 20% of one-time reports,
packs and audits; paid monthly (PayPal or USDC) after a 30-day refund period; minimum payout USD 50.

Attribution: a partner link ?ref=CODE automatically sets a first-party cookie qa_ref=CODE for 60 days on the first
click (owner decision 2026-11-25; no consent bar) and increments an anonymous per-code daily click counter. The
/partners/consent endpoint is kept for backward compatibility but is no longer required to set the cookie. Conversions
created while the cookie is present (report order, pack, audit, monitoring trial/subscription) are recorded in
`referrals` by the DB helpers via attribute(). Last partner link the visitor arrived through wins. Self-referrals and
test orders earn nothing.
"""
import datetime as dt
import hashlib
import hmac
import re
import secrets
import sqlite3

from flask import abort, current_app, g, has_request_context, jsonify, make_response, redirect, render_template, request, url_for

COOKIE = "qa_ref"
COOKIE_DAYS = 60
CODE_RE = re.compile(r"^[A-Z0-9]{3,20}$")
EMAIL_RE = re.compile(r"^[^@\s<>\"']{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$")
WALLET_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
SUB_RATE, ONE_TIME_RATE, SUB_MONTHS, MIN_PAYOUT, HOLD_DAYS = 0.30, 0.20, 12, 50, 30
PLAN_PRICE = {"starter": 29.0, "business": 99.0}

SCHEMA = """
CREATE TABLE IF NOT EXISTS partners (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    code          TEXT UNIQUE,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL,
    channel       TEXT NOT NULL,
    website       TEXT,
    payout        TEXT NOT NULL,
    lang          TEXT NOT NULL DEFAULT 'en',
    status        TEXT NOT NULL DEFAULT 'PENDING',   -- PENDING / ACTIVE / REJECTED / ENDED
    client_hash   TEXT,
    consent_at    TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    approved_at   TEXT
);
CREATE TABLE IF NOT EXISTS referrals (
    kind        TEXT NOT NULL,          -- report / pack / audit / monitor
    ref_id      TEXT NOT NULL,          -- orders.order_id / packs.id / audit_orders.id / monitor_accounts.id
    code        TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    PRIMARY KEY (kind, ref_id)
);
CREATE TABLE IF NOT EXISTS partner_clicks (
    code  TEXT NOT NULL,
    day   TEXT NOT NULL,
    n     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (code, day)
);
CREATE TABLE IF NOT EXISTS pilot_leads (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL,
    company       TEXT,
    client_domain TEXT,
    hostnames     INTEGER,
    white_label   TEXT,            -- 'yes' / 'no' / NULL
    note          TEXT,
    lang          TEXT NOT NULL DEFAULT 'en',
    status        TEXT NOT NULL DEFAULT 'NEW',   -- NEW / CONTACTED / WON / LOST
    client_hash   TEXT,
    consent_at    TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
"""

T = {
"en": {
  "title": "Partner programme: earn 30% recommending post-quantum TLS monitoring",
  "meta": "Marketers, security consultants and agencies earn 30% of monitoring payments for 12 months and 20% of reports and audits for customers they refer to Quantum Aether.",
  "lead": "Recommend Quantum Aether to companies that need post-quantum TLS evidence (banks' vendors, fintech, SaaS, hosting customers) and earn a share of every payment they make.",
  "terms_title": "Terms in short",
  "terms": [
    "30% of every monitoring payment (Starter 29 €/month, Business 99 €/month) for the first 12 months of each customer you refer.",
    "20% of one-time purchases: full report ($49), agency pack, and the small-company audit (€490).",
    "Attribution: your link ?ref=YOURCODE. Visiting your link sets a first-party attribution cookie for 60 days automatically (last partner link wins).",
    "Payout monthly by PayPal or USDC, for payments older than 30 days (refund period), from USD 50. Refunded or charged-back payments are deducted.",
    "No spam, no cold e-mail without the recipient's consent, no ads on our brand name, no misleading security claims (we sell an external observation, not a certification). Self-referrals earn nothing.",
    "Either side can end the partnership at any time; earned commission for payments already made is still paid. Austrian law applies.",
  ],
  "who_title": "Who it is for",
  "who": ["Security and compliance consultants", "Web and hosting agencies, MSPs", "Tech and security content creators, newsletter writers", "Anyone with a network in fintech, SaaS or banking IT"],
  "form_title": "Apply",
  "f_name": "Name", "f_email": "E-mail", "f_channel": "How will you promote us? (audience, channels, size)",
  "f_website": "Website or profile (optional)", "f_payout": "Payout method", "f_payout_opts": {"paypal": "PayPal", "usdc": "USDC (Base or Arbitrum)"},
  "f_consent": "I accept the partner terms above and agree that my data is stored to run the partnership.",
  "f_submit": "Send application", "sent": "Thank you. We review applications within 3 working days and e-mail you your partner link.",
  "err": {"invalid": "Please fill in name, a valid e-mail, how you will promote us, and accept the terms.", "rate_limited": "Too many applications from your connection today. Please try again tomorrow."},
  "bar": "You arrived via a link from our partner {code}. May we store a cookie for 60 days so they are credited if you become a customer?",
  "bar_yes": "Yes, credit them", "bar_no": "No",
  "pilot": {
    "form_title": "Request the MSP pilot",
    "intro": "Prefer not to use e-mail? Leave your details and we'll reply within one business day. No payment now.",
    "f_name": "Your name", "f_email": "E-mail", "f_company": "Your company (optional)",
    "f_client": "Client domain to assess (optional)", "f_hosts": "Approx. hostnames (up to 50, optional)",
    "f_logo": "White-label with your logo?", "f_logo_opts": {"": "—", "yes": "Yes", "no": "No"},
    "f_note": "Anything else? (optional)",
    "f_consent": "I agree that my data is stored so Quantum Aether can contact me about the pilot.",
    "submit": "Request the pilot", "sent": "Thank you. We'll reply within one business day. No payment was taken.",
    "err": {"invalid": "Please enter your name, a valid e-mail, and accept the data note.",
            "rate_limited": "Too many requests from your connection today. Please try again tomorrow."},
  },
},
"de": {
  "title": "Partnerprogramm: 30 % für Empfehlungen zur Post-Quanten-TLS-Überwachung",
  "meta": "Marketer, Sicherheitsberater und Agenturen erhalten 30 % der Überwachungszahlungen für 12 Monate und 20 % von Berichten und Audits für vermittelte Kunden.",
  "lead": "Empfehlen Sie Quantum Aether Unternehmen, die Nachweise zu Post-Quanten-TLS brauchen (Lieferanten von Banken, Fintech, SaaS, Hosting-Kunden), und erhalten Sie einen Anteil an jeder Zahlung.",
  "terms_title": "Bedingungen in Kürze",
  "terms": [
    "30 % jeder Überwachungszahlung (Starter 29 €/Monat, Business 99 €/Monat) in den ersten 12 Monaten jedes vermittelten Kunden.",
    "20 % von Einmalkäufen: vollständiger Bericht (49 $), Agenturpaket und Audit für kleine Unternehmen (490 €).",
    "Zuordnung: Ihr Link ?ref=IHRCODE. Beim Aufruf Ihres Links wird automatisch ein First-Party-Zuordnungscookie für 60 Tage gesetzt (letzter Partnerlink zählt).",
    "Auszahlung monatlich per PayPal oder USDC für Zahlungen, die älter als 30 Tage sind (Rückerstattungsfrist), ab 50 USD. Erstattete oder zurückgebuchte Zahlungen werden abgezogen.",
    "Kein Spam, keine unverlangten E-Mails ohne Einwilligung, keine Anzeigen auf unseren Markennamen, keine irreführenden Sicherheitsversprechen (wir verkaufen eine externe Beobachtung, keine Zertifizierung). Eigenvermittlungen sind ausgeschlossen.",
    "Beide Seiten können die Partnerschaft jederzeit beenden; Provision für bereits geleistete Zahlungen wird weiter ausgezahlt. Es gilt österreichisches Recht.",
  ],
  "who_title": "Für wen",
  "who": ["Sicherheits- und Compliance-Berater", "Web- und Hosting-Agenturen, MSPs", "Tech- und Security-Creator, Newsletter-Autoren", "Alle mit Netzwerk in Fintech, SaaS oder Bank-IT"],
  "form_title": "Bewerben",
  "f_name": "Name", "f_email": "E-Mail", "f_channel": "Wie werden Sie uns empfehlen? (Zielgruppe, Kanäle, Reichweite)",
  "f_website": "Website oder Profil (optional)", "f_payout": "Auszahlung", "f_payout_opts": {"paypal": "PayPal", "usdc": "USDC (Base oder Arbitrum)"},
  "f_consent": "Ich akzeptiere die obigen Partnerbedingungen und stimme zu, dass meine Daten zur Durchführung der Partnerschaft gespeichert werden.",
  "f_submit": "Bewerbung senden", "sent": "Danke. Wir prüfen Bewerbungen innerhalb von 3 Werktagen und mailen Ihnen Ihren Partnerlink.",
  "err": {"invalid": "Bitte Name, gültige E-Mail und Empfehlungsweg angeben und die Bedingungen akzeptieren.", "rate_limited": "Zu viele Bewerbungen heute von Ihrer Verbindung. Bitte morgen erneut."},
  "bar": "Sie kommen über einen Link unseres Partners {code}. Dürfen wir 60 Tage lang ein Cookie speichern, damit er bei einem Kauf berücksichtigt wird?",
  "bar_yes": "Ja, zuordnen", "bar_no": "Nein",
  "pilot": {
    "form_title": "Pilot anfragen",
    "intro": "Lieber ohne E-Mail? Hinterlassen Sie Ihre Daten, wir antworten innerhalb eines Werktags. Keine Zahlung jetzt.",
    "f_name": "Ihr Name", "f_email": "E-Mail", "f_company": "Ihr Unternehmen (optional)",
    "f_client": "Zu prüfende Kunden-Domain (optional)", "f_hosts": "Etwa wie viele Hostnamen (bis 50, optional)",
    "f_logo": "White-Label mit Ihrem Logo?", "f_logo_opts": {"": "—", "yes": "Ja", "no": "Nein"},
    "f_note": "Sonstiges? (optional)",
    "f_consent": "Ich stimme zu, dass meine Daten gespeichert werden, damit Quantum Aether mich zum Pilot kontaktieren kann.",
    "submit": "Pilot anfragen", "sent": "Danke. Wir antworten innerhalb eines Werktags. Es wurde keine Zahlung vorgenommen.",
    "err": {"invalid": "Bitte Name und gültige E-Mail angeben und den Datenhinweis akzeptieren.",
            "rate_limited": "Zu viele Anfragen heute von Ihrer Verbindung. Bitte morgen erneut."},
  },
},
"ar": {
  "title": "برنامج الشركاء: اربح 30% من توصيات مراقبة TLS ما بعد الكمّي",
  "meta": "المسوّقون ومستشارو الأمن والوكالات يربحون 30% من مدفوعات المراقبة لمدة 12 شهراً و20% من التقارير والتدقيقات للعملاء الذين يجلبونهم.",
  "lead": "رشّح Quantum Aether للشركات التي تحتاج أدلة على جاهزية TLS لما بعد الكم (موردو البنوك، والتقنية المالية، وSaaS، وعملاء الاستضافة)، واربح حصة من كل دفعة يدفعونها.",
  "terms_title": "الشروط باختصار",
  "terms": [
    "30% من كل دفعة مراقبة (Starter بـ 29 € شهرياً، Business بـ 99 € شهرياً) خلال أول 12 شهراً لكل عميل تجلبه.",
    "20% من المشتريات لمرة واحدة: التقرير الكامل (49$)، وباقة الوكالات، وتدقيق الشركات الصغيرة (490€).",
    "النسبة: رابطك ‎?ref=رمزك. بمجرد فتح الرابط يُحفظ ملف تعريف ارتباط أولي (cookie) تلقائياً لمدة 60 يوماً لتُحتسب العمولة فوراً (آخر رابط شريك هو المعتمد).",
    "الدفع شهرياً عبر PayPal أو USDC، للمدفوعات التي مضى عليها 30 يوماً (فترة الاسترداد)، بحد أدنى 50 دولاراً. المدفوعات المستردة تُخصم.",
    "ممنوع: الرسائل المزعجة، والإيميل البارد بلا موافقة المستلم، والإعلان على اسم علامتنا، والوعود الأمنية المضلِّلة (نبيع رصداً خارجياً لا شهادة). لا عمولة على الإحالة الذاتية.",
    "لأي طرف إنهاء الشراكة متى شاء، وتُدفع العمولة المستحقة عن المدفوعات السابقة. يسري القانون النمساوي.",
  ],
  "who_title": "لمن البرنامج",
  "who": ["مستشارو الأمن والامتثال", "وكالات الويب والاستضافة ومزوّدو الخدمات المُدارة", "صنّاع المحتوى التقني والأمني وكتّاب النشرات", "كل من لديه شبكة علاقات في التقنية المالية أو SaaS أو تقنية البنوك"],
  "form_title": "قدّم طلبك",
  "f_name": "الاسم", "f_email": "البريد", "f_channel": "كيف ستسوّق لنا؟ (الجمهور، القنوات، الحجم)",
  "f_website": "الموقع أو الحساب (اختياري)", "f_payout": "طريقة الدفع", "f_payout_opts": {"paypal": "PayPal", "usdc": "USDC (على Base أو Arbitrum)"},
  "f_consent": "أوافق على شروط الشراكة أعلاه وعلى حفظ بياناتي لإدارة الشراكة.",
  "f_submit": "إرسال الطلب", "sent": "شكراً. نراجع الطلبات خلال 3 أيام عمل ونرسل لك رابط الشريك بالبريد.",
  "err": {"invalid": "املأ الاسم وبريداً صحيحاً وطريقة التسويق، ووافق على الشروط.", "rate_limited": "طلبات كثيرة اليوم من اتصالك. حاول غداً."},
  "bar": "وصلت عبر رابط شريكنا {code}. هل نحفظ ملف تعريف ارتباط (cookie) لمدة 60 يوماً لتُنسب إليه إن أصبحت عميلاً؟",
  "bar_yes": "نعم، انسبها إليه", "bar_no": "لا",
  "pilot": {
    "form_title": "اطلب بايلوت مزوّدي الخدمات",
    "intro": "تفضّل بلا بريد؟ اترك بياناتك ونردّ خلال يوم عمل واحد. لا دفع الآن.",
    "f_name": "اسمك", "f_email": "البريد", "f_company": "شركتك (اختياري)",
    "f_client": "نطاق العميل المراد فحصه (اختياري)", "f_hosts": "عدد المضيفين تقريباً (حتى 50، اختياري)",
    "f_logo": "بشعارك (White-Label)؟", "f_logo_opts": {"": "—", "yes": "نعم", "no": "لا"},
    "f_note": "أي ملاحظة أخرى؟ (اختياري)",
    "f_consent": "أوافق على حفظ بياناتي ليتواصل معي Quantum Aether بخصوص البايلوت.",
    "submit": "اطلب البايلوت", "sent": "شكراً. سنردّ خلال يوم عمل واحد. لم يُجرَ أي دفع.",
    "err": {"invalid": "أدخل اسمك وبريداً صحيحاً ووافق على حفظ البيانات.",
            "rate_limited": "طلبات كثيرة اليوم من اتصالك. حاول غداً."},
  },
},
}


def init(conn):
    with conn:
        conn.executescript(SCHEMA)


def active_code(conn, code):
    code = (code or "").strip().upper()
    if not CODE_RE.match(code):
        return None
    try:
        row = conn.execute("SELECT code FROM partners WHERE code = ? AND status = 'ACTIVE'", (code,)).fetchone()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def attribute(conn, kind, ref_id):
    """Record a conversion for the partner whose consented cookie is present. Never raises."""
    try:
        if not has_request_context():
            return
        code = g.get("partner_code")
        if not code:
            return
        init(conn)
        with conn:
            conn.execute("INSERT OR IGNORE INTO referrals (kind, ref_id, code) VALUES (?, ?, ?)", (kind, str(ref_id), code))
    except Exception:  # attribution must never break a checkout
        pass


def new_code(conn, name):
    base = re.sub(r"[^A-Z]", "", (name or "").upper())[:8] or "PARTNER"
    for _ in range(20):
        code = f"{base}{secrets.randbelow(90) + 10}"
        if not conn.execute("SELECT 1 FROM partners WHERE code = ?", (code,)).fetchone():
            return code
    return "P" + secrets.token_hex(4).upper()


def _stats_secret(cfg: dict) -> str:
    """Return a stable HMAC secret for private partner stats links (explicit SECRET_KEY or DATA_DIR/partner_stats.key)."""
    explicit = str(cfg.get("SECRET_KEY") or "").strip()
    if explicit:
        return explicit
    data_dir = str(cfg.get("DATA_DIR") or "").strip()
    if not data_dir:
        return ""
    import os
    from pathlib import Path
    key_path = Path(data_dir) / "partner_stats.key"
    if key_path.exists():
        val = key_path.read_text(encoding="utf-8").strip()
        if val:
            return val
    key_path.parent.mkdir(parents=True, exist_ok=True)
    val = secrets.token_hex(32)
    tmp = key_path.with_suffix(".key.tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(val + "\n")
    try:
        os.chmod(tmp, 0o600)
        os.replace(tmp, key_path)
    except OSError:
        tmp.unlink(missing_ok=True)
        if key_path.exists():
            return key_path.read_text(encoding="utf-8").strip()
        raise
    return val


def stats_token(code: str, secret: str) -> str:
    """Deterministic HMAC-SHA256 token (24 hex chars) authorizing private live stats for one partner code."""
    clean = (code or "").strip().upper()
    if not clean or not secret:
        return ""
    return hmac.new(secret.encode("utf-8"), f"qa-partner-stats:{clean}".encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def _affiliate_payload(code: str, payout_method: str, payout_destination: str, base_url: str, already_registered: bool = False) -> dict:
    b = base_url.rstrip("/")
    return {
        "status": "ACTIVE",
        "already_registered": already_registered,
        "code": code,
        "referral_links": {
            "home": f"{b}/?ref={code}",
            "monitoring_trial": f"{b}/monitoring?ref={code}#trial-form",
            "audit": f"{b}/audit?ref={code}",
            "partners": f"{b}/partners?ref={code}",
        },
        "terms": {
            "monitoring_commission_pct": int(SUB_RATE * 100),
            "monitoring_commission_months": SUB_MONTHS,
            "one_time_commission_pct": int(ONE_TIME_RATE * 100),
            "payout_schedule": "monthly_manual_by_owner",
            "payout_method": payout_method,
            "payout_destination": payout_destination,
            "hold_days": HOLD_DAYS,
            "min_payout_usd": MIN_PAYOUT,
            "cookie_days": COOKIE_DAYS,
            "prohibited": ["spam", "unsolicited_cold_email", "brand_ads", "self_referrals", "misleading_security_claims"],
            "terms_url": f"{b}/partners?lang=en",
        },
        "note": (
            "Attach ?ref=" + code + " to any Quantum Aether URL you share. Attribution is set automatically on link click for 60 days. "
            "Commissions are reviewed and paid manually by the owner once per month after the 30-day refund hold (min USD 50). "
            "No automatic payouts; abusive or spam referrals are revoked."
        ),
    }


def _notify_owner(subject: str, text: str) -> None:
    """Best-effort owner-only email alert via Flask Mailer. Never emails applicants and never raises."""
    try:
        from flask import current_app
        mailer = current_app.extensions.get("mailer")
        owner = (current_app.config.get("OWNER_EMAIL") or "").strip()
        if mailer and owner:
            mailer.send(owner, subject, text)
    except Exception:
        pass


def register_agent_affiliate(
    conn,
    *,
    name: str,
    contact_email: str,
    payout_method: str,
    payout_destination: str | None = None,
    channel: str | None = None,
    website: str | None = None,
    client_hash: str = "",
    base_url: str = "https://ather-quantum.com",
) -> tuple[int, dict]:
    """Self-service registration for AI agents / operators. Payout remains monthly & manual by the owner."""
    nm = (name or "").strip()
    em = (contact_email or "").strip().lower()
    method = (payout_method or "").strip().lower()
    dest = (payout_destination or "").strip()
    ch = (channel or "AI agent / MCP recommendation").strip()
    web = (website or "").strip()

    if not 2 <= len(nm) <= 120:
        return 400, {"error": "invalid_name", "message": "name must be 2-120 characters"}
    if not EMAIL_RE.match(em):
        return 400, {"error": "invalid_email", "message": "valid contact_email is required"}
    if method not in ("usdc", "paypal"):
        return 400, {"error": "invalid_payout_method", "message": "payout_method must be 'usdc' or 'paypal'"}
    if method == "usdc":
        if not WALLET_RE.match(dest):
            return 400, {"error": "invalid_wallet", "message": "payout_destination must be a valid 0x EVM address (Base or Arbitrum USDC)"}
    else:
        dest = (dest or em).lower()
        if not EMAIL_RE.match(dest):
            return 400, {"error": "invalid_paypal_email", "message": "payout_destination must be a valid PayPal email"}
    if not 3 <= len(ch) <= 1000 or len(web) > 300:
        return 400, {"error": "invalid_channel", "message": "channel must be 3-1000 chars and website <= 300 chars"}

    init(conn)
    existing = conn.execute(
        "SELECT code, payout FROM partners WHERE lower(email) = ? AND status = 'ACTIVE' AND code IS NOT NULL LIMIT 1",
        (em,),
    ).fetchone()
    if existing:
        stored_payout = existing[1] or method
        if ":" in stored_payout:
            m_old, d_old = stored_payout.split(":", 1)
        else:
            m_old, d_old = stored_payout, em
        return 200, _affiliate_payload(existing[0], m_old, d_old, base_url, already_registered=True)

    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    recent_n = conn.execute(
        "SELECT COUNT(*) FROM partners WHERE client_hash = ? AND created_at >= ?",
        (client_hash, since),
    ).fetchone()[0]
    if recent_n >= 3:
        return 429, {"error": "rate_limited", "message": "Too many affiliate registrations from this client today"}

    code = new_code(conn, nm)
    payout_stored = f"{method}:{dest}"
    now_iso = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with conn:
        cur = conn.execute(
            "INSERT INTO partners (code, name, email, channel, website, payout, lang, status, client_hash, consent_at, approved_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'en', 'ACTIVE', ?, ?, ?)",
            (code, nm, em, f"[agent] {ch}", web or None, payout_stored, client_hash, now_iso, now_iso),
        )
        pid = cur.lastrowid
    b = base_url.rstrip("/")
    _notify_owner(
        f"[Quantum Aether] تسجيل وكيل إحالة جديد ({code}) — {nm}",
        f"تم تسجيل وكيل ذكاء اصطناعي جديد تلقائياً في برنامج الشركاء:\n\n"
        f"- المعرّف: #{pid}\n"
        f"- الاسم: {nm}\n"
        f"- البريد: {em}\n"
        f"- الكود: {code}\n"
        f"- الرابط: {b}/?ref={code}\n"
        f"- الدفع الشهري اليدوي: {method} ({dest})\n"
        f"- الموقع: {web or '-'}\n"
        f"- القناة: {ch}\n\n"
        f"لإيقاف الشريك عند الحاجة:\n"
        f"python3 tools/partners_admin.py end {pid}\n",
    )
    return 201, _affiliate_payload(code, method, dest, base_url, already_registered=False)


def commissions(conn, now=None):
    """-> {code: {"items": [...], "due": float, "pending": float}} from referrals joined with real payments."""
    now = now or dt.datetime.now(dt.timezone.utc)
    hold = (now - dt.timedelta(days=HOLD_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = {}

    def add(code, item, amount, paid_at):
        d = out.setdefault(code, {"items": [], "due": 0.0, "pending": 0.0})
        due = bool(paid_at) and paid_at <= hold
        d["items"].append(dict(item, commission=round(amount, 2), paid_at=paid_at, due=due))
        d["due" if due else "pending"] += amount

    init(conn)
    for kind, ref_id, code, created in conn.execute("SELECT kind, ref_id, code, created_at FROM referrals"):
        if kind == "report":
            r = conn.execute("SELECT amount, currency, status, is_test, created_at FROM orders WHERE order_id = ?", (ref_id,)).fetchone()
            if r and r[2] == "COMPLETED" and not r[3]:
                add(code, {"kind": kind, "ref": ref_id, "currency": r[1]}, float(r[0]) * ONE_TIME_RATE, r[4])
        elif kind == "pack":
            r = conn.execute("SELECT amount, currency, status, is_test, paid_at FROM packs WHERE id = ?", (ref_id,)).fetchone()
            if r and r[2] == "COMPLETED" and not r[3]:
                add(code, {"kind": kind, "ref": ref_id, "currency": r[1]}, float(r[0]) * ONE_TIME_RATE, r[4])
        elif kind == "audit":
            r = conn.execute("SELECT amount, currency, status, is_test, paid_at, refund_id FROM audit_orders WHERE id = ?", (ref_id,)).fetchone()
            if r and r[2] == "COMPLETED" and not r[3] and not r[5]:
                add(code, {"kind": kind, "ref": ref_id, "currency": r[1]}, float(r[0]) * ONE_TIME_RATE, r[4])
        elif kind == "monitor":
            r = conn.execute("SELECT plan, status, subscription_id, updated_at FROM monitor_accounts WHERE id = ?", (ref_id,)).fetchone()
            if r and r[2] and r[1] in ("ACTIVE", "CANCELLED", "SUSPENDED", "EXPIRED"):
                start = r[3] or created
                months = 1
                try:
                    s = dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
                    end = now if r[1] == "ACTIVE" else dt.datetime.fromisoformat((r[3] or start).replace("Z", "+00:00"))
                    months = max(1, min(SUB_MONTHS, (end.year - s.year) * 12 + end.month - s.month + 1))
                except ValueError:
                    pass
                add(code, {"kind": kind, "ref": ref_id, "currency": "USD", "plan": r[0], "months_estimate": months,
                           "note": "verify payments in PayPal"}, PLAN_PRICE.get(r[0], 29.0) * SUB_RATE * months, start)
    return out


def register(bp, deps):
    """deps: db, lang, client_hash."""

    @bp.before_app_request
    def _partner_ref():
        g.partner_code = None
        g.ref_offer = None
        g.set_ref_cookie = None
        cookie = request.cookies.get(COOKIE)
        if not cookie and not request.args.get("ref"):
            return  # the common case: no database access at all
        try:
            conn = deps["db"]()
            if cookie:
                g.partner_code = active_code(conn, cookie)
            ref = request.args.get("ref")
            if ref and request.method == "GET":
                code = active_code(conn, ref)
                if code:
                    with conn:
                        conn.execute("INSERT INTO partner_clicks (code, day, n) VALUES (?, date('now'), 1) "
                                     "ON CONFLICT(code, day) DO UPDATE SET n = n + 1", (code,))
                    g.partner_code = code
                    if code != cookie:
                        g.set_ref_cookie = code
        except Exception:
            pass

    @bp.after_app_request
    def _apply_partner_cookie(response):
        code = g.get("set_ref_cookie")
        if code:
            response.set_cookie(COOKIE, code, max_age=COOKIE_DAYS * 86400, secure=True, httponly=True, samesite="Lax")
        return response

    @bp.app_context_processor
    def _ref_bar():
        if not g.get("ref_offer"):
            return {}
        lang = deps["lang"]()
        return {"ref_bar": dict(T.get(lang, T["en"]), code=g.ref_offer)}

    @bp.post("/partners/consent")
    def partner_consent():
        code = active_code(deps["db"](), (request.get_json(silent=True) or {}).get("code"))
        if not code:
            return jsonify(error="unknown_code"), 400
        resp = make_response(jsonify(ok=True))
        resp.set_cookie(COOKIE, code, max_age=COOKIE_DAYS * 86400, secure=True, httponly=True, samesite="Lax")
        return resp

    @bp.get("/partners")
    def partners_page():
        lang = deps["lang"]()
        d = T.get(lang, T["en"])
        return render_template("partners.html", d=d, sent=request.args.get("sent") == "1",
                               error=d["err"].get(request.args.get("error", "")),
                               pilot_sent=request.args.get("psent") == "1",
                               pilot_error=d["pilot"]["err"].get(request.args.get("perror", "")))

    @bp.post("/partners/apply")
    def partners_apply():
        lang = request.form.get("lang") if request.form.get("lang") in T else "en"
        back = lambda **kw: redirect(url_for("site.partners_page", lang=lang, **kw) + "#apply", code=303)
        if request.form.get("website2"):  # honeypot
            return back(sent="1")
        f = {k: (request.form.get(k) or "").strip() for k in ("name", "email", "channel", "website", "payout")}
        if (not 1 <= len(f["name"]) <= 120 or not EMAIL_RE.match(f["email"]) or not 10 <= len(f["channel"]) <= 2000
                or len(f["website"]) > 300 or f["payout"] not in ("paypal", "usdc") or not request.form.get("consent")):
            return back(error="invalid")
        conn, client = deps["db"](), deps["client_hash"]()
        init(conn)
        n = conn.execute("SELECT COUNT(*) FROM partners WHERE client_hash = ? AND created_at >= ?",
                         (client, (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))).fetchone()[0]
        if n >= 3:
            return back(error="rate_limited")
        with conn:
            cur = conn.execute("INSERT INTO partners (name, email, channel, website, payout, lang, client_hash, consent_at) "
                               "VALUES (?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))",
                               (f["name"], f["email"], f["channel"], f["website"] or None, f["payout"], lang, client))
            pid = cur.lastrowid
        _notify_owner(
            f"[Quantum Aether] طلب شراكة جديد (#{pid}) — {f['name']}",
            f"وصل طلب شراكة جديد من صفحة /partners:\n\n"
            f"- المعرّف: #{pid}\n"
            f"- الاسم: {f['name']}\n"
            f"- البريد: {f['email']}\n"
            f"- طريقة الدفع: {f['payout']}\n"
            f"- اللغة: {lang}\n"
            f"- الموقع: {f['website'] or '-'}\n"
            f"- القناة وطريقة التسويق:\n{f['channel']}\n\n"
            f"لتفعيل الشريك وإرسال رابطه:\n"
            f"python3 tools/partners_admin.py approve {pid}\n",
        )
        return back(sent="1")

    @bp.post("/partners/pilot")
    def partners_pilot():
        lang = request.form.get("lang") if request.form.get("lang") in T else "en"
        back = lambda **kw: redirect(url_for("site.partners_page", lang=lang, **kw) + "#pilot-apply", code=303)
        if request.form.get("website2"):  # honeypot
            return back(psent="1")
        f = {k: (request.form.get(k) or "").strip() for k in ("name", "email", "company", "client_domain", "note")}
        hosts_raw = (request.form.get("hostnames") or "").strip()
        white = (request.form.get("white_label") or "").strip().lower()
        if (not 1 <= len(f["name"]) <= 120 or not EMAIL_RE.match(f["email"]) or len(f["company"]) > 120
                or len(f["client_domain"]) > 253 or len(f["note"]) > 2000
                or white not in ("", "yes", "no") or not request.form.get("consent")):
            return back(perror="invalid")
        hosts = None
        if hosts_raw:
            try:
                hosts = min(max(int(re.sub(r"[^0-9]", "", hosts_raw) or 0), 0), 50) or None
            except ValueError:
                hosts = None
        conn, client = deps["db"](), deps["client_hash"]()
        init(conn)
        n = conn.execute("SELECT COUNT(*) FROM pilot_leads WHERE client_hash = ? AND created_at >= ?",
                         (client, (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"))).fetchone()[0]
        if n >= 3:
            return back(perror="rate_limited")
        with conn:
            cur = conn.execute(
                "INSERT INTO pilot_leads (name, email, company, client_domain, hostnames, white_label, note, lang, "
                "client_hash, consent_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))",
                (f["name"], f["email"], f["company"] or None, f["client_domain"] or None, hosts,
                 white or None, f["note"] or None, lang, client))
            lid = cur.lastrowid
        label = f["company"] or f["name"]
        _notify_owner(
            f"[Quantum Aether] طلب MSP Pilot جديد (#{lid}) — {label}",
            f"وصل طلب MSP Pilot جديد من صفحة /partners:\n\n"
            f"- المعرّف: #{lid}\n"
            f"- الاسم: {f['name']}\n"
            f"- البريد: {f['email']}\n"
            f"- الشركة: {f['company'] or '-'}\n"
            f"- نطاق العميل: {f['client_domain'] or '-'}\n"
            f"- عدد المضيفين: {hosts or '-'}\n"
            f"- White-Label (شعار الشريك): {white or '-'}\n"
            f"- اللغة: {lang}\n"
            f"- ملاحظات:\n{f['note'] or '-'}\n\n"
            f"لمتابعة الحالة:\n"
            f"python3 tools/partners_admin.py pilot {lid} CONTACTED\n",
        )
        return back(psent="1")

    @bp.route("/api/v1/agent/affiliate/register", methods=["POST", "OPTIONS"])
    def api_agent_affiliate_register():
        if request.method == "OPTIONS":
            resp = make_response(("", 204))
            resp.headers.update({
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            })
            return resp
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="invalid_request", message="Expected a JSON object"), 400
        if body.get("consent_terms") is not True:
            return jsonify(error="consent_required", message="consent_terms must be true to accept partner terms"), 400
        base_url = deps["base"]() if deps.get("base") else "https://ather-quantum.com"
        status, payload = register_agent_affiliate(
            deps["db"](),
            name=str(body.get("name") or ""),
            contact_email=str(body.get("contact_email") or body.get("email") or ""),
            payout_method=str(body.get("payout_method") or ""),
            payout_destination=body.get("payout_destination") or body.get("wallet_address"),
            channel=body.get("channel"),
            website=body.get("website"),
            client_hash=deps["client_hash"](),
            base_url=base_url,
        )
        resp = jsonify(payload)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Cache-Control"] = "no-store"
        return resp, status

    @bp.get("/partners/live/<code>/<token>")
    def partner_live_stats(code, token):
        clean_code = (code or "").strip().upper()
        if not CODE_RE.match(clean_code):
            abort(404)
        secret = _stats_secret(current_app.config)
        expected = stats_token(clean_code, secret)
        if not expected or not hmac.compare_digest(str(token or ""), expected):
            abort(404)
        conn = deps["db"]()
        init(conn)
        row = conn.execute(
            "SELECT id, code, name, lang, status, approved_at, created_at FROM partners WHERE code = ? AND status = 'ACTIVE'",
            (clean_code,),
        ).fetchone()
        if not row:
            abort(404)
        partner = {
            "id": row[0], "code": row[1], "name": row[2],
            "lang": (row[3] or "en").lower(), "status": row[4],
            "approved_at": row[5], "created_at": row[6],
        }
        now_utc = dt.datetime.now(dt.timezone.utc)
        today = now_utc.date().isoformat()
        cutoff_7d = (now_utc.date() - dt.timedelta(days=6)).isoformat()
        daily_rows = conn.execute(
            "SELECT day, n FROM partner_clicks WHERE code = ? ORDER BY day DESC LIMIT 60",
            (clean_code,),
        ).fetchall()
        daily = [{"day": r[0], "n": int(r[1] or 0)} for r in daily_rows]
        total_clicks = sum(r["n"] for r in daily)
        today_clicks = sum(r["n"] for r in daily if r["day"] == today)
        last_7d_clicks = sum(r["n"] for r in daily if r["day"] >= cutoff_7d)
        peak_clicks = max((r["n"] for r in daily), default=0)

        ref_rows = conn.execute(
            "SELECT kind, created_at FROM referrals WHERE code = ? ORDER BY created_at DESC LIMIT 50",
            (clean_code,),
        ).fetchall()
        refs = [{"kind": r[0], "created_at": r[1]} for r in ref_rows]
        comm = commissions(conn, now=now_utc).get(clean_code, {"items": [], "due": 0.0, "pending": 0.0})

        stats = {
            "today": today,
            "checked_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_clicks": total_clicks,
            "today_clicks": today_clicks,
            "last_7d_clicks": last_7d_clicks,
            "peak_clicks": peak_clicks,
            "daily": daily,
            "referrals_count": len(refs),
            "referrals": refs,
            "commission_pending": round(float(comm.get("pending") or 0.0), 2),
            "commission_due": round(float(comm.get("due") or 0.0), 2),
        }
        base_url = (deps["base"]() if deps.get("base") else "https://ather-quantum.com").rstrip("/")
        if request.args.get("format") == "json":
            resp = jsonify({"partner": partner, "stats": stats, "referral_url": f"{base_url}/?ref={clean_code}"})
        else:
            q_lang = (request.args.get("lang") or "").lower()
            lang = q_lang if q_lang in ("ar", "en") else ("ar" if partner["lang"] == "ar" else "en")
            resp = make_response(render_template("partner_live.html", partner=partner, stats=stats, lang=lang, base=base_url))
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp
