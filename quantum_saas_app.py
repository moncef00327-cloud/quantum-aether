# quantum_saas_app.py
# تطبيق الويب: فحص جاهزية HTTPS لما بعد الكم (مجاني) + تقرير كامل مدفوع عبر PayPal،
# والدفع يُتحقق منه على الخادم مع PayPal قبل فتح التقرير.
#
# التشغيل المحلي:  python quantum_saas_app.py   ثم افتح http://127.0.0.1:5000
# الإنتاج: gunicorn quantum_saas_app:app خلف nginx (انظر مجلد deploy/)
import datetime as dt
import base64
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
from flask import (Blueprint, Flask, Response, abort, current_app, g, jsonify, make_response, redirect,
                   render_template, request, send_file, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

import adoption
import bio_archive_report
import crypto_pay
import dna_encode
import analytics_db
import guides
import legal
import monitor
import countries
import deadlines
import free_alerts
import packs
import business_pages
import monitor_db
import og_image
import i18n
import quantum_vuln_scanner
import sales_db
import scorecard
import scan_experience
import search_indexing
import badge_evidence
from mailer import Mailer
from paypal_client import SUBSCRIPTION_LIVE_STATUSES, PayPalClient, PayPalError, verify_capture, verify_subscription

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
log = logging.getLogger("quantum_saas")
bp = Blueprint("site", __name__)

# زواحف الذكاء الاصطناعي مذكورة صراحة؛ كلها في مجموعة واحدة مع "*" لتنطبق عليها قواعد الحجب نفسها.
AI_CRAWLERS = [  # زواحف بحث وذكاء اصطناعي نسمح لها صراحةً لتفهرسنا وتستشهد بنا
    "GPTBot", "ChatGPT-User", "OAI-SearchBot",            # OpenAI
    "ClaudeBot", "Claude-User", "Claude-SearchBot", "anthropic-ai",  # Anthropic
    "PerplexityBot", "Perplexity-User",                  # Perplexity
    "Google-Extended", "GoogleOther", "Google-CloudVertexBot",  # Google AI
    "Applebot", "Applebot-Extended",                     # Apple
    "Amazonbot", "Meta-ExternalAgent", "FacebookBot",    # Amazon / Meta
    "Bingbot", "cohere-ai", "CCBot",                     # Bing / Cohere / Common Crawl (يغذّي معظم النماذج)
    "Bytespider", "TikTokSpider",                        # ByteDance
    "DuckAssistBot", "YouBot", "Diffbot", "Ai2Bot", "Timpibot", "PetalBot",
]


def _config_from_env():
    env = os.environ.get
    return {
        "DATA_DIR": env("QS_DATA_DIR", os.path.join(BASE_DIR, "instance")),
        "PUBLIC_URL": env("QS_PUBLIC_URL", "").rstrip("/"),
        "HASH_SALT": env("QS_HASH_SALT", ""),
        "ADMIN_PASSWORD_HASH": env("QS_ADMIN_PASSWORD_HASH", ""),
        "PRICE": env("QS_PRICE", "49.00"),
        "PACK_PRICE": env("QS_PACK_PRICE", "199.00"),
        "PACK_CREDITS": int(env("QS_PACK_CREDITS", "10")),
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
        "USDC_BASE_ADDR": env("QS_USDC_BASE_ADDR", ""),
    }


def create_app(overrides=None, scanner=None, paypal=None, mailer=None, chain=None):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 128 * 1024
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
DE_PAGES = {"site.index", "site.study", "site.monitoring", "site.adoption_page", "site.scanning_page", "site.deadlines_page",
            "site.business_page", "site.pricing_page", "site.agency_page", "site.countries_page", "site.country_page"}


def texts():
    return i18n.TEXTS[current_lang()]


@bp.app_context_processor
def _inject():
    lang = current_lang()
    return {"t": i18n.TEXTS[lang], "lang": lang, "other_lang": "en" if lang == "ar" else "ar",
            "legal_lang": "de" if lang == "de" else "en", "lang_names": i18n.LANG_NAMES,
            "page_langs": ["en", "ar", "de"] if request.endpoint in DE_PAGES else ["en", "ar"],
            "abs_url": lambda endpoint, **kw: public_base() + url_for(endpoint, **kw),
            "localized_url": localized_url, "metadata_url": metadata_url,
            "sx": scan_experience.COPY[lang],
            "domain_discoverable": lambda domain: not search_indexing.is_excluded(domain)}


def public_base():
    return current_app.config["PUBLIC_URL"] or request.url_root.rstrip("/")


def localized_url(lang, canonical=False):
    values = dict(request.view_args or {})
    if request.endpoint == 'site.site_page' and values.get('domain'):
        try:
            values['domain'] = quantum_vuln_scanner.normalize_domain(values['domain'])
        except quantum_vuln_scanner.ScanError:
            pass  # Invalid routes still render their existing 404/noindex response.
    if request.endpoint == 'site.compare' and not canonical:
        values.update({k: request.args[k][:4096] for k in ('a', 'b') if request.args.get(k)})
    if request.endpoint:
        return public_base() + url_for(request.endpoint, **values, lang=lang)
    return public_base() + urllib.parse.quote(request.path, safe='/') + '?lang=' + lang


def metadata_url(lang):
    return localized_url(lang, canonical=True)


def json_object():
    data = request.get_json(silent=True)
    if data is None:
        return {}
    if not isinstance(data, dict):
        abort(400)
    return data


ADMIN_COOKIE = "qa_admin"


def admin_cookie_value():
    """قيمة موقّعة بملح الخادم: لا يمكن تخمينها، وتُستعمل فقط لاستبعاد زيارات المدير من الإحصاءات."""
    return hmac.new(current_app.config["HASH_SALT"].encode(), b"admin-visitor", hashlib.sha256).hexdigest()


def is_admin_visitor():
    value = request.cookies.get(ADMIN_COOKIE, "")
    return bool(value) and hmac.compare_digest(value, admin_cookie_value())


OWNER_CLIENT_HOURS = 24


@bp.before_app_request
def _remember_owner_client():
    """كل اتصال يحمل كوكي المدير يُسجَّل (بصمة IP مملّحة فقط). فحوص CLI/MCP/API من الاتصال نفسه خلال 24 ساعة
    تُعدّ اختبارات، لأن تلك الأدوات لا تحمل الكوكي. نكتب مرة كل 10 دقائق على الأكثر لكل اتصال."""
    if not is_admin_visitor() or request.path.startswith("/static/"):
        return
    try:
        sales_db.remember_owner_client(db(), client_hash())
    except Exception:  # ثانوي
        log.exception("could not remember owner client")


def is_test_request():
    """طلب من المالك: كوكي المدير، أو اتصال استعمل الكوكي خلال آخر 24 ساعة (أدوات بلا متصفح)."""
    if is_admin_visitor():
        return True
    try:
        return sales_db.is_owner_client(db(), client_hash(), OWNER_CLIENT_HOURS)
    except Exception:
        return False


def client_hash():
    salt = current_app.config["HASH_SALT"].encode()
    return hmac.new(salt, (request.remote_addr or "").encode(), hashlib.sha256).hexdigest()[:32]


def payments_enabled():
    return current_app.extensions["paypal"] is not None


def is_api_request():
    return request.path.startswith("/api/")


SCAN_SOURCES = {"home", "example", "site", "scanbox", "compare", "api", "deadlines", "pack"}


def perform_scan(raw_domain, source=None):
    conn, chash = db(), client_hash()
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cfg = current_app.config
    if (sales_db.count_attempts_since(conn, since, chash) >= cfg["SCANS_PER_HOUR"]
            or sales_db.count_attempts_since(conn, since) >= cfg["GLOBAL_SCANS_PER_HOUR"]):
        abort(429)
    sales_db.record_attempt(conn, chash)
    raw_domain = quantum_vuln_scanner.normalize_domain(raw_domain)
    result = current_app.extensions["scanner"](raw_domain)
    scan_id = secrets.token_urlsafe(9)
    sales_db.create_scan(conn, scan_id, secrets.token_urlsafe(32), result, chash, is_test=is_test_request(),
                         source=source if isinstance(source, str) and source in SCAN_SOURCES else None)
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
        "post_quantum_key_exchange": scan_experience.status(result) == 'observed_pq',
        "observation_status": scan_experience.status(result),
        "port": 443,
        "limitations": scan_experience.LIMITATION,
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


HOME_EXAMPLES = ("github.com", "cloudflare.com", "amazon.com")


def home_examples():
    """أمثلة الصفحة الرئيسية مع نتيجتها المعروفة (من المتتبّع، بلا فحص جديد): يرى الزائر أن مواقع كبيرة
    غير جاهزة قبل أن يفحص موقعه."""
    examples = []
    for domain in HOME_EXAMPLES:
        summary, _ = known_result_for(domain)
        examples.append({"domain": domain, "grade": summary["grade"] if summary else None,
                         "pq": bool(summary and summary["pq"]),
                         "unsure": bool(summary and summary.get("unsure"))})
    return examples


@bp.get("/")
def index():
    return render_template("index.html" if current_lang() == "de" else "command_home.html", error=None, domain=request.args.get("domain", "")[:253],
                           jsonld=home_jsonld(), examples=home_examples(), study_snapshot=study_data())


@bp.post("/scan")
def scan_form():
    raw = request.form.get("domain", "")
    try:
        scan_id, _ = perform_scan(raw, request.form.get("src") or "home")
    except quantum_vuln_scanner.ScanError as exc:
        return render_template("index.html", error=texts()["errors"].get(exc.code, str(exc)), domain=raw,
                               jsonld=home_jsonld(), examples=home_examples(), study_snapshot=study_data()), 400
    return redirect(url_for(".scan_page", scan_id=scan_id, lang=current_lang()), code=303)


@bp.get("/scan/<scan_id>")
def scan_page(scan_id):
    scan = sales_db.get_scan(db(), scan_id) or abort(404)
    cfg = current_app.config
    lang = current_lang()
    findings = [dict(f, title=i18n.finding_text(f, lang if lang in ("en", "ar") else "en")[0]) for f in scan["result"]["findings"]]
    return render_template(
        "scan.html", scan=scan, r=scan["result"], paid=sales_db.is_scan_paid(db(), scan_id), findings=findings,
        payments_enabled=payments_enabled(), paypal_client_id=cfg["PAYPAL_CLIENT_ID"],
        crypto_networks=crypto_pay.enabled_networks(cfg), badge=badge_snippets(scan["result"]["domain"]),
        price=cfg["PRICE"], currency=cfg["CURRENCY"],
        observation=scan_experience.status(scan['result']), next_steps=scan_experience.advice(scan['result']),
    )


@bp.get("/report/<token>")
def report(token):
    scan = paid_scan_or_404(token)
    lang = current_lang()
    findings = [dict(f, text=i18n.finding_text(f, lang)) for f in scan["result"]["findings"]]
    return render_template("report.html", scan=scan, r=scan["result"], findings=findings,
                           remediation=i18n.REMEDIATION, token=token,
                           observation=scan_experience.status(scan['result']))


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
                           token=None, sample=True, observation=scan_experience.status(r))


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


