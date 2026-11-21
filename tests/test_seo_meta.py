"""SERP length limits for <title> and meta description (seo_meta)."""
import unittest

import seo_meta


class SeoMetaTests(unittest.TestCase):
    def test_short_title_unchanged(self):
        self.assertEqual(seo_meta.title("About our scans · Quantum Aether", "/scanning", "en"),
                         "About our scans · Quantum Aether")

    def test_long_title_drops_brand(self):
        text = "Enable post-quantum TLS on Go (crypto/tls) (X25519MLKEM768) · Quantum Aether"
        self.assertEqual(seo_meta.title(text, "/tools/pq-tls-config/go", "en"),
                         "Enable post-quantum TLS on Go (crypto/tls) (X25519MLKEM768)")
        self.assertEqual(seo_meta.title("فحص TLS للشركات ومراقبة جاهزية ما بعد الكم · الأثير الكمومي (Quantum Aether)",
                                        "/business", "ar"), "فحص TLS للشركات ومراقبة جاهزية ما بعد الكم · الأثير الكمومي")

    def test_override_for_long_page(self):
        long_ar = "مواعيد الانتقال إلى التشفير ما بعد الكمومي: NIST وCNSA 2.0 والاتحاد الأوروبي وبريطانيا · الأثير الكمومي"
        self.assertEqual(seo_meta.title(long_ar, "/deadlines", "ar"), seo_meta.TITLE_OVERRIDES[("/deadlines", "ar")])

    def test_overrides_fit(self):
        for key, value in seo_meta.TITLE_OVERRIDES.items():
            self.assertLessEqual(len(value), seo_meta.TITLE_MAX, key)

    def test_description_cut_on_word(self):
        text = "word " * 60
        out = seo_meta.description(text)
        self.assertLessEqual(len(out), seo_meta.DESCRIPTION_MAX)
        self.assertTrue(out.endswith("word…"))
        self.assertEqual(seo_meta.description("short  text"), "short text")


if __name__ == "__main__":
    unittest.main()
