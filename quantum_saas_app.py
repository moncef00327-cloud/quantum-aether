# quantum_saas_app.py
# تطبيق الويب: فحص جاهزية HTTPS لما بعد الكم (مجاني) + تقرير كامل مدفوع عبر PayPal،
# والدفع يُتحقق منه على الخادم مع PayPal قبل فتح التقرير.
#
# التشغيل المحلي:  python quantum_saas_app.py   ثم افتح http://127.0.0.1:5000
# الإنتاج: gunicorn quantum_saas_app:app خلف nginx (انظر مجلد deploy/)
import datetime as dt
import functools
import glob
import hashlib
import hmac
import json
import logging
import os
import secrets

import requests
from flask import (Blueprint, Flask, Response, abort, current_app, g, jsonify, redirect,
                   render_template, request, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

import bio_archive_report
import dna_encode
import i18n
import quantum_vuln_scanner
import sales_db
from paypal_client import PayPalClient, PayPalError, verify_capture

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger("quantum_saas")
bp = Blueprint("site", __name__)

# زواحف الذكاء الاصطناعي مذكورة صراحة؛ كلها في مجموعة واحدة مع "*" لتنطبق عليها قواعد الحجب نفسها.
AI_CRAWLERS = ["GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "Claude-SearchBot",
               "anthropic-ai", "PerplexityBot", "Perplexity-User", "Google-Extended", "Bingbot", "cohere-ai"]


def _config_from_env():
    env = os.environ.get
    return {
        "DATA_DIR": env("QS_DATA_DIR", os.path.join(BASE_DIR, "instance")),
        "PUBLIC_URL": env("QS_PUBLIC_URL", "").rstrip("/"),
        "HASH_SALT": env("QS_HASH_SALT", ""),
        "ADMIN_PASSWORD_HASH": env("QS_ADMIN_PASSWORD_HASH", ""),
        "PRICE": env("QS_PRICE", "49.00"),
        "CURRENCY": env("QS_CURRENCY", "USD"),
        "SCANS_PER_HOUR": int(env("QS_SCANS_PER_HOUR", "10")),
        "GLOBAL_SCANS_PER_HOUR": int(env("QS_GLOBAL_SCANS_PER_HOUR", "300")),
        "TRUSTED_PROXIES": int(env("QS_TRUSTED_PROXIES", "1")),
        "PAYPAL_CLIENT_ID": env("PAYPAL_CLIENT_ID", ""),
        "PAYPAL_CLIENT_SECRET": env("PAYPAL_CLIENT_SECRET", ""),
        "PAYPAL_ENV": env("PAYPAL_ENV", "live"),
    }


def create_app(overrides=None, scanner=None, paypal=None):
    app = Flask(__name__)
    app.config.update(_config_from_env())
    app.config.update(overrides or {})
    if not app.config["HASH_SALT"]:
        app.config["HASH_SALT"] = secrets.token_hex(16)
    proxies = app.config["TRUSTED_PROXIES"]
    if proxies:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies)
    if paypal is None and app.config["PAYPAL_CLIENT_ID"] and app.config["PAYPAL_CLIENT_SECRET"]:
        paypal = PayPalClient(app.config["PAYPAL_CLIENT_ID"], app.config["PAYPAL_CLIENT_SECRET"], app.config["PAYPAL_ENV"])
    app.extensions["scanner"] = scanner or quantum_vuln_scanner.scan
    app.extensions["paypal"] = paypal
    app.register_blueprint(bp)
    return app


# ---------------------------------------------------------------- أدوات مشتركة

def db():
    if "db" not in g:
        os.makedirs(current_app.config["DATA_DIR"], exist_ok=True)
        g.db = sales_db.connect(os.path.join(current_app.config["DATA_DIR"], "quantum_saas.db"))
    return g.db


@bp.teardown_app_request
def _close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def current_lang():
    lang = request.args.get("lang")
    if lang in i18n.TEXTS:
        return lang
    return request.accept_languages.best_match(["en", "ar"]) or "en"


def texts():
    return i18n.TEXTS[current_lang()]


@bp.app_context_processor
def _inject():
    lang = current_lang()
    return {"t": i18n.TEXTS[lang], "lang": lang, "other_lang": "en" if lang == "ar" else "ar"}