@functools.lru_cache(maxsize=1)
def study_retry_domains():
    """Audit flags from immutable raw evidence, without rewriting the published archive."""
    domains = set()
    with open(adoption.RAW_STUDY_FILE, encoding='utf-8') as source:
        for line in source:
            row = json.loads(line)
            if row.get('ok') and row.get('key_exchange', {}).get('hrr'):
                domains.add(row['domain'])
    return frozenset(domains)


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


# ---------------------------------------------------------------- باقة الوكالات (10 تقارير، دفعة واحدة)

@bp.get("/business")
def business_page():
    return commercial_page("business")


@bp.get("/pricing")
def pricing_page():
    return commercial_page("pricing")


def commercial_page(section):
    cfg = current_app.config
    return render_template("commercial.html", commercial=business_pages.COPY[current_lang()],
                           section=section, plans=monitor.PLANS, price=cfg["PRICE"],
                           pack_price=cfg["PACK_PRICE"], credits=cfg["PACK_CREDITS"],
                           currency=cfg["CURRENCY"], recurring_enabled=subscriptions_enabled(),
                           payments_enabled=payments_enabled())


@bp.get("/agency")
def agency_page():
    cfg = current_app.config
    return render_template("agency.html", price=cfg["PACK_PRICE"], credits=cfg["PACK_CREDITS"], currency=cfg["CURRENCY"],
                           single=cfg["PRICE"], payments_enabled=payments_enabled(), paypal_client_id=cfg["PAYPAL_CLIENT_ID"])


@bp.post("/api/paypal/packs")
def paypal_create_pack():
    paypal = current_app.extensions["paypal"]
    if paypal is None:
        return jsonify(error="payments_disabled"), 503
    data = json_object()
    if data.get("consent") is not True:
        return jsonify(error="consent_required"), 400
    cfg = current_app.config
    pack_id = packs.new_id()
    try:
        order = paypal.create_order(pack_id, cfg["PACK_PRICE"], cfg["CURRENCY"],
                                    f"Agency pack: {cfg['PACK_CREDITS']} post-quantum TLS reports")
    except (PayPalError, requests.RequestException) as exc:
        log.warning("PayPal create pack order failed: %s", exc)
        return jsonify(error="paypal_unavailable"), 502
    packs.create(db(), pack_id, order["id"], cfg["PACK_CREDITS"], cfg["PACK_PRICE"], cfg["CURRENCY"], current_lang(),
                 now_iso(), is_test_request())
    return jsonify(id=order["id"]), 201


@bp.post("/api/paypal/packs/<order_id>/capture")
def paypal_capture_pack(order_id):
    """مثل التقرير: الخادم يلتقط ويتحقق من المبلغ والمرجع. رابط الباقة يُعاد مرة واحدة هنا ويُرسل بالبريد."""
    paypal = current_app.extensions["paypal"]
    if paypal is None:
        return jsonify(error="payments_disabled"), 503
    conn = db()
    pack = packs.by_order(conn, order_id)
    if not pack:
        return jsonify(error="order_not_found"), 404
    if pack["status"] == "COMPLETED":
        return jsonify(status="COMPLETED", message="already_completed")
    try:
        order = paypal.capture_order(order_id)
    except PayPalError as exc:
        if exc.issue == "INSTRUMENT_DECLINED":
            return jsonify(error="INSTRUMENT_DECLINED"), 422
        if exc.issue == "ORDER_NOT_APPROVED":
            return jsonify(error="order_not_approved"), 409
        if exc.issue != "ORDER_ALREADY_CAPTURED":
            log.warning("PayPal pack capture failed for %s: %s (%s)", order_id, exc, exc.issue)
            return jsonify(error="capture_failed"), 502
        try:
            order = paypal.get_order(order_id)
        except (PayPalError, requests.RequestException):
            return jsonify(error="paypal_unavailable"), 502
    except requests.RequestException:
        return jsonify(error="paypal_unavailable"), 502
    status, capture_id = verify_capture(order, pack["id"], pack["amount"], pack["currency"])
    email = (order.get("payer") or {}).get("email_address")
    token = packs.mark(conn, pack["id"], status, capture_id, email)
    if status == "FAILED":
        log.error("PayPal pack capture for %s did not match the expected amount/reference", order_id)
        return jsonify(error="verification_failed"), 402
    if status != "COMPLETED":
        return jsonify(status=status), 202
    pack_url = public_base() + url_for(".pack_page", token=token, lang=pack["lang"])
    mailer = current_app.extensions["mailer"]
    if email and mailer.enabled:
        subject, text = packs.receipt_email(pack["lang"], dict(pack, order_id=order_id), pack_url, public_base())
        mailer.send(email, subject, text)
    owner = current_app.config["OWNER_EMAIL"]
    if owner and not pack["is_test"]:
        mailer.send(owner, f"[Quantum Aether] Agency pack sold: ${pack['amount']} — {email or '?'}",
                    f"Pack {pack['id']} ({pack['credits']} reports)\nPayPal order {order_id}, capture {capture_id}\n"
                    f"Buyer: {email or '?'} · language {pack['lang']}")
    return jsonify(status="COMPLETED", pack_url=pack_url)


@bp.get("/pack/<token>")
def pack_page(token):
    pack = packs.by_token(db(), token) or abort(404)
    return render_template("pack.html", pack=pack, token=token, reports=packs.redeemed(db(), pack["id"]), error=None)


@bp.post("/pack/<token>/redeem")
def pack_redeem(token):
    conn = db()
    pack = packs.by_token(conn, token) or abort(404)
    error = None
    if pack["used"] >= pack["credits"]:
        error = texts()["pack_empty"]
    else:
        try:
            scan_id, _ = perform_scan(request.form.get("domain", ""), "pack")
        except quantum_vuln_scanner.ScanError as exc:
            error = texts()["errors"].get(exc.code, str(exc))
        else:
            if packs.redeem(conn, pack, scan_id):
                return redirect(report_url(sales_db.get_scan(conn, scan_id)), code=303)
            error = texts()["pack_empty"]
    return render_template("pack.html", pack=packs.by_token(conn, token), token=token,
                           reports=packs.redeemed(conn, pack["id"]), error=error), 400


