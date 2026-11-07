"""فحوص المالك عبر CLI/MCP/API (بلا كوكي) تُصنَّف اختبارات إن جاءت من اتصال استعمل كوكي المدير خلال 24 ساعة."""
import shutil
import tempfile
import unittest

import quantum_saas_app
import sales_db
from tests.test_app import fake_scanner


class OwnerClientTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = quantum_saas_app.create_app(
            {"TESTING": True, "DATA_DIR": self.tmp, "PUBLIC_URL": "https://ather-quatum.cloud", "HASH_SALT": "s"},
            scanner=fake_scanner, paypal=None)
        with self.app.test_request_context():
            self.cookie = quantum_saas_app.admin_cookie_value()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return sales_db.connect(f"{self.tmp}/quantum_saas.db")

    def api_scan(self, ip, domain):
        client = self.app.test_client()
        res = client.get(f"/api/v1/scan?domain={domain}", environ_base={"REMOTE_ADDR": ip},
                         headers={"User-Agent": "quantum-aether-cli/1.0.0"})
        self.assertEqual(res.status_code, 200)
        return self.conn().execute("SELECT is_test FROM scans WHERE domain = ?", (domain,)).fetchone()[0]

    def test_owner_connection_api_scans_are_tests(self):
        browser = self.app.test_client()
        browser.set_cookie(quantum_saas_app.ADMIN_COOKIE, self.cookie)
        browser.get("/?lang=en", environ_base={"REMOTE_ADDR": "203.0.113.7"})
        self.assertEqual(self.api_scan("203.0.113.7", "owner.test"), 1)   # نفس الاتصال، بلا كوكي
        self.assertEqual(self.api_scan("198.51.100.9", "visitor.test"), 0)  # زائر آخر

    def test_expires_after_24_hours(self):
        browser = self.app.test_client()
        browser.set_cookie(quantum_saas_app.ADMIN_COOKIE, self.cookie)
        browser.get("/", environ_base={"REMOTE_ADDR": "203.0.113.7"})
        conn = self.conn()
        with conn:
            conn.execute("UPDATE owner_clients SET last_seen = '2020-01-01T00:00:00Z'")
        self.assertEqual(self.api_scan("203.0.113.7", "later.test"), 0)

    def test_no_cookie_no_record(self):
        self.app.test_client().get("/", environ_base={"REMOTE_ADDR": "203.0.113.7"})
        self.assertEqual(self.conn().execute("SELECT COUNT(*) FROM owner_clients").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
