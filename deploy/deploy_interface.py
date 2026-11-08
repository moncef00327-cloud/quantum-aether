"""Publish the shared interface without replacing the running backend release."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

source = Path('/root/quantum-aether')
target = Path('/var/www/quantum_saas').resolve()
files = ['templates/base.html', 'templates/index.html', 'templates/gravity.html',
         'static/aether.css', 'static/aether-dark.css', 'static/aether-ui.js', 'static/color-directions.html', 'gravity_web.py']
backup = Path(tempfile.mkdtemp(prefix='pre-interface-', dir='/root/backups'))
absent = []
for name in files:
    dest = backup / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if (target / name).exists():
        shutil.copy2(target / name, dest)
    else:
        absent.append(name)

try:
    assert 'gravity_web.register(bp, db)' in (target / 'quantum_saas_app.py').read_text(), 'Gravity route missing'
    for name in files:
        shutil.copyfile(source / name, target / name)
        os.chmod(target / name, 0o644)
    check = '''
import tempfile
import quantum_saas_app
with tempfile.TemporaryDirectory() as data:
    app = quantum_saas_app.create_app({'TESTING': True, 'DATA_DIR': data, 'PAYPAL_CLIENT_ID': '', 'PAYPAL_CLIENT_SECRET': ''})
    with app.test_client() as client:
        for path in ['/', '/gravity', '/adoption', '/monitoring', '/guides', '/research', '/sample-report', '/compare', '/agency']:
            for lang in ['ar', 'en']:
                response = client.get(path + '?lang=' + lang)
                assert response.status_code == 200, (path, lang, response.status_code)
                assert b'aether.css' in response.data, path
print('Production-backend template checks passed: 18 pages')
'''
    subprocess.run([str(target / '.venv/bin/python'), '-c', check], cwd=target,
                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), check=True)
    subprocess.run(['systemctl', 'restart', 'quantum_saas'], check=True)
    for path, marker in [
        ('/?lang=ar', b'aether.css'), ('/?lang=en', b'scanner-panel'),
        ('/gravity?lang=ar', b'gravity-metrics'), ('/adoption?lang=en', b'aether.css'),
        ('/monitoring?lang=ar', b'aether.css'), ('/guides?lang=en', b'aether.css'),
        ('/sample-report?lang=en', b'aether.css'),
        ('/static/aether.css?v=20261106.4', b'--mint'),
        ('/static/aether-dark.css?v=20261106.4', b'.mobile-dock'),
        ('/static/aether-ui.js?v=20261106.1', b'aria-expanded'),
        ('/static/color-directions.html', b'palette-name'),
    ]:
        response = subprocess.run(['curl', '--retry', '4', '--retry-connrefused', '--retry-delay', '2',
                                   '--max-time', '25', '--fail', '--silent', '--show-error',
                                   'https://ather-quantum.com' + path], check=True, capture_output=True).stdout
        assert marker in response, f'Missing expected content: {path}'
        print('OK ' + path)
    subprocess.run(['systemctl', 'is-active', '--quiet', 'quantum_saas'], check=True)
    print(f'Interface deployed. Backup: {backup}')
except BaseException:
    for name in files:
        if name in absent:
            (target / name).unlink(missing_ok=True)
        else:
            shutil.copy2(backup / name, target / name)
    subprocess.run(['systemctl', 'restart', 'quantum_saas'], check=False)
    raise