# ---------------------------------------------------------------- «نبّهني مجاناً» (نطاق واحد، أسبوعياً، تأكيد مزدوج)

@bp.post("/alerts")
def alerts_subscribe():
    email = (request.form.get("email") or "").strip()[:254]
    raw = request.form.get("domain") or ""
    state = "check_inbox"
    if not request.form.get("consent"):
        state = "consent_missing"
    elif not EMAIL_RE.match(email):
        state = "bad_email"
    else:
        try:
            domain = quantum_vuln_scanner.normalize_domain(raw)
        except quantum_vuln_scanner.ScanError:
            abort(400)
        mailer = current_app.extensions["mailer"]
        if not mailer.enabled:
            state = "unavailable"
        else:
            token, reason = free_alerts.subscribe(db(), email, domain, current_lang(), client_hash())
            if reason:
                state = reason
            else:
                url = public_base() + url_for(".alerts_confirm", token=token, lang=current_lang())
                subject, text = free_alerts.confirm_email(current_lang(), domain, url, public_base())
                if not mailer.send(email, subject, text):
                    state = "unavailable"
    status = 200 if state in ("check_inbox", "already_active") else 400
    return render_template("alerts.html", state=state, domain=raw), status


@bp.route("/alerts/confirm/<token>", methods=["GET", "POST"])
def alerts_confirm(token):
    """GET يعرض زراً و POST يؤكد: ماسحات الروابط في البريد (التي تفتح كل رابط) لا تؤكد نيابة عن أحد."""
    alert = free_alerts.get(db(), token) or abort(404)
    if request.method == "POST":
        since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=BADGE_MAX_AGE_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
        latest = sales_db.latest_scan_for_domain(db(), alert["domain"], since)
        free_alerts.confirm(db(), token, latest["result"] if latest else None)
        return render_template("alerts.html", state="confirmed", domain=alert["domain"])
    return render_template("alerts.html", state="confirm_prompt", domain=alert["domain"], token=token)


@bp.route("/alerts/stop/<token>", methods=["GET", "POST"])
def alerts_stop(token):
    alert = free_alerts.get(db(), token)
    if request.method == "POST":
        if alert:
            free_alerts.stop(db(), token)
        return render_template("alerts.html", state="stopped", domain=alert["domain"] if alert else "")
    if not alert:
        return render_template("alerts.html", state="stopped", domain="")
    return render_template("alerts.html", state="stop_prompt", domain=alert["domain"], token=token)


@bp.get("/deadlines")
def deadlines_page():
    d = deadlines.TEXT[current_lang()]
    jsonld = {"@context": "https://schema.org", "@type": "Article", "headline": d["title"], "description": d["description"],
              "inLanguage": current_lang(), "dateModified": deadlines.UPDATED, "url": public_base() + url_for(".deadlines_page"),
              "author": {"@type": "Organization", "name": "Quantum Aether"},
              "citation": [url for _, _, url in deadlines.TIMELINE]}
    return render_template("deadlines.html", d=d, timeline=deadlines.TIMELINE, milestones=deadlines.MILESTONES,
                           updated=deadlines.UPDATED, jsonld=jsonld)


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
    return render_template("study.html", d=d, pct=pct, notable=notable, retry_domains=study_retry_domains())


@bp.get("/study/top-1000-post-quantum-tls.json")
def study_json():
    return current_app.response_class(json.dumps(study_data(), ensure_ascii=False), mimetype="application/json")


# ---------------------------------------------------------------- متتبّع التبنّي الأسبوعي (/adoption)

_SNAPSHOT_CACHE = {}


def cached_snapshot():
    """adoption.snapshot مكلفة (~90ms: آلاف الصفوف) والبيانات تتغير أسبوعياً فقط. نخزّنها في ذاكرة
    العامل ونعيد حسابها حين تتغير «بصمة» الجداول (عدد الصفوف وآخر وقت فحص). اختبار الضغط: 20 طلباً/ث قبلها."""
    conn = db()
    fingerprint = (current_app.config["DATA_DIR"],
                   tuple(conn.execute("SELECT MAX(week), COUNT(*), MAX(scanned_at), SUM(unsure) FROM adoption_results").fetchone()),
                   tuple(conn.execute("SELECT MAX(month), COUNT(*) FROM adoption_monthly").fetchone()))
    hit = _SNAPSHOT_CACHE.get(fingerprint[0])
    if hit and hit[0] == fingerprint:
        return hit[1]
    snap = adoption.snapshot(conn)
    _SNAPSHOT_CACHE[fingerprint[0]] = (fingerprint, snap)
    return snap


_COUNTRIES_CACHE = {}


def cached_countries():
    """ترتيب الدول، يُعاد حسابه فقط حين تتغير بيانات المتتبّع (نفس بصمة cached_snapshot)."""
    conn = db()
    fingerprint = tuple(conn.execute("SELECT MAX(week), COUNT(*), MAX(scanned_at), SUM(unsure) FROM adoption_results").fetchone())
    key = current_app.config["DATA_DIR"]
    hit = _COUNTRIES_CACHE.get(key)
    if hit and hit[0] == fingerprint:
        return hit[1]
    board = countries.leaderboard(conn)
    _COUNTRIES_CACHE[key] = (fingerprint, board)
    return board


def adoption_snapshot():
    """لقطة آخر أسبوع. قبل أول تشغيل للمهمة الأسبوعية نزرع أول أسبوع من بيانات الدراسة المنشورة."""
    snap = cached_snapshot()
    if snap is None:
        adoption.seed_from_study(db())
        snap = cached_snapshot()
    return snap


def _open_data(response):
    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["Access-Control-Allow-Origin"] = "*"  # بيانات مفتوحة (CC BY 4.0)
    return response


@bp.get("/adoption")
def adoption_page():
    # في العربية نعزل اتجاه رمز الأسبوع (Unicode isolate) حتى لا ينقلب «2026-W46» إلى «W46-2026»
    iso = (lambda value: f"\u2066{value}\u2069") if current_lang() == "ar" else str
    return render_template("adoption.html", s=adoption_snapshot(), iso=iso)


@bp.get("/adoption/countries")
def countries_page():
    board = cached_countries() or abort(404)
    lang = current_lang()
    for e in board["entries"]:
        e["name"] = countries.name(e["code"], lang)
    jsonld = {"@context": "https://schema.org", "@type": "Dataset", "name": "Post-quantum TLS readiness by country",
              "description": "Share of each country's top websites (by country-code domain, Tranco top 10,000) that negotiate "
                             "the hybrid post-quantum key exchange X25519MLKEM768, updated weekly.",
              "url": public_base() + url_for(".countries_page"), "license": "https://creativecommons.org/licenses/by/4.0/",
              "temporalCoverage": board["week"], "creator": {"@type": "Organization", "name": "Quantum Aether"},
              "distribution": {"@type": "DataDownload", "encodingFormat": "application/json",
                               "contentUrl": public_base() + url_for(".countries_json")}}
    return render_template("countries.html", b=board, jsonld=jsonld)


@bp.get("/adoption/countries/<code>")
def country_page(code):
    board = cached_countries() or abort(404)
    entry = next((e for e in board["entries"] if e["code"] == code.lower()), None) or abort(404)
    lang = current_lang()
    sites = countries.country_sites(db(), entry["code"], board["week"])
    return render_template("country.html", b=board, e=dict(entry, name=countries.name(entry["code"], lang)), sites=sites)


@bp.get("/adoption/countries.json")
def countries_json():
    board = cached_countries() or abort(404)
    body = dict(board, entries=[dict(e, name=countries.name(e["code"], "en")) for e in board["entries"]],
                license="CC BY 4.0", source=public_base() + url_for(".countries_page"),
                method="Country = country-code top-level domain of each Tranco top-10,000 hostname (generic-use ccTLDs such as "
                       ".io, .ai, .tv, .co, .me excluded). pct = share of measured hostnames that negotiated X25519MLKEM768.")
    return _open_data(current_app.response_class(json.dumps(body, ensure_ascii=False), mimetype="application/json"))


@bp.get("/scanning")
def scanning_page():
    """يشرح فحوصاتنا لمن يراها في سجلاته، مع طريقة طلب الاستبعاد."""
    return render_template("scanning.html")


