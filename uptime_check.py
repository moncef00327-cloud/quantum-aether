# uptime_check.py
# منبّه توقف الموقع + إصلاح ذاتي. يعمل كل 5 دقائق (quantum_uptime.timer) بصلاحية root لأنه يعيد تشغيل الخدمات.
# - يفحص التطبيق مباشرة (127.0.0.1:8000) والموقع العام (عبر Caddy وTLS).
# - بعد فشلين متتاليين: يعيد تشغيل الجزء المعطّل (quantum_saas أو caddy) ويراسل المالك.
# - يرسل رسالة «عاد الموقع» عند التعافي. لا يكرر التنبيه كل 5 دقائق (رسالة عند البدء وأخرى عند العودة).
# حدّه: لا يكشف توقف الخادم كله (لن يعمل هو أيضاً)؛ لذلك يُنصح بمراقب خارجي مجاني إضافةً إليه.
import json
import os
import subprocess
import sys
import time
import urllib.request

from mailer import Mailer

STATE = os.environ.get("QS_UPTIME_STATE", "/var/lib/quantum_uptime/state.json")
PUBLIC = (os.environ.get("QS_PUBLIC_URL") or "https://ather-quantum.com").rstrip("/")
LOCAL = "http://127.0.0.1:8000"
FAILS_BEFORE_ACTION = 2
MAIL_CHECK_EVERY = 3600  # ثانية: فحص صحة البريد مرة كل ساعة
MAIL_PROBE_TO = "delivered@resend.dev"  # عنوان اختبار من Resend: يتحقق من قبول المرسل دون رسالة حقيقية
UA = {"User-Agent": "QuantumAether-Uptime/1.0"}


def probe(url, timeout=10):
    """يعيد (نجح؟, وصف). النجاح = 200 وصفحة تحوي اسم الموقع، في أقل من timeout."""
    started = time.monotonic()
    try:
        req = urllib.request.Request(url + "/?lang=en", headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(200000).decode("utf-8", "replace")
            ms = int((time.monotonic() - started) * 1000)
            if r.status == 200 and "Quantum Aether" in body:
                return True, f"200 in {ms} ms"
            return False, f"HTTP {r.status}, unexpected body ({ms} ms)"
    except Exception as exc:  # مهلة، رفض اتصال، 5xx، شهادة...
        return False, f"{type(exc).__name__}: {exc}"[:300]


def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"fails": 0, "down_since": None, "alerted": False}


def save_state(path, state):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, path)


def decide(state, local_ok, public_ok, now):
    """منطق صافٍ قابل للاختبار. يعيد (الحالة الجديدة، إجراءات). الإجراءات: restart:<unit>، alert_down، alert_up."""
    actions = []
    state = dict(state)
    if local_ok and public_ok:
        if state.get("alerted"):
            actions.append("alert_up")
        return {"fails": 0, "down_since": None, "alerted": False}, actions
    state["fails"] = state.get("fails", 0) + 1
    state["down_since"] = state.get("down_since") or now
    if state["fails"] >= FAILS_BEFORE_ACTION:
        # التطبيق نفسه متوقف ← أعد تشغيله؛ التطبيق سليم والعام متوقف ← المشكلة في Caddy/TLS
        if state["fails"] in (FAILS_BEFORE_ACTION, FAILS_BEFORE_ACTION + 3):  # محاولتان فقط، لا حلقة إعادة تشغيل
            actions.append("restart:quantum_saas" if not local_ok else "restart:caddy")
        if not state.get("alerted"):
            actions.append("alert_down")
            state["alerted"] = True
    return state, actions


def mail_due(state, now_ts):
    return now_ts - state.get("mail_checked", 0) >= MAIL_CHECK_EVERY


