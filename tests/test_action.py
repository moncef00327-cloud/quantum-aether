import importlib.util
import os
import tempfile
import unittest
import urllib.error

_spec = importlib.util.spec_from_file_location(
    "qa_action_scan", os.path.join(os.path.dirname(__file__), "..", "github-action", "scan.py"))
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)

PQ = {"domain": "good.example", "grade": "A", "key_exchange_group": "X25519MLKEM768",
      "post_quantum_key_exchange": True, "scan_url": "https://ather-quatum.cloud/scan/a"}
CLASSIC = {"domain": "old.example", "grade": "B", "key_exchange_group": "x25519",
           "post_quantum_key_exchange": False, "scan_url": "https://ather-quatum.cloud/scan/b"}


class ActionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.out = os.path.join(self.tmp, "out")
        self.summary = os.path.join(self.tmp, "summary")
        self.env = {"GITHUB_OUTPUT": self.out, "GITHUB_STEP_SUMMARY": self.summary,
                    "INPUT_DOMAIN": "x.example", "INPUT_REQUIRE_PQ": "false", "INPUT_MIN_GRADE": ""}
        self._saved = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def run_with(self, status, data, **inputs):
        for k, v in inputs.items():
            os.environ[k] = v
        return scan.main(fetcher=lambda base, domain: (status, data))

    def test_pass_writes_outputs_and_summary(self):
        self.assertEqual(self.run_with(200, PQ), 0)
        out = open(self.out).read()
        self.assertIn("grade=A", out)
        self.assertIn("post-quantum=true", out)
        self.assertIn("X25519MLKEM768", open(self.summary).read())

    def test_classical_site_passes_unless_required(self):
        self.assertEqual(self.run_with(200, CLASSIC), 0)
        self.assertIn("harvest now, decrypt later", open(self.summary).read())
        self.assertEqual(self.run_with(200, CLASSIC, INPUT_REQUIRE_PQ="true"), 1)

    def test_min_grade(self):
        self.assertEqual(self.run_with(200, CLASSIC, INPUT_MIN_GRADE="A"), 1)
        self.assertEqual(self.run_with(200, CLASSIC, INPUT_MIN_GRADE="B"), 0)

    def test_service_problems_never_break_the_deploy(self):
        self.assertEqual(self.run_with(429, {"error": "rate_limited"}, INPUT_REQUIRE_PQ="true"), 1)
        self.assertEqual(self.run_with(502, {}, INPUT_REQUIRE_PQ="true"), 1)
        self.assertEqual(self.run_with(500, {}, INPUT_REQUIRE_PQ="true"), 1)
        self.assertEqual(self.run_with(200, {}, INPUT_REQUIRE_PQ="true"), 1)

        def down(base, domain):
            raise urllib.error.URLError("connection refused")
        os.environ["INPUT_REQUIRE_PQ"] = "true"
        self.assertEqual(scan.main(fetcher=down), 1)

    def test_invalid_domain_fails(self):
        self.assertEqual(self.run_with(400, {"error": "invalid_domain", "message": "bad"}), 1)
        os.environ["INPUT_DOMAIN"] = ""
        self.assertEqual(scan.main(fetcher=lambda b, d: (200, PQ)), 1)


if __name__ == "__main__":
    unittest.main()
