import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import i18n
import mailer as mailer_mod
import quantum_saas_app

try:
    from tests.test_monitor import FakeMailer, FakePayPal, FakeScanner
except ImportError:
    from test_monitor import FakeMailer, FakePayPal, FakeScanner


class MailerEuroTrialFixes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mailer = FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "CURRENCY": "EUR"},
            scanner=FakeScanner(), paypal=FakePayPal(), mailer=self.mailer)
        self.client = self.app.test_client()

    def test_empty_email_is_rejected_with_visible_required_message(self):
        for lang, needle in (("en", "Email required"), ("ar", "البريد مطلوب"), ("de", "E-Mail-Adresse fehlt")):
            r = self.client.post(f"/monitoring/trial?lang={lang}",
                                 data={"email": "", "domain": "acme.org", "consent": "1"})
            self.assertEqual(r.status_code, 400)
            body = r.get_data(as_text=True)
            self.assertIn(needle, body)
            self.assertIn("data-trial-email-error", body)
            self.assertIn('name="email"', body)
            self.assertIn("required", body)

    def test_data_license_and_home_use_euro_plan_copy_not_dollars(self):
        for path in ("/data-license?lang=en", "/data-license?lang=ar", "/data-license?lang=de"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertNotIn("$29", body)
            self.assertNotIn("$99", body)
            self.assertNotIn("29–99$", body)
            self.assertNotIn("29–99 $", body)
            self.assertIn("29 €", body)
            self.assertIn("99 €", body)
        # MCP / discovery copy is not on this page; checked in test_mcp and below.

    def test_pricing_monitoring_and_home_forms_require_visible_email(self):
        for path in ("/pricing?lang=en", "/monitoring?lang=en", "/?lang=en", "/?lang=ar"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertIn('name="email"', body)
            self.assertIn('type="email"', body)
            self.assertIn("required", body)
            self.assertIn("trial-required", body)
            self.assertIn("data-trial-email-error", body)
            self.assertIn("aria-required", body)

    def test_trial_states_include_empty_email(self):
        for lang in ("en", "ar", "de"):
            self.assertEqual(i18n.TEXTS[lang]["trial_states"]["empty_email"],
                             i18n.TEXTS[lang]["trial_email_required"])

    def test_mailer_normalizes_from_display_name(self):
        self.assertEqual(mailer_mod.with_team_from("Quantum Aether <ops@mail.example>"),
                         "Quantum Aether Team <ops@mail.example>")


if __name__ == "__main__":
    unittest.main()
