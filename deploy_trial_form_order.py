"""Guarded hotfix for the live React trial form bundle, whose source is not in this checkout."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


TARGET = Path('/var/www/quantum_saas')
EXPECTED = {
    'templates/command_home.html': '895ee3e4e458443a786688f38ea49d40c445e932fff4f6813689393d821ba802',
    'static/command/app.js': '00ee89f6325b245392b7b52bbecab683d0f81a2913da9e05ef43eadc6cd57e8d',
    'static/command/app.css': 'b3eda915304550a7cac14a90e8e47365dcbf6587862327828edf34116010d1b2',
}
CSS_RULES = '''
/* Trial form alignment: checkbox and consent text stay aligned in RTL and LTR. */
.qa-trial-inline .qa-trial-consent{display:grid;grid-template-columns:20px minmax(0,1fr);align-items:start;gap:10px;direction:rtl;text-align:right;line-height:1.6}
.qa-trial-inline .qa-trial-consent input{grid-column:1;align-self:start;margin:3px 0 0;width:20px;height:20px;flex:none}
.qa-trial-inline .qa-trial-consent span{grid-column:2;min-width:0}
.app.en .qa-trial-inline .qa-trial-consent{direction:ltr;text-align:left}
'''


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


for name, expected in EXPECTED.items():
    assert digest(TARGET / name) == expected, f'Live file changed since review: {name}'

backup = Path(tempfile.mkdtemp(prefix='trial-form-order-', dir='/root/backups'))
for name in EXPECTED:
    saved = backup / name
    saved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TARGET / name, saved)


def atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(path.name + '.trial-form-new')
    temporary.write_bytes(content)
    os.chmod(temporary, 0o644)
    os.replace(temporary, path)


def restart() -> None:
    subprocess.run(['systemctl', 'restart', 'quantum_saas'], check=True)
    subprocess.run(['systemctl', 'is-active', '--quiet', 'quantum_saas'], check=True)


try:
    bundle_path = TARGET / 'static/command/app.js'
    bundle = bundle_path.read_text()
    email_start = '(0,n.jsx)("label",{className:"qa-field-label",htmlFor:"trial-email"'
    domain_start = '(0,n.jsx)("label",{className:"qa-field-label",htmlFor:"trial-domain"'
    consent_start = '(0,n.jsxs)("label",{className:"qa-trial-consent"'
    assert bundle.count(email_start) == 1 and bundle.count(domain_start) == 1
    start, domain, end = bundle.index(email_start), bundle.index(domain_start), bundle.index(consent_start)
    assert start < domain < end
    email_field, domain_field = bundle[start:domain], bundle[domain:end]
    assert email_field.count('placeholder:"you@company.com"') == 1
    assert 'placeholder:"company.com"' in domain_field
    updated = bundle[:start] + domain_field + email_field.replace(
        'placeholder:"you@company.com"', 'placeholder:"email@company.com"') + bundle[end:]
    assert updated.index(domain_start) < updated.index(email_start)
    assert 'placeholder:"email@company.com"' in updated
    atomic_write(bundle_path, updated.encode())

    css_path = TARGET / 'static/command/app.css'
    css = css_path.read_text()
    assert '.qa-trial-inline .qa-trial-consent{' in css
    assert 'Trial form alignment:' not in css
    atomic_write(css_path, (css + CSS_RULES).encode())

    home_path = TARGET / 'templates/command_home.html'
    home = home_path.read_text()
    assert home.count('20261114-ui7') == 2
    home = home.replace('20261114-ui7', '20261114-trialform1')
    atomic_write(home_path, home.encode())

    subprocess.run(['node', '--check', str(bundle_path)], check=True)
    smoke = r'''
import tempfile
import quantum_saas_app
with tempfile.TemporaryDirectory() as data:
    app = quantum_saas_app.create_app({'TESTING': True, 'DATA_DIR': data,
        'PUBLIC_URL': 'https://ather-quantum.com', 'PAYPAL_CLIENT_ID': '', 'PAYPAL_CLIENT_SECRET': ''})
    with app.test_client() as client:
        page = client.get('/?lang=ar')
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        assert 'app.js?v=20261114-trialform1' in html
        assert 'app.css?v=20261114-trialform1' in html
        js = client.get('/static/command/app.js?v=20261114-trialform1').get_data(as_text=True)
        assert js.index('htmlFor:"trial-domain"') < js.index('htmlFor:"trial-email"')
        assert 'placeholder:"email@company.com"' in js
        css = client.get('/static/command/app.css?v=20261114-trialform1').get_data(as_text=True)
        assert 'Trial form alignment:' in css
        print('Home page and updated trial assets render correctly')
'''
    subprocess.run([str(TARGET / '.venv312/bin/python3'), '-c', smoke], cwd=TARGET,
                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), check=True)
    restart()
    for name, expected in EXPECTED.items():
        assert digest(TARGET / name) != expected, f'No deployed change: {name}'
    print(f'DEPLOYED OK; service active; backup: {backup}')
except BaseException:
    for name in EXPECTED:
        shutil.copy2(backup / name, TARGET / name)
    restart()
    raise