@bp.get("/adoption.json")
def adoption_json():
    snap = adoption_snapshot()
    body = dict(snap, license="CC BY 4.0", source=public_base() + url_for(".adoption_page"),
                method="Two TLS connections to port 443 per hostname from one vantage point; "
                       "pq = the server negotiated X25519MLKEM768 with a Chrome-like ClientHello.")
    return _open_data(current_app.response_class(json.dumps(body, ensure_ascii=False), mimetype="application/json"))


@bp.get("/adoption.csv")
def adoption_csv():
    snap = adoption_snapshot()
    response = Response(adoption.to_csv(snap["rows"]), mimetype="text/csv")
    response.headers["Content-Disposition"] = f'inline; filename="pq-adoption-{snap["week"]}.csv"'
    return _open_data(response)


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
        tls = r["key_exchange"].get("version") or r["certificate"].get("negotiated_version")
        return ({"domain": domain, "grade": r["grade"], "group": r["key_exchange"].get("group"), "tls": tls,
                 "pq": scan_experience.status(r) == 'observed_pq', "unsure": adoption.is_unsure(r["key_exchange"], tls),
                 "scanned_at": r["scanned_at"]}, "scan")
    weekly = adoption.latest_for(db(), domain)
    if weekly:
        return ({"domain": domain, "grade": weekly["grade"], "group": weekly["grp"], "tls": weekly["tls"],
                 "pq": bool(weekly["pq"]), "unsure": bool(weekly["unsure"]), "scanned_at": weekly["scanned_at"],
                 "week": weekly["week"], "rank": weekly["rank"]}, "weekly")
    site = study_by_domain().get(domain)
    if site:
        unsure = domain in study_retry_domains()
        return (dict(site, scanned_at=study_data()["scanned_on"], unsure=unsure,
                     pq=bool(site['pq']) and not unsure), "study")
    return (None, None)


def _http_date(iso):
    """تاريخ ISO (يوم أو وقت) إلى صيغة HTTP لترويسة Last-Modified؛ None إن تعذّر."""
    try:
        moment = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=dt.timezone.utc)
    from email.utils import format_datetime
    return format_datetime(moment.astimezone(dt.timezone.utc), usegmt=True)


def with_last_modified(response, iso):
    """يضيف Last-Modified ويجيب 304 إن لم يتغير شيء منذ زيارة الزاحف السابقة (يوفّر ميزانية الزحف)."""
    stamp = _http_date(iso)
    if not stamp:
        return response
    response.headers["Last-Modified"] = stamp
    since = request.headers.get("If-Modified-Since")
    if since and response.status_code == 200:
        from email.utils import parsedate_to_datetime
        try:
            if parsedate_to_datetime(since) >= parsedate_to_datetime(stamp):
                response.status_code, response.data = 304, b""
        except (TypeError, ValueError):
            pass
    return response


def site_verdict(domain, summary):
    """جملة واحدة واضحة قابلة للاقتباس (للبشر ولمحركات الإجابة)، بالإنجليزية لأنها تُقتبس كما هي."""
    day = str(summary.get("scanned_at", ""))[:10]
    if summary.get("unsure"):
        return (f"As of {day}, Quantum Aether could not determine whether {domain} negotiates post-quantum key exchange: "
                "the server or its firewall rejected our raw TLS probe.")
    if summary["pq"]:
        return (f"Yes. As of {day}, {domain} negotiates the hybrid post-quantum key exchange "
                f"{summary.get('group') or 'X25519MLKEM768'} over {summary.get('tls') or 'TLS 1.3'} (Quantum Aether grade {summary['grade']}).")
    return (f"No. As of {day}, {domain} does not negotiate post-quantum key exchange; it uses "
            f"{summary.get('group') or 'classical key exchange'} over {summary.get('tls') or 'TLS'} "
            f"(Quantum Aether grade {summary['grade']}), so recorded traffic is exposed to harvest-now-decrypt-later.")


@bp.get("/site/<domain>")
def site_page(domain):
    """صفحة عامة قابلة للفهرسة لكل نطاق: تعرض ما نعرفه عنه وتدعو لفحص حيّ. لا تُجري فحصاً."""
    try:
        domain = quantum_vuln_scanner.normalize_domain(domain)
    except quantum_vuln_scanner.ScanError:
        abort(404)
    summary, source = known_result_for(domain)
    jsonld, verdict, history, related, network = None, None, [], [], None
    if summary:
        conn = db()
        history = adoption.domain_history(conn, domain)
        last = history[-1] if history else None
        network = last["as_name"] if last else None
        if last:
            seen = {domain}
            for row in adoption.peers(conn, domain, network, last["week"]) + \
                    adoption.rank_neighbors(conn, last["rank"], last["week"], domain):
                if row["domain"] not in seen and not search_indexing.is_excluded(row["domain"]):
                    seen.add(row["domain"])
                    related.append(row)
            related = related[:10]
        verdict = site_verdict(domain, summary)
        page_url = metadata_url(current_lang())
        pq = "yes" if summary["pq"] else ("undetermined" if summary.get("unsure") else "no")
        modified = str(summary["scanned_at"])[:10]
        jsonld = [{"@context": "https://schema.org", "@type": "WebPage",
                   "name": f"{domain} — post-quantum TLS readiness",
                   "url": page_url, "inLanguage": current_lang(), "dateModified": modified,
                   "isPartOf": {"@type": "Dataset", "name": "Post-quantum TLS adoption tracker",
                                "description": "Weekly measurements of post-quantum TLS adoption across ranked websites "
                                               "and selected watchlists, including observed TLS versions, key-exchange "
                                               "groups and readiness grades. Results describe the measured public "
                                               "HTTPS connection, not overall application security.",
                                "url": public_base() + url_for(".adoption_page"),
                                "license": "https://creativecommons.org/licenses/by/4.0/",
                                "creator": {"@type": "Organization", "name": "Quantum Aether"}},
                   "about": {"@type": "WebSite", "name": domain, "url": f"https://{domain}"},
                   "description": f"{domain} TLS grade {summary['grade']}, key exchange {summary.get('group') or 'unknown'}, "
                                  f"post-quantum key exchange: {pq}."},
                  {"@context": "https://schema.org", "@type": "FAQPage",
                   "mainEntity": [{"@type": "Question", "name": f"Does {domain} use post-quantum TLS?",
                                   "acceptedAnswer": {"@type": "Answer", "text": verdict}}]}]
    country = None
    code = countries.code_of(domain)
    board = cached_countries() if (summary and code) else None
    if board:
        entry = next((e for e in board["entries"] if e["code"] == code), None)
        if entry:
            country = dict(entry, name=countries.name(code, current_lang()), total=board["countries"])
    indexing_excluded = search_indexing.is_excluded(domain)
    response = make_response(render_template(
        "site_page.html", domain=domain, summary=summary, source=source, verdict=verdict, history=history,
        related=related, network=network, snippets=badge_snippets(domain) if summary else None, jsonld=jsonld,
        country=country, indexing_excluded=indexing_excluded),
        200 if summary else 404)  # نطاق لا نعرفه (مثل wp-login.php من الماسحات) ليس صفحة حقيقية
    if indexing_excluded:
        response.headers['X-Robots-Tag'] = 'noindex, follow'
        response.headers['Cache-Control'] = 'no-cache'
        # Always deliver the new directive instead of an old-data-date 304.
        return response
    return with_last_modified(response, summary["scanned_at"]) if summary else response


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
                _, result = perform_scan(raw, "compare")
                pair[key] = result
            except quantum_vuln_scanner.ScanError as exc:
                pair[key] = {"error": texts()["errors"].get(exc.code, str(exc)), "domain": raw}
        results = pair
    return render_template("compare.html", a=a, b=b, results=results, error=error)


