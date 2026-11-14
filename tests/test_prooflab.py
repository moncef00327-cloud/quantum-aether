"""ProofLab waitlist page (2026-11-14): en/de/ar, sitemap, footer, form validation, honeypot, rate limit, test rows."""
import os
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import quantum_saas_app
from tests.test_monitor import PLAN_IDS, FakeMailer, FakePayPal

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}


class ProofLabTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mailer = FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PAYPAL_CLIENT_ID": "cid",
             "OWNER_EMAIL": "owner@example.com", "PUBLIC_URL": "https://ather-quantum.com",
             "HASH_SALT": "s", **PLAN_IDS},
            scanner=lambda raw: None, paypal=FakePayPal(), mailer=self.mailer)
        self.client = self.app.test_client()
        self.client.get("/prooflab?lang=en", headers=UA)  # opens the DB once so every table exists

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def rows(self, sql):
        conn = sqlite3.connect(os.path.join(self.tmp, "quantum_saas.db"))
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def join(self, **over):
        data = {"email": "sec@acme.org", "company": "acme.org", "stack": "nginx", "consent": "1"}
        data.update(over)
        return self.client.post("/prooflab?lang=en", data={k: v for k, v in data.items() if v is not None}, headers=UA)

    def test_page_in_three_languages(self):
        needles = {"en": ("prove a post-quantum TLS change works", "Free pilot on one repository", "isolated container"),
                   "de": ("Kostenloser Pilot für ein Repository", "isolierten Container"),
                   "ar": ("تجربة مجانية على مستودع واحد", "حاوية معزولة")}
        for lang, ns in needles.items():
            r = self.client.get(f"/prooflab?lang={lang}", headers=UA)
            self.assertEqual(r.status_code, 200, lang)
            html = r.get_data(as_text=True)
            self.assertIn(f'lang="{lang}"', html)
            for n in ns:
                self.assertIn(n, html, f"{lang}: {n}")
            self.assertIn('name="consent"', html)
            self.assertIn('name="website"', html)
            # consent box sits above the button
            self.assertLess(html.index('name="consent"'), html.index('type="submit"', html.index('prooflab-form')))
            self.assertIn("github.com/moncef00327-cloud/prooflab-action", html)
        self.assertIn('dir="rtl"', self.client.get("/prooflab?lang=ar").get_data(as_text=True))

    def test_no_quantum_overclaim_and_no_prices(self):
        for lang in ("en", "de", "ar"):
            html = self.client.get(f"/prooflab?lang={lang}").get_data(as_text=True)
            body = html[html.index("prooflab-hero"):html.index("</main>") if "</main>" in html else len(html)]
            for bad in ("quantum advantage", "Quantenvorteil", "€", "$"):
                self.assertNotIn(bad, body, f"{lang}: {bad}")

    def test_footer_link_and_sitemap(self):
        html = self.client.get("/agency?lang=en").get_data(as_text=True)
        self.assertIn('/prooflab?lang=en">ProofLab</a>', html)  # footer
        self.assertIn("ProofLab · early access", html)  # sidebar
        self.assertIn("ProofLab · وصول مبكر", self.client.get("/agency?lang=ar").get_data(as_text=True))
        self.assertIn('/prooflab?lang=en">ProofLab</a>', self.client.get("/?lang=en").get_data(as_text=True))  # noscript nav
        sm = self.client.get("/sitemap-pages.xml").get_data(as_text=True)
        self.assertIn("https://ather-quantum.com/prooflab?lang=en", sm)
        self.assertIn("/prooflab?lang=de", sm)

    def test_real_signup_stored_tracked_and_owner_alerted_only(self):
        r = self.join()
        self.assertEqual(r.status_code, 200)
        self.assertIn("you are on the ProofLab waitlist", r.get_data(as_text=True))
        rows = self.rows("SELECT email, company, stack, is_test FROM prooflab_waitlist")
        self.assertEqual(rows, [("sec@acme.org", "acme.org", "nginx", 0)])
        self.assertEqual([m[0] for m in self.mailer.sent], ["owner@example.com"])  # nothing to the visitor
        self.assertIn("Quantum Aether Team", self.mailer.sent[0][2])
        names = {n for (n,) in self.rows("SELECT name FROM events")}
        self.assertIn("prooflab_submit", names)

    def test_view_event_recorded(self):
        self.client.get("/prooflab?lang=en", headers=UA)
        self.assertIn(("prooflab_view",), self.rows("SELECT name FROM events"))

    def test_test_request_marked_and_no_owner_alert(self):
        with patch("quantum_saas_app.is_test_request", return_value=True):
            r = self.join(email="t@acme.org")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.rows("SELECT is_test FROM prooflab_waitlist"), [(1,)])
        self.assertEqual(self.mailer.sent, [])

    def test_validation(self):
        self.assertEqual(self.join(consent=None).status_code, 400)
        self.assertEqual(self.join(email="nope").status_code, 400)
        self.assertEqual(self.join(company="").status_code, 400)
        self.assertEqual(self.join(stack="iis").status_code, 400)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM prooflab_waitlist"), [(0,)])

    def test_honeypot_stores_nothing(self):
        r = self.join(website="http://spam.example")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM prooflab_waitlist"), [(0,)])
        self.assertEqual(self.mailer.sent, [])

    def test_duplicate_and_rate_limit(self):
        self.join()
        self.join()  # duplicate: same answer, no second row
        self.assertEqual(self.rows("SELECT COUNT(*) FROM prooflab_waitlist"), [(1,)])
        self.join(email="b@acme.org")
        self.join(email="c@acme.org")
        r = self.join(email="d@acme.org")
        self.assertEqual(r.status_code, 429)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM prooflab_waitlist"), [(3,)])

    def test_admin_shows_count(self):
        from werkzeug.security import generate_password_hash
        self.app.config["ADMIN_PASSWORD_HASH"] = generate_password_hash("pw")
        self.join()
        import base64
        auth = {"Authorization": "Basic " + base64.b64encode(b"admin:pw").decode()}
        html = self.client.get("/admin", headers=auth).get_data(as_text=True)
        self.assertIn("ProofLab waitlist", html)
        self.assertIn("Real signups: <strong>1</strong>", html)


if __name__ == "__main__":
    unittest.main()
