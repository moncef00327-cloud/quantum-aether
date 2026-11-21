"""Guide links cut off when shared (Reddit/X previews) redirect to the one guide they name."""
import tempfile
import unittest

import quantum_saas_app


class TruncatedGuideLinkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://example.test",
                                           "PAYPAL_CLIENT_ID": "", "PAYPAL_CLIENT_SECRET": ""})
        self.client = app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_unique_prefix_redirects(self):
        for cut in ("enable-x25519ml", "enable-x25519mlkem768-ng", "gulf-banks-post-quantum-"):
            with self.subTest(cut=cut):
                r = self.client.get(f"/guides/{cut}")
                self.assertEqual(r.status_code, 301)
                self.assertIn("/guides/", r.headers["Location"])
        r = self.client.get("/guides/enable-x25519ml?lang=ar")
        self.assertTrue(r.headers["Location"].endswith("/guides/enable-x25519mlkem768-nginx?lang=ar"))
        self.assertTrue(self.client.get("/guides/gulf-banks-post-quantum-").headers["Location"]
                        .endswith("/guides/gulf-banks-post-quantum-cryptography-requirements"))

    def test_short_or_ambiguous_or_unknown_prefix_is_404(self):
        for bad in ("enable", "post-quantum-tls-x", "nothing-like-this-guide"):
            with self.subTest(bad=bad):
                self.assertEqual(self.client.get(f"/guides/{bad}").status_code, 404)

    def test_full_slug_still_renders(self):
        self.assertEqual(self.client.get("/guides/enable-x25519mlkem768-nginx?lang=en").status_code, 200)


if __name__ == "__main__":
    unittest.main()