def public_base():
    return current_app.config["PUBLIC_URL"] or request.url_root.rstrip("/")


def client_hash():
    salt = current_app.config["HASH_SALT"].encode()
    return hmac.new(salt, (request.remote_addr or "").encode(), hashlib.sha256).hexdigest()[:32]


def payments_enabled():
    return current_app.extensions["paypal"] is not None


def is_api_request():
    return request.path.startswith("/api/")


def perform_scan(raw_domain):
    conn, chash = db(), client_hash()
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cfg = current_app.config
    if (sales_db.count_attempts_since(conn, since, chash) >= cfg["SCANS_PER_HOUR"]
            or sales_db.count_attempts_since(conn, since) >= cfg["GLOBAL_SCANS_PER_HOUR"]):
        abort(429)
    sales_db.record_attempt(conn, chash)
    result = current_app.extensions["scanner"](raw_domain)
    scan_id = secrets.token_urlsafe(9)
    sales_db.create_scan(conn, scan_id, secrets.token_urlsafe(32), result, chash)
    return scan_id, result


def scan_summary(scan_id, result):
    kx, cert = result["key_exchange"], result["certificate"]
    return {
        "scan_id": scan_id,
        "domain": result["domain"],
        "grade": result["grade"],
        "scanned_at": result["scanned_at"],
        "tls_version": kx.get("version") or cert.get("negotiated_version"),
        "key_exchange_group": kx.get("group"),
        "post_quantum_key_exchange": bool(kx.get("pq")),
        "certificate_key": f"{cert.get('key_algorithm')}-{cert.get('key_bits')}",
        "certificate_valid": bool(cert.get("verified")),
        "findings_in_full_report": len(result["findings"]),
        "scan_url": public_base() + url_for(".scan_page", scan_id=scan_id),
        "full_report_price": {"amount": current_app.config["PRICE"], "currency": current_app.config["CURRENCY"]},
    }


def report_url(scan):
    return url_for(".report", token=scan["report_token"], lang=current_lang())


def paid_scan_or_404(token):
    scan = sales_db.get_scan_by_report_token(db(), token)
    if not scan or not sales_db.is_scan_paid(db(), scan["id"]):
        abort(404)
    return scan


def _load_results(pattern):
    loaded = []
    for path in sorted(glob.glob(os.path.join(BASE_DIR, "results", pattern))):
        with open(path, encoding="utf-8") as f:
            loaded.append(json.load(f))
    return loaded


@functools.lru_cache(maxsize=1)
def research_data():
    experiments = _load_results("ghz_*.json")
    # نعرض قياسات الدقة من العتاد الحقيقي فقط؛ المحاكاة تبقى في المستودع للتوثيق.
    fidelity_runs = _load_results("fidelity_ghz_hardware_*.json")
    dna_stats = None
    sequence_path = os.path.join(BASE_DIR, bio_archive_report.DEFAULT_SEQUENCE)
    if os.path.exists(sequence_path):
        with open(sequence_path, encoding="ascii") as f:
            dna_stats = dna_encode.sequence_stats("".join(line for line in f.read().splitlines() if not line.startswith(">")))
    return experiments, fidelity_runs, dna_stats


# ---------------------------------------------------------------- الصفحات

@bp.get("/")
def index():
    return render_template("index.html", error=None, domain="")


@bp.post("/scan")
def scan_form():
    raw = request.form.get("domain", "")
    try:
        scan_id, _ = perform_scan(raw)
    except quantum_vuln_scanner.ScanError as exc:
        return render_template("index.html", error=texts()["errors"].get(exc.code, str(exc)), domain=raw), 400
    return redirect(url_for(".scan_page", scan_id=scan_id, lang=current_lang()), code=303)


@bp.get("/scan/<scan_id>")
def scan_page(scan_id):
    scan = sales_db.get_scan(db(), scan_id) or abort(404)
    cfg = current_app.config
    return render_template(
        "scan.html", scan=scan, r=scan["result"], paid=sales_db.is_scan_paid(db(), scan_id),
        payments_enabled=payments_enabled(), paypal_client_id=cfg["PAYPAL_CLIENT_ID"],
        price=cfg["PRICE"], currency=cfg["CURRENCY"],
    )


