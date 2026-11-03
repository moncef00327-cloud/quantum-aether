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
import re
import secrets
import urllib.parse

import requests
from flask import (Blueprint, Flask, Response, abort, current_app, g, jsonify, redirect,
                   render_template, request, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

import bio_archive_report
import crypto_pay
import dna_encode
import analytics_db
import guides
import legal
import monitor
import monitor_db
import i18n
import quantum_vuln_scanner
import sales_db
from mailer import Mailer
from paypal_client import SUBSCRIPTION_LIVE_STATUSES, PayPalClient, PayPalError, verify_capture, verify_subscription

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
        "PAYPAL_PLAN_STARTER": env("PAYPAL_PLAN_STARTER", ""),
        "PAYPAL_PLAN_BUSINESS": env("PAYPAL_PLAN_BUSINESS", ""),
        "RESEND_API_KEY": env("RESEND_API_KEY", ""),
        "MAIL_FROM": env("QS_MAIL_FROM", ""),
        "OWNER_EMAIL": env("QS_OWNER_EMAIL", ""),
        "REPLY_TO": env("QS_REPLY_TO", ""),
        "USDT_POLYGON_ADDR": env("QS_USDT_POLYGON_ADDR", ""),
        "USDC_ARBITRUM_ADDR": env("QS_USDC_ARBITRUM_ADDR", ""),
    }


def create_app(overrides=None, scanner=None, paypal=None, mailer=None, chain=None):
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
    app.extensions["chain"] = chain or crypto_pay.ChainClient()
    app.extensions["mailer"] = mailer or Mailer(app.config["RESEND_API_KEY"], app.config["MAIL_FROM"],
                                                     app.config["REPLY_TO"])
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


def german_allowed():
    return request.endpoint in i18n.DE_ENDPOINTS


def current_lang():
    """لغة الصفحة: en وar في كل الصفحات، وde فقط في الصفحات المترجمة (وإلا الإنجليزية)."""
    lang = request.args.get("lang")
    if lang == "de":
        return "de" if german_allowed() else "en"
    if lang in ("en", "ar"):
        return lang
    return request.accept_languages.best_match(["en", "ar"] + (["de"] if german_allowed() else [])) or "en"


# الصفحات التي لها نسخة ألمانية فعلية (لمبدّل اللغة وhreflang وخريطة الموقع).
DE_PAGES = {"site.index", "site.study", "site.monitoring"}


def texts():
    return i18n.TEXTS[current_lang()]


@bp.app_context_processor
def _inject():
    lang = current_lang()
    return {"t": i18n.TEXTS[lang], "lang": lang, "other_lang": "en" if lang == "ar" else "ar",
            "legal_lang": "de" if lang == "de" else "en", "lang_names": i18n.LANG_NAMES,
            "page_langs": ["en", "ar", "de"] if request.endpoint in DE_PAGES else ["en", "ar"]}


def public_base():
    return current_app.config["PUBLIC_URL"] or request.url_root.rstrip("/")


ADMIN_COOKIE = "qa_admin"


def admin_cookie_value():
    """قيمة موقّعة بملح الخادم: لا يمكن تخمينها، وتُستعمل فقط لاستبعاد زيارات المدير من الإحصاءات."""
    return hmac.new(current_app.config["HASH_SALT"].encode(), b"admin-visitor", hashlib.sha256).hexdigest()


def is_admin_visitor():
    value = request.cookies.get(ADMIN_COOKIE, "")
    return bool(value) and hmac.compare_digest(value, admin_cookie_value())


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
    sales_db.create_scan(conn, scan_id, secrets.token_urlsafe(32), result, chash, is_test=is_admin_visitor())
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

def home_jsonld():
    base, t = public_base(), texts()
    return [
        {"@context": "https://schema.org", "@type": "WebSite", "name": t["brand"], "url": base,
         "inLanguage": current_lang(),
         "potentialAction": {"@type": "SearchAction", "target": base + "/site/{search_term_string}",
                             "query-input": "required name=search_term_string"}},
        {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": t["brand"],
         "applicationCategory": "SecurityApplication", "operatingSystem": "Web",
         "description": t["hero_sub"], "url": base,
         "offers": [{"@type": "Offer", "price": "0", "priceCurrency": "USD", "name": t["free_title"]},
                    {"@type": "Offer", "price": current_app.config["PRICE"], "priceCurrency": "USD", "name": t["paid_title"]}]},
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q,
                         "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in t["faq"]]},
    ]


