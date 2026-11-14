"""Deploy only the recent trial-conversion copy and aggregate funnel events.

Does not touch scheduled content, scan follow-up code, or transparency files.
Uses exact-content guards, backups, local smoke checks, and rollback.
"""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path("/root/quantum-aether")
TARGET = Path("/var/www/quantum_saas")
UNIT = "quantum_saas"
SIMPLE_FILES = ("analytics_db.py", "i18n.py", "templates/admin.html")
APP = "quantum_saas_app.py"


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def patch_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one production anchor for {label}, found {count}")
    return text.replace(old, new, 1)


def patch_app(text):
    if "def record_conversion_event(" in text or "trial_created" in text or "subscription_active" in text:
        raise RuntimeError("Conversion events already exist in production; refusing a duplicate deployment")
    text = patch_once(text,
        '''def client_hash():
    salt = current_app.config["HASH_SALT"].encode()
    return hmac.new(salt, (request.remote_addr or "").encode(), hashlib.sha256).hexdigest()[:32]


def payments_enabled():''',
        '''def client_hash():
    salt = current_app.config["HASH_SALT"].encode()
    return hmac.new(salt, (request.remote_addr or "").encode(), hashlib.sha256).hexdigest()[:32]


def record_conversion_event(name, page="/monitoring"):
    """Record an aggregate funnel event; no account identifier or email enters analytics."""
    try:
        if is_admin_visitor():
            return
        day = dt.date.today().isoformat()
        ua = request.headers.get("User-Agent", "")
        salt = current_app.config["HASH_SALT"].encode()
        visitor = hmac.new(salt, f"{day}|{request.remote_addr}|{ua}".encode(), hashlib.sha256).hexdigest()[:16]
        analytics_db.record_event(db(), day, name, page, current_lang(), visitor,
                                  not ua or bool(analytics_db.BOT_RE.search(ua)), is_test_request())
    except Exception:
        log.exception("conversion event tracking failed")


def payments_enabled():''', "conversion event helper")
    text = patch_once(text,
        '''            if send_dashboard_link(conn, account):
                monitor.notify_owner(mailer, current_app.config["OWNER_EMAIL"], "New free trial", account,''',
        '''            if send_dashboard_link(conn, account):
                record_conversion_event("trial_created")
                monitor.notify_owner(mailer, current_app.config["OWNER_EMAIL"], "New free trial", account,''',
        "successful trial creation")
    text = patch_once(text,
        '''    monitor_db.set_status(conn, account["id"], "ACTIVE", subscription_id)
    token = monitor_db.rotate_token(conn, account["id"])''',
        '''    monitor_db.set_status(conn, account["id"], "ACTIVE", subscription_id)
    record_conversion_event("subscription_active")
    token = monitor_db.rotate_token(conn, account["id"])''',
        "verified subscription activation")
    text = patch_once(text,
        '''        analytics_db.record_event(db(), day, str(data.get("name", ""))[:20], page, lang, visitor,
                                  not ua or bool(analytics_db.BOT_RE.search(ua)))''',
        '''        analytics_db.record_event(db(), day, str(data.get("name", ""))[:20], page, lang, visitor,
                                  not ua or bool(analytics_db.BOT_RE.search(ua)), is_test_request())''',
        "test traffic exclusion")
    return text


def smoke_check():
    script = r'''
import os, tempfile
import analytics_db, quantum_saas_app
from werkzeug.security import generate_password_hash
with tempfile.TemporaryDirectory() as folder:
    app = quantum_saas_app.create_app({"TESTING": True, "TRUSTED_PROXIES": 0,
        "DATA_DIR": folder, "PUBLIC_URL": "https://ather-quantum.com",
        "HASH_SALT": "conversion-smoke", "ADMIN_PASSWORD_HASH": generate_password_hash("smoke")})
    with app.test_client() as client:
        response = client.get("/monitoring?lang=ar")
        assert response.status_code == 200, response.status_code
        page = response.get_data(as_text=True)
        assert "ابدأ تجربة 14 يوماً مجاناً" in page
        response = client.get("/admin", headers={"Authorization": "Basic YWRtaW46c21va2U="})
        assert response.status_code == 200, response.status_code
        admin = response.get_data(as_text=True)
        assert "trial created and access email sent" in admin
        assert "subscription verified active" in admin
    with app.test_request_context("/monitoring?lang=ar", environ_base={"REMOTE_ADDR": "192.0.2.4"},
                                 headers={"User-Agent": "Mozilla/5.0 conversion-smoke"}):
        quantum_saas_app.record_conversion_event("trial_created")
        counts = analytics_db.event_funnel(quantum_saas_app.db(), "0000-01-01")
        assert counts["trial_created"] == 1, counts["trial_created"]
print("conversion funnel smoke check passed")
'''
    run([str(TARGET / ".venv312/bin/python3"), "-B", "-c", script], cwd=TARGET,
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))


def fetch(path):
    for attempt in range(8):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000" + path, timeout=15) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as response:
            return response.code, response.read().decode("utf-8", "replace")
        except Exception:
            if attempt == 7:
                raise
            time.sleep(2)


for name in SIMPLE_FILES:
    baseline = subprocess.check_output(["git", "show", "HEAD:" + name], cwd=ROOT)
    if (TARGET / name).read_bytes() != baseline:
        raise SystemExit(f"Production drift in {name}; no files changed")

app_path = TARGET / APP
app_before = app_path.read_text(encoding="utf-8")
app_after = patch_app(app_before)

Path("/root/backups").mkdir(parents=True, exist_ok=True)
backup = Path(tempfile.mkdtemp(prefix="pre-conversion-funnel-", dir="/root/backups"))
files = list(SIMPLE_FILES) + [APP]
for name in files:
    shutil.copy2(TARGET / name, backup / Path(name).name)

try:
    for name in SIMPLE_FILES:
        src, dst = ROOT / name, TARGET / name
        tmp = dst.with_name(dst.name + ".conversion-new")
        shutil.copyfile(src, tmp)
        os.chmod(tmp, 0o644)
        os.replace(tmp, dst)
    tmp = app_path.with_name(app_path.name + ".conversion-new")
    tmp.write_text(app_after, encoding="utf-8")
    os.chmod(tmp, 0o644)
    os.replace(tmp, app_path)

    smoke_check()
    run(["systemctl", "restart", UNIT])
    run(["systemctl", "is-active", "--quiet", UNIT])
    status, body = fetch("/monitoring?lang=ar")
    assert status == 200 and "ابدأ تجربة 14 يوماً مجاناً" in body
    status, body = fetch("/admin")
    assert status == 401  # admin remains protected
    print("published /monitoring and conversion funnel events; admin authentication remains required")
    print("backup:", backup)
except BaseException:
    for name in SIMPLE_FILES:
        shutil.copy2(backup / Path(name).name, TARGET / name)
    shutil.copy2(backup / Path(APP).name, app_path)
    subprocess.run(["systemctl", "restart", UNIT], check=False)
    raise