@bp.get("/report/<token>")
def report(token):
    scan = paid_scan_or_404(token)
    lang = current_lang()
    findings = [dict(f, text=i18n.finding_text(f, lang)) for f in scan["result"]["findings"]]
    return render_template("report.html", scan=scan, r=scan["result"], findings=findings,
                           remediation=i18n.REMEDIATION, token=token)


@bp.get("/report/<token>/dna.txt")
def report_dna(token):
    scan = paid_scan_or_404(token)
    payload = json.dumps(scan["result"], ensure_ascii=False, indent=2).encode("utf-8")
    name = f"pqc-report-{scan['domain']}.json"
    return Response(bio_archive_report.to_fasta(name, payload), mimetype="text/plain",
                    headers={"Content-Disposition": f'attachment; filename="{name}.fasta.txt"'})


@bp.get("/research")
def research():
    experiments, fidelity_runs, dna_stats = research_data()
    return render_template("research.html", experiments=experiments, fidelity_runs=fidelity_runs, dna_stats=dna_stats)


@bp.get("/admin")
def admin():
    password_hash = current_app.config["ADMIN_PASSWORD_HASH"]
    if not password_hash:
        abort(404)
    auth = request.authorization
    if not (auth and auth.username == "admin" and check_password_hash(password_hash, auth.password or "")):
        return Response(status=401, headers={"WWW-Authenticate": 'Basic realm="Quantum Aether admin", charset="UTF-8"'})
    conn = db()
    return render_template("admin.html", stats=sales_db.stats(conn),
                           orders=sales_db.recent_orders(conn), scans=sales_db.recent_scans(conn))


# ---------------------------------------------------------------- API

@bp.post("/api/scan")
def api_scan():
    data = request.get_json(silent=True) or {}
    try:
        scan_id, result = perform_scan(str(data.get("domain", "")))
    except quantum_vuln_scanner.ScanError as exc:
        return jsonify(error=exc.code, message=str(exc)), 400
    return jsonify(scan_summary(scan_id, result)), 201


def key_size_assessment(key_size):
    cfg = current_app.config
    return {
        "key_size_bits": key_size,
        "algorithm": "RSA",
        "classical_security": "weak" if key_size < 2048 else "acceptable",
        "quantum_vulnerable": True,
        "quantum_note": "Shor's algorithm breaks RSA and elliptic-curve keys of any size; a larger key does not give "
                        "quantum safety. What protects recorded traffic is a post-quantum key exchange.",
        "published_estimate": "RSA-2048: under one million noisy physical qubits in under a week (Gidney, 2025). "
                              "No current quantum computer is close to that.",
        "recommended_action": "Enable hybrid post-quantum key exchange X25519MLKEM768 (ML-KEM, FIPS 203) on your TLS "
                              "servers; plan ML-DSA (FIPS 204) certificates once CAs support them.",
        "scan_your_domain": {"method": "POST", "url": public_base() + url_for(".api_v1_quantum_scan"),
                             "body": {"domain": "example.com"}},
        "full_report": {"price": cfg["PRICE"], "currency": cfg["CURRENCY"],
                        "how": "Scan a domain, then POST /api/v1/orders with its scan_id to get a PayPal approval "
                               "link; once the payer approves it, the report link appears at the order's status_url."},
    }


@bp.post("/api/v1/quantum-scan")
def api_v1_quantum_scan():
    """واجهة الوكلاء: domain يجري فحصاً حقيقياً، وkey_size وحده يعيد تقييماً لحجم المفتاح دون فحص."""
    data = request.get_json(silent=True) or {}
    if data.get("domain"):
        return api_scan()
    try:
        key_size = int(data.get("key_size", 2048))
    except (TypeError, ValueError):
        return jsonify(error="invalid_key_size"), 400
    if not 512 <= key_size <= 16384:
        return jsonify(error="invalid_key_size"), 400
    return jsonify(key_size_assessment(key_size))


@bp.get("/api/scan/<scan_id>")
def api_scan_get(scan_id):
    scan = sales_db.get_scan(db(), scan_id)
    if not scan:
        return jsonify(error="scan_not_found"), 404
    return jsonify(scan_summary(scan_id, scan["result"]))


