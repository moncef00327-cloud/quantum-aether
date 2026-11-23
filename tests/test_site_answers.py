"""'Is <domain> quantum-safe?' answer pages (2026-11-23): question title/H1, FAQ from stored data only (visible and
JSON-LD identical), certificate facts from the last stored handshake, peer comparison, same-country/watchlist links
that respect indexability and the adult/opt-out rules, plan prices, en/ar/de. Indexing rules are unchanged."""
import datetime as dt
import json
import re
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

import quantum_saas_app
import sales_db
import site_answers
from tests.test_crawlers import seed
from tests.test_search_indexing import metadata

BASE = 'https://ather-quantum.com'
NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
WEEK, AT = '2026-W45', '2026-11-02T01:00:00Z'


def jsonld(body):
    return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)]


class SiteAnswerPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.scanner = Mock(side_effect=AssertionError('Answer pages must never scan a domain'))
        self.app = quantum_saas_app.create_app({'TESTING': True, 'DATA_DIR': self.tmp.name, 'PUBLIC_URL': BASE,
                                                'PAYPAL_CLIENT_ID': '', 'PAYPAL_CLIENT_SECRET': '',
                                                'SUBSCRIPTION_CURRENCY': 'EUR', 'HASH_SALT': 'answers'},
                                               scanner=self.scanner)
        self.client = self.app.test_client()
        self.conn = sales_db.connect(self.tmp.name + '/quantum_saas.db')
        seed(self.conn)
        rows = []
        for i in range(22):  # 22 German sites: enough for the country board (MIN_SITES 20)
            rows.append((WEEK, f'site{i:02d}.de', 20 + i, None, 1, 'A' if i % 2 else 'B',
                         'X25519MLKEM768' if i % 2 else 'X25519', 'TLSv1.3', i % 2, 0, 'HETZNER', AT))
        rows.append((WEEK, 'hotxxxvids.de', 3, None, 1, 'B', 'X25519', 'TLSv1.3', 0, 0, 'HETZNER', AT))  # adult name
        rows.append((WEEK, 'deep.de', 90000, None, 1, 'B', 'X25519', 'TLSv1.3', 0, 0, 'OTHER', AT))      # not indexable
        rows.append((WEEK, 'bund.de', 4, 'government-dach', 1, 'B', 'X25519', 'TLSv1.3', 0, 0, 'GOV', AT))
        rows.append((WEEK, 'admin.ch', 7, 'government-dach', 1, 'A', 'X25519MLKEM768', 'TLSv1.3', 1, 0, 'GOV2', AT))
        with self.conn:
            self.conn.executemany('INSERT INTO adoption_results (week,domain,rank,sector,ok,grade,grp,tls,pq,unsure,as_name,scanned_at) '
                                  'VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', rows)
        not_after = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=60)).replace(microsecond=0)
        result = {'domain': 'site01.de', 'grade': 'A', 'scanned_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                  'port': 443, 'findings': [],
                  'key_exchange': {'version': 'TLSv1.3', 'group': 'X25519MLKEM768', 'pq': True, 'hrr': False,
                                   'negotiation_observed': True, 'cipher': 'TLS_AES_256_GCM_SHA384'},
                  'certificate': {'key_algorithm': 'ECDSA', 'key_bits': 256, 'curve': 'secp256r1', 'issuer': "Let's Encrypt",
                                  'signature_algorithm': 'ecdsa-with-SHA384', 'not_after': not_after.isoformat(),
                                  'days_left': 60, 'verified': True}}
        sales_db.create_scan(self.conn, 'scan-site01', 'tok-site01', result, 'h')
        self.expiry = not_after.date().isoformat()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def page(self, host, lang='en'):
        r = self.client.get(f'/site/{host}?lang={lang}')
        return r, r.get_data(as_text=True)

    def test_question_title_h1_and_faq_match(self):
        r, body = self.page('site00.de')
        self.assertEqual(r.status_code, 200)
        self.assertIn('<title>Is site00.de quantum-safe? PQ-TLS check · Quantum Aether</title>', body)
        self.assertIn('<h1>Is <bdi dir="ltr" class="domain">site00.de</bdi> quantum-safe?</h1>', body)
        self.assertNotIn('noindex', r.headers.get('X-Robots-Tag', ''))
        faq = next(o for o in jsonld(body) if o.get('@type') == 'FAQPage')
        names = [q['name'] for q in faq['mainEntity']]
        self.assertIn('Is site00.de quantum-safe? Does it use post-quantum TLS?', names)
        self.assertIn('Which TLS version and key exchange does site00.de use?', names)
        self.assertIn('How does site00.de compare with other websites?', names)
        self.assertIn('When was site00.de last checked?', names)
        for q in faq['mainEntity']:  # visible text equals structured data
            self.assertIn(q['name'].replace("'", '&#39;'), body)
            self.assertIn(q['acceptedAnswer']['text'].replace("'", '&#39;'), body)
        peers = next(q for q in faq['mainEntity'] if q['name'].startswith('How does'))['acceptedAnswer']['text']
        self.assertIn('Among websites from Germany in the top 10,000', peers)
        self.assertIn('site00.de is not one of them yet.', peers)
        # no certificate stored for site00.de: no certificate question and no invented values
        self.assertFalse(any('certificate' in n for n in names))
        self.assertNotIn('Certificate issuer', body)
        self.assertIn('"dateModified": "2026-11-02"', body)
        self.scanner.assert_not_called()

    def test_certificate_facts_from_stored_handshake(self):
        r, body = self.page('site01.de')
        self.assertIn('TLS_AES_256_GCM_SHA384', body)
        self.assertIn('Let&#39;s Encrypt', body)
        self.assertIn('ECDSA-256 (secp256r1)', body)
        self.assertIn(self.expiry, body)
        faq = next(o for o in jsonld(body) if o.get('@type') == 'FAQPage')
        self.assertTrue(any('certificate of site01.de' in q['name'] for q in faq['mainEntity']))
        self.assertIn('site01.de is one of them.', body)

    def test_comparison_internal_links_and_plans(self):
        r, body = self.page('site00.de')
        self.assertIn('id="compare"', body)
        self.assertIn('href="/adoption/countries/de?lang=en"', body)
        self.assertIn('/index?lang=en', body)
        self.assertIn('Other websites from Germany', body)
        self.assertIn('href="/site/site02.de"', body)
        self.assertNotIn('/site/hotxxxvids.de', body)  # adult names are never linked
        self.assertNotIn('/site/deep.de', body)        # only indexable pages are linked
        self.assertIn('Starter 29 €/month (10 domains) or Business 99 €/month (100 domains)', body)
        self.assertIn('/monitoring?domain=site00.de', body)

    def test_sector_comparison_and_links(self):
        r, body = self.page('bund.de')
        self.assertIn('Watchlist: Government (Germany, Austria, Switzerland)', body)
        self.assertIn('Same watchlist: Government (Germany, Austria, Switzerland)', body)

    def test_arabic_and_german(self):
        r, body = self.page('site00.de', 'ar')
        self.assertIn('هل site00.de آمن من الحوسبة الكمّية؟', body)
        self.assertIn('لا. بتاريخ 2026-11-02 لا يتفق site00.de', body)
        self.assertIn('Starter بـ 29 € شهرياً', body)
        # /site/ pages are served in en/ar (de redirects to en, as before); the German texts are ready for later
        with self.app.test_request_context('/'):
            v = site_answers.verdict('a.de', {'pq': True, 'grade': 'A', 'group': 'X25519MLKEM768', 'tls': 'TLSv1.3',
                                              'scanned_at': '2026-11-02'}, 'de', 'EN')
        self.assertTrue(v.startswith('Ja. Am 2026-11-02 handelt a.de'))
        self.assertEqual(site_answers.title('a.de', 'de'), 'Ist a.de quantensicher? PQ-TLS-Check · Quantum Aether')

    def test_indexing_rules_unchanged(self):
        r, body = self.page('deep.de')  # real data, but outside the allow-list: still noindex
        self.assertEqual(r.status_code, 200)
        self.assertIn('noindex', r.headers['X-Robots-Tag'])
        r, body = self.page('hotxxxvids.de')
        self.assertEqual(r.headers['X-Robots-Tag'], 'noindex, nofollow')
        self.assertFalse(any('/site/' in l and 'hotxxxvids.de' not in l for l in metadata(r).links))
        r, body = self.page('never-scanned.example')
        self.assertEqual(r.status_code, 404)
        self.assertNotIn('quantum-safe?</h1>', body)

    def test_sitemap_lists_only_indexable_with_scan_date(self):
        index = ET.fromstring(self.client.get('/sitemap.xml').data)
        pairs = {}
        for loc in index.findall('s:sitemap/s:loc', NS):
            if 'sitemap-sites-' in loc.text:
                doc = ET.fromstring(self.client.get(loc.text.replace(BASE, '')).data)
                for u in doc.findall('s:url', NS):
                    pairs[u.find('s:loc', NS).text] = u.find('s:lastmod', NS).text
        self.assertEqual(pairs.get(BASE + '/site/site00.de?lang=en'), '2026-11-02')  # lastmod = scan date
        self.assertFalse(any('deep.de' in l or 'hotxxxvids' in l for l in pairs))

    def test_pure_helpers(self):
        facts = site_answers.cert_facts({'certificate': {'issuer': 'X', 'key_algorithm': 'RSA', 'key_bits': 2048,
                                                         'not_after': '2027-01-01T00:00:00+00:00'},
                                         'key_exchange': {}, 'scanned_at': '2026-11-20T00:00:00+00:00'},
                                        today=dt.date(2026, 12, 1))
        self.assertEqual((facts['key'], facts['expiry'], facts['days_left']), ('RSA-2048', '2027-01-01', 31))
        self.assertIsNone(site_answers.cert_facts({'certificate': {}, 'key_exchange': {}}))
        self.assertEqual(site_answers.money('29.00', 'EUR'), '29 €')
        self.assertEqual(site_answers.money('99.00', 'EUR'), '99 €')
        items = site_answers.faq('a.test', {'pq': False, 'unsure': True, 'scanned_at': '2026-11-02', 'grade': 'B'},
                                 'en', 'V.', None, [], 'https://x/site/a.test')
        self.assertEqual(len(items), 2)  # no TLS/group facts, no comparison: those questions are omitted


class AgentDirectoryReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = quantum_saas_app.create_app({'TESTING': True, 'DATA_DIR': self.tmp.name, 'PUBLIC_URL': BASE,
                                                'PAYPAL_CLIENT_ID': '', 'PAYPAL_CLIENT_SECRET': '',
                                                'SUBSCRIPTION_CURRENCY': 'EUR', 'HASH_SALT': 'llms'},
                                               scanner=Mock(side_effect=AssertionError('no scans')))
        self.client = self.app.test_client()
        conn = sales_db.connect(self.tmp.name + '/quantum_saas.db')
        seed(conn)
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_stats_endpoint_is_public_json(self):
        r = self.client.get('/api/v1/adoption/stats')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['Access-Control-Allow-Origin'], '*')
        self.assertIn('noindex', r.headers['X-Robots-Tag'])
        body = r.get_json()
        self.assertEqual(body['license'], 'CC BY 4.0')
        self.assertEqual(body['week'], '2026-W45')
        self.assertEqual(body['datasets']['pq_tls_index_json'], BASE + '/index.json')
        self.assertIn('/api/v1/adoption/stats', self.client.get('/openapi.yaml').get_data(as_text=True))

    def test_llms_txt_prices_install_and_endpoints(self):
        text = self.client.get('/llms.txt').get_data(as_text=True)
        # live: subscriptions enabled -> EUR ("29 €"); this test app has no PayPal plans, so the legacy currency shows
        self.assertRegex(text, r'Starter 29 (€|USD|EUR)/month \(10 domains\), Business 99 (€|USD|EUR)/month \(100 domains\)')
        for needle in ['Organisation audit: 490 € one-time', 'pip install quantum-aether-mcp', 'uvx quantum-aether-mcp',
                       'io.github.moncef00327-cloud/quantum-aether', BASE + '/api/v1/adoption/stats',
                       '"Is {domain} quantum-safe?" answer page']:
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertNotIn('$29', text)
        self.assertNotIn('$99', text)
        self.assertIn(BASE + '/api/v1/adoption/stats', self.client.get('/llms-full.txt').get_data(as_text=True))
