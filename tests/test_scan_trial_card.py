"""An unprotected result offers the free monitoring trial first, with an inline form (no extra page)."""
import shutil
import tempfile
import unittest

import quantum_saas_app
from tests.test_app import RESULT
from tests.test_monitor import PLAN_IDS, FakeMailer, FakePayPal


def result(grade, pq, group):
    r = dict(RESULT, grade=grade)
    r["key_exchange"] = dict(RESULT["key_exchange"], pq=pq, group=group)
    return r


class ScanTrialCardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.outcome = result("B", False, "x25519")
        self.mailer = FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PAYPAL_CLIENT_ID": "cid", "OWNER_EMAIL": "owner@example.com", **PLAN_IDS},
            scanner=lambda raw: dict(self.outcome, domain=raw), paypal=FakePayPal(), mailer=self.mailer)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def page(self, domain="www.acme.org", lang="en"):
        sid = self.client.post("/api/scan", json={"domain": domain}).get_json()["scan_id"]
        return self.client.get(f"/scan/{sid}?lang={lang}").get_data(as_text=True)

    def test_classical_result_shows_trial_form_before_everything_else(self):
        html = self.page()
        self.assertIn('id="scan-trial"', html)
        self.assertIn('action="/monitoring/trial', html)
        self.assertIn('name="domain" value="acme.org"', html)  # base domain, without www
        self.assertIn('data-ev="trial_start"', html)
        self.assertLess(html.index('id="scan-trial"'), html.index('id="discovery"'))
        self.assertLess(html.index('id="scan-trial"'), html.index('id="buy"'))
        self.assertNotIn('id="consent" name="consent"', html)  # does not clash with the checkout's #consent
        # result pages exist in en/ar (German visitors get English)
        self.assertIn("مجاناً", self.page(lang="ar").split('id="scan-trial"')[1][:600])

    def test_grade_a_has_no_trial_card(self):
        self.outcome = result("A", True, "X25519MLKEM768")
        self.assertNotIn('id="scan-trial"', self.page())

    def test_inline_form_starts_a_trial(self):
        r = self.client.post("/monitoring/trial?lang=en", data={"email": "it@acme.org", "domain": "acme.org", "consent": "1"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("it@acme.org", [m[0] for m in self.mailer.sent])


if __name__ == "__main__":
    unittest.main()
