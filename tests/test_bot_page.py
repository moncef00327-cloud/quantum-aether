"""/bot explains QuantumAetherBot to admins who see it in their logs; no personal address on /bot or /scanning."""
import re
import tempfile
import unittest

import bot_page
import growth_agent
import quantum_saas_app


class BotPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name}).test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_bot_page_en_ar(self):
        for lang, needle in (("en", "QuantumAetherBot visited your site"), ("ar", "زار QuantumAetherBot موقعك")):
            body = self.client.get(f"/bot?lang={lang}").get_data(as_text=True)
            self.assertIn(needle, body)
            self.assertIn("security.txt", body)
            self.assertIn('id="optout"', body)
            self.assertIn("contact@mail.ather-quantum.com", body)
        self.assertEqual(growth_agent.UA, bot_page.UA)

    def test_no_gmail_on_public_scan_pages(self):
        for path in ("/bot?lang=en", "/scanning?lang=en", "/scanning?lang=ar"):
            self.assertIsNone(re.search(r"[a-z0-9._-]+@gmail\.com", self.client.get(path).get_data(as_text=True)), path)


if __name__ == "__main__":
    unittest.main()
