"""Publish EUR agency pack + EUR monitoring subscriptions with the company billing form, and eps for EUR orders.

Usage on the server, as root, from /root/qa-audit-work:

    python3 deploy/deploy_eur_checkout.py                       # stage 1: code (pack in EUR; subscriptions keep the
                                                                 #   legacy USD plans until EUR plan ids exist)
    python3 deploy/deploy_eur_checkout.py --plans FILE          # stage 2: append PAYPAL_PLAN_STARTER_EUR /
                                                                 #   PAYPAL_PLAN_BUSINESS_EUR (live ids) and restart

Steps: refuse if a live file differs from the base commit -> run the related tests from the work copy -> back up the
files, /etc/quantum_saas.env and the SQLite DB to /root/backups/pre-eur-checkout-* -> copy -> restart -> smoke
checks. Any failure after copying rolls back and restarts the old version. Old USD plans are never touched.
"""
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

WORK = Path(__file__).resolve().parent.parent
TARGET = Path('/var/www/quantum_saas')
ENV_FILE = Path('/etc/quantum_saas.env')
DB = Path('/var/lib/quantum_saas/quantum_saas.db')
BASE = 'https://ather-quantum.com'
UNIT = 'quantum_saas'
BASE_COMMIT = '4bcbd65'
CHANGED = ['quantum_saas_app.py', 'monitor.py', 'i18n.py', 'audit.py', 'audit_checkout.py', 'sales_db.py',
           'static/pack-checkout.js', 'static/subscribe.js', 'templates/admin.html', 'templates/agency.html',
           'templates/audit.html', 'templates/commercial.html', 'templates/executive_brief.html',
           'templates/monitor_dashboard.html', 'templates/monitoring.html', 'tools/paypal_setup_plans.py']
NEW = ['company_billing.py', 'static/company-form.js', 'templates/_company_form.html']
PLAN_KEYS = ('PAYPAL_PLAN_STARTER_EUR', 'PAYPAL_PLAN_BUSINESS_EUR')
TESTS = ['tests/test_packs.py', 'tests/test_eur_checkout.py', 'tests/test_audit_checkout.py', 'tests/test_audit.py',
         'tests/test_trial.py', 'tests/test_regressions.py']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git_show(path):
    return subprocess.run(['git', '-C', str(WORK), 'show', f'{BASE_COMMIT}:{path}'], capture_output=True, check=True).stdout