@bp.post("/api/paypal/orders")
def paypal_create_order():
    paypal = current_app.extensions["paypal"]
    if paypal is None:
        return jsonify(error="payments_disabled"), 503
    data = request.get_json(silent=True) or {}
    conn = db()
    scan = sales_db.get_scan(conn, str(data.get("scan_id", "")))
    if not scan:
        return jsonify(error="scan_not_found"), 404
    if sales_db.is_scan_paid(conn, scan["id"]):
        return jsonify(error="already_paid"), 409
    cfg = current_app.config
    try:
        order = paypal.create_order(scan["id"], cfg["PRICE"], cfg["CURRENCY"],
                                    f"Post-quantum readiness report: {scan['domain']}")
    except (PayPalError, requests.RequestException) as exc:
        log.warning("PayPal create order failed: %s", exc)
        return jsonify(error="paypal_unavailable"), 502
    sales_db.create_order(conn, order["id"], scan["id"], cfg["PRICE"], cfg["CURRENCY"])
    return jsonify(id=order["id"]), 201


def capture_and_record(order_id):
    """يلتقط طلب PayPal أنشأه خادمنا ويتحقق منه ويسجله. يعيد (النتيجة، الفحص)."""
    paypal = current_app.extensions["paypal"]
    if paypal is None:
        return "DISABLED", None
    conn = db()
    row = sales_db.get_order(conn, order_id)
    if not row:  # طلب لم ينشئه خادمنا (مثلاً بمبلغ مختلف من المتصفح): مرفوض
        return "NOT_FOUND", None
    scan = sales_db.get_scan(conn, row["scan_id"])
    if row["status"] == "COMPLETED":
        return "COMPLETED", scan
    try:
        order = paypal.capture_order(order_id)
    except PayPalError as exc:
        if exc.issue == "INSTRUMENT_DECLINED":
            return "INSTRUMENT_DECLINED", scan
        if exc.issue != "ORDER_ALREADY_CAPTURED":
            log.warning("PayPal capture failed for %s: %s (%s)", order_id, exc, exc.issue)
            return "CAPTURE_FAILED", scan
        try:
            order = paypal.get_order(order_id)
        except (PayPalError, requests.RequestException):
            return "UNAVAILABLE", scan
    except requests.RequestException:
        return "UNAVAILABLE", scan
    status, capture_id = verify_capture(order, scan["id"], row["amount"], row["currency"])
    sales_db.update_order(conn, order_id, status, capture_id)
    if status == "FAILED":
        log.error("PayPal capture for %s did not match the expected amount/reference", order_id)
        return "VERIFICATION_FAILED", scan
    return status, scan


CAPTURE_ERRORS = {
    "DISABLED": ("payments_disabled", 503),
    "NOT_FOUND": ("order_not_found", 404),
    "INSTRUMENT_DECLINED": ("INSTRUMENT_DECLINED", 422),
    "CAPTURE_FAILED": ("capture_failed", 502),
    "UNAVAILABLE": ("paypal_unavailable", 502),
    "VERIFICATION_FAILED": ("verification_failed", 402),
}


@bp.post("/api/paypal/orders/<order_id>/capture")
def paypal_capture_order(order_id):
    outcome, scan = capture_and_record(order_id)
    if outcome == "COMPLETED":
        return jsonify(status=outcome, report_url=report_url(scan))
    if outcome == "PENDING":
        return jsonify(status=outcome), 202
    error, code = CAPTURE_ERRORS[outcome]
    return jsonify(error=error), code


# ---------------------------------------------------------------- دفع الوكلاء (رابط موافقة PayPal)

