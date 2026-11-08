"""Validate every rendered Dataset, including nested isPartOf objects."""
import copy
from html.parser import HTMLParser
import json
import tempfile
import unittest
from unittest.mock import Mock

import quantum_saas_app
import sales_db
from tests.test_app import RESULT
from tests.test_countries import seed as seed_countries
from tests.test_crawlers import seed as seed_weekly


class JsonLdScripts(HTMLParser):
    def __init__(self):
        super().__init__();self.active=False;self.parts=[];self.documents=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script' and dict(attrs).get('type')=='application/ld+json':
            self.active=True;self.parts=[]
    def handle_data(self,data):
        if self.active:self.parts.append(data)
    def handle_endtag(self,tag):
        if tag=='script' and self.active:
            self.documents.append(json.loads(''.join(self.parts)))
            self.active=False


def objects(value):
    if isinstance(value,dict):
        yield value
        for child in value.values():yield from objects(child)
    elif isinstance(value,list):
        for child in value:yield from objects(child)


class DatasetJsonLdTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.scanner=Mock(side_effect=AssertionError('Rendering metadata must never scan externally'))
        self.app=quantum_saas_app.create_app({'TESTING':True,'DATA_DIR':self.tmp.name,
            'PUBLIC_URL':'https://ather-quantum.com','PAYPAL_CLIENT_ID':'','PAYPAL_CLIENT_SECRET':''},scanner=self.scanner)
        self.client=self.app.test_client()
        self.conn=sales_db.connect(self.tmp.name+'/quantum_saas.db')
        seed_countries(self.conn);seed_weekly(self.conn)
        sales_db.create_scan(self.conn,'metadata-scan','metadata-token',copy.deepcopy(RESULT),'local-metadata-test',is_test=True)
    def tearDown(self):
        self.scanner.assert_not_called();self.conn.close();self.tmp.cleanup()
    def documents(self,path):
        response=self.client.get(path);self.assertEqual(response.status_code,200,path)
        parser=JsonLdScripts();parser.feed(response.text)
        return parser.documents
    def assert_dataset(self,dataset):
        self.assertTrue(dataset['name'].strip())
        self.assertIsInstance(dataset['description'],str)
        self.assertGreaterEqual(len(dataset['description']),50)
        self.assertLessEqual(len(dataset['description']),5000)
        self.assertEqual(dataset['license'],'https://creativecommons.org/licenses/by/4.0/')
        self.assertEqual(dataset['creator']['@type'],'Organization')
        self.assertEqual(dataset['creator']['name'],'Quantum Aether')

    def test_nested_dataset_has_complete_metadata_for_all_measurement_sources_and_languages(self):
        # The route renders one Dataset regardless of weekly/study/visitor source.
        for domain,source in [('alpha.test','weekly'),('github.com','study'),('example.com','scan')]:
            with self.app.test_request_context('/site/'+domain):
                self.assertEqual(quantum_saas_app.known_result_for(domain)[1],source)
            for lang in ['en','ar']:
                with self.subTest(domain=domain,lang=lang):
                    docs=self.documents('/site/'+domain+'?lang='+lang)
                    page=next(d for d in docs if d.get('@type')=='WebPage')
                    dataset=page['isPartOf'];self.assertEqual(dataset['@type'],'Dataset')
                    self.assert_dataset(dataset)
                    self.assertEqual(dataset['url'],'https://ather-quantum.com/adoption')
                    self.assertIn('observed',dataset['description'].lower())
                    self.assertEqual(page['about']['name'],domain)
                    self.assertEqual([d['@type'] for d in docs],['WebPage','FAQPage'])

    def test_every_dataset_emitter_has_valid_complete_jsonld(self):
        paths=[('/adoption',['en','ar','de']),('/adoption/countries',['en','ar','de']),
               ('/study/top-1000-post-quantum-tls',['en','ar','de']),('/site/alpha.test',['en','ar'])]
        for path,langs in paths:
            for lang in langs:
                with self.subTest(path=path,lang=lang):
                    datasets=[obj for doc in self.documents(path+'?lang='+lang) for obj in objects(doc) if obj.get('@type')=='Dataset']
                    self.assertEqual(len(datasets),1)
                    self.assert_dataset(datasets[0])

    def test_non_dataset_pages_keep_their_structured_data_types(self):
        home=self.documents('/?lang=en')
        self.assertEqual([d['@type'] for d in home],['WebSite','SoftwareApplication','FAQPage'])
        guide=self.documents('/guides/enable-x25519mlkem768-nginx?lang=en')
        self.assertEqual([d['@type'] for d in guide],['TechArticle'])
        for docs in [home,guide]:
            for doc in docs:
                self.assertFalse(any(obj.get('@type')=='Dataset' for obj in objects(doc)))
                self.assertNotIn('license',doc)
        self.assertEqual(self.documents('/sample-report?lang=en'),[])

    def test_normal_domain_page_stays_indexable_and_crawlable(self):
        response=self.client.get('/site/alpha.test?lang=en')
        self.assertEqual(response.status_code,200)
        self.assertNotIn('noindex',response.headers.get('X-Robots-Tag',''))
        self.assertNotIn('<meta name="robots" content="noindex',response.text)
        self.assertIn('/site/alpha.test?lang=en',self.client.get('/sitemap-sites-1.xml').text)
        from urllib.robotparser import RobotFileParser
        robots=RobotFileParser();robots.parse(self.client.get('/robots.txt').text.splitlines())
        self.assertTrue(robots.can_fetch('Googlebot','https://ather-quantum.com/site/alpha.test?lang=en'))