@bp.get("/api/v1/scan")
def api_v1_scan_get():
    """فحص عبر GET ليسهل على أدوات سطر الأوامر والوكلاء: /api/v1/scan?domain=example.com
    مع ?format=text يعيد نصاً ملوّناً للطرفية (ANSI).
    مع ?max_age=N (ساعات، حتى 720) يعيد آخر نتيجة محفوظة أحدث من N ساعة بدل فحص جديد؛ تستعمله إضافة
    WordPress حتى لا تصطدم مواقع الاستضافة المشتركة (عنوان IP واحد) بحدّ الفحوص."""
    try:
        max_age = max(0, min(int(request.args.get("max_age", 0)), 720))
    except ValueError:
        max_age = 0
    if max_age and request.args.get("format") != "text":
        try:
            domain = quantum_vuln_scanner.normalize_domain(request.args.get("domain", ""))
        except quantum_vuln_scanner.ScanError as exc:
            return jsonify(error=exc.code, message=str(exc)), 400
        since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=max_age)).strftime("%Y-%m-%dT%H:%M:%SZ")
        cached = sales_db.latest_scan_for_domain(db(), domain, since)
        if cached:
            body = dict(scan_summary(cached["id"], cached["result"]), cached=True,
                        report_hint=public_base() + url_for(".scan_page", scan_id=cached["id"]))
            return jsonify(body)
    try:
        scan_id, result = perform_scan(request.args.get("domain", ""), "api")
    except quantum_vuln_scanner.ScanError as exc:
        if request.args.get("format") == "text":
            return Response(f"error: {exc}\n", mimetype="text/plain"), 400
        return jsonify(error=exc.code, message=str(exc)), 400
    if request.args.get("format") == "text":
        return Response(terminal_report(result), mimetype="text/plain; charset=utf-8")
    body = dict(scan_summary(scan_id, result), cached=False,
                report_hint=public_base() + url_for(".scan_page", scan_id=scan_id))
    return jsonify(body)


def terminal_report(result):
    kx, cert = result["key_exchange"], result["certificate"]
    g = result["grade"]
    color = {"A": "32", "B": "36", "C": "33", "F": "31"}.get(g, "0")
    state = scan_experience.status(result)
    pq = 'undetermined — verify with a compatible TLS client' if state == 'undetermined' else (
        "yes (hybrid ML-KEM)" if state == 'observed_pq' else "NO — classical, harvest-now-decrypt-later risk")
    base = current_app.config["PUBLIC_URL"] or "https://ather-quantum.com"
    lines = [
        "",
        f"  Quantum Aether — post-quantum TLS scan",
        f"  domain        {result['domain']}",
        f"  grade         \033[1;{color}m{g}\033[0m",
        f"  key exchange  {kx.get('group') or '-'}",
        f"  post-quantum  {pq}",
        f"  TLS           {kx.get('version') or cert.get('negotiated_version') or '-'}",
        f"  certificate   {cert.get('key_algorithm')}-{cert.get('key_bits')}",
        f"  limitations   {scan_experience.LIMITATION}",
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
                           scans_daily=sales_db.scans_per_day(conn, (dt.date.today() - dt.timedelta(days=13)).isoformat()),
                           card=scorecard.build(conn, current_app.config["OWNER_EMAIL"], monitor.PLANS),
                           events=analytics_db.event_funnel(conn, (dt.date.today() - dt.timedelta(days=13)).isoformat()),
                           by_source=sales_db.funnel_by_source(conn, (dt.date.today() - dt.timedelta(days=30)).isoformat()),
                           free_alert_counts=dict(conn.execute("SELECT status, COUNT(*) FROM free_alerts GROUP BY status").fetchall())))
    # كوكي دائم لسنة: كل زيارات هذا المتصفح لا تُحسب في الإحصاءات.
    response.set_cookie(ADMIN_COOKIE, admin_cookie_value(), max_age=365 * 24 * 3600, httponly=True,
                        secure=request.is_secure, samesite="Lax")
    return response


# ---------------------------------------------------------------- API

@bp.post("/api/scan")
def api_scan():
    data = json_object()
    try:
        scan_id, result = perform_scan(data.get("domain", ""), data.get('source') or "api")
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
    data = json_object()
    if 'domain' in data:
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
    data = json_object()
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
                          is_test=is_test_request())
    return jsonify(id=order["id"]), 201


def send_report_receipt(scan, amount, currency, order_id, email):
    """يرسل إيصال/تأكيد شراء التقرير بلغة المشتري. فشل البريد لا يوقف شيئاً."""
    if not email:
        return
    mailer = current_app.extensions["mailer"]
    if not mailer.enabled:
        return
    report_abs = public_base() + url_for(".report", token=scan["report_token"])
    subject, text = monitor.report_receipt_email(current_lang(), scan["domain"], amount, currency, report_abs, order_id)
    mailer.send(email, subject, text)


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
        if exc.issue == "ORDER_NOT_APPROVED":  # المشتري لم يوافق بعد في PayPal: ليس عطلاً في PayPal
            return "NOT_APPROVED", scan
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
    if status == "COMPLETED" and not row["is_test"]:
        send_report_receipt(scan, row["amount"], row["currency"], order_id, (order.get("payer") or {}).get("email_address"))
    if status == "FAILED":
        log.error("PayPal capture for %s did not match the expected amount/reference", order_id)
        return "VERIFICATION_FAILED", scan
    return status, scan


CAPTURE_ERRORS = {
    "DISABLED": ("payments_disabled", 503),
    "NOT_FOUND": ("order_not_found", 404),
    "INSTRUMENT_DECLINED": ("INSTRUMENT_DECLINED", 422),
    "NOT_APPROVED": ("order_not_approved", 409),
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
    data = json_object()
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
                          is_test=is_test_request())
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
    data = json_object()
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
    email = str(data.get("email", "")).strip() or None
    if email and not EMAIL_RE.match(email):
        return jsonify(error="invalid_email"), 400
    order_id = f"cx-{key}-{secrets.token_urlsafe(9)}"
    sales_db.create_order(conn, order_id, scan["id"], amount, net["token"], consent_at=now_iso(),
                          is_test=is_test_request(), email=email)
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
    data = json_object()
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
    if not row["is_test"]:
        send_report_receipt(scan, row["amount"], row["currency"], order_id, row["email"])
    owner = current_app.config["OWNER_EMAIL"]
    if owner and not row["is_test"]:
        current_app.extensions["mailer"].send(
            owner, f"[Quantum Aether] Report paid: {row['amount']} {net['token']} — {scan['domain']}",
            f"Order: {order_id}\nAmount: {row['amount']} {net['token']} on {net['chain']}\n"
            f"To: {net['address']}\nTransaction: {net['explorer']}{tx_hash}")
    return jsonify(status="COMPLETED", report_url=public_base() + url_for(".report", token=scan["report_token"]))


