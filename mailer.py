# mailer.py
# إرسال البريد عبر Resend (https://resend.com). المنفذ 25 مغلق على الخادم، فنستخدم واجهة HTTPS.
# يحتاج RESEND_API_KEY وQS_MAIL_FROM (عنوان من نطاق موثّق في Resend). بدونهما يُعطَّل الإرسال بهدوء.
import logging

import requests

log = logging.getLogger("quantum_saas.mail")


class Mailer:
    def __init__(self, api_key, sender, reply_to="", timeout=15, session=None, fallback_sender=""):
        self.api_key = api_key
        self.sender = sender
        self.fallback_sender = fallback_sender  # نطاق موثّق ثانٍ: يُستخدم إن رفض Resend المرسل الأساسي (مثل نطاق غير موثّق)
        self.last_error = ""
        self.reply_to = reply_to
        self.timeout = timeout
        self.http = session or requests.Session()

    @property
    def enabled(self):
        return bool(self.api_key and self.sender)

    def send(self, to, subject, text, html=None):
        """يعيد True إن قبل Resend الرسالة. لا يرفع استثناءً: فشل البريد لا يوقف الخدمة."""
        if not self.enabled:
            log.info("mail disabled; not sending %r to %s", subject, to)
            return False
        senders = [self.sender] + ([self.fallback_sender] if self.fallback_sender and self.fallback_sender != self.sender else [])
        for i, sender in enumerate(senders):
            ok, status = self._post(sender, to, subject, text, html)
            if ok:
                if i:
                    log.warning("mail sent with FALLBACK sender after primary was rejected: %s", self.last_error)
                return True
            if status not in (403, 422):  # فقط رفض المرسل/النطاق يستحق تجربة المرسل الاحتياطي
                break
        return False

    def _post(self, sender, to, subject, text, html):
        body = {"from": sender, "to": [to], "subject": subject, "text": text}
        if html:
            body["html"] = html
        if self.reply_to:
            body["reply_to"] = self.reply_to  # ردود العملاء تصل إلى صاحب الموقع
        try:
            response = self.http.post("https://api.resend.com/emails", json=body, timeout=self.timeout,
                                      headers={"Authorization": f"Bearer {self.api_key}"})
        except requests.RequestException as exc:
            self.last_error = f"request failed: {exc}"[:300]
            log.warning("Resend request failed: %s", exc)
            return False, None
        if response.status_code >= 300:
            self.last_error = f"{response.status_code}: {response.text[:300]}"
            log.warning("Resend rejected mail (%s): %s", response.status_code, response.text[:300])
            return False, response.status_code
        return True, response.status_code
