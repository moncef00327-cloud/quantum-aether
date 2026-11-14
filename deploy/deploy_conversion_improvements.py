"""Publish the conversion instrumentation and study/agency presentation improvements."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path('/root/quantum-aether')
TARGET = Path('/var/www/quantum_saas').resolve()
BASE = 'https://ather-quantum.com'
UNIT = 'quantum_saas'
COPY_FILES = [
    'static/command/app.js', 'templates/command/ar.html', 'templates/command/en.html',
]
FILES = COPY_FILES + [
    'quantum_saas_app.py', 'analytics_db.py', 'i18n.py',
    'templates/admin.html', 'templates/scan.html', 'templates/index.html',
]
before = {name: (TARGET / name).read_bytes() for name in FILES}
after = dict(before)


def patch(name, old, new, label):
    source = after[name].decode('utf-8')
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one live anchor in {name}, found {count}')
    after[name] = source.replace(old, new, 1).encode('utf-8')


# Rebuild artifacts are generated from frontend/command/App.tsx and the study JSON.
for name in COPY_FILES:
    source = (ROOT / name).read_bytes()
    if source == before[name]:
        continue
    if name.endswith('ar.html') and 'خُفّضت بسبب نتيجة حرجة أخرى' not in source.decode('utf-8'):
        raise RuntimeError('Arabic command page does not contain the reviewed study explanation')
    if name.endswith('en.html') and 'downgraded for another critical finding' not in source.decode('utf-8'):
        raise RuntimeError('English command page does not contain the reviewed study explanation')
    after[name] = source

# Public business CTAs use configured prices and credit counts.
patch('quantum_saas_app.py',
      '            "report_price": current_app.config["PRICE"], "currency": current_app.config["CURRENCY"],\n            "starter_price": monitor.PLANS["starter"]["price"],',
      '            "report_price": current_app.config["PRICE"], "currency": current_app.config["CURRENCY"],\n'
      '            "agency_price_dual": dual_price_label(current_app.config["PACK_PRICE"], current_app.config["CURRENCY"]),\n'
      '            "agency_credits": current_app.config["PACK_CREDITS"],\n'
      '            "starter_price": monitor.PLANS["starter"]["price"],', 'dynamic agency CTA context')

# Server-confirmed funnel events. These contain visitor-day hashes only, no account IDs or emails.
patch('quantum_saas_app.py',
      '''def record_conversion_event(name, page="/monitoring"):
    """Record an aggregate funnel event; no account identifier or email enters analytics."""
    try:
        if is_admin_visitor():
            return
        day = dt.date.today().isoformat()
        ua = request.headers.get("User-Agent", "")
        salt = current_app.config["HASH_SALT"].encode()
        visitor = hmac.new(salt, f"{day}|{request.remote_addr}|{ua}".encode(), hashlib.sha256).hexdigest()[:16]
        analytics_db.record_event(db(), day, name, page, current_lang(), visitor,
                                  not ua or bool(analytics_db.BOT_RE.search(ua)), is_test_request())''',
      '''def record_conversion_event(name, page="/monitoring", is_test=None):
    """Record an aggregate funnel event; no account identifier or email enters analytics."""
    try:
        if is_admin_visitor():
            return
        day = dt.date.today().isoformat()
        ua = request.headers.get("User-Agent", "")
        salt = current_app.config["HASH_SALT"].encode()
        visitor = hmac.new(salt, f"{day}|{request.remote_addr}|{ua}".encode(), hashlib.sha256).hexdigest()[:16]
        test_event = is_test_request() if is_test is None else bool(is_test)
        analytics_db.record_event(db(), day, name, page, current_lang(), visitor,
                                  not ua or bool(analytics_db.BOT_RE.search(ua)), test_event)''',
      'test-aware conversion event helper')

app_events = [
    ('''    packs.create(db(), pack_id, order["id"], cfg["PACK_CREDITS"], cfg["PACK_PRICE"], cfg["CURRENCY"], current_lang(),
                 now_iso(), is_test_request())
    return jsonify(id=order["id"]), 201''',
     '''    packs.create(db(), pack_id, order["id"], cfg["PACK_CREDITS"], cfg["PACK_PRICE"], cfg["CURRENCY"], current_lang(),
                 now_iso(), is_test_request())
    record_conversion_event("agency_start", "/agency")
    return jsonify(id=order["id"]), 201''', 'agency checkout start'),
    ('''    if status != "COMPLETED":
        return jsonify(status=status), 202
    pack_url = public_base() + url_for(".pack_page", token=token, lang=pack["lang"])''',
     '''    if status != "COMPLETED":
        return jsonify(status=status), 202
    record_conversion_event("agency_paid", "/agency", is_test=pack["is_test"])
    pack_url = public_base() + url_for(".pack_page", token=token, lang=pack["lang"])''', 'agency payment confirmed'),
    ('''    sales_db.create_order(conn, order["id"], scan["id"], cfg["PRICE"], cfg["CURRENCY"], consent_at=now_iso(),
                          is_test=is_test_request())
    return jsonify(id=order["id"]), 201''',
     '''    sales_db.create_order(conn, order["id"], scan["id"], cfg["PRICE"], cfg["CURRENCY"], consent_at=now_iso(),
                          is_test=is_test_request())
    record_conversion_event("checkout_start", "/scan/*")
    return jsonify(id=order["id"]), 201''', 'report checkout start'),
    ('''    sales_db.update_order(conn, order_id, status, capture_id)
    if status == "COMPLETED" and not row["is_test"]:''',
     '''    sales_db.update_order(conn, order_id, status, capture_id)
    if status == "COMPLETED":
        record_conversion_event("purchase_complete", "/scan/*", is_test=row["is_test"])
    if status == "COMPLETED" and not row["is_test"]:''', 'PayPal report payment confirmed'),
    ('''    sales_db.create_order(conn, order["id"], scan["id"], cfg["PRICE"], cfg["CURRENCY"], consent_at=now_iso(),
                          is_test=is_test_request())
    return jsonify(order_id=order["id"], approve_url=approve_url,''',
     '''    sales_db.create_order(conn, order["id"], scan["id"], cfg["PRICE"], cfg["CURRENCY"], consent_at=now_iso(),
                          is_test=is_test_request())
    record_conversion_event("checkout_start", "/scan/*")
    return jsonify(order_id=order["id"], approve_url=approve_url,''', 'agent report checkout start'),
    ('''    sales_db.create_order(conn, order_id, scan["id"], amount, net["token"], consent_at=now_iso(),
                          is_test=is_test_request(), email=email)
    return jsonify(_crypto_order_body(order_id, key, net, amount)), 201''',
     '''    sales_db.create_order(conn, order_id, scan["id"], amount, net["token"], consent_at=now_iso(),
                          is_test=is_test_request(), email=email)
    record_conversion_event("checkout_start", "/scan/*")
    return jsonify(_crypto_order_body(order_id, key, net, amount)), 201''', 'crypto checkout start'),
    ('''    except sales_db.sqlite3.IntegrityError:
        return jsonify(error="tx_already_used"), 409
    if not row["is_test"]:''',
     '''    except sales_db.sqlite3.IntegrityError:
        return jsonify(error="tx_already_used"), 409
    record_conversion_event("purchase_complete", "/scan/*", is_test=row["is_test"])
    if not row["is_test"]:''', 'crypto report payment confirmed'),
    ('''    except sales_db.sqlite3.IntegrityError:
        return jsonify(error="payment_already_consumed"),409
    report_url=public_base()+url_for(".report",token=scan["report_token"])''',
     '''    except sales_db.sqlite3.IntegrityError:
        return jsonify(error="payment_already_consumed"),409
    record_conversion_event("purchase_complete", "/scan/*", is_test=bool(scan.get("is_test")))
    report_url=public_base()+url_for(".report",token=scan["report_token"])''', 'x402 report payment confirmed'),
    ('''    monitor_db.set_plan(conn, account["id"], plan, now_iso())
    return jsonify(account_id=account["id"], plan_id=plan_ids()[plan])''',
     '''    monitor_db.set_plan(conn, account["id"], plan, now_iso())
    record_conversion_event("subscription_start", "/monitoring")
    return jsonify(account_id=account["id"], plan_id=plan_ids()[plan])''', 'trial subscription checkout start'),
    ('''    account_id, _token = monitor_db.create_account(conn, email, plan, current_lang(), consent_at=now_iso())
    raw_domain = str(data.get("domain", "")).strip()''',
     '''    account_id, _token = monitor_db.create_account(conn, email, plan, current_lang(), consent_at=now_iso())
    record_conversion_event("subscription_start", "/monitoring")
    raw_domain = str(data.get("domain", "")).strip()''', 'subscription checkout start'),
]
for old, new, label in app_events:
    patch('quantum_saas_app.py', old, new, label)

patch('analytics_db.py',
      'TRACKED_PREFIXES = ("/", "/monitoring", "/guides", "/study", "/research", "/scan/", "/deadlines", "/site/", "/adoption", "/compare")',
      'TRACKED_PREFIXES = ("/", "/monitoring", "/guides", "/study", "/research", "/scan/", "/deadlines", "/site/", "/adoption", "/compare",\n'
      '                    "/pricing", "/business", "/agency", "/sample-report", "/audit")', 'business page tracking')
patch('analytics_db.py',
      '               "trial_created", "subscription_active",  # نتائج الخادم الفعلية، بعد نجاح البريد/PayPal\n'
      '               "history_csv",',
      '               "trial_created", "subscription_start", "subscription_active",\n'
      '               "checkout_start", "purchase_complete",  # أحداث الخادم بعد إنشاء الطلب أو تأكيد الدفع\n'
      '               "agency_start", "agency_paid",  # تحويلات باقة تقارير العملاء لمقدمي الخدمات\n'
      '               "history_csv",', 'conversion event names')

for lang, old, new in [
    ('en', 'Agencies: see the current price for 10 one-time full reports', 'MSPs and consultants: {credits} client reports for {price_dual}, one payment'),
    ('ar', 'للوكالات: اطّلع على سعر باقة التقارير الكاملة لمرة واحدة', 'لمقدمي الخدمات والاستشاريين: {credits} تقارير للعملاء مقابل {price_dual} دفعة واحدة'),
    ('de', 'Für Agenturen: aktuellen Preis für 10 einmalige Vollberichte ansehen', 'Für MSPs und Berater: {credits} Kundenberichte für {price_dual}, einmalig'),
]:
    patch('i18n.py', f'"agency_home_link": "{old}"', f'"agency_home_link": "{new}"', lang + ' MSP CTA')

patch('templates/scan.html',
      '{{ t.agency_home_link }}</a></p>',
      '{{ t.agency_home_link.format(credits=agency_credits, price_dual=agency_price_dual) }}</a></p>',
      'scan page MSP CTA')
patch('templates/index.html',
      '{{ t.agency_home_link }} →</a></p>',
      '{{ t.agency_home_link.format(credits=agency_credits, price_dual=agency_price_dual) }} →</a></p>',
      'home page MSP CTA')
patch('templates/admin.html',
      '''    <tr><th>trial requested</th><th>trial created and access email sent</th><th>subscription verified active</th><th colspan="3">Server-confirmed conversion events</th></tr>
    <tr><td>{{ events.trial_start }}</td><td>{{ events.trial_created }}</td><td>{{ events.subscription_active }}</td><td colspan="3">No email addresses or account IDs are stored in this event table.</td></tr>''',
      '''    <tr><th>trial requested</th><th>trial created and access email sent</th><th>subscription checkout started</th><th>subscription verified active</th></tr>
    <tr><td>{{ events.trial_start }}</td><td>{{ events.trial_created }}</td><td>{{ events.subscription_start }}</td><td>{{ events.subscription_active }}</td></tr>
    <tr><th>report checkout created</th><th>report payment confirmed</th><th colspan="2">Server-confirmed conversion events</th></tr>
    <tr><td>{{ events.checkout_start }}</td><td>{{ events.purchase_complete }}</td><td colspan="2">Counts start after deployment; no email addresses or account IDs are stored here.</td></tr>
    <tr><th>agency pack checkout</th><th>agency pack paid</th><th colspan="2">MSP / consultant offer</th></tr>
    <tr><td>{{ events.agency_start }}</td><td>{{ events.agency_paid }}</td><td colspan="2">Use these to assess demand for client-report packs.</td></tr>''',
      'admin conversion dashboard')

for name in FILES:
    if after[name] == before[name]:
        raise RuntimeError('No deployment change prepared for ' + name)

backup = Path(tempfile.mkdtemp(prefix='pre-conversion-improvements-', dir='/root/backups'))
for name, payload in before.items():
    saved = backup / name
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_bytes(payload)
(backup / 'manifest.json').write_text(json.dumps({'files': FILES}, indent=2))


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def restart():
    run(['systemctl', 'restart', UNIT])
    run(['systemctl', 'is-active', '--quiet', UNIT])


def fetch(path):
    with urllib.request.urlopen(BASE + path, timeout=25) as response:
        return response.status, response.read().decode('utf-8', 'replace')


try:
    for name, payload in after.items():
        dst = TARGET / name
        tmp = dst.with_name(dst.name + '.conversion-improvements-new')
        tmp.write_bytes(payload)
        os.chmod(tmp, 0o644)
        os.replace(tmp, dst)

    smoke = '''
import tempfile
from werkzeug.security import generate_password_hash
import quantum_saas_app
with tempfile.TemporaryDirectory() as data:
 app=quantum_saas_app.create_app({'TESTING':True,'DATA_DIR':data,'PUBLIC_URL':'https://ather-quantum.com','PAYPAL_CLIENT_ID':'','PAYPAL_CLIENT_SECRET':'','ADMIN_PASSWORD_HASH':generate_password_hash('smoke')})
 with app.test_client() as c:
  root=c.get('/?lang=ar'); assert root.status_code==200
print('conversion improvement smoke passed')
'''
    run([str(TARGET / '.venv312/bin/python3'), '-B', '-c', smoke], cwd=TARGET,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    restart()
    for path, marker in [('/?lang=ar', 'خُفّضت بسبب نتيجة حرجة أخرى'.encode())]:
        for attempt in range(8):
            try:
                status, body = fetch(path)
                break
            except Exception:
                if attempt == 7:
                    raise
                time.sleep(2)
        if status != 200 or (marker and marker.decode() not in body):
            raise RuntimeError(f'Live check failed for {path}')
        print('verified', path)
    print('Conversion improvements published; backup:', backup)
except BaseException:
    for name, payload in before.items():
        dst = TARGET / name
        tmp = dst.with_name(dst.name + '.conversion-improvements-rollback')
        tmp.write_bytes(payload)
        os.chmod(tmp, 0o644)
        os.replace(tmp, dst)
    subprocess.run(['systemctl', 'restart', UNIT], check=False)
    raise
