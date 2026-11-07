"""Regression checks for truthful evidence, hostile inputs and metadata/privacy."""
import copy
import datetime as dt
import json
import unittest
from unittest import mock

import adoption
import badge_evidence
import quantum_vuln_scanner as scanner
import sales_db
import scan_experience
import monitor
from tests.test_app import AppTestCase, RESULT
from tests.test_scanner import FakeSocket, record, server_hello


class ProtocolEvidenceTests(unittest.TestCase):
    def test_hrr_is_not_a_completed_post_quantum_selection(self):
        hello = dict(version=0x0304, group=scanner.X25519MLKEM768, hrr=True, cipher=0x1301, kx='TLS1.3')
        with mock.patch.object(scanner, '_hello_attempt', return_value=hello):
            kx = scanner.probe_key_exchange('93.184.215.14', 'example.com')
        self.assertFalse(kx['pq'])
        self.assertFalse(kx['negotiation_observed'])
        self.assertTrue(adoption.is_unsure(kx, 'TLSv1.3'))
        assessment = scanner.assess(kx, RESULT['certificate'])
        self.assertNotEqual(assessment['grade'], 'A')
        self.assertIn('KX_RETRY_REQUESTED', {f['code'] for f in assessment['findings']})

    def test_malformed_server_hello_and_shares_are_rejected(self):
        valid = server_hello()[4:]
        for body in [valid[:38], valid[:-1], valid + b'\x00',
                     server_hello(key_len=1)[4:], server_hello(group=scanner.X25519, key_len=31)[4:],
                     valid[:34] + b'\xff' + valid[35:]]:
            with self.subTest(size=len(body)), self.assertRaises(ValueError):
                scanner.parse_server_hello(body)

    def test_oversized_record_is_rejected_before_reading_payload(self):
        reader = scanner._HandshakeReader(FakeSocket(b'\x16\x03\x03\xff\xff'), limit=64)
        with self.assertRaises(ValueError):
            reader.next_message()

    def test_unoffered_group_cannot_be_reported_as_observed_pq(self):
        sock = mock.Mock()
        sock.recv = FakeSocket(record(0x16, server_hello(group=0x0200, key_len=32))).recv
        with mock.patch.object(scanner, '_connect') as connect:
            connect.return_value.__enter__.return_value = sock
            with self.assertRaises(ValueError):
                scanner._hello_attempt('93.184.215.14', 'example.com', True, 8)

    def test_slow_peer_cannot_reset_the_overall_probe_deadline(self):
        with mock.patch('quantum_vuln_scanner.time.monotonic', side_effect=[0, 9]):
            reader = scanner._HandshakeReader(FakeSocket(b'12345'), timeout=8)
            with self.assertRaises(TimeoutError):
                reader._recv_exact(1)

    def test_urls_are_normalized_without_accepting_credentials_or_schemes(self):
        self.assertEqual(scanner.normalize_domain('HTTPS://ExAmPle.com./path?q=1'), 'example.com')
        self.assertEqual(scanner.normalize_domain('example.com:8443'), 'example.com')
        for bad in [None, [], {}, 42, 'ftp://example.com', 'https://user:pass@example.com',
                    'example.com:bad', 'example.com:99999', 'example.com:0',
                    'example.com\\@127.0.0.1', 'exa\nmple.com', 'https://[::1]/']:
            with self.subTest(value=bad), self.assertRaises(scanner.ScanError):
                scanner.normalize_domain(bad)

    def test_advice_does_not_infer_server_software(self):
        result = copy.deepcopy(RESULT)
        self.assertEqual(scan_experience.advice(result), ['configure'])
        result['key_exchange']['hrr'] = True
        result['key_exchange']['pq'] = True  # historical data must not win over uncertainty
        self.assertEqual(scan_experience.status(result), 'undetermined')
        self.assertIn('verify', scan_experience.advice(result))
        self.assertNotIn('configure', scan_experience.advice(result))

    def test_monitor_does_not_report_pq_loss_from_an_inconclusive_probe(self):
        result = copy.deepcopy(RESULT)
        result['key_exchange'].update(hrr=True, pq=False)
        alerts = monitor.diff({'grade': 'A', 'pq': 1, 'days_left': 60}, result)
        self.assertIn('OBSERVATION_UNDETERMINED', {code for code, _ in alerts})
        self.assertNotIn('PQ_LOST', {code for code, _ in alerts})
        self.assertNotIn('GRADE_CHANGED', {code for code, _ in alerts})