@bp.post("/api/v1/agent/report/<scan_id>")
def x402_agent_report(scan_id):
    """Paid report resource using x402 v2 exact EIP-3009 on Base USDC."""
    address = str(current_app.config.get("USDC_BASE_ADDR", "")).lower()
    if not crypto_pay.ADDRESS_RE.fullmatch(address):
        return jsonify(error="x402_unavailable"), 503
    conn = db()
    scan = sales_db.get_scan(conn, scan_id)
    if not scan:
        return jsonify(error="scan_not_found"), 404
    if sales_db.is_scan_paid(conn, scan_id):
        return jsonify(error="already_paid"), 409

    price = str(current_app.config["PRICE"])
    amount = str(crypto_pay.to_units(price, 6))
    asset = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
    url = public_base() + request.path
    requirements = {"scheme":"exact", "network":"eip155:8453", "amount":amount,
        "asset":asset, "payTo":address, "maxTimeoutSeconds":60,
        "extra":{"assetTransferMethod":"eip3009", "name":"USD Coin", "version":"2"}}
    resource = {"url":url, "description":f"Quantum Aether full TLS evidence report for scan {scan_id}. Immediate delivery after payment; see terms.", "mimeType":"application/json"}
    def payment_required(error=None):
        challenge={"x402Version":2,"resource":resource,"accepts":[requirements]}
        if error: challenge["error"]=error
        encoded=base64.b64encode(json.dumps(challenge,separators=(",",":" )).encode()).decode()
        response=jsonify({"error":"payment_required","currency":"USDC","network":"Base","amount_usd":price,"terms":current_app.config.get("PUBLIC_URL",public_base())+"/agb?lang=en"})
        response.status_code=402;response.headers["PAYMENT-REQUIRED"]=encoded;response.headers["Cache-Control"]="no-store"
        return response

    signed=request.headers.get("PAYMENT-SIGNATURE", "")
    if not signed: return payment_required()
    try:
        padded=signed+"="*((4-len(signed)%4)%4)
        payload=json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except Exception:
        return payment_required("Invalid PAYMENT-SIGNATURE")
    accepted=payload.get("accepted",{}) if isinstance(payload,dict) else {}
    if not isinstance(accepted,dict): accepted={}
    signed_resource=payload.get("resource",{}) if isinstance(payload,dict) else {}
    if not isinstance(signed_resource,dict): signed_resource={}
    extra=accepted.get("extra",{}) if isinstance(accepted,dict) else {}
    if not isinstance(extra,dict) or not isinstance(payload,dict) or payload.get("x402Version")!=2 or signed_resource.get("url")!=url or accepted.get("network")!="eip155:8453" or accepted.get("scheme")!="exact" or not isinstance(accepted.get("asset"),str) or accepted["asset"].lower()!=asset or not isinstance(accepted.get("payTo"),str) or accepted["payTo"].lower()!=address or str(accepted.get("amount"))!=amount or extra.get("assetTransferMethod")!="eip3009":
        return payment_required("Payment does not match the requested amount, network, token or recipient")
    facilitator="https://facilitator.payai.network"
    facilitator_body={"x402Version":2,"paymentPayload":payload,"paymentRequirements":requirements}
    try:
        verified=requests.post(facilitator+"/verify",json=facilitator_body,timeout=20)
        verified.raise_for_status(); verification=verified.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("x402 facilitator verify unavailable: %s",exc)
        return jsonify(error="payment_verifier_unavailable"),503
    if not verification.get("isValid"):
        return payment_required(verification.get("invalidReason","Payment verification failed"))
    try:
        settled=requests.post(facilitator+"/settle",json=facilitator_body,timeout=45)
        settlement=settled.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning("x402 facilitator settlement uncertain: %s",exc)
        return jsonify(error="settlement_status_unknown",message="Check the same signed payment with the facilitator before retrying."),202
    if not settlement.get("success"):
        if settlement.get("errorReason")=="settlement_pending":
            return jsonify(error="settlement_pending",transaction=settlement.get("transaction"),network=settlement.get("network")),202
        return payment_required(settlement.get("errorReason","Settlement failed"))
    transaction=str(settlement.get("transaction", "")).lower()
    if settlement.get("network")!="eip155:8453" or not crypto_pay.TX_RE.fullmatch(transaction):
        log.error("x402 facilitator returned invalid settlement metadata")
        return jsonify(error="settlement_reconciliation_required"),202
    if sales_db.order_by_capture(conn,transaction):
        return jsonify(error="payment_already_consumed"),409
    order_id="x402-base-"+secrets.token_urlsafe(12)
    sales_db.create_order(conn,order_id,scan_id,price,"USDC",consent_at=now_iso(),is_test=bool(scan.get("is_test")))
    try:
        sales_db.update_order(conn,order_id,"COMPLETED",transaction)
    except sales_db.sqlite3.IntegrityError:
        return jsonify(error="payment_already_consumed"),409
    report_url=public_base()+url_for(".report",token=scan["report_token"])
    response=jsonify(status="COMPLETED",report_url=report_url,order_id=order_id,transaction=transaction,network="eip155:8453",currency="USDC",amount=price)
    response.headers["PAYMENT-RESPONSE"]=base64.b64encode(json.dumps(settlement,separators=(",",":" )).encode()).decode()
    response.headers["Cache-Control"]="no-store"
    return response


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
    data = json_object()
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
    data = json_object()
    conn = db()
    account = monitor_db.get_account(conn, str(data.get("account_id", "")))
    subscription_id = str(data.get("subscription_id", ""))
    if not account or not subscription_id:
        return jsonify(error="account_not_found"), 404
    if account["status"] != "PENDING":
        return jsonify(error="already_activated"), 409
    try:
        subscription = paypal.get_subscription(subscription_id)
    except PayPalError as exc:
        if exc.status == 404:  # رقم اشتراك غير موجود في PayPal: خطأ من الطلب لا عطل في PayPal
            return jsonify(error="subscription_not_found"), 404
        log.warning("PayPal subscription lookup failed for %s: %s", subscription_id, exc)
        return jsonify(error="paypal_unavailable"), 502
    except requests.RequestException as exc:
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
    mailer = current_app.extensions["mailer"]
    subject, text = monitor.cancel_email(account, public_base() + url_for(".monitoring", lang=account.get("lang") or "en"))
    mailer.send(account["email"], subject, text)  # تأكيد الإلغاء بلغة العميل
    monitor.notify_owner(mailer, current_app.config["OWNER_EMAIL"], "Cancelled by customer", account)
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
    page = public_base() + url_for('.badge_verify', domain=domain)
    img = public_base() + url_for('.badge', domain=domain)
    alt = "Post-quantum TLS grade by Quantum Aether"
    return {"html": f'<a href="{page}"><img src="{img}" alt="{alt}"></a>',
            "markdown": f"[![{alt}]({img})]({page})"}


def badge_svg(grade, checked_at=None):
    color, value = {'stale': ('#64748b', 'stale: rescan'), 'undetermined': ('#64748b', 'undetermined')}.get(grade, BADGE_STYLE.get(grade, BADGE_STYLE[None]))
    label = "post-quantum TLS"
    lw, vw = 7 * len(label) + 12, 7 * len(value) + 14  # تقدير عرض النص بخط 11px
    w = lw + vw
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="{label}: {value}">
<title>{label}: {value}</title><desc>One TLS observation, not a security guarantee. Last checked: {checked_at or 'unknown'}.</desc>
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
    evidence = badge_evidence.for_domain(db(), domain)
    grade = evidence['grade'] if evidence['state'] == 'fresh' else (evidence['state'] if evidence['state'] != 'not_scanned' else None)
    checked = badge_evidence.moment(evidence['checked_at'])
    response = Response(badge_svg(grade, checked.isoformat() if checked else None), mimetype="image/svg+xml")
    response.headers["Cache-Control"] = f"public, max-age={evidence['cache_seconds']}"
    response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    return response


@bp.get('/api/v1/badge/<domain>')
def badge_status(domain):
    try:
        domain = quantum_vuln_scanner.normalize_domain(domain)
    except quantum_vuln_scanner.ScanError as exc:
        return jsonify(error=exc.code), 400
    evidence = badge_evidence.for_domain(db(), domain)
    response = jsonify(dict(evidence, verification_url=public_base() + url_for('.badge_verify', domain=domain)))
    response.headers['Cache-Control'] = f"public, max-age={evidence['cache_seconds']}"
    return response


@bp.get('/verify/<domain>')
def badge_verify(domain):
    try:
        domain = quantum_vuln_scanner.normalize_domain(domain)
    except quantum_vuln_scanner.ScanError:
        abort(404)
    response = make_response(render_template('badge_verify.html', evidence=badge_evidence.for_domain(db(), domain)))
    response.headers['X-Robots-Tag'] = 'noindex'
    response.headers['Cache-Control'] = 'no-store'
    return response


OG_VERSION = "1"  # غيّره حين يتغير تصميم الصورة فتُبنى من جديد


def _og_response(key, build):
    if not og_image.available():
        abort(404)
    path = og_image.cached_png(os.path.join(current_app.config["DATA_DIR"], "og"), f"{OG_VERSION}|{key}", build)
    response = send_file(path, mimetype="image/png", max_age=86400)
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@bp.get("/og/default.png")
def og_default():
    return _og_response("default", og_image.render_default)


@bp.get("/og/site/<domain>.png")
def og_site(domain):
    try:
        domain = quantum_vuln_scanner.normalize_domain(domain)
    except quantum_vuln_scanner.ScanError:
        abort(404)
    summary, _ = known_result_for(domain)
    if not summary:
        abort(404)
    day = str(summary["scanned_at"])[:10]
    return _og_response(f"site|{domain}|{summary['grade']}|{summary['pq']}|{summary.get('unsure')}|{day}",
                        lambda: og_image.render_result(domain, summary["grade"], summary["pq"], summary.get("unsure"), day))


@bp.get("/og/country/<code>.png")
def og_country(code):
    board = cached_countries() or abort(404)
    e = next((x for x in board["entries"] if x["code"] == code.lower()), None) or abort(404)
    name = countries.name(e["code"], "en")
    return _og_response(f"country|{e['code']}|{board['week']}|{e['pct']}|{e['rank']}|{board['countries']}|{e['delta_pp']}",
                        lambda: og_image.render_country(name, e["pct"], e["rank"], board["countries"], e["delta_pp"], board["week"]))


@bp.get("/og/scan/<scan_id>.png")
def og_scan(scan_id):
    scan = sales_db.get_scan(db(), scan_id) or abort(404)
    r = scan["result"]
    tls = r["key_exchange"].get("version") or r["certificate"].get("negotiated_version")
    unsure = adoption.is_unsure(r["key_exchange"], tls)
    day = str(r["scanned_at"])[:10]
    return _og_response(f"scan|{scan_id}",
                        lambda: og_image.render_result(r["domain"], r["grade"], bool(r["key_exchange"].get("pq")), unsure, day))


