"""Commercial discovery must preserve configured prices and payment gating."""
import tempfile
import unittest
from unittest.mock import Mock
from quantum_saas_app import create_app

class CommercialPagesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'DATA_DIR': self.tmp.name,
            'PAYPAL_CLIENT_ID': '', 'PAYPAL_CLIENT_SECRET': '',
            'PAYPAL_PLAN_STARTER': '', 'PAYPAL_PLAN_BUSINESS': '',
            'PRICE': '57.50', 'PACK_PRICE': '234.00', 'PACK_CREDITS': 12,
            'CURRENCY': 'EUR', 'PUBLIC_URL': 'https://example.test'},
            scanner=Mock(side_effect=AssertionError('No external scans')))
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_localized_pages_show_configured_prices_and_destinations(self):
        for lang in ('ar', 'en', 'de'):
            for path in ('/business', '/pricing'):
                with self.subTest(lang=lang, path=path):
                    response = self.client.get(path, query_string={'lang': lang})
                    self.assertEqual(response.status_code, 200)
                    body = response.get_data(as_text=True)
                    self.assertIn(f'lang="{lang}"', body)
                    self.assertIn('57.50 EUR', body)
                    self.assertIn('234.00 EUR', body)
                    self.assertIn('/agency?lang=' + lang + '#buy', body)
                    self.assertIn('/monitoring?lang=' + lang + '#subscribe', body)
                    self.assertNotIn('paypal.com/sdk', body)
        self.assertIn('dir="rtl"', self.client.get('/business?lang=ar').text)

    def test_disabled_payment_has_no_accidental_provider_call(self):
        response = self.client.post('/api/paypal/packs', json={'consent': True})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.client.post('/api/monitor/signup', json={}).status_code, 503)

    def test_commercial_links_are_discoverable(self):
        body = self.client.get('/?lang=ar').text
        self.assertIn('/business?lang=ar', body)
        self.assertIn('/pricing?lang=ar', body)
        sitemap = self.client.get('/sitemap-pages.xml').text
        self.assertIn('/business', sitemap)
        self.assertIn('/pricing', sitemap)

    def test_configured_checkout_only_on_existing_purchase_pages(self):
        self.app.config.update(PAYPAL_CLIENT_ID='sandbox-client', PAYPAL_ENV='sandbox',
            PAYPAL_PLAN_STARTER='P-STARTER', PAYPAL_PLAN_BUSINESS='P-BUSINESS')
        self.app.extensions['paypal'] = Mock()
        self.assertIn('paypal.com/sdk/js?', self.client.get('/agency?lang=en').text)
        self.assertIn('intent=subscription', self.client.get('/monitoring?lang=en').text)
        self.assertNotIn('paypal.com/sdk', self.client.get('/pricing?lang=en').text)
        self.app.extensions['paypal'].assert_not_called()
