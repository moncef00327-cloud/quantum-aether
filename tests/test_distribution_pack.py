"""Tests for Multi-Agent Plugin Marketplaces, Agent Skills, and Self-Describing CLI (tools/qa_cli.py)."""
import io
import json
from pathlib import Path
import unittest
from unittest import mock

from tools import qa_cli

ROOT = Path(__file__).resolve().parent.parent
EXPECTED_SKILLS = {
    "pqc-tls-audit",
    "pqc-config-fix",
    "nis2-dora-evidence",
    "mcp-security-audit",
    "pqc-ci-gate",
}


class DistributionPackTests(unittest.TestCase):
    def test_marketplace_and_plugin_manifests_are_valid_json(self):
        manifests = [
            ROOT / ".claude-plugin" / "marketplace.json",
            ROOT / ".cursor-plugin" / "marketplace.json",
            ROOT / ".agents" / "plugins" / "marketplace.json",
            ROOT / "plugins" / "quantum-aether" / ".mcp.json",
            ROOT / "plugins" / "quantum-aether" / ".claude-plugin" / "plugin.json",
            ROOT / "plugins" / "quantum-aether" / ".codex-plugin" / "plugin.json",
            ROOT / "plugins" / "quantum-aether" / ".cursor-plugin" / "plugin.json",
        ]
        for path in manifests:
            with self.subTest(path=str(path)):
                self.assertTrue(path.exists(), f"missing {path}")
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertIsInstance(data, dict)

        mcp_cfg = json.loads((ROOT / "plugins" / "quantum-aether" / ".mcp.json").read_text(encoding="utf-8"))
        self.assertEqual(mcp_cfg["mcpServers"]["quantum-aether"]["url"], "https://ather-quantum.com/mcp")

    def test_all_five_skills_exist_in_plugin_and_agents_dirs_with_frontmatter(self):
        for base in (ROOT / "plugins" / "quantum-aether" / "skills", ROOT / ".agents" / "skills"):
            found = {p.name for p in base.iterdir() if p.is_dir()}
            self.assertEqual(found, EXPECTED_SKILLS, str(base))
            for name in EXPECTED_SKILLS:
                text = (base / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"), f"{name} missing YAML frontmatter")
                self.assertIn(f"name: {name}\n", text)
                self.assertIn("description:", text)

    def test_qa_cli_schema_usage_fix_and_scan(self):
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            self.assertEqual(qa_cli.main(["--schema"]), 0)
        schema = json.loads(buf.getvalue())
        self.assertEqual(schema["mcp_url"], "https://ather-quantum.com/mcp")
        self.assertIn("scan", schema["commands"])
        self.assertIn("mcp-index", schema["commands"])

        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            self.assertEqual(qa_cli.main(["fix", "nginx"]), 0)
        self.assertIn("X25519MLKEM768:X25519", buf.getvalue())

        buf = io.StringIO()
        with mock.patch.object(qa_cli, "_request_json", return_value={"grade": "A", "host": "cloudflare.com"}):
            with mock.patch("sys.stdout", buf):
                self.assertEqual(qa_cli.main(["scan", "cloudflare.com"]), 0)
        self.assertEqual(json.loads(buf.getvalue())["grade"], "A")

    def test_well_known_x402_discovery_endpoints(self):
        import os
        import tempfile
        import quantum_saas_app as app_mod

        with tempfile.TemporaryDirectory() as tmp:
            app = app_mod.create_app({
                "TESTING": True,
                "DATA_DIR": tmp,
                "DB_PATH": os.path.join(tmp, "test.db"),
                "USDC_BASE_ADDR": "0x1111111111111111111111111111111111111111",
            })
            client = app.test_client()
            for path in ("/.well-known/x402", "/.well-known/x402.json"):
                r = client.get(path)
                self.assertEqual(r.status_code, 200, path)
                self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), "*")
                doc = r.get_json()
                self.assertEqual(doc["x402Version"], 2)
                self.assertEqual(doc["network"], "eip155:8453")
                self.assertTrue(doc["enabled"])
                self.assertGreaterEqual(len(doc["resources"]), 6)
                ids = {e["id"] for e in doc["endpoints"]}
                self.assertEqual(ids, {"batch_scan", "live_cbom", "sector_snapshot", "tls_attestation", "full_report"})
            robots = client.get("/robots.txt").get_data(as_text=True)
            self.assertIn("/.well-known/x402", robots)


if __name__ == "__main__":
    unittest.main()