@bp.get("/robots.txt")
def robots():
    agents = "".join(f"User-agent: {name}\n" for name in [*AI_CRAWLERS, "*"])
    body = (agents + "Allow: /\nDisallow: /admin\nDisallow: /report/\nDisallow: /api/paypal/\nDisallow: /monitor/\nDisallow: /api/monitor/\n\n"
            f"Sitemap: {public_base()}/sitemap.xml\n"
            f"# AI agents: machine-readable summary and API at {public_base()}/llms.txt\n"
            f"# Full text for AI agents (guides + live figures in one file): {public_base()}/llms-full.txt\n"
            f"# Content feed (Atom): {public_base()}/feed.xml\n")
    return Response(body, mimetype="text/plain")


SITEMAP_CHUNK = 2500  # نطاقات لكل ملف (× لغتين) تحت حدّ 50 ألف رابط بهامش واسع


def _template_day(name):  # تاريخ آخر تعديل حقيقي لقالب الصفحة
    mtime = os.path.getmtime(os.path.join(BASE_DIR, "templates", name))
    return dt.datetime.fromtimestamp(mtime, dt.timezone.utc).date().isoformat()


def _sitemap_pages():
    site_langs, de_langs, legal_langs = ("en", "ar"), ("en", "ar", "de"), legal.LANGS
    pages = [("/", _template_day("index.html"), de_langs), ("/monitoring", _template_day("monitoring.html"), de_langs),
             ("/sample-report", sample_result()["scanned_at"][:10], site_langs),
             ("/research", _template_day("research.html"), site_langs),
             ("/guides", max(g["updated"] for g in guides.GUIDES.values()), site_langs),
             ("/study/top-1000-post-quantum-tls", study_data()["scanned_on"], de_langs)]
    adoption_weeks = adoption.weeks(db())
    pages.append(("/adoption", adoption.week_monday(adoption_weeks[-1]).isoformat() if adoption_weeks
                  else study_data()["scanned_on"], de_langs))
    pages.append(("/scanning", _template_day("scanning.html"), de_langs))
    pages.append(("/deadlines", deadlines.UPDATED, de_langs))
    pages.append(("/business", _template_day("commercial.html"), de_langs))
    pages.append(("/pricing", _template_day("commercial.html"), de_langs))
    pages.append(("/agency", _template_day("agency.html"), de_langs))
    board = countries.leaderboard(db())
    if board:
        week_day = adoption.week_monday(board["week"]).isoformat()
        pages.append(("/adoption/countries", week_day, de_langs))
        pages += [(f"/adoption/countries/{e['code']}", week_day, de_langs) for e in board["entries"]]
    pages += [(f"/guides/{slug}", g["updated"], site_langs) for slug, g in guides.GUIDES.items()]
    pages.append(("/compare", _template_day("compare.html"), site_langs))
    pages.append(("/gravity", _template_day("gravity.html"), site_langs))
    pages.append(("/agents", agent_discovery.UPDATED, site_langs))
    legal_date = os.path.getmtime(os.path.join(BASE_DIR, "legal.py"))
    legal_day = dt.datetime.fromtimestamp(legal_date, dt.timezone.utc).date().isoformat()
    pages += [(f"/{slug}", legal_day, legal_langs) for slug in legal.PAGES]
    return pages


def _sitemap_domains():
    """كل النطاقات التي لها صفحة /site/ مفهرسة: المتتبّع الأسبوعي (بتاريخ فحصها) ثم ما تبقى من الدراسة."""
    rows = adoption.site_domains(db())
    known = {d for d, _ in rows}
    study_day = study_data()["scanned_on"]
    rows += [(site["domain"], study_day) for site in study_data()["sites"] if site["domain"] not in known]
    return [(domain, day) for domain, day in rows if not search_indexing.is_excluded(domain)]


def _urlset(pages):
    base = public_base()

    def esc(u):
        return u.replace("&", "&amp;")

    parts = []
    for path, day, langs in pages:
        default = "de" if langs == legal.LANGS else "en"
        alternates = "".join(f'<xhtml:link rel="alternate" hreflang="{alt}" href="{esc(f"{base}{path}?lang={alt}")}"/>'
                             for alt in langs)
        alternates += f'<xhtml:link rel="alternate" hreflang="x-default" href="{esc(f"{base}{path}?lang={default}")}"/>'
        for lang in langs:
            parts.append(f"  <url><loc>{esc(f'{base}{path}?lang={lang}')}</loc><lastmod>{day}</lastmod>{alternates}</url>\n")
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            + "".join(parts) + "</urlset>\n")
    return Response(body, mimetype="application/xml")


@bp.get("/sitemap.xml")
def sitemap():
    """فهرس خرائط: صفحات الموقع + ملف لكل 2500 نطاق. lastmod لكل جزء = أحدث تاريخ فيه."""
    base = public_base()
    pages = _sitemap_pages()
    domains = _sitemap_domains()
    entries = [(f"{base}/sitemap-pages.xml", max(day for _, day, _ in pages))]
    for i in range(0, len(domains), SITEMAP_CHUNK):
        chunk = domains[i:i + SITEMAP_CHUNK]
        entries.append((f"{base}/sitemap-sites-{i // SITEMAP_CHUNK + 1}.xml", max(day for _, day in chunk)))
    body = ('<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "".join(f"  <sitemap><loc>{url}</loc><lastmod>{day}</lastmod></sitemap>\n" for url, day in entries)
            + "</sitemapindex>\n")
    return Response(body, mimetype="application/xml")


@bp.get("/sitemap-pages.xml")
def sitemap_pages():
    return _urlset(_sitemap_pages())


@bp.get("/sitemap-sites-<int:n>.xml")
def sitemap_sites(n):
    chunk = _sitemap_domains()[(n - 1) * SITEMAP_CHUNK:n * SITEMAP_CHUNK] if n >= 1 else []
    if not chunk:
        abort(404)
    return _urlset([(f"/site/{d}", day, ("en", "ar")) for d, day in chunk])


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


@bp.get("/feed.xml")
def feed():
    """خلاصة Atom للمحتوى (الدراسة والأدلة) ليكتشفها الزواحف والمجمّعات ومساعدات الذكاء بسرعة."""
    base = public_base()

    def esc(t):
        return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def day_to_iso(d):
        return f"{d}T00:00:00Z"

    entries = [
        (f"{base}/study/top-1000-post-quantum-tls", study_data()["scanned_on"],
         "Post-quantum TLS in the top 1,000 sites",
         "Open dataset: share of the Tranco top 1,000 that negotiate X25519MLKEM768, with per-domain results."),
    ]
    entries.append((f"{base}/agents?lang=en", agent_discovery.UPDATED,
                    "Quantum Aether tools for AI agents",
                    "Public TLS and post-quantum observations through HTTP API and remote MCP, with evidence, examples and measurement limits."))
    for slug, g in guides.GUIDES.items():
        entries.append((f"{base}/guides/{slug}", g["updated"], g["en"]["title"], g["en"]["description"]))
    entries.append((f"{base}/deadlines", deadlines.UPDATED, deadlines.TEXT["en"]["title"], deadlines.TEXT["en"]["description"]))
    board = cached_countries()
    if board and board["entries"]:
        top = board["entries"][0]
        entries.append((f"{base}/adoption/countries#{board['week']}", adoption.week_monday(board["week"]).isoformat(),
                        f"Post-quantum TLS by country, week {board['week']}",
                        f"{board['countries']} countries ranked; #1 {countries.name(top['code'], 'en')} at {top['pct']}%."))
    snap = cached_snapshot()
    if snap:  # مدخل جديد كل أسبوع (المعرّف يتضمن الأسبوع) فيظهر في القارئات كخبر جديد
        moved = snap["changes"]
        detail = (f" {len(moved['adopted'])} switched to post-quantum key exchange and {len(moved['dropped'])} lost it this week."
                  if moved else "")
        entries.append((f"{base}/adoption#{snap['week']}", snap["week_start"],
                        f"Post-quantum TLS adoption, week {snap['week']}",
                        f"{snap['pq']} of {snap['reachable']} top sites ({snap['pct']}%) negotiate X25519MLKEM768.{detail}"))
    updated = day_to_iso(max(e[1] for e in entries))
    items = []
    for url, day, title, summary in entries:
        items.append(
            "  <entry>\n"
            f"    <title>{esc(title)}</title>\n"
            f'    <link href="{esc(url)}"/>\n'
            f"    <id>{esc(url)}</id>\n"
            f"    <updated>{day_to_iso(day)}</updated>\n"
            f"    <summary>{esc(summary)}</summary>\n"
            "  </entry>\n")
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        "  <title>Quantum Aether — post-quantum TLS</title>\n"
        f'  <link href="{base}/"/>\n'
        f'  <link rel="self" href="{base}/feed.xml"/>\n'
        f"  <id>{base}/</id>\n"
        f"  <updated>{updated}</updated>\n"
        "  <author><name>Quantum Aether</name></author>\n"
        + "".join(items) + "</feed>\n")
    return Response(body, mimetype="application/atom+xml")