def mail_decide(state, ok):
    """يعيد (الحالة، إجراء أو None). ينبّه مرة واحدة عند العطل ومرة عند العودة."""
    state = dict(state)
    action = None
    if not ok and state.get("mail_ok", True):
        action = "mail_down"
    elif ok and not state.get("mail_ok", True):
        action = "mail_up"
    state["mail_ok"] = ok
    return state, action


def check_mail(state, owner, now_ts):
    """يرسل رسالة اختبار بالمرسل الأساسي فقط (بلا احتياطي) ليكشف رفض النطاق قبل أن يخسر زائر رسالته."""
    if not mail_due(state, now_ts):
        return state
    state = dict(state, mail_checked=now_ts)
    probe_mailer = Mailer(os.environ.get("RESEND_API_KEY", ""), os.environ.get("QS_MAIL_FROM", ""))
    if not probe_mailer.enabled:
        return state
    ok = probe_mailer.send(MAIL_PROBE_TO, "Quantum Aether mail health check", "Automated hourly sender check.")
    state, action = mail_decide(state, ok)
    print("mail check:", "ok" if ok else "FAILED " + probe_mailer.last_error, "|", action or "")
    alert = Mailer(os.environ.get("RESEND_API_KEY", ""), os.environ.get("QS_MAIL_FROM", ""),
                   fallback_sender=os.environ.get("QS_MAIL_FROM_FALLBACK", ""))
    if owner and action == "mail_down":
        alert.send(owner, "[Quantum Aether] SITE EMAIL IS FAILING",
                   f"Resend rejected the site's sender ({os.environ.get('QS_MAIL_FROM', '')}).\n\n"
                   f"Error: {probe_mailer.last_error}\n\n"
                   "Visitors cannot receive confirmation links, receipts or alerts until this is fixed. "
                   "Check the domain in Resend (resend.com/domains) and QS_MAIL_FROM in /etc/quantum_saas.env.")
    if owner and action == "mail_up":
        alert.send(owner, "[Quantum Aether] site email works again", "The hourly sender check passed again.")
    return state


def main():
    now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    local_ok, local_info = probe(LOCAL)
    public_ok, public_info = probe(PUBLIC)
    state, actions = decide(load_state(STATE), local_ok, public_ok, now)
    report = f"app (127.0.0.1:8000): {local_info}\npublic ({PUBLIC}): {public_info}"
    print(now, "|", report.replace("\n", " | "), "|", actions or "ok")
    restarted = []
    for action in actions:
        if action.startswith("restart:"):
            unit = action.split(":", 1)[1]
            result = subprocess.run(["systemctl", "restart", unit], capture_output=True, text=True)
            restarted.append(f"{unit}: {'restarted' if result.returncode == 0 else 'restart FAILED ' + result.stderr.strip()}")
    mailer = Mailer(os.environ.get("RESEND_API_KEY", ""), os.environ.get("QS_MAIL_FROM", ""),
                    fallback_sender=os.environ.get("QS_MAIL_FROM_FALLBACK", ""))
    owner = os.environ.get("QS_OWNER_EMAIL", "")
    if owner and mailer.enabled:
        if "alert_down" in actions:
            mailer.send(owner, f"[Quantum Aether] SITE DOWN since {state['down_since']}",
                        f"{PUBLIC} failed {state['fails']} checks in a row (every 5 minutes).\n\n{report}\n\n"
                        + ("Automatic action: " + "; ".join(restarted) + "\n" if restarted else "")
                        + "\nYou will get another email when it is back.\nLogs: journalctl -u quantum_saas -u caddy --since -1h")
        if "alert_up" in actions:
            mailer.send(owner, "[Quantum Aether] site is back up", f"{PUBLIC} is answering again.\n\n{report}")
    old = load_state(STATE)
    for key in ("mail_checked", "mail_ok"):  # decide() يعيد حالة جديدة بلا مفاتيح البريد
        if key in old:
            state.setdefault(key, old[key])
    state = check_mail(state, owner, int(time.time()))
    save_state(STATE, state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
