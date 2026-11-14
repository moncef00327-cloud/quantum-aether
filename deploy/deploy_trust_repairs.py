"""Publish reviewed trust-plan repairs with per-file drift guards and rollback."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path('/root/quantum-aether')
TARGET = Path('/var/www/quantum_saas')
BASE = 'https://ather-quantum.com'
UNIT = 'quantum_saas'

# These files contain only the reviewed trust-plan edits in this worktree.
COPY_FILES = [
    'adoption.py', 'business_pages.py', 'static/command/app.js',
    'templates/adoption.html', 'templates/agency.html', 'templates/command/ar.html',
    'templates/command/en.html', 'templates/commercial.html', 'templates/compare.html',
    'templates/executive_brief.html', 'templates/index.html', 'templates/llms.txt',
    'templates/monitor_dashboard.html', 'templates/monitoring.html',
    'templates/report.html', 'templates/site_page.html', 'templates/study.html',
]

# Files with unrelated local edits are reconstructed from HEAD plus selected diff
# hunks. Any drift on production aborts before the first write.
PATCH_FILES = ['quantum_saas_app.py', 'i18n.py', 'templates/base.html']
TOKENS = {
    'quantum_saas_app.py': [
        'parseaddr', 'contact_email_address', 'dual_price_label', 'public_price_labels',
        'grade_guide_url', 'report_price', 'pq_critical', 'contact_html',
        'audit_price=cfg', 'price_dual=dual_price_label', 'methodology="hrr_retry_once"',
        'usd_per_eur=business_pages.USD_PER_EUR', '**public_price_labels()',
    ],
    'i18n.py': [
        '"grade_definitions"', '"grade_scope"', 'agency_meta', 'agency_lead',
        'agency_items', 'agency_compare', 'agency_home_link', 'mon_one_time_alt',
        'alerts_upsell_cta',
    ],
    'templates/base.html': ['Indicative EUR conversions', 'تواصل معنا', 'Kontakt'],
}


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def live_diff(name):
    result = subprocess.run(['git', 'diff', '--no-index', '--unified=0', '--',
                             str(ROOT / name), str(TARGET / name)],
                            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode not in (0, 1):
        raise RuntimeError(result.stderr)
    return result.stdout


def selected_hunks(name):
    diff = live_diff(name)
    chunks, current = [], None
    for line in diff.splitlines(keepends=True):
        if line.startswith('@@ '):
            if current:
                chunks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current:
        chunks.append(current)
    tokens = TOKENS[name]
    # The old side is the reviewed worktree; the new side is production.
    return [chunk for chunk in chunks if any(
        line.startswith('-') and not line.startswith('---') and any(token in line for token in tokens)
        for line in chunk)]


def apply_hunks(name, baseline):
    raw = live_diff(name)
    chunks = selected_hunks(name)
    if not chunks:
        raise RuntimeError('No reviewed diff hunks selected for ' + name)
    lines = baseline.decode('utf-8').splitlines(keepends=True)
    edits = []
    for chunk in chunks:
        header = chunk[0]
        import re
        match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', header)
        if not match:
            raise RuntimeError('Unrecognized diff hunk: ' + header.strip())
        local_start, local_count = int(match.group(1)), int(match.group(2) or 1)
        prod_start, prod_count = int(match.group(3)), int(match.group(4) or 1)
        local, prod = [], []
        for line in chunk[1:]:
            if line.startswith('\\'):
                continue
            if line.startswith(' '):
                local.append(line[1:]); prod.append(line[1:])
            elif line.startswith('-'):
                local.append(line[1:])
            elif line.startswith('+'):
                prod.append(line[1:])
        index = prod_start - 1 if prod_count else prod_start
        if lines[index:index + prod_count] != prod:
            raise RuntimeError(f'Live production anchor mismatch in {name} at line {prod_start}')
        edits.append((index, prod_count, local))
    for index, count, local in sorted(edits, reverse=True):
        lines[index:index + count] = local
    return ''.join(lines).encode('utf-8')


def restart():
    run(['systemctl', 'restart', UNIT])
    run(['systemctl', 'is-active', '--quiet', UNIT])


def fetch(path):
    for attempt in range(8):
        try:
            with urllib.request.urlopen(BASE + path, timeout=25) as response:
                return response.status, response.read().decode('utf-8', 'replace')
        except Exception:
            if attempt == 7:
                raise
            time.sleep(2)


FILES = COPY_FILES + PATCH_FILES
before, after = {}, {}
for name in FILES:
    current = (TARGET / name).read_bytes()
    before[name] = current
    if name in COPY_FILES:
        baseline = subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=ROOT)
        if current != baseline:
            raise SystemExit('Production drift; no files changed: ' + name)
        after[name] = (ROOT / name).read_bytes()
    else:
        after[name] = apply_hunks(name, current)

backup = Path(tempfile.mkdtemp(prefix='pre-trust-repairs-', dir='/root/backups'))
for name, payload in before.items():
    path = backup / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
(backup / 'manifest.json').write_text(json.dumps({'files': FILES}, indent=2))

try:
    for name, payload in after.items():
        dst = TARGET / name
        tmp = dst.with_name(dst.name + '.trust-new')
        tmp.write_bytes(payload)
        os.chmod(tmp, 0o644)
        os.replace(tmp, dst)

    # Narrow server-side integration smoke: render the public pages and study labels.
    smoke = '''
import tempfile
import quantum_saas_app
with tempfile.TemporaryDirectory() as data:
 app=quantum_saas_app.create_app({'TESTING':True,'DATA_DIR':data,'PUBLIC_URL':'https://ather-quantum.com','PAYPAL_CLIENT_ID':'','PAYPAL_CLIENT_SECRET':''})
 with app.test_client() as c:
  for path in ['/?lang=ar','/study/top-1000-post-quantum-tls?lang=ar','/business?lang=ar','/pricing?lang=ar','/monitoring?lang=ar','/agency?lang=ar','/llms.txt','/impressum?lang=de']:
   r=c.get(path); assert r.status_code==200,(path,r.status_code)
print('trust-plan route smoke passed')
'''
    run([str(TARGET / '.venv312/bin/python3'), '-B', '-c', smoke], cwd=TARGET,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    restart()
    for path, marker in [('/?lang=ar', None), ('/study/top-1000-post-quantum-tls?lang=ar', 'تعريف الدرجات'),
                         ('/pricing?lang=ar', 'اطلب'), ('/monitoring?lang=ar', 'حدود الباقات'),
                         ('/llms.txt', 'EUR')]:
        status, body = fetch(path)
        if status != 200 or (marker and marker not in body):
            raise RuntimeError(f'Live verification failed: {path}, status={status}, marker={marker}')
        print('verified', path)
    print('Published trust-plan repairs; backup:', backup)
except BaseException:
    for name, payload in before.items():
        dst = TARGET / name
        tmp = dst.with_name(dst.name + '.trust-rollback')
        tmp.write_bytes(payload)
        os.chmod(tmp, 0o644)
        os.replace(tmp, dst)
    subprocess.run(['systemctl', 'restart', UNIT], check=False)
    raise
