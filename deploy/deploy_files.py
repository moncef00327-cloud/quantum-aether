"""Deploy selected files from this work copy to /var/www/quantum_saas with backup, smoke checks and rollback.
Usage (root, from /root/qa-audit-work):  python3 deploy/deploy_files.py --base <commit> --tag <name> FILE [FILE ...]
Refuses if any live file differs from <commit> (someone else changed it) unless it already equals the work copy.
Backs up the live files and the SQLite DB to /root/backups/pre-<tag>-<stamp>, copies, restarts, smoke-checks
/, /pricing, /business, /monitoring, /agency, /audit in ar/en/de; any failure restores the backup and restarts."""
from pathlib import Path
import argparse, hashlib, os, shutil, sqlite3, subprocess, sys, time, urllib.error, urllib.request

WORK = Path(__file__).resolve().parent.parent
TARGET = Path('/var/www/quantum_saas')
DB = Path('/var/lib/quantum_saas/quantum_saas.db')
BASE = 'https://ather-quantum.com'
UNIT = 'quantum_saas'
PAGES = ['/', '/pricing', '/business', '/monitoring', '/agency', '/audit', '/sample-report']


def sha(b):
    return hashlib.sha256(b).hexdigest()


def git_show(commit, path):
    r = subprocess.run(['git', '-C', str(WORK), 'show', f'{commit}:{path}'], capture_output=True)
    return r.stdout if r.returncode == 0 else None


def fetch(path):
    req = urllib.request.Request(BASE + path, headers={'User-Agent': 'qa-deploy-smoke'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')


def wait_active():
    for _ in range(30):
        if subprocess.run(['systemctl', 'is-active', '--quiet', UNIT]).returncode == 0 and fetch('/?lang=en')[0] == 200:
            return True
        time.sleep(2)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--tag', required=True)
    ap.add_argument('--expect', action='append', default=[], help='PATH::TEXT that must appear after deploy')
    ap.add_argument('files', nargs='+')
    a = ap.parse_args()
    for name in a.files:
        live = TARGET / name
        work = (WORK / name).read_bytes()
        if live.exists() and sha(live.read_bytes()) == sha(work):
            continue
        base = git_show(a.base, name)
        if live.exists() and (base is None or sha(live.read_bytes()) != sha(base)):
            sys.exit(f'live {name} differs from {a.base}; someone else changed it - stop')
        if not live.exists() and base is not None:
            sys.exit(f'live {name} missing but exists in {a.base} - stop')
    stamp = time.strftime('%Y%m%d%H%M%S')
    backup = Path(f'/root/backups/pre-{a.tag}-{stamp}')
    backup.mkdir(parents=True)
    existed = []
    for name in a.files:
        if (TARGET / name).exists():
            d = backup / name
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(TARGET / name, d)
            existed.append(name)
    src = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    dst = sqlite3.connect(backup / 'quantum_saas.db')
    src.backup(dst); dst.close(); src.close()
    os.chmod(backup / 'quantum_saas.db', 0o600)
    print('backup:', backup)
    started = time.strftime('%Y-%m-%d %H:%M:%S')
    try:
        for name in a.files:
            (TARGET / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(WORK / name, TARGET / name)
        subprocess.run(['systemctl', 'restart', UNIT], check=True)
        if not wait_active():
            raise RuntimeError('service did not come back')
        bad = []
        for p in PAGES:
            for lang in ('ar', 'en', 'de'):
                s, _ = fetch(f'{p}?lang={lang}')
                print(f'[{s}] {p}?lang={lang}')
                if s != 200:
                    bad.append((p, lang, s))
        for e in a.expect:
            p, text = e.split('::', 1)
            s, b = fetch(p)
            ok = s == 200 and text in b
            print(f"[{'OK' if ok else 'FAIL'}] {p} contains {text!r}")
            if not ok:
                bad.append((p, text))
        out = subprocess.run(['journalctl', '-u', UNIT, '--since', started, '--no-pager', '-o', 'cat'],
                             capture_output=True, text=True).stdout
        errs = [l for l in out.splitlines() if 'Traceback' in l or ' ERROR ' in l]
        if errs:
            print('\n'.join(errs[:20])); bad.append('journal errors')
        if bad:
            raise RuntimeError(f'smoke failed: {bad}')
    except Exception as exc:
        print('ROLLBACK:', exc)
        for name in a.files:
            if name in existed:
                shutil.copy2(backup / name, TARGET / name)
            elif (TARGET / name).exists():
                (TARGET / name).unlink()
        subprocess.run(['systemctl', 'restart', UNIT])
        wait_active()
        sys.exit(1)
    print('deployed at', time.strftime('%Y-%m-%d %H:%M:%S %Z'))


if __name__ == '__main__':
    main()
