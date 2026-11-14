"""Publish the immediate Grade A next step on scan results with rollback."""
from pathlib import Path
import os
import shutil
import sqlite3
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path('/root/quantum-aether')
TARGET = Path('/var/www/quantum_saas').resolve()
BASE = 'https://ather-quantum.com'
NAME = 'templates/scan.html'


def restart():
    subprocess.run(['systemctl', 'restart', 'quantum_saas'], check=True)
    subprocess.run(['systemctl', 'is-active', '--quiet', 'quantum_saas'], check=True)


def fetch(path):
    for attempt in range(8):
        try:
            with urllib.request.urlopen(BASE + path, timeout=25) as response:
                assert response.status == 200, (path, response.status)
                return response.read().decode('utf-8', 'replace')
        except Exception:
            if attempt == 7:
                raise
            time.sleep(2)


baseline = subprocess.check_output(['git', 'show', 'HEAD:' + NAME], cwd=ROOT)
assert (TARGET / NAME).read_bytes() == baseline, 'Production drift: ' + NAME
backup = Path(tempfile.mkdtemp(prefix='pre-grade-a-offer-', dir='/root/backups'))
shutil.copy2(TARGET / NAME, backup / 'scan.html')

try:
    temporary = (TARGET / NAME).with_name('scan.html.grade-a-new')
    shutil.copyfile(ROOT / NAME, temporary)
    os.chmod(temporary, 0o644)
    os.replace(temporary, TARGET / NAME)

    smoke = '''
import tempfile
import quantum_saas_app, sales_db
from tests.test_app import RESULT
def seed(app, grade, pq, group, scan_id):
    conn=sales_db.connect(app.config['DATA_DIR']+'/quantum_saas.db')
    result=dict(RESULT,domain='example.org',grade=grade)
    result['key_exchange']=dict(RESULT['key_exchange'],pq=pq,group=group)
    sales_db.create_scan(conn,scan_id,'token-'+scan_id,result,'smoke',is_test=True)
    conn.close()
with tempfile.TemporaryDirectory() as data:
    app=quantum_saas_app.create_app({'TESTING':True,'DATA_DIR':data,'PAYPAL_CLIENT_ID':'','PAYPAL_CLIENT_SECRET':''})
    seed(app,'A',True,'X25519MLKEM768','grade-a-smoke')
    seed(app,'B',False,'x25519','grade-b-smoke')
    with app.test_client() as client:
        good=client.get('/scan/grade-a-smoke?lang=ar').get_data(as_text=True)
        offer=good.index('id="grade-a-next-step"')
        alert=good.index('id="alert"')
        summary=good.index('<table class="kv">')
        assert offer < alert < summary
        assert good.count('id="alert"') == 1
        classical=client.get('/scan/grade-b-smoke?lang=ar').get_data(as_text=True)
        assert 'id="grade-a-next-step"' not in classical
        assert 'id="scan-trial"' in classical
print('Immediate Grade A offer and existing classical flow verified')
'''
    subprocess.run([str(TARGET / '.venv312/bin/python3'), '-c', smoke], cwd=TARGET,
                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), check=True)
    restart()

    conn = sqlite3.connect('file:/var/lib/quantum_saas/quantum_saas.db?mode=ro', uri=True)
    row = conn.execute("SELECT id FROM scans WHERE grade='A' AND is_test=0 ORDER BY created_at DESC LIMIT 1").fetchone()
    conn.close()
    assert row, 'No real Grade A scan available for live verification'
    page = fetch('/scan/' + row[0] + '?lang=ar')
    assert 'id="grade-a-next-step"' in page and 'id="alert"' in page
    assert page.index('id="grade-a-next-step"') < page.index('id="alert"') < page.index('<table class="kv">')
    assert page.count('id="alert"') == 1
    print(f'Live Grade A result verified; backup: {backup}')
except BaseException:
    shutil.copy2(backup / 'scan.html', TARGET / NAME)
    restart()
    raise
