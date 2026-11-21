"""Quantum Aether ProofLab (2026-11-14): waitlist page for proving a PQC/TLS change works before production.

Waitlist only: no payment, no account. Rows are stored in prooflab_waitlist; test rows (admin cookie / owner client)
carry is_test=1 and never trigger an owner alert. The copy promises only what the prototype Action does today.
"""
import datetime as dt

SIGNUPS_PER_CLIENT_PER_DAY = 3
STACKS = ("nginx", "caddy", "haproxy", "other")
ACTION_REPO = "https://github.com/moncef00327-cloud/prooflab-action"

SCHEMA = """
CREATE TABLE IF NOT EXISTS prooflab_waitlist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT NOT NULL,
    company     TEXT NOT NULL,
    stack       TEXT NOT NULL,
    lang        TEXT NOT NULL DEFAULT 'en',
    client_hash TEXT,
    is_test     INTEGER NOT NULL DEFAULT 0,
    consent_at  TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS prooflab_waitlist_client ON prooflab_waitlist (client_hash, created_at);
"""


def init(conn):
    conn.executescript(SCHEMA)


def _now(delta=None):
    return (dt.datetime.now(dt.timezone.utc) + (delta or dt.timedelta())).strftime("%Y-%m-%dT%H:%M:%SZ")


def rate_limited(conn, client_hash):
    n = conn.execute("SELECT COUNT(*) FROM prooflab_waitlist WHERE client_hash = ? AND created_at >= ?",
                     (client_hash, _now(dt.timedelta(days=-1)))).fetchone()[0]
    return n >= SIGNUPS_PER_CLIENT_PER_DAY


def already_listed(conn, email):
    return conn.execute("SELECT 1 FROM prooflab_waitlist WHERE email = ? LIMIT 1", (email,)).fetchone() is not None


def create(conn, *, email, company, stack, lang, client_hash, is_test):
    with conn:
        cur = conn.execute(
            "INSERT INTO prooflab_waitlist (email, company, stack, lang, client_hash, is_test, consent_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)", (email, company, stack, lang, client_hash, 1 if is_test else 0, _now()))
    return cur.lastrowid


def counts(conn):
    """Real (non-test) signups in total and by stack, plus the latest rows for the admin page."""
    total = conn.execute("SELECT COUNT(*) FROM prooflab_waitlist WHERE is_test = 0").fetchone()[0]
    by_stack = dict(conn.execute("SELECT stack, COUNT(*) FROM prooflab_waitlist WHERE is_test = 0 GROUP BY stack").fetchall())
    tests = conn.execute("SELECT COUNT(*) FROM prooflab_waitlist WHERE is_test = 1").fetchone()[0]
    recent = conn.execute("SELECT email, company, stack, lang, created_at FROM prooflab_waitlist WHERE is_test = 0 "
                          "ORDER BY id DESC LIMIT 20").fetchall()
    return {"total": total, "by_stack": by_stack, "tests": tests, "recent": recent}


def owner_email(row_id, email, company, stack, lang, base):
    subject = f"[Quantum Aether] ProofLab waitlist signup — {company}"
    text = "\n".join([
        "Event: ProofLab waitlist signup (free pilot on one repository)",
        f"Email: {email}", f"Company/domain: {company}", f"Stack: {stack}", f"Language: {lang}",
        f"Signup id: {row_id}", f"Admin: {base}/admin",
        "", "No automatic email was sent to this person.", "— Quantum Aether Team",
    ])
    return subject, text