@bp.get("/")
def index():
    return render_template("index.html", error=None, domain=request.args.get("domain", "")[:253],
                           jsonld=home_jsonld())


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
        crypto_networks=crypto_pay.enabled_networks(cfg), badge=badge_snippets(scan["result"]["domain"]),
        price=cfg["PRICE"], currency=cfg["CURRENCY"],
    )


@bp.get("/report/<token>")
def report(token):
    scan = paid_scan_or_404(token)
    lang = current_lang()
    findings = [dict(f, text=i18n.finding_text(f, lang)) for f in scan["result"]["findings"]]
    return render_template("report.html", scan=scan, r=scan["result"], findings=findings,
                           remediation=i18n.REMEDIATION, token=token)


SAMPLE_FILE = os.path.join(BASE_DIR, "data", "sample_report.json")


@functools.lru_cache(maxsize=1)
def sample_result():
    with open(SAMPLE_FILE, encoding="utf-8") as f:
        return json.load(f)


@bp.get("/sample-report")
def sample_report():
    """تقرير كامل حقيقي (فحص github.com) يُعرض كما يصل للمشتري، ليرى الزائر ما يدفع مقابله."""
    r = sample_result()
    findings = [dict(f, text=i18n.finding_text(f, current_lang())) for f in r["findings"]]
    return render_template("report.html", scan=None, r=r, findings=findings, remediation=i18n.REMEDIATION,
                           token=None, sample=True)


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


# ---------------------------------------------------------------- المحتوى: الأدلة والدراسة

STUDY_FILE = os.path.join(BASE_DIR, "data", "pq_study_top1000.json")
# مواقع معروفة تظهر في قسم «مواقع كبيرة بلا تبادل مقاوم للكم» إن كانت في النتائج بلا PQ.
STUDY_NOTABLE = ["amazon.com", "github.com", "wikipedia.org", "netflix.com", "bing.com", "live.com",
                 "office.com", "azure.com", "sharepoint.com", "mail.ru", "dzen.ru", "paypal.com",
                 "apple.com", "icloud.com", "yahoo.com", "zoom.us", "adobe.com", "ebay.com"]


