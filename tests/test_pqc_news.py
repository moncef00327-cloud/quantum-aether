import json
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
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
        unrelated_quantum_paper = {**article(), "source": "arXiv quant-ph",
                                   "title": "Analytic spread complexity in three-level systems",
                                   "description": "The spread complexity characterizes a quantum state over the Krylov basis."}
        self.assertIsNone(generate_pqc_news.classify(unrelated_quantum_paper))
        self.assertIsNotNone(generate_pqc_news.classify({**unrelated_quantum_paper, "source": "Cloudflare Blog",
            "description": "Quantum computers threaten RSA encryption; Shor's algorithm."}))
        signature_paper = {**unrelated_quantum_paper,
                           "title": "Information-Theoretic Threshold Designated-Verifier Digital Signatures",
                           "description": "Preparation for quantum adversaries. A comparable post-quantum signature scheme meets the standard security criterion."}
        self.assertIsNone(generate_pqc_news.classify(signature_paper))
        titled_pqc_paper = {**signature_paper, "title": "Post-Quantum Threshold Designated-Verifier Digital Signatures"}
        self.assertEqual(generate_pqc_news.classify(titled_pqc_paper)["category"], "research")
        adoption_sok = {**unrelated_quantum_paper,
                        "title": "SoK: Assessing Post-Quantum Cryptography Adoption in Software Development: Standards, Lifecycle Coverage, Deployment Maturity",
                        "description": "A survey of industry practices and standards."}
        self.assertEqual(generate_pqc_news.classify(adoption_sok)["category"], "research")
        tls_paper = {**unrelated_quantum_paper,
                     "title": "Post-Quantum TLS Deployment Measurement Study"}
        self.assertEqual(generate_pqc_news.classify(tls_paper)["category"], "implementation")

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

    def test_generator_drops_old_results_from_refreshed_sources_but_keeps_failed_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "news_feed.json"
            stale = {**article("https://research.ibm.com/research/news"), "source": "IBM Research",
                     "title": "Unrelated quantum physics", "category": "research", "importance": "medium",
                     "takeaway": {lang: "Editorial" for lang in ("en", "ar", "de")}}
            retained = {**article("https://blog.google/old-pqc"), "source": "Google Blog"}
            output.write_text(json.dumps({"items": [stale, retained]}))
            sources = [("IBM Research", "https://research.ibm.com/rss", "ibm.com"),
                       ("Google Blog", "https://blog.google/rss/", "blog.google")]

            def fetch(source):
                if source[0] == "Google Blog":
                    raise OSError("temporarily offline")
                unrelated = {**article("https://research.ibm.com/research/new"), "source": source[0],
                             "title": "Quantum state correlations", "description": "A physics result."}
                return source[0], [unrelated]

            with patch.object(generate_pqc_news, "OUTPUT", output), \
                    patch.object(generate_pqc_news, "SOURCES", sources), \
                    patch.object(generate_pqc_news, "fetch_source", side_effect=fetch):
                self.assertEqual(generate_pqc_news.main(), 0)
            items = json.loads(output.read_text())["items"]
            self.assertEqual([item["url"] for item in items], [retained["url"]])

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
                rss = client.get("/analytics/feed.xml?lang=ar")
            self.assertEqual(arabic.status_code, 200)
            self.assertIn("مستجدات ما بعد الكم وTLS", arabic.get_data(as_text=True))
            self.assertIn("https://www.nist.gov/news-events/news/2026/11/pqc-guidance", english.get_data(as_text=True))
            self.assertEqual(data.get_json()["items"][0]["title"], article()["title"])
            page = english.get_data(as_text=True)
            match = re.search(r'<script type="application/ld\+json">(.*?)</script>', page)
            self.assertIsNotNone(match)
            structured = json.loads(match.group(1))
            self.assertEqual(structured["@type"], "CollectionPage")
            self.assertEqual(structured["mainEntity"]["itemListElement"][0]["url"], article()["url"])
            self.assertIn('type="application/rss+xml"', page)
            self.assertEqual(rss.status_code, 200)
            self.assertIn("application/rss+xml", rss.headers["Content-Type"])
            rss_root = ET.fromstring(rss.data)
            self.assertEqual(rss_root.findtext("./channel/language"), "ar")
            self.assertEqual(rss_root.findtext("./channel/item/title"), article()["title"])
            self.assertEqual(rss_root.findtext("./channel/item/link"), article()["url"])


if __name__ == "__main__":
    unittest.main()
