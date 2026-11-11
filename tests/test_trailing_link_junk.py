"""Links pasted with a trailing backtick/bracket/full stop reach the real page (seen from reddit.com)."""
import tempfile
import unittest
from unittest.mock import Mock

import quantum_saas_app


class TrailingJunkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app = quantum_saas_app.create_app({'TESTING': True, 'DATA_DIR': self.tmp.name, 'PUBLIC_URL': 'https://ather-quantum.com',
                                           'PAYPAL_CLIENT_ID': '', 'PAYPAL_CLIENT_SECRET': ''},
                                          scanner=Mock(side_effect=AssertionError('no scans')))
        self.client = app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_trailing_punctuation_redirects_to_the_page(self):
        for junk in ['%60', '`', ')', '.', ',', '%22', "'", ').', '`.']:
            with self.subTest(junk=junk):
                r = self.client.get('/study/top-1000-post-quantum-tls' + junk + '?lang=en')
                self.assertEqual(r.status_code, 301)
                self.assertEqual(r.headers['Location'], '/study/top-1000-post-quantum-tls?lang=en')
        r = self.client.get('/guides/enable-x25519mlkem768-nginx%60')
        self.assertEqual((r.status_code, r.headers['Location']), (301, '/guides/enable-x25519mlkem768-nginx'))

    def test_real_404_stays_404(self):
        for path in ['/no-such-page', '/no-such-page.', '/no-such-page%60']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
        # A dynamic route with an unknown slug: one redirect, then an ordinary 404, never a loop.
        r = self.client.get('/guides/does-not-exist)', follow_redirects=True)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(len(r.history), 1)

    def test_post_is_never_redirected(self):
        self.assertNotEqual(self.client.post('/study/top-1000-post-quantum-tls%60').status_code, 301)


if __name__ == '__main__':
    unittest.main()
