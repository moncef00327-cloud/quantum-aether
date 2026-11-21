"""2026-11-21: trial rejection details are "source|reason" (old glued rows normalised), QA browser runs are tests,
the empty-email message sits under the field, the DACH correction table exists from startup, and replies arriving
through the Resend inbound webhook are verified, stored and announced to the owner (QA mails are not)."""
import base64
import json
import os
import shutil
import sqlite3
import tempfile
import time
import unittest

import analytics_db
import dach_hosting
import inbound_mail
import quantum_saas_app
import sales_db
from tests.test_crawlers import seed

SECRET = "whsec_" + base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeMailer:
    enabled = True

    def __init__(self):
        self.sent = []

    def send(self, to, subject, text, html=None, attachments=None):
        self.sent.append((to, subject, text))
        return True


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quantum.com", "HASH_SALT": "s",
             "OWNER_EMAIL": "owner@example.test", "RESEND_WEBHOOK_SECRET": SECRET},
            scanner=lambda raw: None, paypal=None)
        self.mailer = FakeMailer()
        self.app.extensions["mailer"] = self.mailer
        self.client = self.app.test_client()
        conn = sales_db.connect(f"{self.tmp}/quantum_saas.db")
        seed(conn)
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return sales_db.connect(f"{self.tmp}/quantum_saas.db")


class TrialDetailTests(Base):
    def test_pipe_survives_clean_detail(self):
        self.assertEqual(analytics_db.clean_detail("scan_result|bad_email:domain_only"), "scan_result|bad_email:domain_only")
        self.assertEqual(analytics_db.trial_detail("", "empty_email"), "none|empty_email")

    def test_browser_event_keeps_source_and_reason(self):
        self.client.post("/api/ev", data=json.dumps({"name": "trial_invalid", "page": "/pricing", "lang": "de",
                                                     "detail": "pricing|consent_missing"}),
                         headers={"User-Agent": "Mozilla/5.0 (X11)"})
        self.client.post("/api/ev", data=json.dumps({"name": "trial_invalid", "page": "/monitoring", "lang": "de",
                                                     "detail": "monitoring|need_domain"}),
                         headers={"User-Agent": "Mozilla/5.0 (X11)"})
        details = sorted(r[0] for r in self.conn().execute("SELECT detail FROM events WHERE name='trial_invalid'"))
        self.assertEqual(details, ["monitoring|need_domain", "pricing|consent_missing"])

    def test_server_rejection_records_source_and_state(self):
        for form in ({"email": "it@firma-test.example", "domain": "firma-test.example", "src": "pricing"},  # no consent
                     {"email": "nope", "consent": "1", "src": "business"},
                     {"email": "me@gmail.com", "consent": "1"}):
            self.client.post("/monitoring/trial?lang=en", data=form, headers={"User-Agent": "Mozilla/5.0 (X11)"})
        details = sorted(r[0] for r in self.conn().execute("SELECT detail FROM events WHERE name='trial_failed'"))
        self.assertEqual(details, ["business|bad_email", "none|need_domain", "pricing|consent_missing"])

    def test_old_glued_rows_are_normalised_once(self):
        conn = self.conn()
        rows = [("trial_invalid", "/scan/*", "scan_resultbad_email"), ("trial_invalid", "/monitoring", "monitoringbad_email"),
                ("trial_invalid", "/pricing", "empty_email"), ("trial_invalid", "/monitoring", "monitoring"),
                ("trial_failed", "/monitoring", "scan_result"), ("trial_invalid", "/", "home:bad_email:domain_only"),
                ("trial_created", "/monitoring", "scan_result")]
        with conn:
            for name, page, detail in rows:
                conn.execute("INSERT INTO events (day, name, page, lang, visitor, is_bot, is_test, detail) "
                             "VALUES ('2026-11-16', ?, ?, 'en', 'v', 0, 0, ?)", (name, page, detail))
        self.assertEqual(analytics_db.normalize_trial_details(conn), 6)
        got = [r[0] for r in conn.execute("SELECT detail FROM events WHERE day='2026-11-16' ORDER BY rowid")]
        self.assertEqual(got, ["scan_result|bad_email", "monitoring|bad_email", "pricing|empty_email", "monitoring|unknown",
                               "scan_result|unknown", "home|bad_email:domain_only", "scan_result"])
        self.assertEqual(analytics_db.normalize_trial_details(conn), 0)
        reasons = {(r["source"], r["reason"]) for r in analytics_db.trial_reasons(conn, "2026-11-01")}
        self.assertIn(("pricing", "empty_email"), reasons)

    def test_qa_browser_user_agent_is_a_test(self):
        ua = "Mozilla/5.0 (X11) QA-trial-test"
        self.client.post("/api/ev", data=json.dumps({"name": "trial_invalid", "page": "/pricing", "lang": "en",
                                                     "detail": "pricing|empty_email"}), headers={"User-Agent": ua})
        self.assertEqual(self.conn().execute("SELECT is_test FROM events WHERE name='trial_invalid'").fetchone()[0], 1)


