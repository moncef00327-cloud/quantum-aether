"""Trial signup forgives what RTL pages and phone keyboards add to an address (bidi marks, spaces, full-width @)."""
import unittest

import quantum_saas_app
from tests.test_trial import TrialTest


class CleanEmailTest(unittest.TestCase):
    def test_clean_email(self):
        c = quantum_saas_app.clean_email
        self.assertEqual(c("‏ security@Bank.com ‎"), "security@bank.com")
        self.assertEqual(c("ops＠acme.org"), "ops@acme.org")
        self.assertEqual(c("mailto:<a@b.co>."), "a@b.co")
        self.assertEqual(c(None), "")
        self.assertEqual(c("bank.com"), "bank.com")  # still rejected by EMAIL_RE, not guessed into an address


class TrialEmailSignupTest(TrialTest):
    def test_address_with_bidi_marks_starts_trial(self):
        r = self.start_trial(email="‏ops＠acme.org‎ ", domain="acme.org", lang="ar")
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(self.account("ops@acme.org"))

    def test_domain_typed_as_email_is_still_rejected(self):
        r = self.start_trial(email="acme.org", domain="")
        self.assertEqual(r.status_code, 400)

    def test_pages_load_the_new_form_script(self):
        body = self.client.get("/monitoring?lang=ar").get_data(as_text=True)
        self.assertIn("trial-form.js?v=20261123-email-required2", body)
        js = self.client.get("/static/trial-form.js").get_data(as_text=True)
        for text in ("هذا يبدو نطاقاً لا بريداً", "That looks like a domain", "Meinten Sie", "domain_only",
                     "qa_recent_scans", "qa-multi-scan-nudge", "extra_domains"):
            self.assertIn(text, js)

    def test_trial_accepts_extra_domains_up_to_limit(self):
        extras = ",".join([f"d{i}.example" for i in range(1, 15)] + ["acme.org", "not a domain!!!"])
        r = self.client.post("/monitoring/trial?lang=en", data={
            "email": "ops@acme.org", "domain": "acme.org", "extra_domains": extras, "consent": "1",
        })
        self.assertEqual(r.status_code, 200)
        acc = self.account("ops@acme.org")
        self.assertIsNotNone(acc)
        with self.conn() as c:
            doms = [row[0] for row in c.execute(
                "SELECT domain FROM monitor_domains WHERE account_id = ? ORDER BY domain", (acc["id"],)
            ).fetchall()]
        self.assertEqual(len(doms), 10)  # monitor.TRIAL_DOMAINS cap
        self.assertIn("acme.org", doms)
        self.assertIn("d1.example", doms)
        self.assertNotIn("d10.example", doms)


if __name__ == "__main__":
    unittest.main()
