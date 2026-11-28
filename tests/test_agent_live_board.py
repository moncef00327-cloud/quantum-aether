"""Tests for owner-only Real-Time Agent Operations Dashboard (/admin/agents-live & /feed)."""
import base64
import tempfile
import unittest

from werkzeug.security import generate_password_hash

import quantum_saas_app as qapp


class AgentLiveBoardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = qapp.create_app({
            "TESTING": True,
            "DATA_DIR": self.tmp.name,
            "HASH_SALT": "test-salt-live-board",
            "ADMIN_PASSWORD_HASH": generate_password_hash("s3cret-owner-pass"),
        })
        self.client = self.app.test_client()

    def _basic(self, user="admin", pw="s3cret-owner-pass"):
        tok = base64.b64encode(f"{user}:{pw}".encode()).decode()
        return {"Authorization": f"Basic {tok}"}

    def test_requires_owner_auth(self):
        r1 = self.client.get("/admin/agents-live")
        self.assertEqual(r1.status_code, 401)
        self.assertIn("noindex", r1.headers.get("X-Robots-Tag", ""))
        r2 = self.client.get("/admin/agents-live/feed")
        self.assertEqual(r2.status_code, 401)

    def test_html_and_live_json_feed_with_auth_and_cookie(self):
        r = self.client.get("/admin/agents-live", headers=self._basic())
        self.assertEqual(r.status_code, 200)
        self.assertIn("noindex", r.headers.get("X-Robots-Tag", ""))
        self.assertIn("no-store", r.headers.get("Cache-Control", ""))
        html = r.get_data(as_text=True)
        self.assertIn("agents-live.css", html)
        self.assertIn("agents-live.js", html)
        self.assertNotIn("<style>", html, "must use external CSS to pass strict CSP")
        self.assertNotIn("api_secret", html)
        self.assertEqual(self.client.get("/static/agents-live.css").status_code, 200)
        self.assertEqual(self.client.get("/static/agents-live.js").status_code, 200)

        # Follow-up JSON poll works via cookie alone (no Basic header needed)
        rf = self.client.get("/admin/agents-live/feed")
        self.assertEqual(rf.status_code, 200)
        doc = rf.get_json()
        self.assertIn("server_time_utc", doc)
        self.assertIn("kpis", doc)
        self.assertIn("events", doc)
        self.assertIn("timers", doc)
        self.assertIn("active_agents", doc["kpis"])


if __name__ == "__main__":
    unittest.main()