class PublicInputAndBadgeTests(AppTestCase):
    def test_scalar_json_never_becomes_a_server_error(self):
        for payload in [[], ['domain'], 1, True, 'text']:
            for path in ['/api/scan', '/api/v1/quantum-scan']:
                with self.subTest(payload=payload, path=path):
                    response = self.client.post(path, json=payload)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.get_json()['error'], 'invalid_request')

    def test_request_size_limit_and_malformed_domain_types(self):
        self.assertEqual(self.client.post('/api/scan', json={'domain': 'a' * 140000}).status_code, 413)
        for value in [None, [], {}]:
            with self.subTest(value=value):
                self.assertEqual(self.client.post('/api/scan', json={'domain': value}).status_code, 400)

    def test_badge_verification_never_initiates_a_scan(self):
        with mock.patch.dict(self.app.extensions, scanner=mock.Mock(side_effect=AssertionError('must not scan'))):
            result = self.client.get('/api/v1/badge/unknown.example')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.get_json()['state'], 'not_scanned')
            self.assertEqual(self.client.get('/verify/unknown.example').status_code, 200)
            self.assertEqual(self.client.get('/badge/unknown.example.svg').status_code, 200)

    def test_badge_expiry_and_cache_do_not_outlive_evidence(self):
        now = dt.datetime(2026, 11, 6, tzinfo=dt.timezone.utc)
        result = copy.deepcopy(RESULT)
        result['scanned_at'] = (now - dt.timedelta(days=30) + dt.timedelta(seconds=45)).isoformat()
        conn = sales_db.connect(self.data_dir + '/quantum_saas.db')
        try:
            sales_db.create_scan(conn, 'badge1', 'private-token', result, 'test')
            current = badge_evidence.for_domain(conn, 'example.com', now=now)
            self.assertEqual(current['state'], 'fresh')
            self.assertEqual(current['cache_seconds'], 45)
            expired = badge_evidence.for_domain(conn, 'example.com', now=now + dt.timedelta(seconds=46))
            self.assertEqual(expired['state'], 'stale')
            self.assertIsNone(expired['grade'])
        finally:
            conn.close()
        response = self.client.get('/api/v1/badge/example.com')
        self.assertNotIn('private-token', response.get_data(as_text=True))

    def test_uncertain_evidence_never_produces_a_positive_badge(self):
        result = copy.deepcopy(RESULT)
        result['scanned_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
        result['grade'] = 'A'
        result['key_exchange'].update(hrr=True, pq=True, group='X25519MLKEM768')
        conn = sales_db.connect(self.data_dir + '/quantum_saas.db')
        try:
            sales_db.create_scan(conn, 'uncertain', 'private', result, 'test')
        finally:
            conn.close()
        self.assertIn('undetermined', self.client.get('/badge/example.com.svg').get_data(as_text=True))
        self.assertIsNone(self.client.get('/api/v1/badge/example.com').get_json()['grade'])

    def test_scan_results_are_not_indexed_or_cached_and_limits_offer_retry(self):
        scan = self.scan()
        response = self.client.get('/scan/' + scan['scan_id'])
        self.assertIn('noindex', response.headers['X-Robots-Tag'])
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        self.assertEqual(response.headers['Referrer-Policy'], 'no-referrer')
        self.app.config['SCANS_PER_HOUR'] = 0
        limited = self.client.post('/api/scan', json={'domain': 'example.com'})
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.headers['Retry-After'], '3600')

    def test_canonical_uses_configured_origin_and_compare_language_keeps_domains(self):
        self.app.config['PUBLIC_URL'] = 'https://trusted.example'
        response = self.client.get('/?lang=en&utm_source=test', base_url='https://untrusted.example')
        body = response.get_data(as_text=True)
        self.assertIn('rel="canonical" href="https://trusted.example/?lang=en"', body)
        self.assertNotIn('property="og:url" content="https://untrusted.example', body)
