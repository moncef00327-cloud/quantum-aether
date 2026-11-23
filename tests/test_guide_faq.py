"""Short answer + FAQ (visible HTML and FAQPage JSON-LD) on the guides that rank in Google."""
import json
import re
import tempfile
import unittest

import guide_faq
import guides
import quantum_saas_app


class GuideFaqTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name}).test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_language_of_each_guide_has_faq(self):
        for slug, langs in guide_faq.FAQ.items():
            self.assertIn(slug, guides.GUIDES)
            self.assertEqual(set(langs), {k for k in guides.GUIDES[slug] if k != "updated"}, slug)

    def test_page_shows_short_answer_faq_and_jsonld(self):
        for slug, langs in guide_faq.FAQ.items():
            for lang, entry in langs.items():
                body = self.client.get(f"/guides/{slug}?lang={lang}").get_data(as_text=True)
                self.assertIn('id="short-answer"', body, (slug, lang))
                self.assertLess(body.index('id="short-answer"'), body.index('id="domain-box-top"'))
                self.assertEqual(body.count("<h3>"), len(entry["faq"]), (slug, lang))
                blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)]
                faq = [b for b in blocks if b.get("@type") == "FAQPage"]
                self.assertEqual(len(faq), 1)
                self.assertEqual(len(faq[0]["mainEntity"]), len(entry["faq"]))
                self.assertNotIn("<", faq[0]["mainEntity"][0]["acceptedAnswer"]["text"])
                self.assertIn(guides.GUIDES[slug]["updated"], body)
                self.assertGreaterEqual(guides.GUIDES[slug]["updated"], guide_faq.CHECKED)

    def test_other_guides_unchanged(self):
        body = self.client.get("/guides/harvest-now-decrypt-later?lang=en").get_data(as_text=True)
        self.assertNotIn('id="short-answer"', body)
        self.assertNotIn("FAQPage", body)


if __name__ == "__main__":
    unittest.main()