COPY = {
    "en": {
        "title": "ProofLab: prove a post-quantum TLS change works before production",
        "meta": "ProofLab finds your TLS crypto, proposes a minimal X25519MLKEM768 change with evidence, tests it in an isolated container and hands you a verifiable result. Free pilot on one repository.",
        "kicker": "Quantum Aether ProofLab · early access",
        "lead": "Most tools warn you or write a plan. ProofLab tries the fix in a safe place first and shows you the evidence: a patch, the tests that passed and failed, measurements and rollback steps. Nothing touches production without your explicit approval.",
        "how_title": "How it works",
        "steps": [
            ("Discover", "Finds where TLS and crypto are configured in your repository: nginx, Caddy and HAProxy configs, Dockerfiles and the OpenSSL version they ship."),
            ("Propose, with evidence", "Suggests a minimal change (for example X25519MLKEM768 hybrid key exchange with a classical fallback) and shows the files and lines it is based on."),
            ("Test in an isolated container", "Builds the original and the patched config side by side and checks connectivity, client compatibility (post-quantum and classical-only clients), handshake time and handshake size."),
            ("Verifiable result", "You get the patch diff, a pass/fail table, the measurements and the rollback steps, in your CI job summary or as a pull request."),
            ("You stay in control", "Nothing is applied to production. Your code stays in your GitHub/CI: the check runs as a GitHub Action in your own runner."),
        ],
        "scope_title": "Honest scope today",
        "scope": "The first version covers nginx, Caddy and HAProxy TLS configs in one repository. It does not change running servers, and it does not need access to your infrastructure. An experimental lab that compares classical and quantum methods on a narrow planning problem may follow; its results will be shown as they are.",
        "proto": "Open-source prototype (MIT):",
        "pilot_title": "Free pilot on one repository",
        "pilot_sub": "Join the waitlist. We pick a small number of teams for a free pilot on one repository and contact you at this address only about ProofLab.",
        "email": "Work email", "company": "Company or domain", "stack": "TLS stack",
        "stack_names": {"nginx": "nginx", "caddy": "Caddy", "haproxy": "HAProxy", "other": "Other"},
        "consent": "I agree to the Terms and the Privacy Policy",
        "button": "Join the waitlist",
        "fine": "No payment, no card. One request per address.",
        "ok": "Thanks, you are on the ProofLab waitlist. We will reach out about a free pilot.",
        "err_consent": "Please tick the box to accept the Terms and the Privacy Policy.",
        "err_email": "Please enter a valid work email address.",
        "err_company": "Please enter your company name or domain.",
        "err_stack": "Please choose your TLS stack.",
        "err_limit": "Too many requests from this connection today. Please try again tomorrow.",
        "nav": "ProofLab",
    },
    "de": {
        "title": "ProofLab: Post-Quanten-TLS vor der Produktion prüfen",
        "meta": "ProofLab findet Ihre TLS-Kryptografie, schlägt eine minimale X25519MLKEM768-Änderung vor, testet sie isoliert und liefert ein prüfbares Ergebnis.",
        "kicker": "Quantum Aether ProofLab · Early Access",
        "lead": "Die meisten Werkzeuge warnen oder schreiben einen Plan. ProofLab probiert die Korrektur zuerst an einem sicheren Ort aus und zeigt die Belege: Patch, bestandene und fehlgeschlagene Tests, Messwerte und Rückfallschritte. Nichts erreicht die Produktion ohne Ihre ausdrückliche Freigabe.",
        "how_title": "So funktioniert es",
        "steps": [
            ("Erkennen", "Findet, wo TLS und Kryptografie in Ihrem Repository konfiguriert sind: nginx-, Caddy- und HAProxy-Konfigurationen, Dockerfiles und die mitgelieferte OpenSSL-Version."),
            ("Vorschlagen, mit Belegen", "Schlägt eine minimale Änderung vor (z. B. hybriden Schlüsselaustausch X25519MLKEM768 mit klassischem Fallback) und zeigt die Dateien und Zeilen, auf denen sie beruht."),
            ("Im isolierten Container testen", "Baut die ursprüngliche und die geänderte Konfiguration nebeneinander und prüft Verbindung, Client-Kompatibilität (Post-Quanten- und rein klassische Clients), Handshake-Dauer und Handshake-Größe."),
            ("Überprüfbares Ergebnis", "Sie erhalten den Patch-Diff, eine Bestanden/Fehlgeschlagen-Tabelle, die Messwerte und die Rückfallschritte – in der CI-Zusammenfassung oder als Pull Request."),
            ("Sie behalten die Kontrolle", "Nichts wird in der Produktion angewendet. Ihr Code bleibt in Ihrem GitHub/CI: Die Prüfung läuft als GitHub Action in Ihrem eigenen Runner."),
        ],
        "scope_title": "Ehrlicher Umfang heute",
        "scope": "Die erste Version deckt nginx-, Caddy- und HAProxy-TLS-Konfigurationen in einem Repository ab. Sie ändert keine laufenden Server und braucht keinen Zugriff auf Ihre Infrastruktur. Ein experimentelles Labor, das klassische und Quantenverfahren an einem eng umrissenen Planungsproblem vergleicht, kann folgen; die Ergebnisse werden so gezeigt, wie sie sind.",
        "proto": "Open-Source-Prototyp (MIT):",
        "pilot_title": "Kostenloser Pilot für ein Repository",
        "pilot_sub": "Tragen Sie sich in die Warteliste ein. Wir wählen wenige Teams für einen kostenlosen Pilot mit einem Repository aus und kontaktieren Sie über diese Adresse ausschließlich zu ProofLab.",
        "email": "Geschäftliche E-Mail", "company": "Unternehmen oder Domain", "stack": "TLS-Stack",
        "stack_names": {"nginx": "nginx", "caddy": "Caddy", "haproxy": "HAProxy", "other": "Andere"},
        "consent": "Ich stimme den AGB und der Datenschutzerklärung zu",
        "button": "Auf die Warteliste",
        "fine": "Keine Zahlung, keine Karte. Eine Anfrage pro Adresse.",
        "ok": "Danke, Sie stehen auf der ProofLab-Warteliste. Wir melden uns wegen eines kostenlosen Pilots.",
        "err_consent": "Bitte bestätigen Sie die AGB und die Datenschutzerklärung (Kästchen anhaken).",
        "err_email": "Bitte geben Sie eine gültige geschäftliche E-Mail-Adresse ein.",
        "err_company": "Bitte geben Sie Ihr Unternehmen oder Ihre Domain ein.",
        "err_stack": "Bitte wählen Sie Ihren TLS-Stack.",
        "err_limit": "Zu viele Anfragen von dieser Verbindung heute. Bitte versuchen Sie es morgen erneut.",
        "nav": "ProofLab",
    },
    "ar": {
        "title": "ProofLab: أثبت أن تغيير TLS المقاوم للكم يعمل قبل الإنتاج",
        "meta": "يكتشف ProofLab تشفير TLS لديك، ويقترح تعديلاً صغيراً لتفعيل X25519MLKEM768 مع الأدلة، ويختبره في حاوية معزولة، ويسلّمك نتيجة قابلة للتحقق. تجربة مجانية على مستودع واحد.",
        "kicker": "Quantum Aether ProofLab · وصول مبكر",
        "lead": "أغلب الأدوات تكتفي بالتحذير أو بكتابة خطة. ProofLab يجرّب الإصلاح أولاً في مكان آمن ويعرض لك الدليل: التعديل، والاختبارات الناجحة والفاشلة، والقياسات، وخطوات الرجوع. لا شيء يصل إلى الإنتاج من دون موافقتك الصريحة.",
        "how_title": "كيف يعمل",
        "steps": [
            ("الاكتشاف", "يجد أين يُضبط TLS والتشفير في مستودعك: إعدادات nginx وCaddy وHAProxy، وملفات Dockerfile، وإصدار OpenSSL الذي تأتي به."),
            ("اقتراح مع الأدلة", "يقترح تعديلاً صغيراً (مثل تبادل المفاتيح الهجين X25519MLKEM768 مع بديل تقليدي) ويعرض الملفات والأسطر التي استند إليها."),
            ("الاختبار في حاوية معزولة", "يبني الإعداد الأصلي والمعدّل جنباً إلى جنب، ويفحص الاتصال، وتوافق العملاء (عميل مقاوم للكم وعميل تقليدي فقط)، وزمن المصافحة وحجمها."),
            ("نتيجة قابلة للتحقق", "تحصل على فرق التعديل، وجدول نجاح وفشل، والقياسات، وخطوات الرجوع، في ملخص مهمة CI أو كطلب دمج (Pull Request)."),
            ("القرار لك", "لا يُطبَّق شيء على الإنتاج. يبقى كودك في GitHub أو CI الخاص بك: الفحص يعمل كإجراء GitHub على خادمك أنت."),
        ],
        "scope_title": "النطاق الحالي بصراحة",
        "scope": "النسخة الأولى تغطي إعدادات TLS في nginx وCaddy وHAProxy داخل مستودع واحد. لا تغيّر أي خادم يعمل، ولا تحتاج وصولاً إلى بنيتك التحتية. قد يُضاف لاحقاً مختبر تجريبي يقارن بين الطرق التقليدية والكمية في مسألة تخطيط محددة، وتُعرض نتائجه كما هي.",
        "proto": "نموذج أولي مفتوح المصدر (MIT):",
        "pilot_title": "تجربة مجانية على مستودع واحد",
        "pilot_sub": "سجّل في قائمة الانتظار. نختار عدداً صغيراً من الفرق لتجربة مجانية على مستودع واحد، ونتواصل معك على هذا البريد بخصوص ProofLab فقط.",
        "email": "بريد العمل", "company": "الشركة أو النطاق", "stack": "خادم TLS",
        "stack_names": {"nginx": "nginx", "caddy": "Caddy", "haproxy": "HAProxy", "other": "غير ذلك"},
        "consent": "أوافق على الشروط وسياسة الخصوصية",
        "button": "انضم إلى قائمة الانتظار",
        "fine": "بلا دفع ولا بطاقة. طلب واحد لكل بريد.",
        "ok": "شكراً، أنت الآن في قائمة انتظار ProofLab. سنتواصل معك بخصوص التجربة المجانية.",
        "err_consent": "ضع علامة الموافقة على الشروط وسياسة الخصوصية.",
        "err_email": "اكتب بريد عمل صحيحاً.",
        "err_company": "اكتب اسم الشركة أو النطاق.",
        "err_stack": "اختر خادم TLS الذي تستخدمه.",
        "err_limit": "طلبات كثيرة من هذا الاتصال اليوم. حاول مرة أخرى غداً.",
        "nav": "ProofLab",
    },
}
