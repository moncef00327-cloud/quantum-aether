"""Publish the public aggregate transparency page with a drift guard and rollback."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path('/root/quantum-aether')
TARGET = Path('/var/www/quantum_saas').resolve()
BASE = 'https://ather-quantum.com'
FILES = ['quantum_saas_app.py', 'public_stats.py', 'templates/base.html', 'templates/transparency.html']
TRACKED = {'quantum_saas_app.py', 'templates/base.html'}


def restart():
    subprocess.run(['systemctl', 'restart', 'quantum_saas'], check=True)
    subprocess.run(['systemctl', 'is-active', '--quiet', 'quantum_saas'], check=True)


def fetch(path):
    for attempt in range(8):
        try:
            with urllib.request.urlopen(BASE + path, timeout=25) as response:
                assert response.status == 200, (path, response.status)
                return response.read()
        except Exception:
            if attempt == 7:
                raise
            time.sleep(2)


# Stop if production changed since the reviewed workspace base.
for name in TRACKED:
    baseline = subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=ROOT)
    assert (TARGET / name).read_bytes() == baseline, 'Production drift: ' + name
for name in set(FILES) - TRACKED:
    assert not (TARGET / name).exists(), 'Unexpected production file: ' + name

backup = Path(tempfile.mkdtemp(prefix='pre-transparency-', dir='/root/backups'))
(backup / 'manifest.json').write_text(json.dumps({'files': FILES}, indent=2))
try:
    for name in FILES:
        destination = TARGET / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + '.transparency-new')
        shutil.copyfile(ROOT / name, temporary)
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)

    smoke = '''
import tempfile
import quantum_saas_app
with tempfile.TemporaryDirectory() as data:
    app=quantum_saas_app.create_app({'TESTING':True,'DATA_DIR':data,'PUBLIC_URL':'https://ather-quantum.com','PAYPAL_CLIENT_ID':'','PAYPAL_CLIENT_SECRET':''})
    with app.test_client() as client:
        for path,marker in [('/transparency?lang=ar','شفافية الزيارات'),('/transparency?lang=en','Traffic and scan transparency')]:
            response=client.get(path);assert response.status_code==200,(path,response.status_code);assert marker.encode() in response.data,path
        data=client.get('/api/public-stats.json');assert data.status_code==200 and data.json['period']['days']==30
        sitemap=client.get('/sitemap-pages.xml');assert sitemap.status_code==200 and b'/transparency?lang=en' in sitemap.data
print('Transparency routes and sitemap smoke check passed')
'''
    subprocess.run([str(TARGET / '.venv312/bin/python3'), '-c', smoke], cwd=TARGET,
                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), check=True)
    restart()
    for path, marker in [('/transparency?lang=ar', 'شفافية الزيارات'),
                         ('/transparency?lang=en', 'Traffic and scan transparency')]:
        body = fetch(path).decode('utf-8', 'replace')
        assert marker in body, path
        print('verified', path)
    payload = json.loads(fetch('/api/public-stats.json'))
    assert payload['period']['days'] == 30 and 'individual_records' in payload['privacy']
    manifest = {'status': 'published', 'url': BASE + '/transparency', 'backup': str(backup),
                'files': FILES, 'period': payload['period'], 'updated_at': payload['updated_at']}
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
except BaseException:
    for name in FILES:
        destination = TARGET / name
        if name in TRACKED:
            shutil.copy2(backup / name, destination)
        else:
            destination.unlink(missing_ok=True)
    restart()
    raise
