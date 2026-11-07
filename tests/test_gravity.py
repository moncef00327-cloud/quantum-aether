import unittest
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import gravity


def discussion(url, source="GitHub"):
    return dict(url=url, source=source, title="How to enable X25519MLKEM768 on nginx?", text="TLS configuration")


class GravityTests(unittest.TestCase):
    def test_tracking_and_question_aliases_do_not_inflate_demand(self):
        rows = gravity.opportunities([
            discussion("https://github.com/a/b/issues/1?utm_source=x"),
            discussion("https://github.com/a/b/issues/1?utm_source=y#comment"),
            discussion("https://serverfault.com/q/42/123", "Server Fault"),
            discussion("https://serverfault.com/questions/42/title", "Server Fault"),
        ])
        self.assertEqual(rows[0]["discussion_count"], 2)

    def test_invalid_discussions_do_not_crash_or_count(self):
        urls = ["https://github.com:bad/a", "https://[broken", "https://github.com/",
                "https://user@github.com/a/b/issues/1", "https://github.com:444/a/b/issues/1"]
        self.assertEqual(gravity.opportunities([None] + [discussion(u) for u in urls]), [])
        self.assertIsNone(gravity.evidence_url("https://news.ycombinator.com/item?id=1&id=2", "Hacker News"))

    def test_cli_report_and_input_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dest = Path(tmp) / "input.json", Path(tmp) / "report.json"
            content = json.dumps([discussion("https://github.com/a/b/issues/1")])
            src.write_text(content)
            script = str(Path(gravity.__file__))
            result = subprocess.run([sys.executable, script, str(src), str(dest)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(dest.read_text())["opportunities"][0]["discussion_count"], 1)
            result = subprocess.run([sys.executable, script, str(src), str(src)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(src.read_text(), content)

    def test_evidence_deduplication_and_source_validation(self):
        rows = gravity.opportunities([
            discussion("https://github.com/a/b/issues/1"),
            discussion("https://github.com/a/b/issues/1#comment"),
            discussion("https://evil.example/a"),
            discussion("https://github.com.evil.example/a"),
            discussion("https://serverfault.com/questions/1", "Server Fault"),
        ])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["discussion_count"], 2)
        self.assertEqual(rows[0]["score_components"]["source_diversity"], 10)
        self.assertEqual(rows[0]["status"], "needs_review")

    def test_noise_and_irrelevant_evidence_are_excluded(self):
        self.assertEqual(gravity.opportunities([
            dict(discussion("https://github.com/a/b/issues/1"), title="Bump OpenSSL MLKEM nginx"),
            dict(discussion("https://github.com/a/b/issues/2"), title="How to configure nginx?", text="TLS"),
        ]), [])

    def test_ranking_is_bounded_and_hn_ids_remain_distinct(self):
        rows = gravity.opportunities([
            discussion(f"https://news.ycombinator.com/item?id={i}", "Hacker News") for i in range(1, 21)
        ])
        self.assertEqual(rows[0]["discussion_count"], 20)
        self.assertLessEqual(rows[0]["score"], 100)


if __name__ == "__main__":
    unittest.main()
