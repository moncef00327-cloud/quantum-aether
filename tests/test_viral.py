import shutil
import tempfile
import unittest

import quantum_saas_app
from tests.test_app import fake_scanner
from tests.test_monitor import result_for


class ViralFeaturesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # الماسح يعطي B لـ example.com (كلاسيكي) وA لغيرها
        def scanner(raw):
            import quantum_vuln_scanner as q
            d = q.normalize_domain(raw)
            return fake_scanner(raw) if d == "example.com" else result_for(d, grade="A")
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quantum.com", "HASH_SALT": "s"},
            scanner=scanner, paypal=None)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    # 1) الشارة لكل الدرجات مع HTML وMarkdown
    def test_badge_snippet_on_every_grade(self):
        sid = self.client.post("/api/scan", json={"domain": "example.com"}).get_json()["scan_id"]  # B
        body = self.client.get(f"/scan/{sid}?lang=en").get_data(as_text=True)
        self.assertIn("badge/example.com.svg", body)
        self.assertIn("![Post-quantum TLS grade by Quantum Aether]", body)  # Markdown
        self.assertIn('data-copy="#badge-md"', body)

    def test_badge_svg_renders_for_b_and_unknown(self):
        self.client.post("/api/scan", json={"domain": "example.com"})
        svg = self.client.get("/badge/example.com.svg").get_data(as_text=True)
        self.assertIn("B · classical", svg)
        self.assertIn("not scanned", self.client.get("/badge/never-scanned.test.svg").get_data(as_text=True))

    # 4) صفحة لكل نطاق
    def test_site_page_from_study_and_unknown(self):
        body = self.client.get("/site/google.com?lang=en").get_data(as_text=True)  # في الدراسة
        self.assertIn("google.com", body)
        self.assertIn("top-1000 study", body)
        self.assertNotIn("noindex", body)
        unknown = self.client.get("/site/no-such-domain-xyz.test?lang=en").get_data(as_text=True)
        self.assertIn("noindex", unknown)
        self.assertIn("Scan this site now for free", unknown)

    def test_site_page_prefers_recent_scan(self):
        self.client.post("/api/scan", json={"domain": "example.com"})  # B، حديث
        body = self.client.get("/site/example.com?lang=en").get_data(as_text=True)
        self.assertIn("From a live scan on", body)
        self.assertIn(">B<", body)

    # 5) المقارنة
    def test_compare_two_sites(self):
        body = self.client.get("/compare?a=example.com&b=google.com&lang=en").get_data(as_text=True)
        self.assertEqual(body.count('class="grade grade-'), 2)
        self.assertIn("example.com", body)
        self.assertIn("google.com", body)

    def test_compare_handles_bad_domain(self):
        body = self.client.get("/compare?a=example.com&b=not a domain&lang=en").get_data(as_text=True)
        self.assertEqual(self.client.get("/compare?a=example.com&b=not a domain&lang=en").status_code, 200)
        self.assertIn("example.com", body)

    # 2+3) فحص GET للـ CLI والوكلاء
    def test_get_scan_json_and_text(self):
        j = self.client.get("/api/v1/scan?domain=example.com").get_json()
        self.assertEqual(j["grade"], "B")
        self.assertFalse(j["post_quantum_key_exchange"])
        self.assertIn("/scan/", j["report_hint"])
        text = self.client.get("/api/v1/scan?domain=example.com&format=text").get_data(as_text=True)
        self.assertIn("grade", text)
        self.assertIn("harvest-now-decrypt-later", text)
        self.assertIn("example.com", text)

    def test_get_scan_max_age_reuses_recent_result(self):
        first = self.client.get("/api/v1/scan?domain=example.com").get_json()
        self.assertFalse(first["cached"])
        again = self.client.get("/api/v1/scan?domain=example.com&max_age=168").get_json()
        self.assertTrue(again["cached"])
        self.assertEqual(again["scan_id"], first["scan_id"])
        fresh = self.client.get("/api/v1/scan?domain=example.com").get_json()   # بلا max_age: فحص جديد
        self.assertNotEqual(fresh["scan_id"], first["scan_id"])
        self.assertEqual(self.client.get("/api/v1/scan?domain=not a domain&max_age=24").status_code, 400)

    def test_get_scan_bad_domain(self):
        self.assertEqual(self.client.get("/api/v1/scan?domain=").status_code, 400)
        self.assertEqual(self.client.get("/api/v1/scan?domain=x y&format=text").status_code, 400)

    def test_sitemap_lists_compare_and_site_pages(self):
        self.assertIn("/compare?lang=en", self.client.get("/sitemap-pages.xml").get_data(as_text=True))
        self.assertIn("/site/amazon.com?lang=en", self.client.get("/sitemap-sites-1.xml").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