@bp.post("/api/v1/orders")
def api_v1_create_order():
    """ينشئ طلب PayPal ويعيد رابط الموافقة؛ بعد الموافقة يعيد PayPal المشتري إلى /paypal/return فيُلتقط الدفع."""
    paypal = current_app.extensions["paypal"]
    if paypal is None:
        return jsonify(error="payments_disabled"), 503
    data = request.get_json(silent=True) or {}
    conn = db()
    scan = sales_db.get_scan(conn, str(data.get("scan_id", "")))
    if not scan:
        return jsonify(error="scan_not_found"), 404
    if sales_db.is_scan_paid(conn, scan["id"]):
        return jsonify(error="already_paid"), 409
    cfg, base = current_app.config, public_base()
    try:
        order = paypal.create_order(scan["id"], cfg["PRICE"], cfg["CURRENCY"],
                                    f"Post-quantum readiness report: {scan['domain']}",
                                    return_url=base + url_for(".paypal_return"),
                                    cancel_url=base + url_for(".scan_page", scan_id=scan["id"]))
    except (PayPalError, requests.RequestException) as exc:
        log.warning("PayPal create order failed: %s", exc)
        return jsonify(error="paypal_unavailable"), 502
    approve_url = next((link["href"] for link in order.get("links", [])
                        if link.get("rel") in ("payer-action", "approve")), None)
    if not approve_url:
        return jsonify(error="paypal_unavailable"), 502
    sales_db.create_order(conn, order["id"], scan["id"], cfg["PRICE"], cfg["CURRENCY"])
    return jsonify(order_id=order["id"], approve_url=approve_url,
                   status_url=base + url_for(".api_v1_order_status", order_id=order["id"]),
                   amount=cfg["PRICE"], currency=cfg["CURRENCY"]), 201


@bp.get("/api/v1/orders/<order_id>")
def api_v1_order_status(order_id):
    row = sales_db.get_order(db(), order_id)
    if not row:
        return jsonify(error="order_not_found"), 404
    body = {"order_id": order_id, "status": row["status"], "amount": row["amount"], "currency": row["currency"]}
    if row["status"] == "COMPLETED":
        scan = sales_db.get_scan(db(), row["scan_id"])
        body["report_url"] = public_base() + url_for(".report", token=scan["report_token"])
    return jsonify(body)


@bp.get("/paypal/return")
def paypal_return():
    outcome, scan = capture_and_record(request.args.get("token", ""))
    if outcome == "COMPLETED":
        return redirect(report_url(scan), code=303)
    if outcome == "NOT_FOUND":
        abort(404)
    message = texts()["pay_pending" if outcome == "PENDING" else "pay_error"]
    return render_template("error.html", message=message), 202 if outcome == "PENDING" else 400


# ---------------------------------------------------------------- ملفات للاكتشاف والصحة

@bp.get("/healthz")
def healthz():
    return jsonify(status="ok", payments=payments_enabled())


@bp.get("/favicon.ico")
def favicon():
    return current_app.send_static_file("favicon.svg")


@bp.get("/robots.txt")
def robots():
    agents = "".join(f"User-agent: {name}\n" for name in [*AI_CRAWLERS, "*"])
    body = (agents + "Allow: /\nDisallow: /admin\nDisallow: /report/\nDisallow: /api/paypal/\n\n"
            f"Sitemap: {public_base()}/sitemap.xml\n")
    return Response(body, mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap():
    base = public_base()
    urls = [f"{base}/?lang=en", f"{base}/?lang=ar", f"{base}/research?lang=en", f"{base}/research?lang=ar"]
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"  <url><loc>{u.replace('&', '&amp;')}</loc></url>\n" for u in urls) + "</urlset>\n")
    return Response(body, mimetype="application/xml")


@bp.get("/openapi.yaml")
def openapi():
    with open(os.path.join(BASE_DIR, "openapi.yaml"), encoding="utf-8") as f:
        return Response(f.read().replace("{{PUBLIC_URL}}", public_base()), mimetype="application/yaml")


@bp.get("/llms.txt")
def llms_txt():
    return Response(render_template("llms.txt", base=public_base(), price=current_app.config["PRICE"]),
                    mimetype="text/plain")


@bp.after_app_request
def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.path.startswith(("/report/", "/admin")):
        # رابط التقرير يحمل مفتاح الوصول: لا نخزنه ولا نرسله في Referer ولا نسمح بالفهرسة.
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Robots-Tag"] = "noindex"
        response.headers["Content-Security-Policy"] = ("default-src 'self'; img-src 'self' data:; "
                                                       "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
    return response


def _error(status, key):
    if is_api_request():
        return jsonify(error=key), status
    return render_template("error.html", message=texts()[key]), status


@bp.app_errorhandler(404)
def _not_found(_e):
    return _error(404, "not_found")


@bp.app_errorhandler(429)
def _rate_limited(_e):
    return _error(429, "rate_limited")


@bp.app_errorhandler(500)
def _server_error(_e):
    return _error(500, "server_error")


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="127.0.0.1", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
