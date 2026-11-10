import shutil
import tempfile
import unittest

import config_gen
import guides
import quantum_saas_app


class ConfigGenTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.client = quantum_saas_app.create_app({"DATA_DIR": self.dir, "TESTING": True}).test_client()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_data_is_complete(self):
        for key, s in config_gen.SERVERS.items():
            self.assertIn(s["guide"], guides.GUIDES, key)
            for vkey, v in s["variants"].items():
                self.assertEqual(set(v["label"]), {"en", "ar", "de"}, (key, vkey))
                for st in v["steps"]:
                    self.assertIn(st["kind"], config_gen.STEP_TITLES)
                    self.assertTrue(st["code"] or st["note"], (key, vkey))
                    if st["note"]:
                        self.assertEqual(set(st["note"]), {"en", "ar", "de"}, (key, vkey))

    def test_every_server_page_in_three_languages(self):
        for key in config_gen.SERVERS:
            for lang in ("en", "ar", "de"):
                r = self.client.get(f"/tools/pq-tls-config/{key}?lang={lang}")
                self.assertEqual(r.status_code, 200, (key, lang))
                body = r.get_data(as_text=True)
                self.assertIn(f'<html lang="{lang}"', body)
                self.assertIn('hreflang="de"', body)
        self.assertEqual(self.client.get("/tools/pq-tls-config/iis").status_code, 404)

    def test_old_version_warns_and_has_no_config(self):
        body = self.client.get("/tools/pq-tls-config/nginx?v=openssl30&lang=en").get_data(as_text=True)
        self.assertIn("cannot negotiate post-quantum key exchange", body)
        self.assertNotIn("ssl_ecdh_curve X25519MLKEM768", body)
        body = self.client.get("/tools/pq-tls-config/nginx?lang=en").get_data(as_text=True)
        self.assertIn("ssl_ecdh_curve X25519MLKEM768:X25519:prime256v1", body)
        self.assertIn('rel="canonical" href="http://localhost/tools/pq-tls-config/nginx?lang=en"', body)

    def test_unknown_variant_falls_back_and_sitemap(self):
        self.assertEqual(self.client.get("/tools/pq-tls-config/go?v=zzz").status_code, 200)
        sm = self.client.get("/sitemap-pages.xml").get_data(as_text=True)
        self.assertIn("/tools/pq-tls-config/haproxy?lang=de", sm)
        self.assertIn("/tools/pq-tls-config?lang=ar", sm)


if __name__ == "__main__":
    unittest.main()
