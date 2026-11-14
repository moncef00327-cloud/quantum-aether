"""Regression tests for payment attribution, recovery, deadlines and scan uncertainty."""
import concurrent.futures as cf
import copy
import datetime as dt
import io
import os
import re
import tempfile
import threading
import unittest
import urllib.error
from contextlib import closing
from decimal import Decimal
from unittest import mock

import access_links
import bio_archive_report
import crypto_pay
import dna_encode
import monitor
import monitor_db
import monitor_job
import packs
import quantum_saas_app
import quantum_vuln_scanner as qs
import sales_db
import scorecard
from tools.backup_db import backup_database
from tests.test_app import RESULT, fake_scanner
from tests.test_crypto import FakeChain, POLY_ADDR, TX
from tests.test_monitor import FakeMailer, FakePayPal
from tests.test_scanner import FakeSocket, handshake, record, server_hello


class SecurityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "quantum_saas.db")
        self.mailer = FakeMailer()
        self.chain = FakeChain()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://example.test",
             "HASH_SALT": "stable-test-salt", "TRUSTED_PROXIES": 0,
             "USDT_POLYGON_ADDR": POLY_ADDR}, scanner=fake_scanner, paypal=None,
            mailer=self.mailer, chain=self.chain)
        self.client = self.app.test_client()

    def db(self):
        conn = sales_db.connect(self.path)
        self.addCleanup(conn.close)
        return conn

    def account(self):
        conn = self.db()
        account_id, token = monitor_db.create_account(conn, "ops@example.com", "starter", "en")
        monitor_db.set_status(conn, account_id, "ACTIVE", "I-TEST")
        return account_id, token

    def recovery_token(self):
        return re.search(r"/access/([A-Za-z0-9_-]+)", self.mailer.sent[-1][2]).group(1)

    def crypto_order(self):
        scan = self.client.post("/api/scan", json={"domain": "example.com"}).get_json()
        return self.client.post("/api/crypto/orders", json={"scan_id": scan["scan_id"],
            "network": "polygon-usdt", "consent": True}).get_json()

    def test_json_arrays_scalars_null_and_malformed_are_400(self):
        for endpoint in ("/api/scan", "/api/paypal/orders", "/api/monitor/signup", "/api/crypto/orders"):
            for body in ("[1]", "true", "123", '"text"', "null", "{"):
                with self.subTest(endpoint=endpoint, body=body):
                    response = self.client.post(endpoint, data=body, content_type="application/json")
                    self.assertEqual(response.status_code, 400)
                    # "invalid_request" is the API's published error code for a non-object body (test_platform2).
                    self.assertEqual(response.get_json()["error"], "invalid_request")

    def test_body_size_is_limited(self):
        # MAX_CONTENT_LENGTH is 128 KiB (create_app); anything larger is refused before parsing.
        response = self.client.post("/api/scan", data='{"domain":"' + 'x' * (128 * 1024) + '"}',
                                    content_type="application/json")
        self.assertEqual(response.status_code, 413)

    def test_overpayment_cannot_claim_another_order(self):
        order = self.crypto_order()
        self.chain.pay(TX, crypto_pay.to_units(Decimal(order["amount"]) + Decimal("0.01"), 6))
        response = self.client.post(f"/api/crypto/orders/{order['order_id']}/verify", json={"tx_hash": TX})
        self.assertEqual((response.status_code, response.get_json()["error"]), (402, "wrong_amount"))

    def test_crypto_amount_is_not_reused_after_completion(self):
        conn = self.db()
        sales_db.create_scan(conn, "scan", "report", RESULT, "client")
        with mock.patch("crypto_pay.secrets.randbelow", side_effect=[0, 0, 1]):
            first = sales_db.create_crypto_order(conn, "first", "scan", "49", "USDT")
            sales_db.update_order(conn, "first", "COMPLETED", TX)
            second = sales_db.create_crypto_order(conn, "second", "scan", "49", "USDT")
        self.assertNotEqual(Decimal(first), Decimal(second))

    def test_legacy_duplicate_amount_requires_manual_reconciliation(self):
        order = self.crypto_order()
        conn = self.db()
        scan_id = sales_db.get_order(conn, order["order_id"])["scan_id"]
        sales_db.create_order(conn, "duplicate", scan_id, order["amount"], "USDT")
        self.chain.pay(TX, crypto_pay.to_units(order["amount"], 6))
        response = self.client.post(f"/api/crypto/orders/{order['order_id']}/verify", json={"tx_hash": TX})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "ambiguous_payment_amount")

    def test_scan_quota_is_atomic_under_concurrency(self):
        self.db()
        barrier = threading.Barrier(4)
        def attempt(_):
            with closing(sales_db.connect(self.path)) as conn:
                barrier.wait(timeout=5)
                return sales_db.claim_scan_attempt(conn, "same-client", "2000-01-01", 1, 100)
        with cf.ThreadPoolExecutor(4) as pool:
            self.assertEqual(sum(pool.map(attempt, range(4))), 1)

    def test_login_request_does_not_revoke_existing_access(self):
        _, old = self.account()
        self.client.post("/monitoring/login", data={"email": "ops@example.com"})
        self.assertEqual(self.client.get(f"/monitor/{old}").status_code, 200)
        recovery = self.recovery_token()
        self.assertEqual(self.client.get(f"/access/{recovery}").status_code, 200)
        self.assertEqual(self.client.get(f"/monitor/{old}").status_code, 200)
        response = self.client.post(f"/access/{recovery}")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.client.get(response.location).status_code, 200)
        self.assertEqual(self.client.get(f"/monitor/{old}").status_code, 404)
        self.assertEqual(self.client.post(f"/access/{recovery}").status_code, 404)

    def test_failed_recovery_email_keeps_old_access(self):
        _, old = self.account()
        with mock.patch.object(self.mailer, "send", return_value=False):
            self.client.post("/monitoring/login", data={"email": "ops@example.com"})
        self.assertEqual(self.client.get(f"/monitor/{old}").status_code, 200)
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM access_links").fetchone()[0], 0)

    def test_recovery_is_rate_limited_without_disclosing_account(self):
        self.account()
        responses = [self.client.post("/monitoring/login", data={"email": "ops@example.com"}) for _ in range(6)]
        self.assertTrue(all(r.status_code == 303 for r in responses))
        self.assertEqual(len(self.mailer.sent), 3)

    def test_recovery_expires_and_cannot_reactivate_cancelled_account(self):
        account_id, old = self.account()
        conn = self.db()
        token = access_links.issue(conn, "monitor", account_id, now=1000)
        self.assertIsNone(access_links.consume(conn, token, now=1900))
        token = access_links.issue(conn, "monitor", account_id)
        monitor_db.set_status(conn, account_id, "CANCELLED")
        self.assertIsNone(access_links.consume(conn, token))
        self.assertIsNotNone(monitor_db.get_account_by_token(conn, old))

    def test_pack_can_be_recovered_by_verified_email(self):
        conn = self.db()
        packs.create(conn, "pack", "order", 10, "199", "USD", "en", "now", False)
        old = packs.mark(conn, "pack", "COMPLETED", "capture", "agency@example.com")
        response = self.client.post("/agency/recover", data={"email": "agency@example.com"})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.client.get(f"/pack/{old}").status_code, 200)
        response = self.client.post(f"/access/{self.recovery_token()}")
        self.assertEqual(self.client.get(response.location).status_code, 200)
        self.assertEqual(self.client.get(f"/pack/{old}").status_code, 404)

    def test_sensitive_api_and_recovery_are_not_cached(self):
        account_id, _ = self.account()
        token = access_links.issue(self.db(), "monitor", account_id)
        for url in (f"/access/{token}", "/api/v1/orders/missing"):
            response = self.client.get(url)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")

    def test_suspended_subscription_resumes_and_does_not_repeat_notifications(self):
        account_id, _ = self.account()
        conn = self.db()
        paypal = FakePayPal()
        paypal.subscriptions["I-TEST"] = {"status": "SUSPENDED"}
        monitor_job.sync_subscriptions(conn, paypal, self.mailer, "owner@example.com")
        count = len(self.mailer.sent)
        monitor_job.sync_subscriptions(conn, paypal, self.mailer, "owner@example.com")
        self.assertEqual(len(self.mailer.sent), count)
        paypal.subscriptions["I-TEST"]["status"] = "ACTIVE"
        monitor_job.sync_subscriptions(conn, paypal)
        self.assertEqual(monitor_db.get_account(conn, account_id)["status"], "ACTIVE")

    def test_unknown_probe_is_not_reported_as_classical(self):
        result = copy.deepcopy(RESULT)
        result["key_exchange"] = {"error": "blocked", "pq": None, "group": None}
        self.app.extensions["scanner"] = lambda _: result
        response = self.client.post("/api/scan", json={"domain": "example.com"})
        # Published contract (openapi.yaml, llms.txt): the flag is a boolean that is true only when PQ was observed;
        # "undetermined" is reported through observation_status, never as "classical".
        self.assertIs(response.get_json()["post_quantum_key_exchange"], False)
        self.assertEqual(response.get_json()["observation_status"], "undetermined")
        page = self.client.get(response.get_json()["scan_url"]).get_data(as_text=True)
        self.assertIn("Support undetermined", page)
        self.assertNotIn("Enable hybrid post-quantum key exchange on your server", page)
        with self.app.test_request_context():
            self.assertIn("undetermined", quantum_saas_app.terminal_report(result))
        self.assertNotIn("PQ_LOST", [kind for kind, _ in monitor.diff({"grade": "B", "pq": 1}, result)])

    def test_versioned_schema_skips_migrations_after_initialization(self):
        conn = self.db()
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], sales_db.SCHEMA_VERSION)
        with mock.patch("sales_db.initialize", side_effect=AssertionError("migration repeated")):
            sales_db.connect(self.path).close()

    def test_concurrent_first_connections_migrate_once(self):
        barrier = threading.Barrier(4)
        def connect(_):
            barrier.wait(timeout=5)
            with closing(sales_db.connect(self.path)) as conn:
                return conn.execute("PRAGMA user_version").fetchone()[0]
        with cf.ThreadPoolExecutor(4) as pool:
            self.assertEqual(list(pool.map(connect, range(4))), [sales_db.SCHEMA_VERSION] * 4)


    def test_completed_order_cannot_be_downgraded_or_notified_twice(self):
        conn = self.db()
        sales_db.create_scan(conn, "scan", "report", RESULT, "client")
        sales_db.create_order(conn, "order", "scan", "49", "USD")
        self.assertTrue(sales_db.update_order(conn, "order", "COMPLETED", "capture"))
        self.assertFalse(sales_db.update_order(conn, "order", "COMPLETED", "capture"))
        self.assertFalse(sales_db.update_order(conn, "order", "FAILED", "other"))
        self.assertEqual(sales_db.get_order(conn, "order")["status"], "COMPLETED")
        self.assertEqual(sales_db.get_order(conn, "order")["capture_id"], "capture")

    def test_concurrent_pack_capture_issues_only_one_token(self):
        conn = self.db()
        packs.create(conn, "pack", "order", 10, "199", "USD", "en", "now", False)
        barrier = threading.Barrier(4)
        def mark(_):
            with closing(sales_db.connect(self.path)) as other:
                barrier.wait(timeout=5)
                return packs.mark(other, "pack", "COMPLETED", "capture", "agency@example.com")
        with cf.ThreadPoolExecutor(4) as pool:
            tokens = [token for token in pool.map(mark, range(4)) if token is not None]
        self.assertEqual(len(tokens), 1)
        self.assertIsNotNone(packs.by_token(conn, tokens[0]))
        packs.mark(conn, "pack", "FAILED")
        self.assertIsNotNone(packs.by_token(conn, tokens[0]))

    def test_recovery_consumption_is_atomic(self):
        account_id, _ = self.account()
        token = access_links.issue(self.db(), "monitor", account_id)
        barrier = threading.Barrier(4)
        def consume(_):
            with closing(sales_db.connect(self.path)) as conn:
                barrier.wait(timeout=5)
                return access_links.consume(conn, token)
        with cf.ThreadPoolExecutor(4) as pool:
            outcomes = list(pool.map(consume, range(4)))
        self.assertEqual(sum(outcome is not None for outcome in outcomes), 1)

    def test_online_backup_contains_committed_wal_and_can_be_restored(self):
        conn = self.db()
        sales_db.create_scan(conn, "backed-up", "report", RESULT, "client")
        destination = os.path.join(self.tmp.name, "backup.db")
        backup_database(self.path, destination)
        self.assertEqual(os.stat(destination).st_mode & 0o777, 0o600)
        with closing(sales_db.connect(destination)) as restored:
            self.assertEqual(sales_db.get_scan(restored, "backed-up")["domain"], "example.com")
            self.assertEqual(restored.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_backup_never_overwrites_existing_file(self):
        conn = self.db()
        destination = os.path.join(self.tmp.name, "backup.db")
        backup_database(self.path, destination)
        sales_db.create_scan(conn, "later", "report", RESULT, "client")
        with self.assertRaises(FileExistsError):
            backup_database(self.path, destination)
        with closing(sales_db.connect(destination)) as backup:
            self.assertIsNone(sales_db.get_scan(backup, "later"))

    def test_unavailable_database_is_not_healthy(self):
        with mock.patch.object(quantum_saas_app, "db", side_effect=OSError("disk unavailable")):
            self.assertEqual(self.client.get("/healthz").status_code, 503)

    def test_scorecard_does_not_add_different_currencies(self):
        conn = self.db()
        sales_db.create_scan(conn, "scan", "report", RESULT, "client")
        for index, (amount, currency) in enumerate((("10", "USD"), ("50", "USDT"), ("70", "EUR"))):
            sales_db.create_order(conn, str(index), "scan", amount, currency)
            sales_db.update_order(conn, str(index), "COMPLETED", "capture" + str(index))
        with conn:
            conn.execute("UPDATE orders SET created_at = '2026-11-04T00:00:00Z'")
        card = scorecard.build(conn, today=dt.date(2026, 11, 5))
        self.assertEqual(card["totals"]["revenue"], 10)

    def test_unknown_result_preserves_last_known_pq_for_future_alerts(self):
        account_id, _ = self.account()
        conn = self.db()
        monitor_db.add_domain(conn, account_id, "example.com")
        row = monitor_db.list_domains(conn, account_id)[0]
        known = copy.deepcopy(RESULT)
        known["key_exchange"]["pq"] = True
        monitor_db.save_check(conn, row["id"], known)
        unknown = copy.deepcopy(RESULT)
        unknown["key_exchange"] = {"error": "blocked"}
        monitor_db.save_check(conn, row["id"], unknown)
        row = monitor_db.list_domains(conn, account_id)[0]
        self.assertEqual(row["pq"], 1)
        self.assertIn("PQ_LOST", [kind for kind, _ in monitor.diff(row, RESULT)])


class ProtocolSecurityTest(unittest.TestCase):
    def test_truncated_server_key_share_is_rejected(self):
        message = server_hello(key_len=0)
        with self.assertRaises(ValueError):
            qs.parse_server_hello(message[4:])

    def test_extension_length_and_duplicate_extensions_are_rejected(self):
        body = server_hello()[4:]
        with self.assertRaises(ValueError):
            qs.parse_server_hello(body[:-1])
        duplicate = b"\x00\x2b\x00\x02\x03\x04"
        pos = 35 + body[34] + 3
        length = int.from_bytes(body[pos:pos + 2], "big")
        body = body[:pos] + (length + len(duplicate)).to_bytes(2, "big") + body[pos + 2:] + duplicate
        with self.assertRaises(ValueError):
            qs.parse_server_hello(body)

    def test_retry_is_unknown_not_success(self):
        # Current design (2026-11-11 "hrr" deploy): the scanner answers a HelloRetryRequest once, like browsers. If the
        # retry does not complete, the HRR alone is kept as evidence but is never counted as post-quantum support,
        # no negotiation is claimed, and every consumer classifies the result as undetermined.
        hello = {"version": 0x0304, "group": 0x11EB, "cipher": 0x1301, "hrr": True, "kx": "TLS1.3",
                 "retry_error": "server answered the retried ClientHello inconsistently"}
        with mock.patch.object(qs, "_hello_attempt", return_value=hello):
            result = qs.probe_key_exchange("1.1.1.1", "example.com")
        self.assertFalse(result["pq"])
        self.assertFalse(result["negotiation_observed"])
        self.assertTrue(result["hrr"])
        self.assertIn("inconsistently", result["hello_retry_error"])
        import adoption
        self.assertTrue(adoption.is_unsure(result, result["version"]))

    def test_slow_drip_cannot_extend_tls_deadline(self):
        with mock.patch.object(qs.time, "monotonic", side_effect=[0, 0, 9]):
            reader = qs._HandshakeReader(FakeSocket(b"abcd", chunk=1))
            with self.assertRaises(TimeoutError):
                reader._recv_exact(4)

    def test_dns_has_a_deadline(self):
        with mock.patch.object(qs.queue.Queue, "get", side_effect=qs.queue.Empty), \
             mock.patch.object(qs.socket, "getaddrinfo", return_value=[]):
            with self.assertRaises(qs.ScanError):
                qs.resolve_public_ip("example.com")

    def test_dns_failure_stops_the_scan_without_network(self):
        # The scanner resolves every address with resolve_public_ips (multi-endpoint design, 2026-11-13);
        # there is no shared scan budget any more, so a DNS failure simply ends this scan with ScanError.
        with mock.patch.object(qs, "resolve_public_ips", side_effect=qs.ScanError("dns_failure", "offline")), \
             mock.patch.object(qs, "probe_key_exchange", side_effect=AssertionError("must not probe")):
            with self.assertRaises(qs.ScanError):
                qs.scan("example.com")

    def test_short_dna_header_has_a_validation_error(self):
        encoded = dna_encode.bytes_to_dna(bytes(dna_encode.RSCodec(32).encode(b"short")))
        with self.assertRaises(ValueError):
            dna_encode.restore(encoded)

    def test_fasta_sha256_is_checked(self):
        fasta = bio_archive_report.to_fasta("report", b"hello")
        bad = re.sub(r"sha256=[0-9a-f]{64}", "sha256=" + "0" * 64, fasta)
        with self.assertRaises(ValueError):
            bio_archive_report.from_fasta(bad)
        self.assertEqual(bio_archive_report.from_fasta(fasta), b"hello")

    def test_mcp_unknown_and_invalid_certificate_are_honest(self):
        from tests.test_mcp import core
        self.assertIn("undetermined", core.describe({"domain": "x.test", "post_quantum_key_exchange": None}))
        text = core.describe({"domain": "x.test", "grade": "F", "post_quantum_key_exchange": True,
                              "certificate_valid": False})
        self.assertNotIn("No action needed", text)
        self.assertIn("Fix the certificate", text)

    def test_mcp_get_returns_http_errors_as_structured_results(self):
        from tests.test_mcp import core
        error = urllib.error.HTTPError("https://example.test", 429, "limited", {}, io.BytesIO(b'{"error":"rate_limited"}'))
        with mock.patch.object(core.urllib.request, "urlopen", side_effect=error):
            self.assertEqual(core.scan("example.com"), {"error": "rate_limited"})


class ClientRegressionTest(unittest.TestCase):
    def test_unknown_probe_does_not_bypass_the_required_grade(self):
        from tests.test_action import scan
        result = {"domain": "x.test", "grade": "F", "post_quantum_key_exchange": None}
        self.assertFalse(scan.evaluate(result, False, "A")[0])
        self.assertFalse(scan.evaluate(result, True, "")[0])
        self.assertTrue(scan.evaluate(result, False, "")[0])
        self.assertIn("undetermined", scan.summary_markdown(result))
        self.assertNotIn("classical key exchange only", scan.summary_markdown(result))
