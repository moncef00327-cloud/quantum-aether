"""Vendor security questionnaire guide (2026-11-21): ar/de/en, trial CTA, listed."""
import tempfile
import unittest
from unittest.mock import Mock

import quantum_saas_app
from tests.test_app import RESULT

SLUG = "post-quantum-vendor-security-questionnaire"


class QuestionnaireGuideTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name, "PUBLIC_URL": "https://ather-quantum.com"},
                                               scanner=Mock(return_value=dict(RESULT)))
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_three_languages_with_trial(self):
        for lang, word in (("en", "Three honest answers"), ("de", "Drei ehrliche Antworten"), ("ar", "ثلاث إجابات صادقة")):
            r = self.client.get(f"/guides/{SLUG}?lang={lang}")
            self.assertEqual(r.status_code, 200, lang)
            html = r.get_data(as_text=True)
            self.assertIn(word, html)
            self.assertIn('id="guide-next"', html)

    def test_listed(self):
        self.assertIn(SLUG, self.client.get("/llms.txt").get_data(as_text=True))
        self.assertIn(SLUG, self.client.get("/guides?lang=en").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
