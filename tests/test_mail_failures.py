import re
import shutil
import tempfile
import unittest

import discovery
import mailer as mailer_mod
import quantum_saas_app
import sales_db
import uptime_check
from test_discovery import FakeHTTP, fake_probe, _result


class _Resp:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text


class _Session:
    def __init__(self, statuses):
        self.statuses, self.calls = list(statuses), []

    def post(self, url, json=None, timeout=None, headers=None):
        self.calls.append(json["from"])
        return _Resp(self.statuses.pop(0), "domain is not verified")


class MailerFallbackTests(unittest.TestCase):
    def test_rejected_primary_retries_with_fallback(self):
        s = _Session([403, 200])
        m = mailer_mod.Mailer("k", "a@new.example", session=s, fallback_sender="a@old.example")
        self.assertTrue(m.send("x@y.z", "s", "t"))
        self.assertEqual(s.calls, ["a@new.example", "a@old.example"])

    def test_server_error_does_not_switch_sender(self):
        s = _Session([500])
        m = mailer_mod.Mailer("k", "a@new.example", session=s, fallback_sender="a@old.example")
        self.assertFalse(m.send("x@y.z", "s", "t"))
        self.assertEqual(s.calls, ["a@new.example"])
        self.assertIn("500", m.last_error)

    def test_no_fallback_reports_error(self):
        m = mailer_mod.Mailer("k", "a@new.example", session=_Session([403]))
        self.assertFalse(m.send("x@y.z", "s", "t"))
        self.assertIn("not verified", m.last_error)


class MailHealthTests(unittest.TestCase):
    def test_alerts_once_down_and_once_up(self):
        st, a = uptime_check.mail_decide({}, False)
        self.assertEqual(a, "mail_down")
        st, a = uptime_check.mail_decide(st, False)
        self.assertIsNone(a)
        st, a = uptime_check.mail_decide(st, True)
        self.assertEqual(a, "mail_up")
        self.assertFalse(uptime_check.mail_due({"mail_checked": 1000}, 1000 + 60))
        self.assertTrue(uptime_check.mail_due({"mail_checked": 1000}, 1000 + 3600))


class BrokenToVisitorMailer:
    """يرفض البريد للزائر ويقبل بريد المالك (كما يحدث مع مرسل احتياطي)."""
    enabled = True
    last_error = "403: domain is not verified"

    def __init__(self):
        self.sent = []

    def send(self, to, subject, text, html=None):
        if to == "owner@example.org":
            self.sent.append((to, subject, text))
            return True
        return False


class DiscoveryMailFailureTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.mailer = BrokenToVisitorMailer()
        self.app = quantum_saas_app.create_app(
            {"DATA_DIR": self.dir, "TESTING": True, "TRUSTED_PROXIES": 0, "OWNER_EMAIL": "owner@example.org"},
            scanner=lambda raw: dict(_result(), domain=raw), mailer=self.mailer,
            discovery_http=FakeHTTP(), discovery_probe=fake_probe)
        self.client = self.app.test_client()
        self.scan_id = self.client.post("/api/scan", json={"domain": "www.example.com"}).get_json()["scan_id"]
        self.client.post(f"/api/discovery/{self.scan_id}")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_failed_confirmation_notifies_owner_and_frees_the_request(self):
        r = self.client.post("/discovery/request?lang=en",
                             data={"scan_id": self.scan_id, "email": "it@example.com", "consent": "1"})
        self.assertEqual(r.status_code, 503)
        to, subject, text = self.mailer.sent[-1]
        self.assertEqual(to, "owner@example.org")
        self.assertIn("it@example.com", text)
        self.assertIn("not verified", text)
        conn = sales_db.connect(self.dir + "/quantum_saas.db")
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM discovery_requests").fetchone()[0], 0)
        finally:
            conn.close()


class BrandedHtmlTests(unittest.TestCase):
    def test_text_mail_gets_logo_html(self):
        sent = {}

        class S:
            def post(self, url, json=None, timeout=None, headers=None):
                sent.update(json)
                return _Resp(200)
        m = mailer_mod.Mailer("k", "a@x.example", session=S(), site_url="https://ather-quantum.com/")
        self.assertTrue(m.send("u@y.z", "Hi <b>", "Hello\n\nOpen https://ather-quantum.com/x?a=1&b=2.\nBye"))
        h = sent["html"]
        self.assertIn('src="https://ather-quantum.com/static/brand/logo-email.png"', h)
        self.assertIn('href="https://ather-quantum.com/x?a=1&amp;b=2"', h)
        self.assertNotIn("<b>", h)
        self.assertIn('dir="ltr"', h)
        self.assertEqual(sent["text"].split("\n")[0], "Hello")

    def test_arabic_is_rtl_and_no_site_url_means_text_only(self):
        self.assertIn('dir="rtl"', mailer_mod.render_html("s", "مرحباً", "https://e.example"))
        sent = {}

        class S:
            def post(self, url, json=None, timeout=None, headers=None):
                sent.update(json)
                return _Resp(200)
        mailer_mod.Mailer("k", "a@x.example", session=S()).send("u@y.z", "s", "t")
        self.assertNotIn("html", sent)