def fetch(path):
    req = urllib.request.Request(BASE + path, headers={'User-Agent': 'qa-deploy-smoke'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')


def wait_active():
    for _ in range(30):
        if subprocess.run(['systemctl', 'is-active', '--quiet', UNIT]).returncode == 0 and fetch('/?lang=en')[0] == 200:
            return True
        time.sleep(2)
    return False


def smoke(expect_sub):
    checks = []
    for lang in ('ar', 'en', 'de'):
        s, b = fetch(f'/agency?lang={lang}')
        checks.append((f'agency {lang}', s == 200 and 'currency=EUR' in b and 'enable-funding=card,eps' in b
                       and 'pack-checkout-form' in b and 'company-form.js' in b and '199.00 EUR' in b))
        s, b = fetch(f'/monitoring?lang={lang}')
        checks.append((f'monitoring {lang}', s == 200 and 'sub-company-form' in b and f'currency={expect_sub}' in b
                       and f'29.00 {expect_sub}' in b))
        s, b = fetch(f'/audit?lang={lang}')
        checks.append((f'audit {lang}', s == 200 and 'audit-checkout-form' in b and 'currency=EUR' in b
                       and 'select name="country"' in b))
    s, b = fetch('/pricing?lang=en')
    checks.append(('pricing', s == 200 and '199.00 EUR' in b and f'29.00 {expect_sub}' in b))
    for path in ('/static/company-form.js', '/static/pack-checkout.js', '/static/subscribe.js', '/', '/scan?lang=en'):
        s, _ = fetch(path)
        checks.append((path, s in (200, 302, 303, 405) and s != 500))
    return checks


def journal_errors(since):
    out = subprocess.run(['journalctl', '-u', UNIT, '--since', since, '--no-pager', '-o', 'cat'], capture_output=True,
                         text=True).stdout
    return [l for l in out.splitlines() if 'Traceback' in l or ' ERROR ' in l or 'Exception' in l]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--plans', help='file with PAYPAL_PLAN_STARTER_EUR=... and PAYPAL_PLAN_BUSINESS_EUR=... (live)')
    args = ap.parse_args()
    stamp = time.strftime('%Y%m%d%H%M%S')
    backup = Path(f'/root/backups/pre-eur-checkout-{stamp}')
    started = time.strftime('%Y-%m-%d %H:%M:%S')

    code_live = all((TARGET / n).exists() and sha((TARGET / n).read_bytes()) == sha((WORK / n).read_bytes())
                    for n in CHANGED + NEW)
    if not code_live:
        for name in CHANGED:
            if sha((TARGET / name).read_bytes()) != sha(git_show(name)):
                sys.exit(f'live {name} changed since {BASE_COMMIT}; rebase first')
        for name in NEW:
            if (TARGET / name).exists():
                sys.exit(f'live {name} already exists')
    plans = {}
    if args.plans:
        for line in Path(args.plans).read_text().splitlines():
            line = line.split('#')[0].strip()
            if '=' in line:
                k, v = line.split('=', 1)
                if k.strip() in PLAN_KEYS:
                    plans[k.strip()] = v.strip()
        if set(plans) != set(PLAN_KEYS) or not all(v.startswith('P-') for v in plans.values()):
            sys.exit('plans file must contain both EUR plan ids')
        if any(line.split('=', 1)[0].strip() in PLAN_KEYS for line in ENV_FILE.read_text().splitlines()):
            sys.exit('EUR plan ids already in the env file')

    py = WORK / '.venv-test/bin/python'
    t = subprocess.run([str(py), '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-o', 'pythonpath=tests .', *TESTS],
                       cwd=WORK)
    if t.returncode:
        sys.exit('tests failed; nothing deployed')

    backup.mkdir(parents=True)
    for name in CHANGED + [n for n in NEW if (TARGET / n).exists()]:
        dest = backup / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TARGET / name, dest)
    shutil.copy2(ENV_FILE, backup / 'quantum_saas.env')
    os.chmod(backup / 'quantum_saas.env', 0o600)
    src = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    dst = sqlite3.connect(backup / 'quantum_saas.db')
    src.backup(dst)
    dst.close(); src.close()
    os.chmod(backup / 'quantum_saas.db', 0o600)
    print(f'backup: {backup}')

    env_before = ENV_FILE.read_bytes()
    created = [n for n in NEW if not (TARGET / n).exists()]
    try:
        if not code_live:
            for name in CHANGED + NEW:
                shutil.copy2(WORK / name, TARGET / name)
        if plans:
            with ENV_FILE.open('a') as f:
                f.write('\n# Monitoring subscriptions in EUR (live PayPal plans; the USD plans above stay for existing subscribers)\n')
                for k in PLAN_KEYS:
                    f.write(f"{k}='{plans[k]}'\n")
        subprocess.run(['systemctl', 'restart', UNIT], check=True)
        if not wait_active():
            raise RuntimeError('service did not come back')
        checks = smoke('EUR' if plans or 'PAYPAL_PLAN_STARTER_EUR' in ENV_FILE.read_text() else 'USD')
        for name, ok in checks:
            print(f"[{'OK' if ok else 'FAIL'}] {name}")
        if not all(ok for _, ok in checks):
            raise RuntimeError('smoke checks failed')
        errors = journal_errors(started)
        if errors:
            print('\n'.join(errors[:20]))
            raise RuntimeError('errors in the journal')
    except Exception as exc:
        print(f'ROLLBACK: {exc}')
        ENV_FILE.write_bytes(env_before)
        for name in CHANGED:
            shutil.copy2(backup / name, TARGET / name)
        for name in created:
            (TARGET / name).unlink(missing_ok=True)
        subprocess.run(['systemctl', 'restart', UNIT])
        wait_active()
        sys.exit(1)
    print('deployed at', time.strftime('%Y-%m-%d %H:%M:%S %Z'))


if __name__ == '__main__':
    main()
