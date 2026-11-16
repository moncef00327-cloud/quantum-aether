import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import generate_pqc_news
import pqc_news
import quantum_saas_app


def article(url="https://www.nist.gov/news-events/news/2026/11/pqc-guidance"):
    return {
        "source": "NIST Standards",
        "url": url,
        "title": "NIST post-quantum migration guidance",
        "description": "Guidance for a cryptographic inventory and migration.",
        "published_at": "2026-11-16T06:00:00Z",
    }


class PQCNewsTests(unittest.TestCase):
    def test_classification_adds_localized_editorial_context(self):
        classified = generate_pqc_news.classify(article())
        self.assertEqual(classified["category"], "standards")
        self.assertEqual(classified["importance"], "high")
        self.assertTrue(all(classified["takeaway"][lang] for lang in ("en", "ar", "de")))
        self.assertIsNone(generate_pqc_news.classify({**article(), "title": "A new gardening tool"}))

    def test_feed_generator_keeps_metadata_and_preserves_old_feed_on_total_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "news_feed.json"
            with patch.object(generate_pqc_news, "OUTPUT", output), \
                    patch.object(generate_pqc_news, "fetch_source", side_effect=lambda source: (source[0], [article()])):
                self.assertEqual(generate_pqc_news.main(), 0)
            generated = json.loads(output.read_text())
            self.assertEqual(len(generated["items"]), 1)
            self.assertNotIn("description", generated["items"][0])
            previous = output.read_bytes()
            with patch.object(generate_pqc_news, "OUTPUT", output), \
                    patch.object(generate_pqc_news, "fetch_source", side_effect=OSError("offline")):
                self.assertEqual(generate_pqc_news.main(), 1)
            self.assertEqual(output.read_bytes(), previous)

    def test_feed_validator_rejects_untrusted_links_and_accepts_official_subdomains(self):
        good = {"schema_version": 1, "items": [{
            "title": "PQC update", "url": "https://csrc.nist.gov/pqc", "source": "NIST",
            "category": "standards", "importance": "high",
            "takeaway": {lang: "Editorial note" for lang in ("en", "ar", "de")},
        }]}
        self.assertTrue(pqc_news._valid(good))
        bad = json.loads(json.dumps(good))
        bad["items"][0]["url"] = "https://nist.gov.attacker.example/pqc"
        self.assertFalse(pqc_news._valid(bad))

    def test_analytics_page_and_json_are_localized_and_source_linked(self):
        feed = {"schema_version": 1, "updated_at": "2026-11-16T06:00:00Z", "sources": [],
                "items": [{**{k: article()[k] for k in ("source", "url", "title", "published_at")},
                           "category": "standards", "importance": "high",
                           "takeaway": {lang: "Editorial note" for lang in ("en", "ar", "de")}}]}
        with tempfile.TemporaryDirectory() as directory:
            app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": directory,
                                                "PUBLIC_URL": "https://ather-quantum.com"})
            with patch.object(pqc_news, "load_feed", return_value=feed):
                client = app.test_client()
                arabic = client.get("/analytics?lang=ar")
                english = client.get("/analytics?lang=en")
                data = client.get("/analytics/news.json")
            self.assertEqual(arabic.status_code, 200)
            self.assertIn("مستجدات ما بعد الكم وTLS", arabic.get_data(as_text=True))
            self.assertIn("https://www.nist.gov/news-events/news/2026/11/pqc-guidance", english.get_data(as_text=True))
            self.assertEqual(data.get_json()["items"][0]["title"], article()["title"])


if __name__ == "__main__":
    unittest.main()
