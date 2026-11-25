"""Unit tests for tools/a2a_outreach.py (sync filtering, dry-run, send cap, dedup, opt-out suppression)."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import a2a_outreach  # noqa: E402


class A2AOutreachTests(unittest.TestCase):
    def test_relevance_filter_accepts_b2b_security_and_rejects_self_and_toys(self):
        self.assertTrue(a2a_outreach.is_relevant_candidate(
            "ZeroTrust Auditor", "Enterprise security compliance agent", "tls audit", "https://auditor.example.org/a2a"))
        self.assertFalse(a2a_outreach.is_relevant_candidate(
            "Quantum Aether", "Post-quantum TLS", "tls", "https://ather-quantum.com/a2a"))
        self.assertFalse(a2a_outreach.is_relevant_candidate(
            "Weather Joke Bot", "Daily jokes and weather", "fun", "https://weather.example.org/a2a"))

    def test_sync_dry_run_send_dedup_and_optout_suppression(self):
        with tempfile.TemporaryDirectory() as tmp:
            targets_file = os.path.join(tmp, "a2a_targets.json")
            db_path = os.path.join(tmp, "test.db")

            def fake_registry(url):
                if "a2aregistry.org" in url:
                    if "offset=0" not in url:
                        return {"agents": []}
                    return {"agents": [
                        {"name": "Braigetori", "description": "Agent coordination network", "is_healthy": True,
                         "url": "https://braigetori.example.org/a2a", "wellKnownURI": "https://braigetori.example.org/.well-known/agent-card.json",
                         "skills": [{"id": "join", "tags": ["network"]}]},
                        {"name": "AuthOnly", "description": "Security agent", "is_healthy": True,
                         "url": "https://authonly.example.org/a2a", "securitySchemes": {"bearer": {}}},
                        {"name": "StopBot", "description": "Enterprise compliance audit agent", "is_healthy": True,
                         "url": "https://stopbot.example.org/a2a", "wellKnownURI": "https://stopbot.example.org/.well-known/agent-card.json",
                         "skills": [{"id": "audit", "tags": ["compliance"]}]},
                    ]}
                return {"items": []}

            synced = a2a_outreach.sync_targets(targets_file, getter=fake_registry)
            self.assertEqual([t["host"] for t in synced], ["braigetori.example.org", "stopbot.example.org"])

            cards = {
                "https://braigetori.example.org/.well-known/agent-card.json": {
                    "name": "Braigetori", "url": "https://braigetori.example.org/a2a", "protocolVersion": "0.3.0",
                    "skills": [{"id": "join"}],
                },
                "https://stopbot.example.org/.well-known/agent-card.json": {
                    "name": "StopBot", "url": "https://stopbot.example.org/a2a", "protocolVersion": "0.3.0",
                    "skills": [{"id": "audit"}],
                },
            }
            posted = []

            def fake_http(url, *, method="GET", body=None, timeout=15.0):
                if method == "GET":
                    return (200, cards[url]) if url in cards else (404, "not found")
                posted.append((url, body))
                if "stopbot" in url:
                    return 200, {"jsonrpc": "2.0", "id": body["id"], "result": {"parts": [{"kind": "text", "text": "Please stop and opt-out."}]}}
                return 200, {"jsonrpc": "2.0", "id": body["id"], "result": {"parts": [{"kind": "text", "text": "Welcome to Braigetori!"}]}}

            def fake_handshake(host):
                return {"tls_version": "TLSv1.3", "group": "X25519", "kex_class": "classical"}

            # 1) Dry run sends nothing and writes no sent rows
            dr = a2a_outreach.run_batch(
                mode="dry-run", targets_path=targets_file, db_path=db_path, limit=5,
                card_fetcher=fake_http, handshake_fn=fake_handshake, sleep_fn=lambda _: None,
            )
            self.assertEqual(dr["rendered"], 2)
            self.assertEqual(len(posted), 0)

            # 2) Live send sends once per target, logs reply, suppresses opt-out host
            res = a2a_outreach.run_batch(
                mode="send", targets_path=targets_file, db_path=db_path, limit=5, daily_cap=5, pause_s=0,
                card_fetcher=fake_http, handshake_fn=fake_handshake, sleep_fn=lambda _: None,
            )
            self.assertEqual(res["sent"], 2)
            self.assertEqual(len(posted), 2)
            self.assertIn("/api/v1/attestation/sample.pdf", posted[0][1]["params"]["message"]["parts"][0]["text"])
            self.assertIn("X25519", posted[0][1]["params"]["message"]["parts"][0]["text"])

            # 3) Second run never repeats either agent
            res2 = a2a_outreach.run_batch(
                mode="send", targets_path=targets_file, db_path=db_path, limit=5, daily_cap=5, pause_s=0,
                card_fetcher=fake_http, handshake_fn=fake_handshake, sleep_fn=lambda _: None,
            )
            self.assertEqual(res2["sent"], 0)
            self.assertEqual(len(posted), 2)

            # 4) stopbot.example.org was auto-suppressed
            c = sqlite3.connect(db_path)
            sup = [r[0] for r in c.execute("SELECT host FROM a2a_outreach_suppress")]
            self.assertEqual(sup, ["stopbot.example.org"])
            c.close()


if __name__ == "__main__":
    unittest.main()
