"""Selective, evidence-reviewed exclusions without crawler or dataset restrictions."""
import copy
from html.parser import HTMLParser
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

import quantum_saas_app
import sales_db
import search_indexing
from tests.test_app import RESULT
from tests.test_crawlers import seed

BASE='https://ather-quantum.com'
NS={'s':'http://www.sitemaps.org/schemas/sitemap/0.9'}

class HeadAndLinks(HTMLParser):
    def __init__(self):super().__init__();self.robots=[];self.canonical=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='meta' and a.get('name')=='robots':self.robots.append(a.get('content',''))
        if tag=='link' and a.get('rel')=='canonical':self.canonical.append(a.get('href'))
        if tag=='a':self.links.append(a.get('href',''))

def metadata(response):
    doc=HeadAndLinks();doc.feed(response.get_data(as_text=True));return doc

class SearchIndexingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.scanner=Mock(side_effect=AssertionError('Indexing pages must never scan a domain'))
        self.app=quantum_saas_app.create_app({'TESTING':True,'DATA_DIR':self.tmp.name,'PUBLIC_URL':BASE,
            'PAYPAL_CLIENT_ID':'','PAYPAL_CLIENT_SECRET':'','HASH_SALT':'indexing-test'},scanner=self.scanner)
        self.client=self.app.test_client()
        self.conn=sales_db.connect(self.tmp.name+'/quantum_saas.db');seed(self.conn)
        with self.conn:
            self.conn.execute("INSERT INTO adoption_results (week,domain,rank,ok,grade,grp,tls,pq,unsure,scanned_at) VALUES ('2026-W45','ordinary.example',1,1,'A','X25519MLKEM768','TLSv1.3',1,0,'2026-11-02T01:00:00Z')")
            for i,domain in enumerate(sorted(search_indexing.reviewed_hosts())+['xxx-industry.test']):
                self.conn.execute('INSERT INTO adoption_results (week,domain,rank,ok,grade,grp,tls,pq,unsure,as_name,scanned_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    ('2026-W45',domain,4998+i,1,'B','X25519','TLSv1.3',0,0,'CLOUDFLARENET','2026-11-02T01:00:00Z'))
        with self.conn:
            self.conn.execute("UPDATE adoption_results SET sector='review-fixture'")
    def tearDown(self):self.conn.close();self.tmp.cleanup()

    def test_every_reviewed_host_is_noindex_crawlable_in_each_language_and_default(self):
        robots=RobotFileParser();robots.parse(self.client.get('/robots.txt').text.splitlines())
        for host in search_indexing.reviewed_hosts():
            for suffix in ['', '?lang=en','?lang=ar','?lang=de','?lang=en&utm_source=search']:
                with self.subTest(host=host,suffix=suffix):
                    path='/site/'+host+suffix;response=self.client.get(path);doc=metadata(response)
                    self.assertEqual(response.status_code,200)
                    self.assertIn('noindex',response.headers['X-Robots-Tag'])
                    self.assertTrue(any('noindex' in tag for tag in doc.robots))
                    self.assertTrue(robots.can_fetch('Googlebot',BASE+path))
                    lang='ar' if suffix=='?lang=ar' else 'en'
                    self.assertEqual(doc.canonical,[BASE+'/site/'+host+'?lang='+lang])
        self.scanner.assert_not_called()

    def test_normalized_host_and_canonical_receive_same_policy(self):
        response=self.client.get('/site/PORNHUB.COM.?lang=ar')
        self.assertEqual(response.status_code,200)
        self.assertIn('noindex',response.headers['X-Robots-Tag'])
        self.assertEqual(metadata(response).canonical,[BASE+'/site/pornhub.com?lang=ar'])

    def test_no_substring_suffix_or_automatic_subdomain_classification(self):
        for host in ['xxx-industry.test','xxx-ordinary.test','erome.com','xhamster999.test',
                     'news.pornhub.com','www.pornhub.com','pornhub.com.example','notpornhub.com','']:
            with self.subTest(host=host):self.assertFalse(search_indexing.is_excluded(host))
        response=self.client.get('/site/xxx-industry.test?lang=en&q=pornhub.com&search=xxx')
        self.assertEqual(response.status_code,200);self.assertNotIn('noindex',response.headers.get('X-Robots-Tag',''))
        self.assertFalse(metadata(response).robots)

    def test_excluded_pages_deliver_directives_even_for_old_conditional_requests(self):
        response=self.client.get('/site/pornhub.com?lang=en',headers={'If-Modified-Since':'Mon, 02 Nov 2099 01:00:00 GMT'})
        self.assertEqual(response.status_code,200);self.assertIn('noindex',response.headers['X-Robots-Tag'])
        self.assertTrue(response.data)
        head=self.client.head('/site/pornhub.com?lang=ar')
        self.assertEqual(head.status_code,200);self.assertIn('noindex',head.headers['X-Robots-Tag'])

    def test_sitemap_excludes_only_reviewed_hosts_across_all_chunks(self):
        index=ET.fromstring(self.client.get('/sitemap.xml').data)
        locations=[]
        for item in index.findall('s:sitemap/s:loc',NS):
            if 'sitemap-sites-' not in item.text:continue
            doc=ET.fromstring(self.client.get(item.text.removeprefix(BASE)).data)
            locations.extend(e.text for e in doc.findall('s:url/s:loc',NS))
            xml=ET.tostring(doc,encoding='unicode')
            for host in search_indexing.reviewed_hosts():self.assertNotIn('/site/'+host+'?',xml)
        self.assertIn(BASE+'/site/alpha.test?lang=en',locations)
        self.assertNotIn(BASE+'/site/onlyfans.com?lang=ar',locations)  # reviewed exclusion since 2026-11-10
        self.assertIn(BASE+'/site/xxx-industry.test?lang=en',locations)
        self.assertEqual(len(locations),len(set(locations)))

    def test_related_discovery_links_remove_only_excluded_destinations(self):
        response=self.client.get('/site/alpha.test?lang=en');links=metadata(response).links
        self.assertTrue(any('/site/beta.test' in link for link in links))
        for host in search_indexing.reviewed_hosts():
            self.assertFalse(any('/site/'+host in link for link in links))

    @patch('adoption.load_watchlists',return_value={'review-fixture': {'labels': {'en':'Review fixture','ar':'عينة مراجعة','de':'Testdaten'}, 'domains':[]}})
    def test_adoption_keeps_data_but_not_excluded_domain_links(self,_watchlists):
        for lang in ['en','ar','de']:
            response=self.client.get('/adoption?lang='+lang);doc=metadata(response)
            self.assertEqual(response.status_code,200);self.assertFalse(doc.robots)
            self.assertIn('pornhub.com',response.text)
            self.assertFalse(any('/site/pornhub.com' in link for link in doc.links))
            self.assertTrue(any('/site/alpha.test' in link for link in doc.links))
        data=self.client.get('/adoption.json').json
        self.assertIn('pornhub.com',json.dumps(data))

    def test_study_guides_weekly_and_ordinary_domain_pages_remain_indexable(self):
        for path in ['/study/top-1000-post-quantum-tls','/adoption','/guides','/guides/enable-x25519mlkem768-nginx','/site/alpha.test','/site/beta.test']:
            for lang in ['en','ar']:
                with self.subTest(path=path,lang=lang):
                    response=self.client.get(path+'?lang='+lang)
                    self.assertEqual(response.status_code,200)
                    self.assertNotIn('noindex',response.headers.get('X-Robots-Tag',''))
                    self.assertFalse(metadata(response).robots)
        response=self.client.get('/study/top-1000-post-quantum-tls?lang=en')
        self.assertIn('pornhub.com',response.text)

    def test_exclusion_is_independent_of_measurement_source(self):
        with self.app.test_request_context('/site/pornhub.com'):
            self.assertEqual(quantum_saas_app.known_result_for('pornhub.com')[1],'weekly')
        result=copy.deepcopy(RESULT);result['domain']='pornhub.com'
        sales_db.create_scan(self.conn,'reviewed-scan','test-report-token',result,'local-test',is_test=True)
        with self.app.test_request_context('/site/pornhub.com'):
            self.assertEqual(quantum_saas_app.known_result_for('pornhub.com')[1],'scan')
        self.assertIn('noindex',self.client.get('/site/pornhub.com').headers['X-Robots-Tag'])
        with patch('adoption.latest_for',return_value=None),patch('sales_db.latest_scan_for_domain',return_value=None):
            with self.app.test_request_context('/site/pornhub.com'):
                self.assertEqual(quantum_saas_app.known_result_for('pornhub.com')[1],'study')
            self.assertIn('noindex',self.client.get('/site/pornhub.com').headers['X-Robots-Tag'])

    def test_ordinary_domain_conditional_get_still_works(self):
        first=self.client.get('/site/alpha.test?lang=en')
        again=self.client.get('/site/alpha.test?lang=en',headers={'If-Modified-Since':first.headers['Last-Modified']})
        self.assertEqual(again.status_code,304);self.assertNotIn('noindex',again.headers.get('X-Robots-Tag',''))

    def test_unknown_domain_keeps_404(self):
        response=self.client.get('/site/no-record.example')
        self.assertEqual(response.status_code,404);self.assertTrue(any('noindex' in tag for tag in metadata(response).robots))

    def test_country_discovery_keeps_row_but_omits_reviewed_link(self):
        from tests.test_countries import seed as country_seed
        country_seed(self.conn)
        with patch.object(search_indexing,'reviewed_hosts',return_value=frozenset({'de0.de'})):
            response=self.client.get('/adoption/countries/de?lang=en')
            self.assertEqual(response.status_code,200)
            self.assertIn('de0.de',response.text)
            self.assertFalse(any('/site/de0.de' in link for link in metadata(response).links))
            self.assertTrue(any('/site/de1.de' in link for link in metadata(response).links))

    def test_user_agent_does_not_change_indexing_policy_or_access(self):
        for host in ['pornhub.com','alpha.test']:
            for agent in ['Mozilla/5.0','Googlebot','Bingbot']:
                response=self.client.get('/site/'+host+'?lang=en',headers={'User-Agent':agent})
                self.assertEqual(response.status_code,200)
                self.assertEqual('noindex' in response.headers.get('X-Robots-Tag',''),host=='pornhub.com')

    def test_www_site_alias_points_to_same_excluded_apex_canonical(self):
        response=self.client.get('/site/pornhub.com?lang=ar',base_url='https://www.ather-quantum.com')
        self.assertEqual(response.status_code,200)
        self.assertIn('noindex',response.headers['X-Robots-Tag'])
        self.assertEqual(metadata(response).canonical,[BASE+'/site/pornhub.com?lang=ar'])

    def test_every_policy_entry_has_reviewable_evidence(self):
        entries=json.loads(search_indexing.POLICY_FILE.read_text())['domains']
        self.assertEqual(len(entries),len(search_indexing.reviewed_hosts()))
        for entry in entries:
            self.assertIn(entry['classification'],search_indexing.CLASSIFICATIONS)
            self.assertTrue(entry['reviewed_on']);self.assertTrue(entry['review_method'])
            self.assertTrue(all(s['url'].startswith('https://') and s['publisher'] and s['locator'] for s in entry['sources']))
