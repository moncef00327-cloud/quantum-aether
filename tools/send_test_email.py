# tools/send_test_email.py
# يرسل رسالة تجريبية إلى بريد صاحب الموقع للتأكد من إعداد Resend.
# التشغيل: set -a; . /etc/quantum_saas.env; set +a; python tools/send_test_email.py
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mailer import Mailer  # noqa: E402


def main():
    mailer = Mailer(os.environ.get("RESEND_API_KEY", ""), os.environ.get("QS_MAIL_FROM", ""), os.environ.get("QS_REPLY_TO", ""))
    to = os.environ.get("QS_OWNER_EMAIL", "")
    if not mailer.enabled or not to:
        print("Missing RESEND_API_KEY, QS_MAIL_FROM or QS_OWNER_EMAIL")
        return 1
    ok = mailer.send(to, "Quantum Aether: test email",
                     "Resend is configured. Welcome emails, alerts and subscription notifications will now be delivered.")
    print("sent" if ok else "FAILED (see log above)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