@bp.get("/llms.txt")
def llms_txt():
    return Response(render_template("llms.txt", base=public_base(), price=current_app.config["PRICE"],
                                    retry_count=len(study_retry_domains())),
                    mimetype="text/plain")


def html_to_markdown(fragment):
    """تحويل بسيط لنص الأدلة (HTML نظيف نكتبه نحن) إلى Markdown لملف llms-full.txt."""
    from html.parser import HTMLParser

    class Conv(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.out, self.href, self.pre = [], None, False

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag in ("h1", "h2", "h3"):
                self.out.append("\n\n" + "#" * (int(tag[1]) + 1) + " ")
            elif tag == "p":
                self.out.append("\n\n")
            elif tag == "li":
                self.out.append("\n- ")
            elif tag == "pre":
                self.pre = True
                self.out.append("\n\n```\n")
            elif tag == "code" and not self.pre:
                self.out.append("`")
            elif tag == "a":
                self.href = attrs.get("href")
                self.out.append("[")
            elif tag == "br":
                self.out.append("\n")

        def handle_endtag(self, tag):
            if tag == "pre":
                self.pre = False
                self.out.append("\n```")
            elif tag == "code" and not self.pre:
                self.out.append("`")
            elif tag == "a":
                href = self.href or ""
                if href.startswith("/"):
                    href = public_base() + href
                self.out.append(f"]({href})")
                self.href = None

        def handle_data(self, data):
            self.out.append(data if self.pre else re.sub(r"\s+", " ", data))

    conv = Conv()
    conv.feed(fragment)
    return re.sub(r"\n{3,}", "\n\n", "".join(conv.out)).strip()


@bp.get("/llms-full.txt")
def llms_full_txt():
    """كل المحتوى المفيد في ملف واحد: ملخص llms.txt + أرقام المتتبّع الحية + نص الأدلة كاملاً.
    زواحف الذكاء الاصطناعي ووكلاؤه يقرؤونه بطلب واحد بدل عشرات الصفحات."""
    base = public_base()
    parts = [render_template("llms.txt", base=base, price=current_app.config["PRICE"]).strip()]
    snap = cached_snapshot()
    if snap:
        lines = [f"\n\n## Live adoption figures (week {snap['week']}, scanned {snap['scanned_at'][:10]})\n",
                 f"- Tranco top 1,000: {snap['pq']} of {snap['reachable']} reachable sites ({snap['pct']}%) negotiate X25519MLKEM768."]
        if snap.get("top10k"):
            t = snap["top10k"]
            lines.append(f"- Tranco top 10,000: {t['pq']} of {t['reachable']} ({t['pct']}%).")
        for sector in snap["sectors"]:
            label = sector["labels"].get("en") or sector["key"]
            lines.append(f"- {label}: {sector['pq']} of {sector['reachable']} measured sites.")
        if snap.get("providers"):
            lines.append(f"\n### Share of sites with post-quantum key exchange by hosting network ({snap['providers']['period']})\n")
            lines.append("| Network | Sites | Post-quantum |\n|---|---|---|")
            lines += [f"| {r['name']} (AS{r['asn']}) | {r['reachable']} | {r['pct']}% |" for r in snap["providers"]["rows"]]
        lines.append(f"\nPer-domain answers: {base}/site/<domain> (for example {base}/site/github.com). "
                     f"Full data: {base}/adoption.csv (CC BY 4.0).")
        parts.append("\n".join(lines))
    for slug, g in guides.GUIDES.items():
        parts.append(f"\n\n---\n\n# {g['en']['title']}\n\nSource: {base}/guides/{slug} (updated {g['updated']})\n\n"
                     + html_to_markdown(g["en"]["body"]))
    return Response("\n".join(parts) + "\n", mimetype="text/plain")


@bp.get("/.well-known/security.txt")
@bp.get("/security.txt")
def security_txt():
    """RFC 9116: موقع يبيع خدمة أمنية يجب أن يقول أين يُبلَّغ عن الثغرات."""
    expires = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=180)).strftime("%Y-%m-%dT00:00:00Z")
    email = re.search(r"mailto:([^\"'>]+)", legal.EMAIL)
    contact = email.group(1) if email else legal.EMAIL
    body = (f"Contact: mailto:{contact}\nExpires: {expires}\nPreferred-Languages: en, de, ar\n"
            f"Canonical: {public_base()}/.well-known/security.txt\nPolicy: {public_base()}/scanning\n")
    return Response(body, mimetype="text/plain")


@bp.get("/apple-touch-icon.png")
@bp.get("/apple-touch-icon-precomposed.png")
def apple_touch_icon():
    response = current_app.send_static_file("apple-touch-icon.png")
    response.headers["Cache-Control"] = "public, max-age=604800"
    return response


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


@bp.post("/api/ev")
def track_event():
    """حدث داخل الصفحة (لمس خانة الفحص، مثال، إرسال، نتيجة...). نفس قواعد /api/pv: من صفحتنا فقط،
    بلا كوكيز، بصمة يومية لا تُربط بين الأيام، والمدير لا يُحسب. أي خطأ يُهمَل."""
    if request.headers.get("Sec-Fetch-Site", "same-origin") != "same-origin" or is_admin_visitor():
        return "", 204
    try:
        data = json.loads(request.get_data(as_text=True)[:1000] or "{}")
        if not isinstance(data, dict):
            return "", 204
        page = analytics_db.normalize_path(str(data.get("page", ""))) or "(other)"
        lang = str(data.get("lang", ""))[:2] if str(data.get("lang", ""))[:2] in ("en", "ar", "de") else "?"
        day = dt.date.today().isoformat()
        ua = request.headers.get("User-Agent", "")
        salt = current_app.config["HASH_SALT"].encode()
        visitor = hmac.new(salt, f"{day}|{request.remote_addr}|{ua}".encode(), hashlib.sha256).hexdigest()[:16]
        analytics_db.record_event(db(), day, str(data.get("name", ""))[:20], page, lang, visitor,
                                  not ua or bool(analytics_db.BOT_RE.search(ua)))
    except Exception:  # الإحصاءات ثانوية
        log.exception("event tracking failed")
    return "", 204


@bp.after_app_request
def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.path in ('/', '/agents', '/llms.txt', '/llms-full.txt', '/openapi.yaml'):
        response.headers.add('Link', f'<{public_base()}/.well-known/agent-service.json>; rel="service-desc"; type="application/json"')
        response.headers.add('Link', f'<{public_base()}/agents?lang=en>; rel="service-doc"; type="text/html"')
    if request.path.startswith(('/scan/', '/api/')) or (request.endpoint == 'site.compare' and request.args.get('a')):
        response.headers.setdefault('Cache-Control', 'no-store')
        response.headers.setdefault('X-Robots-Tag', 'noindex')
    if request.path.startswith('/scan/'):
        response.headers['Referrer-Policy'] = 'no-referrer'
    if request.path.startswith(("/report/", "/admin", "/monitor/", "/alerts/", "/pack/")):
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
    response = make_response(_error(429, "rate_limited"))
    response.headers['Retry-After'] = '3600'
    return response


@bp.app_errorhandler(400)
def _bad_request(_e):
    if is_api_request():
        return jsonify(error='invalid_request', message='Expected a JSON object.'), 400
    return render_template('error.html', message=texts()['errors']['invalid_domain']), 400


@bp.app_errorhandler(413)
def _too_large(_e):
    if is_api_request():
        return jsonify(error='request_too_large'), 413
    return render_template('error.html', message=texts()['errors']['invalid_domain']), 413


@bp.app_errorhandler(500)
def _server_error(_e):
    return _error(500, "server_error")


import agent_discovery
agent_discovery.register(bp, {'base': public_base, 'db': db, 'scan': perform_scan, 'summary': scan_summary, 'sample': sample_result,
                             'crypto_create_order': crypto_create_order, 'crypto_verify': crypto_verify})

import gravity_web
gravity_web.register(bp, db)

app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="127.0.0.1", port=5000, debug=os.environ.get("FLASK_DEBUG") == "1")
