"""Billing, subscription and access hardening restored on 2026-11-14 (approved by Omar): behaviour around the
fixes that test_security does not reach directly."""
import datetime as dt
import os
import re
import tempfile
import unittest
from unittest import mock

import monitor_db
import packs
import quantum_saas_app
import sales_db
import scorecard
from tests.test_app import RESULT, fake_scanner
from tests.test_crypto import FakeChain, POLY_ADDR
from tests.test_monitor import FakeMailer


class HardeningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "quantum_saas.db")
        self.mailer = FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://example.test",
             "HASH_SALT": "stable-test-salt", "TRUSTED_PROXIES": 0, "USDT_POLYGON_ADDR": POLY_ADDR},
            scanner=fake_scanner, paypal=None, mailer=self.mailer, chain=FakeChain())
        self.client = self.app.test_client()

    def db(self):
        conn = sales_db.connect(self.path)
        self.addCleanup(conn.close)
        return conn

    def test_failed_dashboard_email_keeps_the_current_link(self):
        conn = self.db()
        account_id, old = monitor_db.create_account(conn, "ops@example.com", "starter", "en")
        monitor_db.set_status(conn, account_id, "ACTIVE", "I-1")
        with self.app.test_request_context(), mock.patch.object(self.mailer, "send", return_value=False):
            self.assertFalse(quantum_saas_app.send_dashboard_link(conn, monitor_db.get_account(conn, account_id)))
        self.assertEqual(self.client.get(f"/monitor/{old}").status_code, 200)
        with self.app.test_request_context():
            self.assertTrue(quantum_saas_app.send_dashboard_link(conn, monitor_db.get_account(conn, account_id)))
        new = re.search(r"/monitor/([A-Za-z0-9_-]+)", self.mailer.sent[-1][2]).group(1)
        self.assertEqual(self.client.get(f"/monitor/{new}").status_code, 200)
        self.assertEqual(self.client.get(f"/monitor/{old}").status_code, 404)

    def test_trial_form_with_an_existing_address_sends_recovery_and_keeps_access(self):
        conn = self.db()
        account_id, old = monitor_db.create_account(conn, "ops@example.com", "starter", "en")
        monitor_db.set_status(conn, account_id, "ACTIVE", "I-1")
        r = self.client.post("/monitoring/trial?lang=en", data={"email": "ops@example.com", "domain": "example.com",
                                                                "consent": "1"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("/access/", self.mailer.sent[-1][2])
        self.assertEqual(self.client.get(f"/monitor/{old}").status_code, 200)

    def test_trial_account_can_recover_access(self):
        conn = self.db()
        account_id, old = monitor_db.create_account(conn, "trial@example.com", "starter", "de")
        monitor_db.set_status(conn, account_id, "TRIAL")
        self.client.post("/monitoring/login", data={"email": "trial@example.com"})
        token = re.search(r"/access/([A-Za-z0-9_-]+)", self.mailer.sent[-1][2]).group(1)
        self.assertIn("Zugang", self.mailer.sent[-1][1])
        page = self.client.get(f"/access/{token}?lang=de")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers["Cache-Control"], "no-store")
        response = self.client.post(f"/access/{token}")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.client.get(response.location).status_code, 200)

    def test_agency_page_offers_pack_link_recovery(self):
        body = self.client.get("/agency?lang=en").get_data(as_text=True)
        self.assertIn('action="/agency/recover', body)
        r = self.client.post("/agency/recover?lang=en", data={"email": "nobody@example.com"})
        self.assertEqual(r.status_code, 303)
        self.assertEqual(self.mailer.sent, [])

    def test_failed_pack_status_never_downgrades_a_completed_pack(self):
        conn = self.db()
        packs.create(conn, "pack", "order", 10, "199", "USD", "en", "now", False)
        token = packs.mark(conn, "pack", "COMPLETED", "capture", "agency@example.com")
        self.assertIsNone(packs.mark(conn, "pack", "FAILED", "other"))
        self.assertEqual(packs.by_order(conn, "order")["capture_id"], "capture")
        self.assertIsNotNone(packs.by_token(conn, token))

    def test_scorecard_lists_other_currencies_beside_usd(self):
        conn = self.db()
        sales_db.create_scan(conn, "scan", "report", RESULT, "client")
        for index, (amount, currency) in enumerate((("10", "USD"), ("50", "USDT"), ("70", "EUR"), ("29", "EUR"))):
            sales_db.create_order(conn, str(index), "scan", amount, currency)
            sales_db.update_order(conn, str(index), "COMPLETED", "capture" + str(index))
        with conn:
            conn.execute("UPDATE orders SET created_at = '2026-11-04T00:00:00Z'")
        card = scorecard.build(conn, today=dt.date(2026, 11, 5))
        self.assertEqual(card["totals"]["revenue_by_currency"], {"USD": 10, "USDT": 50, "EUR": 99})
        self.assertIn("99.00 EUR", scorecard.as_text(card))
        self.assertIn("50.00 USDT", scorecard.as_text(card))

    def test_schema_version_changes_when_a_schema_module_changes(self):
        self.assertIsInstance(sales_db.SCHEMA_VERSION, int)
        self.assertTrue(0 < sales_db.SCHEMA_VERSION < 2 ** 31)
        conn = self.db()
        with conn:
            conn.execute("PRAGMA user_version = 1")
        with mock.patch("sales_db.initialize", wraps=sales_db.initialize) as init:
            sales_db.connect(self.path).close()
        init.assert_called_once()

    def test_paypal_and_signup_reject_bad_json_even_when_disabled(self):
        for endpoint in ("/api/paypal/orders", "/api/monitor/signup"):
            self.assertEqual(self.client.post(endpoint, data="[1]", content_type="application/json").status_code, 400)
            self.assertEqual(self.client.post(endpoint, json={}).status_code, 503)
