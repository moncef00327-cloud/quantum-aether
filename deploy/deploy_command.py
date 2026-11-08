"""Deploy the user-owned Sites review interface to the existing Vultr Flask app."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path('/root/quantum-aether')
TARGET = Path('/var/www/quantum_saas').resolve()
FILES = ['templates/report.html', 'templates/base.html', 'templates/command_home.html',
         'templates/command/ar.html', 'templates/command/en.html',
         'templates/command/sidebar-ar.html', 'templates/command/sidebar-en.html',
         'templates/command/header-ar.html', 'templates/command/header-en.html',
         'static/command/app.js', 'static/command/app.css',
         'static/command/pages.css', 'static/command/shell.js']
OBSOLETE = ['static/style.css', 'static/aether.css', 'static/aether-dark.css',
            'static/observatory.css', 'static/aether-ui.js', 'static/color-directions.html']
# This publication changes templates/assets only; keep the active backend intact.
assert (TARGET/'quantum_saas_app.py').read_bytes() == (ROOT/'quantum_saas_app.py').read_bytes(), 'Production backend differs from tested backend'
assert all((ROOT/name).is_file() for name in FILES)
BACKUP = Path(tempfile.mkdtemp(prefix='pre-command-review-', dir='/root/backups'))
existing = []
for name in FILES + OBSOLETE:
    src = TARGET/name
    if src.exists():
        saved = BACKUP/name
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, saved)
        existing.append(name)
(BACKUP/'manifest.json').write_text(json.dumps({'files': FILES, 'removed': OBSOLETE, 'existing': existing}))

def restart():
    subprocess.run(['systemctl', 'restart', 'quantum_saas'], check=True)
    subprocess.run(['systemctl', 'is-active', '--quiet', 'quantum_saas'], check=True)

def fetch(path):
    for attempt in range(8):
        try:
            with urllib.request.urlopen('https://ather-quantum.com'+path, timeout=25) as response:
                assert response.status == 200
                return response.read()
        except Exception:
            if attempt == 7:
                raise
            time.sleep(1)

try:
    for name in FILES:
        target = TARGET/name
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name+'.command-new')
        shutil.copyfile(ROOT/name, temporary)
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    for name in OBSOLETE:
        (TARGET/name).unlink(missing_ok=True)
    check = '''
import tempfile
import quantum_saas_app
with tempfile.TemporaryDirectory() as data:
    app = quantum_saas_app.create_app({'TESTING': True, 'DATA_DIR': data, 'PAYPAL_CLIENT_ID': '', 'PAYPAL_CLIENT_SECRET': ''})
    with app.test_client() as client:
        for lang in ['ar','en']:
            response = client.get('/?lang='+lang)
            assert response.status_code == 200
            assert b'command-root' in response.data
            assert b'20261107-sample4' in response.data
            assert b'LLM / API' in response.data
        for path in ['/business','/pricing','/agency','/monitoring','/gravity','/guides','/llms.txt','/llms-full.txt','/openapi.yaml','/impressum','/datenschutz','/agb']:
            response = client.get(path)
            assert response.status_code == 200, path
            if response.mimetype == 'text/html':
                assert b'command-sidebar' in response.data, path
                assert b'primary-nav' not in response.data and b'mobile-dock' not in response.data, path
                assert b'/static/aether' not in response.data and b'/static/style.css' not in response.data, path
print('Production integration checks passed')
'''
    subprocess.run([str(TARGET/'.venv/bin/python'), '-c', check], cwd=TARGET,
                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), check=True)
    restart()
    for lang in ['ar','en']:
        page = fetch('/?lang='+lang)
        assert b'command-root' in page and b'20261107-sample4' in page
        print('Verified review interface: '+lang)
    for name in ['static/command/app.js','static/command/app.css','static/command/pages.css','static/command/shell.js']:
        assert fetch('/'+name+'?v=20261107-sample4') == (ROOT/name).read_bytes(), name
        print('Verified exact asset: '+name)
    for path in ['/sample-report?lang=en','/sample-report?lang=ar','/business?lang=ar','/pricing?lang=en','/llms.txt','/llms-full.txt','/openapi.yaml']:
        body = fetch(path)
        if path.startswith(('/business','/pricing')):
            assert b'command-sidebar' in body and b'primary-nav' not in body and b'mobile-dock' not in body, path
        if path.startswith('/sample-report'):
            assert b'full-report' in body and b'20261107-sample4' in body
        print('Verified '+path)
    for name in OBSOLETE:
        try:
            urllib.request.urlopen('https://ather-quantum.com/'+name+'?v=20261107-sample4',timeout=25)
        except urllib.error.HTTPError as exc:
            assert exc.code == 404, name
        else:
            raise AssertionError('Obsolete asset still served: '+name)
    print('Verified removal of all six obsolete interface assets')
    print('Published https://ather-quantum.com — backup: '+str(BACKUP))
except BaseException:
    for name in FILES + OBSOLETE:
        if name in existing:
            shutil.copy2(BACKUP/name, TARGET/name)
        else:
            (TARGET/name).unlink(missing_ok=True)
    restart()
    raise