class TrialFormMarkupTests(Base):
    def test_pricing_and_business_forms_carry_source_and_required_email(self):
        for path, src in (("/pricing", "pricing"), ("/business", "business")):
            body = self.client.get(f"{path}?lang=en").get_data(as_text=True)
            self.assertIn(f'data-trial-source="{src}"', body)
            self.assertIn(f'name="src" value="{src}"', body)
            self.assertIn('aria-required="true"', body)
            self.assertIn("trial-required", body)

    def test_script_sends_pipe_and_places_empty_message_under_email(self):
        with open(os.path.join(BASE, "static", "trial-form.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn('src + "|" + reason', js)
        self.assertIn("row.parentNode.insertBefore(el, row.nextSibling)", js)
        self.assertIn("focusTrialEmail", js)
        for lang in ("en:", "de:", "ar:"):
            self.assertIn(lang, js)


class DachCorrectionTests(Base):
    def test_table_exists_after_connect(self):
        names = {r[0] for r in self.conn().execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("dach_corrections", names)
        self.assertIn("inbound_mail", names)

    @unittest.skipUnless(dach_hosting.load(BASE), "no DACH study data in this checkout")
    def test_marked_submission_is_stored_without_error(self):
        provider = dach_hosting.load(BASE)["providers"][0]["provider"]
        r = self.client.post("/adoption/dach-hosting/correction",
                             data={"provider": provider, "name": "QA test", "email": "delivered@resend.dev",
                                   "message": "QA test correction, please ignore", "lang": "de"},
                             headers={"User-Agent": "QA-trial-test"})
        self.assertEqual(r.status_code, 303)
        self.assertIn("sent=1", r.headers["Location"])
        self.assertEqual(self.conn().execute("SELECT COUNT(*) FROM dach_corrections").fetchone()[0], 1)


class InboundMailTests(Base):
    def deliver(self, event, msg_id="msg_1", secret=SECRET, ts=None):
        body = json.dumps(event)
        ts = str(int(ts if ts is not None else time.time()))
        return self.client.post("/hooks/resend/inbound", data=body, content_type="application/json",
                                headers={"svix-id": msg_id, "svix-timestamp": ts,
                                         "svix-signature": inbound_mail.sign(secret, msg_id, ts, body)})

    def event(self, sender="Kunde <it@kunde.example>", subject="Re: your measurement"):
        return {"type": "email.received", "created_at": "2026-11-21T12:00:00Z",
                "data": {"email_id": "e-1", "created_at": "2026-11-21T12:00:00Z", "from": sender,
                         "to": ["reply@mail.ather-quantum.com"], "subject": subject}}

    def test_signed_reply_is_stored_and_owner_notified_once(self):
        self.assertEqual(self.deliver(self.event()).status_code, 200)
        self.assertEqual(self.deliver(self.event()).get_json().get("duplicate"), True)
        rows = self.conn().execute("SELECT from_addr, to_addr, subject, is_test, notified FROM inbound_mail").fetchall()
        self.assertEqual([tuple(r) for r in rows],
                         [("Kunde <it@kunde.example>", "reply@mail.ather-quantum.com", "Re: your measurement", 0, 1)])
        self.assertEqual(len(self.mailer.sent), 1)
        self.assertEqual(self.mailer.sent[0][0], "owner@example.test")
        self.assertIn("Quantum Aether Team", self.mailer.sent[0][2])

    def test_bad_or_stale_signature_rejected(self):
        other = "whsec_" + base64.b64encode(b"x" * 32).decode()
        self.assertEqual(self.deliver(self.event(), secret=other).status_code, 401)
        self.assertEqual(self.deliver(self.event(), ts=time.time() - 3600).status_code, 401)
        self.assertEqual(self.conn().execute("SELECT COUNT(*) FROM inbound_mail").fetchone()[0], 0)

    def test_qa_mail_is_stored_as_test_without_notice(self):
        self.deliver(self.event("Quantum Aether <alerts@ather-quantum.com>", "[QA-TEST] reply path"))
        self.assertEqual(self.conn().execute("SELECT is_test, notified FROM inbound_mail").fetchone()[:], (1, 0))
        self.assertEqual(self.mailer.sent, [])

    def test_other_events_ignored_and_unconfigured_is_503(self):
        self.assertTrue(self.deliver({"type": "email.delivered", "data": {}}).get_json()["ignored"])
        self.app.config["RESEND_WEBHOOK_SECRET"] = ""
        self.assertEqual(self.deliver(self.event()).status_code, 503)