@functools.lru_cache(maxsize=1)
def study_data():
    with open(STUDY_FILE, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- الصفحات القانونية (النمسا)

@bp.get("/<any(impressum, datenschutz, agb):slug>")
def legal_page(slug):
    lang = request.args.get("lang")
    lang = lang if lang in legal.LANGS else (request.accept_languages.best_match(list(legal.LANGS)) or "de")
    other = "en" if lang == "de" else "de"
    # الصفحة بالألمانية أو الإنجليزية: نمرر لغة القالب صراحة فتتجاوز لغة الموقع (عربي/إنجليزي).
    t = dict(i18n.TEXTS["en"], dir="ltr", other_lang="English" if lang == "de" else "Deutsch")
    return render_template("legal.html", page=legal.PAGES[slug][lang], t=t, lang=lang, other_lang=other,
                           legal_lang=lang, page_langs=list(legal.LANGS))


@bp.get("/guides")
def guides_index():
    lang = current_lang()
    items = [(slug, g[lang]) for slug, g in guides.GUIDES.items()]
    return render_template("guides_index.html", items=items)


@bp.get("/guides/<slug>")
def guide(slug):
    g = guides.GUIDES.get(slug) or abort(404)
    page = g[current_lang()]
    return render_template("guide.html", slug=slug, page=page, updated=g["updated"])


@bp.get("/study/top-1000-post-quantum-tls")
def study():
    d = study_data()
    pct = round(100 * d["pq"] / d["reachable"], 1) if d["reachable"] else 0
    by_domain = {s["domain"]: s for s in d["sites"]}
    notable = [by_domain[n] for n in STUDY_NOTABLE if n in by_domain and not by_domain[n]["pq"]]
    notable.sort(key=lambda s: s["rank"])
    return render_template("study.html", d=d, pct=pct, notable=notable)


@bp.get("/study/top-1000-post-quantum-tls.json")
def study_json():
    return current_app.response_class(json.dumps(study_data(), ensure_ascii=False), mimetype="application/json")


# ---------------------------------------------------------------- صفحة لكل نطاق + المقارنة + CLI

def study_by_domain():
    return {s["domain"]: s for s in study_data()["sites"]}


def known_result_for(domain):
    """نتيجة معروفة للنطاق دون إجراء فحص جديد: آخر فحص خلال 30 يوماً، وإلا بيانات الدراسة.
    يعيد (ملخص، المصدر) أو (None, None)."""
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=BADGE_MAX_AGE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan = sales_db.latest_scan_for_domain(db(), domain, since)
    if scan:
        r = scan["result"]
        return ({"domain": domain, "grade": r["grade"], "group": r["key_exchange"].get("group"),
                 "tls": r["key_exchange"].get("version") or r["certificate"].get("negotiated_version"),
                 "pq": bool(r["key_exchange"].get("pq")), "scanned_at": r["scanned_at"]}, "scan")
    site = study_by_domain().get(domain)
    if site:
        return (dict(site, scanned_at=study_data()["scanned_on"]), "study")
    return (None, None)


@bp.get("/site/<domain>")
def site_page(domain):
    """صفحة عامة قابلة للفهرسة لكل نطاق: تعرض ما نعرفه عنه وتدعو لفحص حيّ. لا تُجري فحصاً."""
    try:
        domain = quantum_vuln_scanner.normalize_domain(domain)
    except quantum_vuln_scanner.ScanError:
        abort(404)
    summary, source = known_result_for(domain)
    jsonld = None
    if summary:
        pq = "yes" if summary["pq"] else "no"
        jsonld = [{"@context": "https://schema.org", "@type": "WebPage",
                   "name": f"{domain} — post-quantum TLS readiness",
                   "url": public_base() + url_for(".site_page", domain=domain),
                   "inLanguage": current_lang(),
                   "about": {"@type": "WebSite", "name": domain, "url": f"https://{domain}"},
                   "description": f"{domain} TLS grade {summary['grade']}, key exchange {summary.get('group') or 'unknown'}, "
                                  f"post-quantum key exchange: {pq}."}]
    return render_template("site_page.html", domain=domain, summary=summary, source=source,
                           snippets=badge_snippets(domain) if summary else None, jsonld=jsonld)


@bp.get("/compare")
def compare():
    """مقارنة موقعين جنباً إلى جنب. الفحص حيّ ومحدود بنفس حد الفحوصات."""
    a = (request.args.get("a") or "").strip()
    b = (request.args.get("b") or "").strip()
    results, error = {}, None
    if a and b:
        pair = {}
        for key, raw in (("a", a), ("b", b)):
            try:
                _, result = perform_scan(raw)
                pair[key] = result
            except quantum_vuln_scanner.ScanError as exc:
                pair[key] = {"error": texts()["errors"].get(exc.code, str(exc)), "domain": raw}
        results = pair
    return render_template("compare.html", a=a, b=b, results=results, error=error)


@bp.get("/api/v1/scan")
def api_v1_scan_get():
    """فحص عبر GET ليسهل على أدوات سطر الأوامر والوكلاء: /api/v1/scan?domain=example.com
    مع ?format=text يعيد نصاً ملوّناً للطرفية (ANSI)."""
    try:
        scan_id, result = perform_scan(request.args.get("domain", ""))
    except quantum_vuln_scanner.ScanError as exc:
        if request.args.get("format") == "text":
            return Response(f"error: {exc}\n", mimetype="text/plain"), 400
        return jsonify(error=exc.code, message=str(exc)), 400
    if request.args.get("format") == "text":
        return Response(terminal_report(result), mimetype="text/plain; charset=utf-8")
    body = dict(scan_summary(scan_id, result), report_hint=public_base() + url_for(".scan_page", scan_id=scan_id))
    return jsonify(body)


def terminal_report(result):
    kx, cert = result["key_exchange"], result["certificate"]
    g = result["grade"]
    color = {"A": "32", "B": "36", "C": "33", "F": "31"}.get(g, "0")
    pq = "yes (hybrid ML-KEM)" if kx.get("pq") else "NO — classical, harvest-now-decrypt-later risk"
    base = current_app.config["PUBLIC_URL"] or "https://ather-quatum.cloud"
    lines = [
        "",
        f"  Quantum Aether — post-quantum TLS scan",
        f"  domain        {result['domain']}",
        f"  grade         \033[1;{color}m{g}\033[0m",
        f"  key exchange  {kx.get('group') or '-'}",
        f"  post-quantum  {pq}",
        f"  TLS           {kx.get('version') or cert.get('negotiated_version') or '-'}",
        f"  certificate   {cert.get('key_algorithm')}-{cert.get('key_bits')}",
        f"  full report   {base}/?domain={result['domain']}  (${current_app.config['PRICE']})",
        "",
    ]
    return "\n".join(lines)


@bp.get("/admin")
def admin():
    password_hash = current_app.config["ADMIN_PASSWORD_HASH"]
    if not password_hash:
        abort(404)
    auth = request.authorization
    if not (auth and auth.username == "admin" and check_password_hash(password_hash, auth.password or "")):
        return Response(status=401, headers={"WWW-Authenticate": 'Basic realm="Quantum Aether admin", charset="UTF-8"'})
    conn = db()
    response = current_app.make_response(render_template("admin.html", stats=sales_db.stats(conn),
                           orders=sales_db.recent_orders(conn), scans=sales_db.recent_scans(conn),
                           subs=monitor_db.stats(conn, monitor.PLANS), accounts=monitor_db.recent_accounts(conn),
                           traffic=analytics_db.summary(conn, (dt.date.today() - dt.timedelta(days=13)).isoformat()),
                           scans_daily=sales_db.scans_per_day(conn, (dt.date.today() - dt.timedelta(days=13)).isoformat())))
    # كوكي دائم لسنة: كل زيارات هذا المتصفح لا تُحسب في الإحصاءات.
    response.set_cookie(ADMIN_COOKIE, admin_cookie_value(), max_age=365 * 24 * 3600, httponly=True,
                        secure=request.is_secure, samesite="Lax")
    return response


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
    if data.get("consent") is not True:
        return jsonify(error="consent_required"), 400
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
    sales_db.create_order(conn, order["id"], scan["id"], cfg["PRICE"], cfg["CURRENCY"], consent_at=now_iso(),
                          is_test=is_admin_visitor())
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
    if data.get("consent_immediate_delivery") is not True:
        return jsonify(error="consent_required",
                       message="Set consent_immediate_delivery to true only after the payer has expressly agreed that "
                               "the report is delivered immediately and acknowledged losing the right of withdrawal."), 400
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
    sales_db.create_order(conn, order["id"], scan["id"], cfg["PRICE"], cfg["CURRENCY"], consent_at=now_iso(),
                          is_test=is_admin_visitor())
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


# ---------------------------------------------------------------- الدفع بالعملات المستقرة (USDT / USDC)

def _crypto_network_of(order_id):
    for key in crypto_pay.NETWORKS:
        if order_id.startswith(f"cx-{key}-"):
            return key
    return None


def _crypto_order_body(order_id, key, net, amount):
    base = public_base()
    return {"order_id": order_id, "network": key, "chain": net["chain"], "chain_id": net["chain_id"],
            "token": net["token"], "token_contract": net["contract"], "pay_to": net["address"],
            "amount": amount, "confirmations_required": net["confirmations"],
            "verify_url": base + url_for(".crypto_verify", order_id=order_id),
            "status_url": base + url_for(".api_v1_order_status", order_id=order_id),
            "instructions": f"Send exactly {amount} {net['token']} on {net['chain']} to {net['address']}, "
                            "then POST the transaction hash as {\"tx_hash\": \"0x...\"} to verify_url."}


@bp.post("/api/crypto/orders")
@bp.post("/api/v1/crypto/orders", endpoint="api_v1_crypto_create_order")
def crypto_create_order():
    """ينشئ طلب دفع بعملة مستقرة بمبلغ فريد. نفس المسار للبشر (صفحة النتيجة) ولوكلاء الذكاء الاصطناعي."""
    networks = crypto_pay.enabled_networks(current_app.config)
    if not networks:
        return jsonify(error="crypto_disabled"), 503
    data = request.get_json(silent=True) or {}
    if data.get("consent") is not True and data.get("consent_immediate_delivery") is not True:
        return jsonify(error="consent_required",
                       message="Set consent_immediate_delivery to true only after the payer has expressly agreed that "
                               "the report is delivered immediately and acknowledged losing the right of withdrawal."), 400
    key = str(data.get("network", ""))
    if key not in networks:
        return jsonify(error="unknown_network", networks=sorted(networks)), 400
    conn = db()
    scan = sales_db.get_scan(conn, str(data.get("scan_id", "")))
    if not scan:
        return jsonify(error="scan_not_found"), 404
    if sales_db.is_scan_paid(conn, scan["id"]):
        return jsonify(error="already_paid"), 409
    net = networks[key]
    amount = str(crypto_pay.unique_amount(current_app.config["PRICE"], sales_db.open_amounts(conn, net["token"])))
    order_id = f"cx-{key}-{secrets.token_urlsafe(9)}"
    sales_db.create_order(conn, order_id, scan["id"], amount, net["token"], consent_at=now_iso(),
                          is_test=is_admin_visitor())
    return jsonify(_crypto_order_body(order_id, key, net, amount)), 201


@bp.post("/api/crypto/orders/<order_id>/verify")
@bp.post("/api/v1/crypto/orders/<order_id>/verify", endpoint="api_v1_crypto_verify")
def crypto_verify(order_id):
    """يتحقق من المعاملة على الشبكة نفسها؛ لا يُفتح التقرير إلا بتحويل مؤكد للمبلغ إلى عنواننا."""
    conn = db()
    key = _crypto_network_of(order_id)
    row = sales_db.get_order(conn, order_id) if key else None
    if not row:
        return jsonify(error="order_not_found"), 404
    scan = sales_db.get_scan(conn, row["scan_id"])
    if row["status"] == "COMPLETED":
        return jsonify(status="COMPLETED", report_url=public_base() + url_for(".report", token=scan["report_token"]))
    net = crypto_pay.enabled_networks(current_app.config).get(key)
    if not net:
        return jsonify(error="crypto_disabled"), 503
    data = request.get_json(silent=True) or {}
    tx_hash = str(data.get("tx_hash", "")).strip().lower()
    if not crypto_pay.TX_RE.match(tx_hash):
        return jsonify(error="invalid_tx_hash"), 400
    used = sales_db.order_by_capture(conn, tx_hash)
    if used and used["order_id"] != order_id:
        return jsonify(error="tx_already_used"), 409
    created = dt.datetime.strptime(row["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    try:
        status, details = crypto_pay.verify_transfer(current_app.extensions["chain"], key, net, tx_hash,
                                                     net["address"], row["amount"], created.timestamp())
    except crypto_pay.ChainError as exc:
        log.warning("chain verification unavailable for %s: %s", order_id, exc)
        return jsonify(error="chain_unavailable"), 502
    if status in ("PENDING", "CONFIRMING"):
        return jsonify(dict(details, status=status, confirmations_required=net["confirmations"])), 202
    if status != "OK":
        return jsonify(dict(details, error=status.lower(), expected=row["amount"], token=net["token"])), 402
    try:
        sales_db.update_order(conn, order_id, "COMPLETED", tx_hash)
    except sales_db.sqlite3.IntegrityError:
        return jsonify(error="tx_already_used"), 409
    owner = current_app.config["OWNER_EMAIL"]
    if owner and not row["is_test"]:
        current_app.extensions["mailer"].send(
            owner, f"[Quantum Aether] Report paid: {row['amount']} {net['token']} — {scan['domain']}",
            f"Order: {order_id}\nAmount: {row['amount']} {net['token']} on {net['chain']}\n"
            f"To: {net['address']}\nTransaction: {net['explorer']}{tx_hash}")
    return jsonify(status="COMPLETED", report_url=public_base() + url_for(".report", token=scan["report_token"]))


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


# ---------------------------------------------------------------- اشتراك المراقبة الشهري

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,}$")
MANUAL_SCAN_INTERVAL = dt.timedelta(hours=1)


def now_iso():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def plan_ids():
    cfg = current_app.config
    return {name: cfg[p["env"]] for name, p in monitor.PLANS.items()}


def subscriptions_enabled():
    return current_app.extensions["paypal"] is not None and all(plan_ids().values())


def dashboard_url(token, lang):
    return f"{public_base()}/monitor/{token}?lang={lang}"


def account_or_404(token):
    account = monitor_db.get_account_by_token(db(), token)
    if not account or account["status"] == "PENDING":
        abort(404)
    return account


@bp.get("/monitoring")
def monitoring():
    cfg = current_app.config
    return render_template("monitoring.html", plans=monitor.PLANS, plan_ids=plan_ids(),
                           enabled=subscriptions_enabled(), paypal_client_id=cfg["PAYPAL_CLIENT_ID"],
                           currency=cfg["CURRENCY"], sent=request.args.get("sent"))


@bp.post("/api/monitor/signup")
def monitor_signup():
    """الخطوة 1: ينشئ حساباً معلقاً ويعيد معرّفه ليُرفق بالاشتراك في PayPal (custom_id)."""
    if not subscriptions_enabled():
        return jsonify(error="subscriptions_disabled"), 503
    data = request.get_json(silent=True) or {}
    email, plan = str(data.get("email", "")).strip().lower(), str(data.get("plan", ""))
    if plan not in monitor.PLANS:
        return jsonify(error="invalid_plan"), 400
    if not EMAIL_RE.match(email):
        return jsonify(error="invalid_email"), 400
    if data.get("consent") is not True:
        return jsonify(error="consent_required"), 400
    account_id, _token = monitor_db.create_account(db(), email, plan, current_lang(), consent_at=now_iso())
    return jsonify(account_id=account_id, plan_id=plan_ids()[plan]), 201


@bp.post("/api/monitor/activate")
def monitor_activate():
    """الخطوة 2: بعد موافقة المشترك في PayPal نتحقق من الاشتراك على خادم PayPal ثم نفعّل الحساب."""
    paypal = current_app.extensions["paypal"]
    if not subscriptions_enabled():
        return jsonify(error="subscriptions_disabled"), 503
    data = request.get_json(silent=True) or {}
    conn = db()
    account = monitor_db.get_account(conn, str(data.get("account_id", "")))
    subscription_id = str(data.get("subscription_id", ""))
    if not account or not subscription_id:
        return jsonify(error="account_not_found"), 404
    if account["status"] != "PENDING":
        return jsonify(error="already_activated"), 409
    try:
        subscription = paypal.get_subscription(subscription_id)
    except (PayPalError, requests.RequestException) as exc:
        log.warning("PayPal subscription lookup failed for %s: %s", subscription_id, exc)
        return jsonify(error="paypal_unavailable"), 502
    status = verify_subscription(subscription, plan_ids()[account["plan"]], account["id"])
    if status not in SUBSCRIPTION_LIVE_STATUSES:
        log.warning("Subscription %s for %s not active: %s", subscription_id, account["id"], status)
        return jsonify(error="subscription_not_active", status=status), 402
    monitor_db.set_status(conn, account["id"], "ACTIVE", subscription_id)
    token = monitor_db.rotate_token(conn, account["id"])  # الرمز يُكشف مرة واحدة فقط، هنا
    url = dashboard_url(token, account["lang"])
    subject, text = monitor.welcome_email(account, url)
    mailer = current_app.extensions["mailer"]
    mailer.send(account["email"], subject, text)
    monitor.notify_owner(mailer, current_app.config["OWNER_EMAIL"], "New subscription",
                         dict(account, subscription_id=subscription_id))
    return jsonify(dashboard_url=url)


@bp.post("/monitoring/login")
def monitor_login():
    """يرسل رابط لوحة التحكم إلى بريد مشترك فعّال. الرد نفسه دائماً حتى لا يُكشف من هو مشترك."""
    email = request.form.get("email", "").strip().lower()
    conn = db()
    # بلا بريد مفعّل لا نغيّر الرمز، وإلا فقد المشترك رابطه الحالي دون أن يصله بديل.
    if EMAIL_RE.match(email) and current_app.extensions["mailer"].enabled:
        for account in monitor_db.active_accounts_by_email(conn, email):
            token = monitor_db.rotate_token(conn, account["id"])
            subject, text = monitor.welcome_email(account, dashboard_url(token, account["lang"]))
            current_app.extensions["mailer"].send(email, subject, text)
    return redirect(url_for(".monitoring", lang=current_lang(), sent=1, _anchor="login"), code=303)


@bp.get("/monitor/<token>")
def monitor_dashboard(token):
    account = account_or_404(token)
    conn = db()
    alerts = monitor_db.recent_alerts(conn, account["id"])
    lang = current_lang()
    for a in alerts:
        a["text"] = monitor.alert_text(a, lang)
    return render_template("monitor_dashboard.html", account=account, token=token,
                           domains=monitor_db.list_domains(conn, account["id"]), alerts=alerts,
                           plan=monitor.PLANS[account["plan"]], notice=request.args.get("n"))


def _back(token, notice):
    return redirect(url_for(".monitor_dashboard", token=token, lang=current_lang(), n=notice), code=303)


@bp.post("/monitor/<token>/domains")
def monitor_add_domains(token):
    account = account_or_404(token)
    if account["status"] != "ACTIVE":
        return _back(token, "inactive")
    conn = db()
    limit = monitor.PLANS[account["plan"]]["domains"]
    raw = re.split(r"[\s,]+", request.form.get("domains", ""))
    added, notice = 0, "added"
    for item in filter(None, raw):
        if monitor_db.count_domains(conn, account["id"]) >= limit:
            notice = "limit"
            break
        try:
            domain = monitor.normalize(item)
        except quantum_vuln_scanner.ScanError:
            notice = "invalid"
            continue
        added += monitor_db.add_domain(conn, account["id"], domain)
    return _back(token, notice)


@bp.post("/monitor/<token>/domains/<int:domain_id>/delete")
def monitor_remove_domain(token, domain_id):
    account = account_or_404(token)
    monitor_db.remove_domain(db(), account["id"], domain_id)
    return _back(token, "removed")


@bp.post("/monitor/<token>/scan")
def monitor_scan_now(token):
    account = account_or_404(token)
    if account["status"] != "ACTIVE":
        return _back(token, "inactive")
    now = dt.datetime.now(dt.timezone.utc)
    last = account.get("last_manual_scan")
    if last and now - dt.datetime.fromisoformat(last) < MANUAL_SCAN_INTERVAL:
        return _back(token, "wait")
    conn = db()
    monitor_db.mark_manual_scan(conn, account["id"], now.isoformat(timespec="seconds"))
    monitor.check_account(conn, account, scanner=current_app.extensions["scanner"])
    return _back(token, "scanned")


@bp.post("/monitor/<token>/cancel")
def monitor_cancel(token):
    account = account_or_404(token)
    if account["status"] != "ACTIVE":
        return _back(token, "inactive")
    paypal = current_app.extensions["paypal"]
    try:
        paypal.cancel_subscription(account["subscription_id"], "Cancelled by customer from dashboard")
    except (PayPalError, requests.RequestException) as exc:
        log.warning("PayPal cancel failed for %s: %s", account["id"], exc)
        return _back(token, "cancel_failed")
    monitor_db.set_status(db(), account["id"], "CANCELLED")
    monitor.notify_owner(current_app.extensions["mailer"], current_app.config["OWNER_EMAIL"],
                         "Cancelled by customer", account)
    return _back(token, "cancelled")


# ---------------------------------------------------------------- شارة قابلة للتضمين

BADGE_MAX_AGE_DAYS = 30
BADGE_STYLE = {
    "A": ("#16a34a", "A · ML-KEM"),
    "B": ("#0284c7", "B · classical"),
    "C": ("#d97706", "C · no TLS 1.3"),
    "F": ("#dc2626", "F"),
    None: ("#64748b", "not scanned"),
}


def badge_snippets(domain):
    """أكواد تضمين الشارة: HTML وMarkdown، يستعملها قالب صفحة النتيجة وصفحة النطاق."""
    page = url_for(".index", domain=domain, _external=True)
    img = url_for(".badge", domain=domain, _external=True)
    alt = "Post-quantum TLS grade by Quantum Aether"
    return {"html": f'<a href="{page}"><img src="{img}" alt="{alt}"></a>',
            "markdown": f"[![{alt}]({img})]({page})"}


def badge_svg(grade):
    color, value = BADGE_STYLE.get(grade, BADGE_STYLE[None])
    label = "post-quantum TLS"
    lw, vw = 7 * len(label) + 12, 7 * len(value) + 14  # تقدير عرض النص بخط 11px
    w = lw + vw
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{label}: {value}">
<title>{label}: {value}</title>
<rect width="{lw}" height="20" fill="#1e293b"/><rect x="{lw}" width="{vw}" height="20" fill="{color}"/>
<g fill="#fff" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11" text-anchor="middle">
<text x="{lw / 2}" y="14">{label}</text><text x="{lw + vw / 2}" y="14">{value}</text></g></svg>"""


@bp.get("/badge/<domain>.svg")
def badge(domain):
    """شارة تعرض درجة آخر فحص للنطاق (خلال 30 يوماً). لا تُجري فحصاً جديداً حتى لا تُستغل لإغراق الخادم."""
    try:
        domain = quantum_vuln_scanner.normalize_domain(domain)
    except quantum_vuln_scanner.ScanError:
        abort(404)
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=BADGE_MAX_AGE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    scan = sales_db.latest_scan_for_domain(db(), domain, since)
    response = Response(badge_svg(scan["grade"] if scan else None), mimetype="image/svg+xml")
    response.headers["Cache-Control"] = "public, max-age=86400"
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    return response


@bp.get("/robots.txt")
def robots():
    agents = "".join(f"User-agent: {name}\n" for name in [*AI_CRAWLERS, "*"])
    body = (agents + "Allow: /\nDisallow: /admin\nDisallow: /report/\nDisallow: /api/paypal/\nDisallow: /monitor/\nDisallow: /api/monitor/\n\n"
            f"Sitemap: {public_base()}/sitemap.xml\n"
            f"# AI agents: machine-readable summary and API at {public_base()}/llms.txt\n")
    return Response(body, mimetype="text/plain")


@bp.get("/sitemap.xml")
def sitemap():
    base = public_base()
    def template_date(name):  # تاريخ آخر تعديل حقيقي لقالب الصفحة
        mtime = os.path.getmtime(os.path.join(BASE_DIR, "templates", name))
        return dt.datetime.fromtimestamp(mtime, dt.timezone.utc).date().isoformat()

    site_langs, de_langs, legal_langs = ("en", "ar"), ("en", "ar", "de"), legal.LANGS
    pages = [("/", template_date("index.html"), de_langs), ("/monitoring", template_date("monitoring.html"), de_langs),
             ("/sample-report", sample_result()["scanned_at"][:10], site_langs),
             ("/research", template_date("research.html"), site_langs),
             ("/guides", max(g["updated"] for g in guides.GUIDES.values()), site_langs),
             ("/study/top-1000-post-quantum-tls", study_data()["scanned_on"], de_langs)]
    pages += [(f"/guides/{slug}", g["updated"], site_langs) for slug, g in guides.GUIDES.items()]
    pages.append(("/compare", template_date("compare.html"), site_langs))
    study_day = study_data()["scanned_on"]
    # صفحة قابلة للفهرسة لكل نطاق في الدراسة (SEO برمجي طويل الذيل)
    pages += [(f"/site/{site['domain']}", study_day, site_langs) for site in study_data()["sites"]]
    legal_date = os.path.getmtime(os.path.join(BASE_DIR, "legal.py"))
    legal_day = dt.datetime.fromtimestamp(legal_date, dt.timezone.utc).date().isoformat()
    pages += [(f"/{slug}", legal_day, legal_langs) for slug in legal.PAGES]

    def esc(u):
        return u.replace("&", "&amp;")

    parts = []
    for path, day, langs in pages:
        default = "de" if langs == legal_langs else "en"
        alternates = "".join(f'<xhtml:link rel="alternate" hreflang="{alt}" href="{esc(f"{base}{path}?lang={alt}")}"/>'
                             for alt in langs)
        alternates += f'<xhtml:link rel="alternate" hreflang="x-default" href="{esc(f"{base}{path}?lang={default}")}"/>'
        for lang in langs:
            parts.append(f"  <url><loc>{esc(f'{base}{path}?lang={lang}')}</loc><lastmod>{day}</lastmod>{alternates}</url>\n")
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "".join(parts) + "</urlset>\n")
    return Response(body, mimetype="application/xml")


@bp.get("/<key>.txt")
def indexnow_key(key):
    """ملف التحقق لـ IndexNow (Bing وYandex وغيرهما) يجب أن يكون في جذر النطاق."""
    path = os.path.join(BASE_DIR, "data", "indexnow.key")
    try:
        with open(path, encoding="utf-8") as f:
            expected = f.read().strip()
    except FileNotFoundError:
        abort(404)
    if not expected or not hmac.compare_digest(key, expected):
        abort(404)
    return Response(expected, mimetype="text/plain")


@bp.get("/openapi.yaml")
def openapi():
    with open(os.path.join(BASE_DIR, "openapi.yaml"), encoding="utf-8") as f:
        return Response(f.read().replace("{{PUBLIC_URL}}", public_base()), mimetype="application/yaml")


@bp.get("/llms.txt")
def llms_txt():
    return Response(render_template("llms.txt", base=public_base(), price=current_app.config["PRICE"]),
                    mimetype="text/plain")


@bp.post("/api/pv")
def track_pageview():
    """يسجل زيارة صفحة عامة. يرسلها app.js من المتصفح بعد تحميل الصفحة، فلا تُحسب الروبوتات
    التي تطلب HTML فقط دون تشغيل JavaScript (وهي أغلب الزيارات المتنكرة بمتصفح). أي خطأ هنا يُهمَل."""
    # مصدر الطلب يجب أن يكون صفحتنا نفسها
    if request.headers.get("Sec-Fetch-Site", "same-origin") != "same-origin":
        return "", 204
    try:
        data = json.loads(request.get_data(as_text=True)[:2000] or "{}")
    except ValueError:
        return "", 204
    if not isinstance(data, dict):
        return "", 204
    try:
        path = analytics_db.normalize_path(str(data.get("path", "")))
        if path is None or is_admin_visitor():
            return "", 204
        query = urllib.parse.parse_qs(str(data.get("search", "")).lstrip("?"))
        day = dt.date.today().isoformat()
        ua = request.headers.get("User-Agent", "")
        salt = current_app.config["HASH_SALT"].encode()
        visitor = hmac.new(salt, f"{day}|{request.remote_addr}|{ua}".encode(), hashlib.sha256).hexdigest()[:16]
        own_host = (current_app.config["PUBLIC_URL"].split("://")[-1] or request.host).split("/")[0]
        source = (analytics_db.utm_source((query.get("utm_source") or [None])[0])
                  or analytics_db.referrer_host(str(data.get("ref", "")) or None, own_host))
        analytics_db.record(db(), day, path, source, visitor, not ua or bool(analytics_db.BOT_RE.search(ua)))
    except Exception:  # الإحصاءات ثانوية
        log.exception("pageview tracking failed")
    return "", 204


@bp.after_app_request
def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.path.startswith(("/report/", "/admin", "/monitor/")):
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
