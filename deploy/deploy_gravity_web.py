"""Targeted deployment preserving newer production application changes."""
import datetime
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

source = Path('/root/quantum-aether')
target = Path('/var/www/quantum_saas').resolve()
backup = Path(tempfile.mkdtemp(prefix='pre-gravity-web-', dir='/root/backups'))
files = ['gravity.py', 'gravity_web.py', 'templates/gravity.html',
         'quantum_saas_app.py', 'templates/base.html', 'templates/index.html']
absent = []
for name in files:
    dest = backup / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if (target / name).exists():
        shutil.copy2(target / name, dest)
    else:
        absent.append(name)

try:
    for name in ['gravity.py', 'gravity_web.py', 'templates/gravity.html']:
        shutil.copyfile(source / name, target / name)
        os.chmod(target / name, 0o644)
    app_file = target / 'quantum_saas_app.py'
    content = app_file.read_text()
    if 'gravity_web.register(bp, db)' not in content:
        anchor = '\napp = create_app()'
        assert content.count(anchor) == 1, 'Application registration anchor changed'
        content = content.replace(anchor, '\nimport gravity_web\ngravity_web.register(bp, db)\n' + anchor)
        app_file.write_text(content)
    for name, anchor, insert in [
        ('templates/base.html', '<nav>', '<a href="/gravity?lang={{ lang }}">Gravity Engine</a>'),
        ('templates/index.html', '<section class="hero">', '<p><a class="tag" href="/gravity?lang={{ lang }}">AETHER GRAVITY ENGINE ↗</a></p>'),
    ]:
        path = target / name
        content = path.read_text()
        if '/gravity?' not in content:
            assert anchor in content, f'Missing template anchor: {name}'
            path.write_text(content.replace(anchor, anchor + '\n' + insert, 1))
    subprocess.run(['systemctl', 'restart', 'quantum_saas'], check=True)
    subprocess.run(['systemctl', 'is-active', '--quiet', 'quantum_saas'], check=True)
    for path in ['/?lang=en', '/gravity?lang=ar', '/gravity?lang=en']:
        response = subprocess.run(['curl', '--retry', '4', '--retry-connrefused', '--retry-delay', '2',
                                   '--max-time', '25', '--fail', '--silent', '--show-error',
                                   'https://ather-quatum.cloud' + path], check=True, capture_output=True).stdout
        assert b'AETHER GRAVITY ENGINE' in response, f'Page marker missing: {path}'
        print(f'OK {path}')
    print(f'Backup: {backup}')
except BaseException:
    for name in files:
        if name in absent:
            (target / name).unlink(missing_ok=True)
        else:
            shutil.copy2(backup / name, target / name)
    subprocess.run(['systemctl', 'restart', 'quantum_saas'], check=False)
    raise
