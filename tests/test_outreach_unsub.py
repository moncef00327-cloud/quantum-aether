"""One-click unsubscribe for outreach (/u/<token>, RFC 8058) and the shared suppression list (2026-11-23)."""
import json
import os
import sqlite3
import tempfile
import time
import unittest

from flask import Blueprint, Flask

import inbound_mail
import outreach_suppress as osup

SECRET = "test-salt-not-a-real-secret"
WEBHOOK = "whsec_" + "c2VjcmV0c2VjcmV0c2VjcmV0c2VjcmV0"


class TokenTests(unittest.TestCase):
    def test_roundtrip_and_normalisation(self):
        tok = osup.make_token("  Security@Example.COM ", SECRET)
        self.assertEqual(osup.read_token(tok, SECRET), "security@example.com")

    def test_tampered_or_foreign_tokens_fail(self):
        tok = osup.make_token("a@example.com", SECRET)
        payload, sig = tok.split(".")
        other = osup.make_token("b@example.com", SECRET).split(".")[0]
        for bad in (f"{other}.{sig}", tok[:-1] + ("A" if tok[-1] != "A" else "B"), "x", "", "a.b", tok + "x",
                    "../../etc/passwd", "%2e%2e.aaaaaaaaaaaaaaaaaaaaaa"):
            self.assertIsNone(osup.read_token(bad, SECRET), bad)
        self.assertIsNone(osup.read_token(tok, "another-secret"))
        self.assertIsNone(osup.read_token(tok, ""))

    def test_no_secret_refuses_to_mint(self):
        with self.assertRaises(ValueError):
            osup.make_token("a@example.com", "")
        with self.assertRaises(ValueError):
            osup.make_token("not-an-address", SECRET)

    def test_headers(self):
        h = osup.list_unsubscribe_headers("https://ather-quantum.com/", "a@example.com", SECRET)
        self.assertEqual(h["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")
        url = "https://ather-quantum.com/u/" + osup.make_token("a@example.com", SECRET)
        self.assertEqual(h["List-Unsubscribe"], f"<{url}>, <mailto:reply@mail.ather-quantum.com?subject=unsubscribe>")


class SuppressTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)

    def test_idempotent_and_mirrored(self):
        self.assertTrue(osup.suppress(self.conn, "Sec <Sec@Example.org>", "one-click"))
        self.assertFalse(osup.suppress(self.conn, "sec@example.org", "one-click"))
        self.assertEqual(self.conn.execute("SELECT email, domain, reason FROM outreach_suppress").fetchall(),
                         [("sec@example.org", "example.org", "one-click")])
        self.assertEqual(self.conn.execute("SELECT domain FROM growth_suppress").fetchall(), [("example.org",)])
        self.assertTrue(osup.is_suppressed(self.conn, "sec@example.org"))
        self.assertTrue(osup.is_suppressed(self.conn, "other@example.org"))  # organisation-level
        self.assertTrue(osup.is_suppressed(self.conn, domain="example.org"))
        self.assertFalse(osup.is_suppressed(self.conn, "sec@example.net"))

    def test_www_host_maps_to_org_domain(self):
        osup.suppress(self.conn, "sec@www.example.io", "one-click")
        self.assertTrue(osup.is_suppressed(self.conn, domain="example.io"))

    def test_growth_suppress_counts(self):
        osup.init(self.conn)
        self.conn.execute("INSERT INTO growth_suppress VALUES ('bounced.example', 'x', 'bounced')")
        self.assertTrue(osup.is_suppressed(self.conn, "a@bounced.example"))


class RouteTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.remove, self.path)
        bp = Blueprint("site", __name__)
        osup.register(bp, {"db": lambda: sqlite3.connect(self.path), "secret": lambda: SECRET})
        app = Flask(__name__)
        app.register_blueprint(bp)
        self.client = app.test_client()
        self.tok = osup.make_token("security@example.com", SECRET)

    def rows(self):
        with sqlite3.connect(self.path) as c:
            osup.init(c)
            return c.execute("SELECT email, reason FROM outreach_suppress").fetchall()

    def test_get_renders_confirmation_without_writing(self):
        r = self.client.get(f"/u/{self.tok}")
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        self.assertIn("<form method=\"post\"", body)
        self.assertIn("إلغاء الاشتراك", body)
        self.assertIn("Abmelden", body)
        self.assertIn("s***@example.com", body)
        self.assertNotIn("security@example.com", body)
        self.assertIn("noindex", r.headers["X-Robots-Tag"])
        self.assertIn('name="robots" content="noindex', body)
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        self.assertEqual(self.rows(), [])

    def test_one_click_post_and_repeat(self):
        for _ in range(2):
            r = self.client.post(f"/u/{self.tok}", data="List-Unsubscribe=One-Click",
                                 content_type="application/x-www-form-urlencoded")
            self.assertEqual(r.status_code, 200)
            self.assertIn("noindex", r.headers["X-Robots-Tag"])
        self.assertEqual(self.rows(), [("security@example.com", "one-click")])

    def test_button_post(self):
        self.assertEqual(self.client.post(f"/u/{self.tok}").status_code, 200)
        self.assertEqual(self.rows(), [("security@example.com", "unsubscribe-page")])

    def test_bad_token_is_400_and_leaks_nothing(self):
        for bad in ("nope", self.tok[:-2] + "zz", "Zm9vQGV4YW1wbGUuY29t.aaaaaaaaaaaaaaaaaaaaaa"):
            for method in (self.client.get, self.client.post):
                r = method(f"/u/{bad}")
                self.assertEqual(r.status_code, 400)
                body = r.get_data(as_text=True)
                self.assertNotIn("foo@example.com", body)
                self.assertNotIn("Traceback", body)
                self.assertIn("noindex", r.headers["X-Robots-Tag"])
        self.assertEqual(self.rows(), [])


class InboundStopTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.addCleanup(self.conn.close)

        class Mailer:
            def send(self, *args):
                return True

        bp = Blueprint("inbound", __name__)
        inbound_mail.register(bp, {"db": lambda: self.conn, "mailer": Mailer, "owner": lambda: "owner@example.net",
                                   "secret": lambda: WEBHOOK})
        app = Flask(__name__)
        app.register_blueprint(bp)
        self.client = app.test_client()

    def receive(self, sender, subject, msg_id, extra=None):
        data = {"from": sender, "to": ["reply@mail.ather-quantum.com"], "subject": subject}
        if extra:
            data.update(extra)
        body = json.dumps({"type": "email.received", "data": data})
        stamp = str(int(time.time()))
        headers = {"svix-id": msg_id, "svix-timestamp": stamp, "svix-signature": inbound_mail.sign(WEBHOOK, msg_id, stamp, body)}
        self.assertEqual(self.client.post("/hooks/resend/inbound", data=body, headers=headers).status_code, 200)

    def test_reply_stop_suppresses_sender(self):
        self.receive("Sec Team <security@target.example>", "Re: target.example: TLS key exchange - STOP", "m1")
        self.receive("Ops <ops@other.example>", "Re: thanks, interesting", "m2")
        self.receive("Bot <alerts@ather-quantum.com>", "stop", "m3")
        self.receive("فريق <sec@arab.example>", "إيقاف", "m4")
        # Body-only "stop" (with neutral subject) MUST suppress
        self.receive("CSIRT <csirt@bank.example>", "Re: bank.example: TLS key exchange observed", "m5",
                     extra={"text": "stop"})
        # Body-only German "abmelden" MUST suppress
        self.receive("IT <it@firma.de>", "AW: TLS Check", "m6",
                     extra={"text": "Bitte abmelden."})
        # Warm reply quoting our own footer ("reply \"stop\"") MUST NOT suppress!
        self.receive("Lead <cto@lead.example>", "Re: lead.example: TLS key exchange observed", "m7",
                     extra={"text": "Looks useful, can we talk Tuesday?\n\nOn Thu, Nov 26 Quantum Aether wrote:\n> Unsubscribe in one click (or reply \"stop\")."})
        rows = self.conn.execute("SELECT email, reason FROM outreach_suppress ORDER BY email").fetchall()
        self.assertEqual(rows, [
            ("csirt@bank.example", "reply-stop"),
            ("it@firma.de", "reply-stop"),
            ("sec@arab.example", "reply-stop"),
            ("security@target.example", "reply-stop"),
        ])



class SendScriptRenderTests(unittest.TestCase):
    """tools/outreach_send.py fills the approved template; no network, no sending."""

    def setUp(self):
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "outreach_send.py")
        spec = importlib.util.spec_from_file_location("outreach_send", path)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.target = {"region": "Americas", "domain": "example.com", "handshake_host": "www.example.com",
                       "contact_email": "security@example.com"}

    def test_en_classical(self):
        m = self.mod.render(self.target, {"tls_version": "TLSv1.3", "group": "X25519", "kex_class": "classical"},
                            SECRET, date="2026-11-23")
        self.assertEqual(m["lang"], "en")
        self.assertEqual(m["subject"], "example.com: TLS key exchange observed on 2026-11-23")
        self.assertIn("www.example.com:443 negotiated TLSv1.3 with X25519 key exchange.", m["text"])
        self.assertIn("That is classical key exchange.", m["text"])
        self.assertNotIn("already covered", m["text"])
        url = "https://ather-quantum.com/u/" + osup.make_token("security@example.com", SECRET)
        self.assertIn(f"Unsubscribe in one click: {url}", m["text"])
        self.assertEqual(m["headers"]["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")
        self.assertIn("https://ather-quantum.com/monitoring?domain=example.com&lang=en#trial-form", m["text"])
        self.assertNotIn("{", m["text"])
        self.assertTrue(m["text"].rstrip().endswith("https://ather-quantum.com/impressum"))

    def test_ar_for_arab_world(self):
        t = dict(self.target, region="Arab world")
        m = self.mod.render(t, {"tls_version": "TLSv1.3", "group": "X25519MLKEM768", "kex_class": "hybrid-pq"},
                            SECRET, date="2026-11-23")
        self.assertEqual(m["lang"], "ar")
        self.assertIn("هذه هي المجموعة الهجينة", m["text"])
        self.assertIn("lang=ar", m["text"])
        self.assertIn("https://ather-quantum.com/monitoring?domain=example.com&lang=ar#trial-form", m["text"])
        self.assertNotIn("{", m["text"])

    def test_requires_explicit_mode(self):
        with self.assertRaises(SystemExit):
            self.mod.main([])


if __name__ == "__main__":
    unittest.main()
