"""Adult/gambling host names (keyword backstop + family-DNS list): noindex, nofollow, out of the sitemap and links.
Search Console 2026-11-23 showed /site/<adult host> pages ranking for porn queries. Keyword matches never 410."""
import tempfile
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

import quantum_saas_app
import sales_db
import search_indexing
from tests.test_crawlers import seed
from tests.test_search_indexing import metadata

BASE = 'https://ather-quantum.com'
NS = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
FAMILY = frozenset({'famblocked.test'})
ROWS = [('hotxxxvids.test', 3), ('famblocked.test', 4), ('bestcasino.test', 5), ('essex.ac.test', 6)]


class AdultDeindexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.scanner = Mock(side_effect=AssertionError('Indexing pages must never scan a domain'))
        self.app = quantum_saas_app.create_app({'TESTING': True, 'DATA_DIR': self.tmp.name, 'PUBLIC_URL': BASE,
                                                'PAYPAL_CLIENT_ID': '', 'PAYPAL_CLIENT_SECRET': '',
                                                'HASH_SALT': 'adult-test'}, scanner=self.scanner)
        self.client = self.app.test_client()
        self.conn = sales_db.connect(self.tmp.name + '/quantum_saas.db')
        seed(self.conn)
        with self.conn:
            for domain, rank in ROWS:  # top ranks: would be indexable if the name filter did not apply
                self.conn.execute('INSERT INTO adoption_results (week,domain,rank,ok,grade,grp,tls,pq,unsure,as_name,scanned_at) '
                                  'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                                  ('2026-W45', domain, rank, 1, 'B', 'X25519', 'TLSv1.3', 0, 0, 'CLOUDFLARENET', '2026-11-02T01:00:00Z'))
        self.family = patch('search_indexing.family_dns_blocked_hosts', return_value=FAMILY)
        self.family.start()

    def tearDown(self):
        self.family.stop()
        self.conn.close()
        self.tmp.cleanup()

    def test_keyword_classifier(self):
        for host in ['hotxxxvids.test', 'freesexkahani.com', 'w4nkr.com', 'besthindiporn.com', 'feedtofap.com',
                     'bestcasino.test', 'XHAMSTER19.COM.', 'tubepussy.org', 'desikahani2.net']:
            with self.subTest(host=host):
                self.assertTrue(search_indexing.keyword_suspect(host))
                self.assertTrue(search_indexing.is_sensitive(host))
                self.assertFalse(search_indexing.is_excluded(host) and host.endswith('.test'))
        for host in ['essex.ac.uk', 'sussex.ac.uk', 'dnsexit.com', 'gambleaware.org', 'gamblingcommission.gov.uk',
                     'jeuxvideo.com', 'nflxvideo.net', 'xxxlutz.de', 'java.com', 'alpha.test', 'tencent.com', '']:
            with self.subTest(host=host):
                self.assertFalse(search_indexing.keyword_suspect(host))
        # keyword alone never becomes a 410 exclusion or a stats filter
        self.assertFalse(search_indexing.is_excluded('hotxxxvids.test'))

    def test_sensitive_pages_render_but_are_noindex_nofollow(self):
        for host in ['hotxxxvids.test', 'famblocked.test', 'bestcasino.test']:
            for suffix in ['', '?lang=en', '?lang=ar']:
                with self.subTest(host=host, suffix=suffix):
                    r = self.client.get('/site/' + host + suffix)
                    self.assertEqual(r.status_code, 200)  # users who scan it still see a result page
                    self.assertEqual(r.headers['X-Robots-Tag'], 'noindex, nofollow')
                    self.assertIn('noindex, nofollow', metadata(r).robots)
                    self.assertFalse(metadata(r).canonical)
                    self.assertFalse(any('/site/' in l and host not in l for l in metadata(r).links))
        self.assertFalse(search_indexing.is_indexable('hotxxxvids.test', 3))
        self.scanner.assert_not_called()

    def test_ordinary_and_false_positive_pages_unchanged(self):
        for host in ['alpha.test', 'essex.ac.test']:
            with self.subTest(host=host):
                r = self.client.get('/site/' + host + '?lang=en')
                self.assertEqual(r.status_code, 200)
                self.assertNotIn('noindex', r.headers.get('X-Robots-Tag', ''))
                self.assertFalse(any('noindex' in t for t in metadata(r).robots))

    def test_sitemap_and_links_skip_sensitive_hosts(self):
        index = ET.fromstring(self.client.get('/sitemap.xml').data)
        locs = []
        for item in index.findall('s:sitemap/s:loc', NS):
            doc = ET.fromstring(self.client.get(item.text.removeprefix(BASE)).data)
            locs.extend(e.text for e in doc.findall('s:url/s:loc', NS))
        text = '\n'.join(locs)
        for host in ['hotxxxvids.test', 'famblocked.test', 'bestcasino.test']:
            self.assertNotIn(host, text)
        self.assertIn(BASE + '/site/alpha.test?lang=en', locs)
        self.assertIn(BASE + '/site/essex.ac.test?lang=en', locs)
        with self.app.test_request_context('/'):
            known = quantum_saas_app.site_pages_known(['alpha.test', 'hotxxxvids.test', 'famblocked.test'])
        self.assertEqual(known, {'alpha.test'})
        links = metadata(self.client.get('/site/alpha.test?lang=en')).links
        for host in ['hotxxxvids.test', 'famblocked.test', 'bestcasino.test']:
            self.assertFalse(any('/site/' + host in l for l in links))


if __name__ == '__main__':
    unittest.main()
