# packs.py
# باقة الوكالات: 10 تقارير كاملة بسعر 199$ (تُدفع مرة واحدة عبر PayPal، بلا انتهاء صلاحية).
# بعد الدفع يحصل المشتري على رابط سرّي /pack/<token> (يُرسل بالبريد أيضاً): يكتب أي نطاق فيُفحص ويُفتح تقريره
# الكامل ويُخصم رصيد واحد. كل تقرير مفتوح يُسجَّل كطلب COMPLETED بمبلغ 0 مرتبط بالفحص (فيعمل منطق التقرير القائم
# كما هو)، والإيراد الحقيقي هو دفعة الباقة نفسها في جدول packs (فلا يُحسب المبلغ مرتين).
import hashlib
import secrets

SCHEMA = """
CREATE TABLE IF NOT EXISTS packs (
    id          TEXT PRIMARY KEY,               -- مرجع PayPal (reference_id)
    order_id    TEXT UNIQUE,                    -- طلب PayPal
    token_hash  TEXT UNIQUE,                    -- رابط الباقة (يُنشأ بعد الدفع فقط)
    email       TEXT,
    lang        TEXT NOT NULL DEFAULT 'en',
    credits     INTEGER NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0,
    amount      TEXT NOT NULL,
    currency    TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'CREATED',  -- CREATED / COMPLETED / PENDING / FAILED
    capture_id  TEXT,
    consent_at  TEXT,
    is_test     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    paid_at     TEXT
);
"""


def init(conn):
    conn.executescript(SCHEMA)


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_id():
    return "pk_" + secrets.token_urlsafe(9)


def create(conn, pack_id, order_id, credits, amount, currency, lang, consent_at, is_test):
    with conn:
        conn.execute("INSERT INTO packs (id, order_id, credits, amount, currency, lang, consent_at, is_test) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (pack_id, order_id, credits, amount, currency, lang, consent_at, int(is_test)))


def by_order(conn, order_id):
    row = conn.execute("SELECT * FROM packs WHERE order_id = ?", (order_id,)).fetchone()
    return dict(row) if row else None


def by_token(conn, token):
    row = conn.execute("SELECT * FROM packs WHERE token_hash = ? AND status = 'COMPLETED'", (_hash(token),)).fetchone()
    return dict(row) if row else None


def mark(conn, pack_id, status, capture_id=None, email=None):
    """يحدّث الحالة. عند COMPLETED لأول مرة يُنشأ رمز الرابط ويُعاد (وإلا None)."""
    token = None
    with conn:
        row = conn.execute("SELECT status, token_hash FROM packs WHERE id = ?", (pack_id,)).fetchone()
        if status == "COMPLETED" and not row["token_hash"]:
            token = secrets.token_urlsafe(24)
            conn.execute("UPDATE packs SET token_hash = ?, paid_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now') WHERE id = ?",
                         (_hash(token), pack_id))
        conn.execute("UPDATE packs SET status = ?, capture_id = COALESCE(?, capture_id), email = COALESCE(?, email) WHERE id = ?",
                     (status, capture_id, email, pack_id))
    return token


def redeem(conn, pack, scan_id):
    """يخصم رصيداً ويفتح تقرير الفحص. يعيد True، أو False إن نفد الرصيد. الفحص المفتوح مسبقاً لا يُخصم مرتين."""
    order_id = f"pack:{pack['id']}:{scan_id}"
    with conn:
        if conn.execute("SELECT 1 FROM orders WHERE order_id = ?", (order_id,)).fetchone():
            return True
        updated = conn.execute("UPDATE packs SET used = used + 1 WHERE id = ? AND used < credits", (pack["id"],)).rowcount
        if not updated:
            return False
        conn.execute("INSERT INTO orders (order_id, scan_id, status, amount, currency, consent_at, is_test) "
                     "VALUES (?, ?, 'COMPLETED', '0.00', ?, ?, ?)",
                     (order_id, scan_id, pack["currency"], pack["consent_at"], pack["is_test"]))
    return True


def redeemed(conn, pack_id):
    cur = conn.execute("SELECT s.domain, s.grade, s.report_token, o.created_at FROM orders o JOIN scans s ON s.id = o.scan_id "
                       "WHERE o.order_id LIKE ? ORDER BY o.created_at DESC", (f"pack:{pack_id}:%",))
    return [dict(r) for r in cur]


def revenue(conn):
    """إيراد الباقات الحقيقية المدفوعة (لا اختبارات)."""
    return conn.execute("SELECT COUNT(*), COALESCE(SUM(CAST(amount AS REAL)), 0) FROM packs "
                        "WHERE status = 'COMPLETED' AND is_test = 0").fetchone()


_RECEIPT = {
    "en": ("Your Quantum Aether agency pack: {credits} full reports",
           "Thank you for your purchase.\n\nOrder: {order_id}\nAmount: {amount} {currency} (one-time, no subscription)\n"
           "Included: {credits} full post-quantum TLS reports, no expiry.\n\nYour private pack link (keep it safe, anyone with it can "
           "use your reports):\n{pack_url}\n\nOpen it, enter any domain, and its full report opens immediately.\n\nQuantum Aether · {base}"),
    "ar": ("باقة الوكالات من الأثير الكمومي: {credits} تقارير كاملة",
           "شكراً لشرائك.\n\nالطلب: {order_id}\nالمبلغ: {amount} {currency} (دفعة واحدة، بلا اشتراك)\n"
           "المشمول: {credits} تقارير كاملة لجاهزية TLS ما بعد الكم، بلا تاريخ انتهاء.\n\nرابط باقتك الخاص (احفظه، فمن يملكه يستطيع "
           "استخدام تقاريرك):\n{pack_url}\n\nافتحه واكتب أي نطاق، فيُفتح تقريره الكامل فوراً.\n\nالأثير الكمومي · {base}"),
    "de": ("Ihr Quantum-Aether-Agenturpaket: {credits} vollständige Berichte",
           "Vielen Dank für Ihren Kauf.\n\nBestellung: {order_id}\nBetrag: {amount} {currency} (einmalig, kein Abonnement)\n"
           "Enthalten: {credits} vollständige Post-Quanten-TLS-Berichte, ohne Ablaufdatum.\n\nIhr privater Paket-Link (gut aufbewahren; "
           "wer ihn hat, kann Ihre Berichte nutzen):\n{pack_url}\n\nÖffnen, eine Domain eingeben, und der vollständige Bericht öffnet "
           "sich sofort.\n\nQuantum Aether · {base}"),
}


def receipt_email(lang, pack, pack_url, base):
    subject, body = _RECEIPT[lang if lang in _RECEIPT else "en"]
    fields = dict(credits=pack["credits"], order_id=pack["order_id"], amount=pack["amount"], currency=pack["currency"],
                  pack_url=pack_url, base=base)
    return subject.format(**fields), body.format(**fields)
