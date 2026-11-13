# mailer.py
# إرسال البريد عبر Resend (https://resend.com). المنفذ 25 مغلق على الخادم، فنستخدم واجهة HTTPS.
# يحتاج RESEND_API_KEY وQS_MAIL_FROM (عنوان من نطاق موثّق في Resend). بدونهما يُعطَّل الإرسال بهدوء.
import html as htmlmod
import logging
import re

import requests

log = logging.getLogger("quantum_saas.mail")


class Mailer:
    def __init__(self, api_key, sender, reply_to="", timeout=15, session=None, fallback_sender="", site_url=""):
        self.api_key = api_key
        self.site_url = (site_url or "").rstrip("/")  # إن وُجد: تُرسل نسخة HTML بشعار الموقع مع كل رسالة نصية
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
        if html is None and self.site_url:
            html = render_html(subject, text, self.site_url)
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


_ARABIC = re.compile(r"[\u0600-\u06FF]")
_URL = re.compile(r"https?://[^\s<>\"']+")


def _linkify(escaped):
    def repl(m):
        url = m.group(0).rstrip(".,;:)")
        tail = m.group(0)[len(url):]
        return f'<a href="{url}" style="color:#6d3fc0;word-break:break-all">{url}</a>{tail}'
    return _URL.sub(repl, escaped)


def render_html(subject, text, site_url):
    """نسخة HTML بسيطة بشعار الموقع للنص نفسه. لا صور خارجية غير الشعار، ولا CSS خارجي (عملاء البريد يحذفونه)."""
    rtl = bool(_ARABIC.search(text))
    direction, align = ("rtl", "right") if rtl else ("ltr", "left")
    paragraphs = "".join(
        f'<p style="margin:0 0 16px;line-height:1.6">{_linkify(htmlmod.escape(block)).replace(chr(10), "<br>")}</p>'
        for block in text.strip().split("\n\n") if block.strip())
    host = site_url.split("://", 1)[-1]
    logo = f"{site_url}/static/brand/logo-email.png"
    return f"""<!doctype html><html lang="{'ar' if rtl else 'en'}" dir="{direction}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{htmlmod.escape(subject)}</title></head>
<body style="margin:0;padding:0;background:#f3f1f8">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f1f8"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #e4e0ee">
<tr><td style="background:#191426;padding:18px 24px" dir="ltr">
<a href="{site_url}" style="text-decoration:none;color:#ffffff;font:600 17px Arial,Helvetica,sans-serif">
<img src="{logo}" width="40" height="40" alt="Quantum Aether" style="vertical-align:middle;border:0;border-radius:9px;margin-right:10px">
<span style="vertical-align:middle">Quantum Aether</span></a></td></tr>
<tr><td dir="{direction}" style="padding:28px 24px 12px;text-align:{align};color:#1c1830;font:15px Tahoma,Arial,Helvetica,sans-serif">{paragraphs}</td></tr>
<tr><td style="padding:14px 24px 22px;border-top:1px solid #eeeaf5;text-align:center;color:#7a7390;font:12px Arial,Helvetica,sans-serif">
<a href="{site_url}" style="color:#7a7390;text-decoration:none">{htmlmod.escape(host)}</a></td></tr>
</table></td></tr></table></body></html>"""
