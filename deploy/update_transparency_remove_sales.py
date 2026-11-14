"""Remove paid-order counts from the public transparency API and page."""
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
BASE = 'https://ather-quantum.com'
FILES = ['public_stats.py', 'templates/transparency.html']
EXPECTED = {
    'public_stats.py': '6a20b595e55537c594d129c721fb9a88ecea90b9813a4f0cf79aff3d50aef5c7',
    'templates/transparency.html': 'cc72209662b80e101647d1039db6a0fd4c2f68e1bcb5955731d23d0f494b272a',
}


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


for name in FILES:
    digest = hashlib.sha256((TARGET / name).read_bytes()).hexdigest()
    assert digest == EXPECTED[name], 'Production drift: ' + name

backup = Path(tempfile.mkdtemp(prefix='pre-transparency-hide-sales-', dir='/root/backups'))
for name in FILES:
    saved = backup / name
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TARGET / name, saved)

try:
    for name in FILES:
        destination = TARGET / name
        temporary = destination.with_name(destination.name + '.hide-sales-new')
        shutil.copyfile(ROOT / name, temporary)
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)

    smoke = '''
import tempfile
import quantum_saas_app
with tempfile.TemporaryDirectory() as data:
    app=quantum_saas_app.create_app({'TESTING':True,'DATA_DIR':data,'PUBLIC_URL':'https://ather-quantum.com','PAYPAL_CLIENT_ID':'','PAYPAL_CLIENT_SECRET':''})
    with app.test_client() as client:
        payload=client.get('/api/public-stats.json').get_json()
        assert 'paid_orders_completed' not in payload['funnel']
        for path in ['/transparency?lang=ar','/transparency?lang=en']:
            response=client.get(path);assert response.status_code==200
            assert 'Completed paid orders'.encode() not in response.data
            assert 'طلبات مدفوعة مكتملة'.encode() not in response.data
print('Paid-order field absent from transparency page and JSON')
'''
    subprocess.run([str(TARGET / '.venv312/bin/python3'), '-c', smoke], cwd=TARGET,
                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), check=True)
    restart()
    payload = json.loads(fetch('/api/public-stats.json'))
    assert 'paid_orders_completed' not in payload['funnel']
    page = fetch('/transparency?lang=ar').decode('utf-8', 'replace')
    assert 'طلبات مدفوعة مكتملة' not in page
    print(json.dumps({'status': 'updated', 'url': BASE + '/transparency', 'backup': str(backup),
                      'paid_order_metric': 'removed from public page and API'}, ensure_ascii=False))
except BaseException:
    for name in FILES:
        shutil.copy2(backup / name, TARGET / name)
    restart()
    raise
