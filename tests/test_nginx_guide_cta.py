"""Nginx guide (2026-11-14): after the steps, offer the GitHub Action and a 14-day trial (source=nginx_guide)."""
import shutil
import tempfile
import unittest

import quantum_saas_app
from tests.test_monitor import PLAN_IDS, FakeMailer, FakePayPal


class NginxGuideCtaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mailer = FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PAYPAL_CLIENT_ID": "cid",
             "OWNER_EMAIL": "owner@example.com", "PUBLIC_URL": "https://ather-quantum.com",
             "HASH_SALT": "s", **PLAN_IDS},
            scanner=lambda raw: None, paypal=FakePayPal(), mailer=self.mailer)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_cta_and_action_link_present_in_en_de_ar(self):
        cases = {
            "en": ("After you confirm the fix", "Add the Post-Quantum TLS Check GitHub Action",
                   "Start 14-day free monitoring, no card"),
            "de": ("Wenn die Prüfung erfolgreich ist", "Post-Quantum TLS Check",
                   "14 Tage kostenlos überwachen, ohne Karte"),
            "ar": ("بعد أن تتأكد أن الإصلاح نجح", "إجراء GitHub",
                   "ابدأ مراقبة 14 يوماً مجاناً، بلا بطاقة"),
        }
        for lang, needles in cases.items():
            html = self.client.get(f"/guides/enable-x25519mlkem768-nginx?lang={lang}").get_data(as_text=True)
            self.assertIn('id="guide-next"', html, lang)
            self.assertIn('data-trial-source="nginx_guide"', html, lang)
            self.assertIn('name="src" value="nginx_guide"', html, lang)
            self.assertIn("github.com/marketplace/actions/post-quantum-tls-check-quantum-aether", html, lang)
            for n in needles:
                self.assertIn(n, html, f"{lang}: {n}")
            self.assertIn('lang="%s"' % lang, html)
            # CTA sits after the article body
            self.assertLess(html.index("</article>"), html.index('id="guide-next"'), lang)

    def test_other_guides_do_not_get_this_cta(self):
        html = self.client.get("/guides/harvest-now-decrypt-later?lang=en").get_data(as_text=True)
        self.assertNotIn('id="guide-next"', html)
        self.assertNotIn("nginx_guide", html)


class TrialTestNotifySkip(unittest.TestCase):
    """Live/owner test requests must not send a 'New free trial' owner alert."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mailer = FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PAYPAL_CLIENT_ID": "cid",
             "OWNER_EMAIL": "owner@example.com", "PUBLIC_URL": "https://ather-quantum.com",
             "HASH_SALT": "s", **PLAN_IDS},
            scanner=lambda raw: None, paypal=FakePayPal(), mailer=self.mailer)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_is_test_request_skips_owner_notification_but_still_emails_the_trial(self):
        from unittest.mock import patch
        with patch("quantum_saas_app.is_test_request", return_value=True):
            r = self.client.post("/monitoring/trial?lang=en",
                                 data={"email": "it@acme.org", "domain": "acme.org", "consent": "1",
                                       "src": "nginx_guide"},
                                 headers={"User-Agent": "Mozilla/5.0 (X11)"})
        self.assertEqual(r.status_code, 200)
        recipients = [m[0] for m in self.mailer.sent]
        self.assertIn("it@acme.org", recipients)
        self.assertNotIn("owner@example.com", recipients)


if __name__ == "__main__":
    unittest.main()
