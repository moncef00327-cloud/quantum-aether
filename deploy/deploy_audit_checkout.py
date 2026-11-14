"""Publish the small-company audit checkout (PayPal, EUR 490) — audit-related files only.

NOT RUN AUTOMATICALLY. Usage on the server, as root:

    python3 deploy/deploy_audit_checkout.py --credentials /root/qa-audit-work/.audit-sandbox.env   # sandbox mode
    python3 deploy/deploy_audit_checkout.py --go-live     # later, only after the sandbox test passed and the owner approved

--credentials: a chmod-600 file with QS_AUDIT_PAYPAL_CLIENT_ID=... and QS_AUDIT_PAYPAL_SECRET=... (sandbox app).
Values are never printed.

Steps: refuse if any live file changed since the snapshot this work is based on (a5db647) -> run the audit tests
from the work copy -> backup files, /etc/quantum_saas.env and the SQLite DB to /root/backups/pre-audit-checkout-* ->
copy the audit files -> append the audit PayPal settings to the env file -> restart quantum_saas -> smoke checks.
Any failure after copying rolls everything back and restarts the old version.
Prices of reports, packs and subscriptions and the subscription logic are not touched.
"""
from pathlib import Path
import argparse
import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

WORK = Path(__file__).resolve().parent.parent          # /root/qa-audit-work
TARGET = Path('/var/www/quantum_saas')
ENV_FILE = Path('/etc/quantum_saas.env')
DB = Path('/var/lib/quantum_saas/quantum_saas.db')
BASE = 'https://ather-quantum.com'
UNIT = 'quantum_saas'
BASE_COMMIT = 'a5db647'   # snapshot of the live tree this change was built on

CHANGED = ['quantum_saas_app.py', 'audit.py', 'legal.py', 'mailer.py', 'paypal_client.py', 'sales_db.py',
           'templates/audit.html', 'templates/admin.html']
NEW = ['audit_checkout.py', 'static/audit-checkout.js']
FILES = CHANGED + NEW
AUDIT_KEYS = ('QS_AUDIT_PAYPAL_CLIENT_ID', 'QS_AUDIT_PAYPAL_CLIENT_SECRET', 'QS_AUDIT_PAYPAL_ENV',
              'QS_AUDIT_PAYMENTS_ENABLED')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git_show(path):
    return subprocess.run(['git', '-C', str(WORK), 'show', f'{BASE_COMMIT}:{path}'], capture_output=True, check=True).stdout


