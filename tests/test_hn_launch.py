import shutil
import tempfile
import unittest

import quantum_saas_app
from test_discovery import _result


class HnLaunchTests(unittest.TestCase):
    def make(self, **cfg):
        self.dir = tempfile.mkdtemp()
        self.calls = []

        def scanner(raw):
            self.calls.append(raw)
            return dict(_result(), domain=raw)
        self.app = quantum_saas_app.create_app(dict({"DATA_DIR": self.dir, "TESTING": True, "TRUSTED_PROXIES": 0}, **cfg),
                                               scanner=scanner)
        return self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_recent_result_is_reused_without_new_probe(self):
        c = self.make(SCAN_REUSE_SECONDS=600)
        a = c.post("/api/scan", json={"domain": "example.com"}).get_json()["scan_id"]
        b = c.post("/api/scan", json={"domain": "https://example.com/"}).get_json()["scan_id"]
        self.assertEqual(a, b)
        self.assertEqual(len(self.calls), 1)

    def test_global_limit_says_busy_not_your_fault(self):
        c = self.make(GLOBAL_SCANS_PER_HOUR=0)
        r = c.post("/scan?lang=en", data={"domain": "example.com"})
        self.assertEqual(r.status_code, 429)
        self.assertIn("a lot of scans right now", r.get_data(as_text=True))
        self.assertEqual(r.headers["Retry-After"], "300")

    def test_snippets_are_pinned_and_no_pipe_to_shell(self):
        self.make()
        with self.app.test_request_context():
            s = quantum_saas_app.badge_snippets("example.com")
        self.assertIn("pq-tls-action@v1", s["action"])
        self.assertNotIn("@main", s["action"])
        self.assertNotIn("| sh", s["cli"])
        body = self.app.test_client().get("/install-agent.sh").get_data(as_text=True)
        self.assertNotIn("README", body)
        self.assertNotIn(".mcp.json", body)
