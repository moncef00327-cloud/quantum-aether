"""New SEO-gap pages: checker landing, OpenSSL 3.5 cookbook, BSI TR-02102-2 guide."""
import json
import re
import tempfile
import unittest

import guide_faq
import guide_pages_seo_gap
import guides
import pq_tls_checker
import quantum_saas_app
import seo_meta

CHECKER = "/tools/post-quantum-tls-checker"
OPENSSL = "openssl-3-5-x25519mlkem768"
BSI = "bsi-tr-02102-2-post-quantum-tls"
GUIDE_SLUGS = (OPENSSL, BSI)
LANGS = ("en", "ar", "de")

JSONLD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def jsonld_blocks(body):
    return [json.loads(block) for block in JSONLD_RE.findall(body)]


class SeoGapPagesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp.name}).test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def get(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.get_data(as_text=True)

    def test_new_guides_registered_in_all_languages(self):
        for slug in GUIDE_SLUGS:
            self.assertIn(slug, guides.GUIDES)
            self.assertEqual(set(guides.GUIDES[slug]) - {"updated"}, set(LANGS))
            self.assertEqual(guides.GUIDES[slug]["updated"], "2026-11-24")
            self.assertEqual(set(guide_faq.FAQ[slug]), set(LANGS))
            self.assertEqual(guide_faq.FAQ[slug], guide_pages_seo_gap.FAQ[slug])

    def test_checker_http_200_h1_canonical_og_and_jsonld(self):
        for lang, h1_part in (
            ("en", "Post-Quantum TLS Checker"),
            ("ar", "فاحص TLS المقاوم للكم"),
            ("de", "Post-Quanten-TLS-Checker"),
        ):
            path = f"{CHECKER}?lang={lang}"
            body = self.get(path)
            self.assertIn(f'<html lang="{lang}"', body)
            self.assertIn(f"<h1>{h1_part}", body)
            self.assertIn(f'rel="canonical" href="http://localhost{CHECKER}?lang={lang}"', body)
            self.assertIn('property="og:title"', body)
            self.assertIn(f'property="og:url" content="http://localhost{CHECKER}?lang={lang}"', body)
            self.assertIn(f'hreflang="de" href="http://localhost{CHECKER}?lang=de"', body)
            self.assertIn(f'hreflang="en" href="http://localhost{CHECKER}?lang=en"', body)
            self.assertIn(f'hreflang="ar" href="http://localhost{CHECKER}?lang=ar"', body)
            blocks = jsonld_blocks(body)
            types = {b.get("@type") for b in blocks}
            self.assertIn("SoftwareApplication", types, lang)
            self.assertIn("FAQPage", types, lang)
            app = next(b for b in blocks if b.get("@type") == "SoftwareApplication")
            self.assertEqual(app["url"], f"http://localhost{CHECKER}?lang={lang}")
            self.assertEqual(app["applicationCategory"], "SecurityApplication")
            faq = next(b for b in blocks if b.get("@type") == "FAQPage")
            self.assertGreaterEqual(len(faq["mainEntity"]), 4)
            self.assertNotIn("<", faq["mainEntity"][0]["acceptedAnswer"]["text"])

    def test_checker_content_scan_form_prices_and_links(self):
        body = self.get(f"{CHECKER}?lang=en")
        for needle in (
            "X25519MLKEM768", "ML-KEM-768", "ML-KEM-1024", "port 443",
            "29 €", "99 €", "490 €",
            f"/guides/{OPENSSL}",
            f"/guides/{BSI}",
            "/index",
            'name="domain"',
            "pq-tls-checker",
        ):
            self.assertIn(needle, body, needle)
        self.assertIn('action="/scan?lang=en"', body)
        self.assertIn("Is TLS 1.3 quantum safe?", body)
        self.assertIn("post-quantum certificate", body.lower())
        title = re.search(r"<title>(.*?)</title>", body).group(1)
        self.assertLessEqual(len(title), seo_meta.TITLE_MAX)
        desc = re.search(r'<meta name="description" content="(.*?)"', body).group(1)
        self.assertLessEqual(len(desc), seo_meta.DESCRIPTION_MAX)

    def test_openssl_guide_http_200_canonical_jsonld_and_content(self):
        for lang, title_part in (
            ("en", "Test X25519MLKEM768 with OpenSSL 3.5"),
            ("ar", "اختبار X25519MLKEM768 باستخدام OpenSSL 3.5"),
            ("de", "X25519MLKEM768 mit OpenSSL 3.5 prüfen"),
        ):
            path = f"/guides/{OPENSSL}?lang={lang}"
            body = self.get(path)
            self.assertIn(f'<html lang="{lang}"', body)
            self.assertIn(f"<h1>{title_part}</h1>", body)
            self.assertIn(f'rel="canonical" href="http://localhost/guides/{OPENSSL}?lang={lang}"', body)
            blocks = jsonld_blocks(body)
            types = {b.get("@type") for b in blocks}
            self.assertIn("TechArticle", types, lang)
            self.assertIn("FAQPage", types, lang)
            article = next(b for b in blocks if b.get("@type") == "TechArticle")
            self.assertEqual(article["dateModified"], "2026-11-24")
            self.assertIn('id="short-answer"', body)
        body = self.get(f"/guides/{OPENSSL}?lang=en")
        for needle in (
            "openssl s_client", "Negotiated TLS1.3 group", "Peer Temp Key",
            "alert 40", "OpenSSL 3.5", "3.0", "3.4",
            CHECKER, "/monitoring", "/audit", "29 €", "99 €", "490 €",
            f"/guides/{BSI}",
        ):
            self.assertIn(needle, body, needle)

    def test_bsi_guide_http_200_canonical_jsonld_and_content(self):
        for lang, title_part in (
            ("en", "BSI TR-02102-2: Post-Quantum TLS"),
            ("ar", "BSI TR-02102-2: TLS المقاوم للكم"),
            ("de", "BSI TR-02102-2: Post-Quanten-TLS"),
        ):
            path = f"/guides/{BSI}?lang={lang}"
            body = self.get(path)
            self.assertIn(f'<html lang="{lang}"', body)
            self.assertIn(f"<h1>{title_part}</h1>", body)
            self.assertIn(f'rel="canonical" href="http://localhost/guides/{BSI}?lang={lang}"', body)
            blocks = jsonld_blocks(body)
            types = {b.get("@type") for b in blocks}
            self.assertIn("TechArticle", types, lang)
            self.assertIn("FAQPage", types, lang)
        body = self.get(f"/guides/{BSI}?lang=en")
        for needle in (
            "TR-02102-2", "2026-01", "X25519MLKEM768",
            "SecP256r1MLKEM768", "SecP384r1MLKEM1024",
            "2031", "2032", "port 443",
            "not", "certification",
            "bsi.bund.de", "RFC 10024",
            CHECKER, f"/guides/{OPENSSL}",
            "/monitoring", "/audit", "/index",
            "29 €", "99 €", "490 €",
        ):
            self.assertIn(needle, body, needle)
        de = self.get(f"/guides/{BSI}?lang=de")
        self.assertIn("keine BSI-Zertifizierung", de)
        self.assertIn("Ende 2031", de)

    def test_sitemap_lists_new_urls_including_german(self):
        body = self.get("/sitemap-pages.xml")
        self.assertIn(f"{CHECKER}?lang=en", body)
        self.assertIn(f"{CHECKER}?lang=ar", body)
        self.assertIn(f"{CHECKER}?lang=de", body)
        for slug in GUIDE_SLUGS:
            for lang in LANGS:
                self.assertIn(f"/guides/{slug}?lang={lang}", body, (slug, lang))
        index = self.get("/sitemap.xml")
        self.assertIn("/sitemap-pages.xml", index)

    def test_guides_index_and_related_links(self):
        index = self.get("/guides?lang=en")
        self.assertIn(f"/guides/{OPENSSL}?lang=en", index)
        self.assertIn(f"/guides/{BSI}?lang=en", index)
        # Existing guides should point readers at the new pages.
        check = self.get("/guides/check-website-post-quantum-tls?lang=en")
        self.assertIn(f"/guides/{OPENSSL}", check)
        self.assertIn(CHECKER, check)
        nis2 = self.get("/guides/nis2-dora-post-quantum-cryptography?lang=en")
        self.assertIn(f"/guides/{BSI}", nis2)
        curl = self.get("/guides/openssl-3-5-curl-test-x25519mlkem768?lang=en")
        self.assertIn(f"/guides/{OPENSSL}", curl)
        self.assertIn('id="related-guides"', curl)

    def test_nav_includes_checker(self):
        body = self.get("/guides?lang=en")
        self.assertIn(CHECKER, body)
        ar = self.get("/guides?lang=ar")
        self.assertIn(CHECKER, ar)

    def test_titles_and_descriptions_fit_serp_limits(self):
        for lang, page in pq_tls_checker.COPY.items():
            rendered = f"{page['title']} · Quantum Aether"
            self.assertLessEqual(len(seo_meta.title(rendered, CHECKER, lang)), seo_meta.TITLE_MAX, lang)
            self.assertLessEqual(len(seo_meta.description(page["description"])), seo_meta.DESCRIPTION_MAX, lang)
        for slug in GUIDE_SLUGS:
            for lang in LANGS:
                page = guides.GUIDES[slug][lang]
                rendered = f"{page['title']} · Quantum Aether"
                self.assertLessEqual(
                    len(seo_meta.title(rendered, f"/guides/{slug}", lang)), seo_meta.TITLE_MAX, (slug, lang))
                self.assertLessEqual(len(seo_meta.description(page["description"])), seo_meta.DESCRIPTION_MAX, (slug, lang))

    def test_checker_does_not_change_prices_or_invent_scans(self):
        self.assertEqual(pq_tls_checker.COPY["en"]["cta_mon"].count("29 €"), 1)
        self.assertIn("99 €", pq_tls_checker.COPY["en"]["cta_mon"])
        self.assertIn("490 €", pq_tls_checker.COPY["en"]["cta_audit"])
        # The landing page must keep using the existing /scan form, not a new probe.
        body = self.get(f"{CHECKER}?lang=en")
        self.assertNotRegex(body, r'action="[^"]*scan[^"]*445')
        self.assertIn("port 443 only", body.lower())


if __name__ == "__main__":
    unittest.main()