def read_env_file(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            values[k.strip()] = v.strip().strip("'\"")
    return values


def fetch(path, data=None, headers=None):
    req = urllib.request.Request(BASE + path, data=data, headers=dict({'User-Agent': 'qa-deploy-smoke'}, **(headers or {})))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')


def wait_active():
    for _ in range(30):
        if subprocess.run(['systemctl', 'is-active', '--quiet', UNIT]).returncode == 0:
            status, _ = fetch('/?lang=en')
            if status == 200:
                return True
        time.sleep(2)
    return False


def smoke(mode):
    checks = []
    s, body = fetch('/audit?lang=ar')
    checks.append(('audit page ar', s == 200 and 'audit-checkout-form' in body and 'enterprise-quote' in body
                   and 'currency=EUR' in body and 'audit-checkout.js' in body))
    if mode == 'sandbox':
        checks.append(('sandbox notice', 'PayPal-Sandbox' in body or 'PayPal Sandbox' in body))
    for lang in ('en', 'de'):
        s, body = fetch(f'/audit?lang={lang}')
        checks.append((f'audit page {lang}', s == 200 and 'audit-paypal-buttons' in body))
    s, body = fetch('/agency?lang=en')
    checks.append(('agency pack page unchanged', s == 200 and 'pack-checkout.js' in body and 'currency=USD' in body))
    s, body = fetch('/monitoring?lang=en')
    checks.append(('monitoring page', s == 200))
    s, body = fetch('/agb?lang=de')
    checks.append(('AGB mentions audit', s == 200 and 'Subdomain-Audit für kleine Unternehmen' in body))
    s, body = fetch('/api/paypal/audit', data=b'{"name":""}', headers={'Content-Type': 'application/json'})
    checks.append(('server-side validation (no PayPal order)', s == 400 and 'required_fields' in body))
    ok = True
    for name, passed in checks:
        print(f"  [{'OK' if passed else 'FAIL'}] {name}")
        ok &= passed
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--credentials', help='file with sandbox QS_AUDIT_PAYPAL_CLIENT_ID / QS_AUDIT_PAYPAL_SECRET')
    ap.add_argument('--go-live', action='store_true', help='switch the already deployed audit checkout to live PayPal')
    args = ap.parse_args()
    if os.geteuid() != 0:
        sys.exit('run as root')
    stamp = time.strftime('%Y%m%d-%H%M%S')
    backup = Path(f'/root/backups/pre-audit-checkout-{"golive-" if args.go_live else ""}{stamp}')
    backup.mkdir(parents=True)
    os.chmod(backup, 0o700)
    env_before = ENV_FILE.read_bytes()
    shutil.copy2(ENV_FILE, backup / 'quantum_saas.env')
    os.chmod(backup / 'quantum_saas.env', 0o600)

    if args.go_live:
        env = read_env_file(ENV_FILE)
        if env.get('QS_AUDIT_PAYPAL_ENV') != 'sandbox':
            sys.exit('audit checkout is not in sandbox mode; nothing to switch')
        lines = [l for l in env_before.decode().splitlines() if not l.split('=', 1)[0].strip() in AUDIT_KEYS]
        lines += ['# Audit checkout: live PayPal (same live app as reports/packs)',
                  f"QS_AUDIT_PAYPAL_CLIENT_ID='{env['PAYPAL_CLIENT_ID']}'",
                  f"QS_AUDIT_PAYPAL_CLIENT_SECRET='{env['PAYPAL_CLIENT_SECRET']}'",
                  "QS_AUDIT_PAYPAL_ENV='live'", "QS_AUDIT_PAYMENTS_ENABLED='1'"]
        ENV_FILE.write_text('\n'.join(lines) + '\n')
        subprocess.run(['systemctl', 'restart', UNIT], check=True)
        if wait_active() and smoke('live'):
            print('Audit checkout is LIVE. Backup:', backup)
            return
        ENV_FILE.write_bytes(env_before)
        subprocess.run(['systemctl', 'restart', UNIT], check=True)
        sys.exit('go-live smoke check failed; env restored')

    if not args.credentials:
        sys.exit('--credentials is required for the sandbox deployment')
    creds = read_env_file(args.credentials)
    cid = creds.get('QS_AUDIT_PAYPAL_CLIENT_ID')
    secret = creds.get('QS_AUDIT_PAYPAL_CLIENT_SECRET') or creds.get('QS_AUDIT_PAYPAL_SECRET')
    if not (cid and secret):
        sys.exit('credentials file lacks QS_AUDIT_PAYPAL_CLIENT_ID / QS_AUDIT_PAYPAL_SECRET')
    if any(l.split('=', 1)[0].strip() in AUDIT_KEYS for l in env_before.decode().splitlines()):
        sys.exit('env file already has QS_AUDIT_* settings; refusing to append twice')

    # 1. The live files must still be exactly the snapshot this work was built on.
    for name in CHANGED:
        if sha((TARGET / name).read_bytes()) != sha(git_show(name)):
            sys.exit(f'live {name} changed since {BASE_COMMIT}; rebase the audit change first')
    for name in NEW:
        if (TARGET / name).exists():
            sys.exit(f'live {name} already exists')

    # 2. Tests for the audit checkout and the existing audit page must pass in the work copy.
    py = WORK / '.venv-test/bin/python'
    t = subprocess.run([str(py), '-B', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-o', 'pythonpath=tests .',
                        'tests/test_audit_checkout.py', 'tests/test_audit.py'], cwd=WORK)
    if t.returncode:
        sys.exit('audit tests failed; nothing deployed')

    # 3. Backups: files (originals), env file (above), and a consistent SQLite copy.
    for name in CHANGED:
        dest = backup / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TARGET / name, dest)
    src = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    dst = sqlite3.connect(backup / 'quantum_saas.db')
    src.backup(dst)
    dst.close(); src.close()
    os.chmod(backup / 'quantum_saas.db', 0o600)
    print('Backup:', backup)

    def rollback(reason):
        print('ROLLBACK:', reason)
        for name in CHANGED:
            shutil.copy2(backup / name, TARGET / name)
        for name in NEW:
            (TARGET / name).unlink(missing_ok=True)
        ENV_FILE.write_bytes(env_before)
        subprocess.run(['systemctl', 'restart', UNIT])
        print('restored; service', 'active' if wait_active() else 'NOT ACTIVE - check journalctl -u quantum_saas')
        sys.exit(1)

    try:
        # 4. Copy files atomically, keeping root ownership and 0644 like the rest of the tree.
        for name in FILES:
            target = TARGET / name
            tmp = target.with_name(f'.{target.name}.audit-tmp')
            shutil.copyfile(WORK / name, tmp)
            os.chmod(tmp, 0o644)
            os.replace(tmp, target)
        # 5. Env: append only the audit PayPal settings (sandbox).
        with ENV_FILE.open('a') as f:
            f.write('\n# Audit checkout (small-company audit, EUR 490): separate PayPal app, sandbox until go-live\n'
                    f"QS_AUDIT_PAYPAL_CLIENT_ID='{cid}'\nQS_AUDIT_PAYPAL_CLIENT_SECRET='{secret}'\n"
                    "QS_AUDIT_PAYPAL_ENV='sandbox'\nQS_AUDIT_PAYMENTS_ENABLED='1'\n")
        # 6. Restart (ExecStartPre runs sales_db -> creates audit_orders / audit_invoice_sequence) and smoke check.
        subprocess.run(['systemctl', 'restart', UNIT], check=True)
        if not wait_active():
            rollback('service did not come back')
        if not smoke('sandbox'):
            rollback('smoke checks failed')
    except Exception as exc:  # noqa: BLE001
        rollback(f'{type(exc).__name__}: {exc}')
    print('Deployed in SANDBOX mode: https://ather-quantum.com/audit?lang=ar')


if __name__ == '__main__':
    main()
