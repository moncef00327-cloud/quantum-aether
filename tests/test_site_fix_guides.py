"""/site/<domain> links to the fix guide that matches the site's hosting network."""
import tempfile
import unittest
from unittest.mock import Mock

import quantum_saas_app
import sales_db
import search_indexing
from tests.test_crawlers import seed

BASE = 'https://ather-quantum.com'
ROW = ("INSERT INTO adoption_results (week,domain,rank,ok,grade,grp,tls,pq,unsure,as_name,scanned_at) "
       "VALUES ('2026-W45',?,?,1,?,?,'TLSv1.3',?,0,?,'2026-11-02T01:00:00Z')")


class SiteFixGuidesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = quantum_saas_app.create_app({'TESTING': True, 'DATA_DIR': self.tmp.name, 'PUBLIC_URL': BASE,
                                                'PAYPAL_CLIENT_ID': '', 'PAYPAL_CLIENT_SECRET': '', 'HASH_SALT': 'guides-test'},
                                               scanner=Mock(side_effect=AssertionError('no scans')))
        self.client = self.app.test_client()
        self.conn = sales_db.connect(self.tmp.name + '/quantum_saas.db')
        seed(self.conn)
        with self.conn:
            self.conn.execute(ROW, ('aws-hosted.example', 11, 'B', 'X25519', 0, 'Amazon.com, Inc.'))
            self.conn.execute(ROW, ('self-hosted.example', 12, 'B', 'X25519', 0, 'Hetzner Online GmbH'))
            self.conn.execute(ROW, ('already-pq.example', 13, 'A', 'X25519MLKEM768', 1, 'Cloudflare, Inc.'))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def page(self, domain, lang='en'):
        r = self.client.get(f'/site/{domain}?lang={lang}')
        self.assertEqual(r.status_code, 200)
        return r.get_data(as_text=True)

    def test_aws_site_links_aws_guide_first(self):
        html = self.page('aws-hosted.example')
        self.assertIn('How to turn on post-quantum key exchange', html)
        aws = html.index('/guides/aws-alb-cloudfront-post-quantum-tls')
        nginx = html.index('/guides/enable-x25519mlkem768-nginx')
        self.assertLess(aws, nginx)

    def test_self_hosted_site_links_server_guides(self):
        html = self.page('self-hosted.example', 'ar')
        self.assertIn('كيف تفعّل التبادل المقاوم للكم', html)
        self.assertIn('/guides/enable-x25519mlkem768-nginx', html)
        self.assertIn('/guides/post-quantum-tls-apache-caddy-haproxy-cloudflare', html)

    def test_pq_site_offers_learn_guides(self):
        html = self.page('already-pq.example')
        self.assertIn('Want the same result for your site?', html)
        self.assertIn('/guides/check-website-post-quantum-tls', html)

    def test_helper_never_returns_unknown_or_duplicate_guides(self):
        for net in ['Amazon.com, Inc.', 'Cloudflare, Inc.', 'Hetzner', None]:
            for pq in (0, 1):
                for lang in ('en', 'ar', 'de'):
                    out = quantum_saas_app.site_fix_guides(net, pq, lang)
                    slugs = [g['slug'] for g in out]
                    self.assertTrue(1 <= len(slugs) <= 3)
                    self.assertEqual(len(slugs), len(set(slugs)))
                    self.assertTrue(all(g['title'] for g in out))

    def test_kamareels2_is_excluded(self):
        self.assertTrue(search_indexing.is_excluded('kamareels2.com'))
        self.assertEqual(self.client.get('/site/kamareels2.com').status_code, 410)


if __name__ == '__main__':
    unittest.main()


class SiteSnippetTests(SiteFixGuidesTests):
    """The search snippet shows the measured answer and date; breadcrumbs give a readable SERP path."""

    def test_meta_description_carries_result_and_date(self):
        import re
        html = self.page('self-hosted.example')
        meta = re.search(r'<meta name="description" content="([^"]*)"', html).group(1)
        self.assertIn('No post-quantum key exchange yet.', meta)
        self.assertIn('TLS 1.3', meta)
        self.assertIn('X25519', meta)
        self.assertIn('grade B', meta)
        self.assertIn('2026-11-02', meta)
        self.assertLessEqual(len(meta), 170)
        pq = re.search(r'<meta name="description" content="([^"]*)"', self.page('already-pq.example', 'ar')).group(1)
        self.assertIn('نعم', pq)

    def test_breadcrumb_jsonld(self):
        html = self.page('aws-hosted.example')
        self.assertIn('"BreadcrumbList"', html)
        self.assertIn(f'"item": "{BASE}/"', html.replace('"item":"', '"item": "'))


class SiteWwwAliasTests(SiteFixGuidesTests):
    """A site tracked only as www.<domain> (or only as the apex) still gets its /site/ page under the other name."""

    def setUp(self):
        super().setUp()
        with self.conn:
            self.conn.execute(ROW, ('www.bank-www.example', 14, 'B', 'X25519', 0, 'Hetzner Online GmbH'))

    def test_apex_falls_back_to_www_row(self):
        html = self.page('bank-www.example')
        self.assertIn('bank-www.example', html)
        self.assertIn('TLS 1.3', html)

    def test_www_falls_back_to_apex_row(self):
        self.page('www.self-hosted.example')

    def test_unknown_domain_is_still_404(self):
        self.assertEqual(self.client.get('/site/nothing-here.example').status_code, 404)
