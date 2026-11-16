"""Infrastructure hosts (CDN, DNS, ad/analytics, telemetry, API): scanned and counted, never indexed."""
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET

import adoption
import quantum_saas_app
import sales_db
import search_indexing
from tests.test_crawlers import seed

BASE = 'https://ather-quantum.com'
NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}


class InfrastructurePolicyTests(unittest.TestCase):
    def test_list_is_reviewed_top_1000_exact_hosts(self):
        policy = json.loads(search_indexing.INFRASTRUCTURE_FILE.read_text(encoding='utf-8'))
        hosts = policy['hosts']
        self.assertEqual(len(hosts), len(set(hosts)))
        self.assertTrue(all(h == h.lower().strip() and h for h in hosts))
        top = {d for _, d in adoption.load_tranco(search_indexing.INDEX_MAX_RANK)}
        self.assertEqual(set(hosts) - top, set())

    def test_no_overlap_with_exclusions_or_watchlists(self):
        infra = search_indexing.infrastructure_hosts()
        self.assertEqual(infra & search_indexing.reviewed_hosts(), frozenset())
        watched = {d.lower() for s in adoption.load_watchlists().values() for d in s.get('domains', [])}
        self.assertEqual(infra & watched, frozenset())

    def test_infrastructure_is_not_indexable_but_not_excluded(self):
        for host in ['googleapis.com', 'doubleclick.net', 'GOOGLE-ANALYTICS.COM.', 'app-analytics-services.com']:
            with self.subTest(host=host):
                self.assertFalse(search_indexing.is_indexable(host, 5))
                self.assertFalse(search_indexing.is_excluded(host))
        for host in ['google.com', 'cloudflare.com', 'github.com', 'tencent.com']:
            with self.subTest(host=host):
                self.assertTrue(search_indexing.is_indexable(host, 5))
        self.assertTrue(search_indexing.is_indexable('googleapis.com', None, 'review-fixture'))  # a sector always wins

    def test_infrastructure_stays_in_the_weekly_sample(self):
        targets = {t['domain'] for t in adoption.load_targets()}
        self.assertIn('googleapis.com', targets)
        self.assertIn('doubleclick.net', targets)

    def test_owner_requested_exclusions(self):
        for host in ['dicrotin.com', 'xnhau.pics', 'uncenz.com']:
            with self.subTest(host=host):
                self.assertTrue(search_indexing.is_excluded(host))
        # cgbum.com is an Indonesian comics site (reviewed 2026-11-14); the owner reverted its exclusion on 2026-11-16.
        self.assertFalse(search_indexing.is_excluded('cgbum.com'))


class InfrastructurePageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = quantum_saas_app.create_app({'TESTING': True, 'DATA_DIR': self.tmp.name, 'PUBLIC_URL': BASE,
                                                'PAYPAL_CLIENT_ID': '', 'PAYPAL_CLIENT_SECRET': '',
                                                'HASH_SALT': 'infra-test'})
        self.client = self.app.test_client()
        self.conn = sales_db.connect(self.tmp.name + '/quantum_saas.db')
        seed(self.conn)
        with self.conn:
            self.conn.execute(
                "INSERT INTO adoption_results (week,domain,rank,ok,grade,grp,tls,pq,unsure,as_name,scanned_at) "
                "VALUES ('2026-W45','googleapis.com',8,1,'A','X25519MLKEM768','TLSv1.3',1,0,'CLOUDFLARENET',"
                "'2026-11-02T01:00:00Z')")

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_page_is_served_with_noindex(self):
        response = self.client.get('/site/googleapis.com?lang=en')
        self.assertEqual(response.status_code, 200)
        self.assertIn('noindex', response.headers.get('X-Robots-Tag', ''))
        ordinary = self.client.get('/site/alpha.test?lang=en')
        self.assertNotIn('noindex', ordinary.headers.get('X-Robots-Tag', ''))

    def test_sitemap_leaves_out_infrastructure(self):
        index = ET.fromstring(self.client.get('/sitemap.xml').data)
        locations = []
        for item in index.findall('s:sitemap/s:loc', NS):
            if 'sitemap-sites-' not in item.text:
                continue
            doc = ET.fromstring(self.client.get(item.text.removeprefix(BASE)).data)
            locations.extend(e.text for e in doc.findall('s:url/s:loc', NS))
        self.assertIn(BASE + '/site/alpha.test?lang=en', locations)
        self.assertFalse(any('/site/googleapis.com' in loc for loc in locations))


if __name__ == '__main__':
    unittest.main()
