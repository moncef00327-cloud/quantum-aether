"""Make the configured Resend sender the public contact address."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request

TARGET = Path('/var/www/quantum_saas')
APP = TARGET / 'quantum_saas_app.py'
OLD = '''    address = parseaddr(current_app.config.get("REPLY_TO") or current_app.config.get("OWNER_EMAIL")
                        or current_app.config.get("MAIL_FROM") or "")[1]'''
NEW = '''    address = parseaddr(current_app.config.get("MAIL_FROM") or current_app.config.get("REPLY_TO")
                        or current_app.config.get("OWNER_EMAIL") or "")[1]'''
before = APP.read_text(encoding='utf-8')
if before.count(OLD) != 1:
    raise SystemExit('Expected public contact helper was not found exactly once; no changes made')
backup = Path(tempfile.mkdtemp(prefix='pre-resend-contact-', dir='/root/backups'))
shutil.copy2(APP, backup / APP.name)
try:
    tmp = APP.with_name(APP.name + '.resend-contact-new')
    tmp.write_text(before.replace(OLD, NEW, 1), encoding='utf-8')
    os.chmod(tmp, 0o644)
    os.replace(tmp, APP)
    subprocess.run([str(TARGET / '.venv312/bin/python3'), '-c',
                    'import ast,pathlib,sys; ast.parse(pathlib.Path(sys.argv[1]).read_text(),filename=sys.argv[1])', str(APP)],
                   cwd=TARGET, check=True)
    subprocess.run(['systemctl', 'restart', 'quantum_saas'], check=True)
    subprocess.run(['systemctl', 'is-active', '--quiet', 'quantum_saas'], check=True)
    for attempt in range(8):
        try:
            body = urllib.request.urlopen('https://ather-quantum.com/business?lang=ar', timeout=20).read().decode('utf-8', 'replace')
            break
        except Exception:
            if attempt == 7:
                raise
            time.sleep(2)
    assert 'mailto:alerts@ather-quantum.com' in body, 'Resend contact address missing from business page'
    assert 'mailto:sajad.vip56@gmail.com' not in body, 'Personal Gmail still exposed on business page'
    print('Resend contact verified: alerts@ather-quantum.com; backup:', backup)
except BaseException:
    shutil.copy2(backup / APP.name, APP)
    subprocess.run(['systemctl', 'restart', 'quantum_saas'], check=False)
    raise
