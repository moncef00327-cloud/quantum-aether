import io
import json
import os
import re
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))
from quantum_aether_mcp import core  # noqa: E402


class McpCoreTest(unittest.TestCase):
    def test_describe_safe_site_has_no_upsell(self):
        msg = core.describe({"domain": "safe.example", "grade": "A", "key_exchange_group": "X25519MLKEM768",
                             "post_quantum_key_exchange": True, "scan_url": "https://ather-quantum.com/scan/x"})
        self.assertIn("already negotiates post-quantum", msg)
        self.assertIn("not a comprehensive security assessment", msg)
        self.assertIn("Re-check periodically", msg)
        self.assertNotIn("$49", msg)        # لا بيع لموقع آمن
        self.assertNotIn("$29", msg)

    def test_describe_vulnerable_site_states_problem_and_solution(self):
        msg = core.describe({"domain": "weak.example", "grade": "B", "key_exchange_group": "x25519",
                             "post_quantum_key_exchange": False, "scan_url": "https://ather-quantum.com/scan/y",
                             "full_report_price": {"amount": "49.00", "currency": "USD"}})
        self.assertIn("harvest now, decrypt later", msg)
        self.assertIn("classical key exchange was observed", msg)
        self.assertIn("NIST standardized ML-KEM", msg)
        self.assertIn("Problem:", msg)
        self.assertIn("Solution:", msg)
        self.assertIn("$49", msg)
        self.assertIn("$29/month", msg)
        self.assertIn("scan/y", msg)

    def test_describe_handles_scan_error(self):
        self.assertIn("Scan failed", core.describe({"error": "invalid_domain", "message": "bad domain"}))

    def test_describe_undetermined_never_calls_it_classical_or_promotes_purchase(self):
        msg = core.describe({'domain': 'unknown.example', 'observation_status': 'undetermined',
                             'post_quantum_key_exchange': False})
        self.assertIn('undetermined', msg)
        self.assertNotIn('classical key exchange', msg)
        self.assertNotIn('$49', msg)

    def test_consent_is_required_for_purchase_and_monitoring(self):
        self.assertEqual(core.prepare_report_purchase("s1", False)["error"], "consent_required")
        self.assertEqual(core.start_monitoring("a@b.co", "starter", False)["error"], "consent_required")

    def test_base_url_override(self):
        os.environ["QUANTUM_AETHER_BASE"] = "https://example.test/"
        try:
            self.assertEqual(core.base_url(), "https://example.test")
        finally:
            del os.environ["QUANTUM_AETHER_BASE"]


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class McpCoreHttpTest(unittest.TestCase):
    def _urlopen(self, body=b"{}", exc=None):
        calls = []

        def fake(req, timeout=None):
            calls.append(req)
            if exc is not None:
                raise exc
            return _Response(body)
        return mock.patch.object(core.urllib.request, "urlopen", side_effect=fake), calls

    def test_network_failure_returns_error_instead_of_raising(self):
        patcher, _ = self._urlopen(exc=urllib.error.URLError("Name or service not known"))
        with patcher:
            result = core.scan("example.com")
        self.assertEqual(result["error"], "network_error")
        self.assertIn("Name or service not known", result["message"])
        self.assertIn("Scan failed", core.describe(result))

    def test_timeout_returns_error_instead_of_raising(self):
        patcher, _ = self._urlopen(exc=TimeoutError("timed out"))
        with patcher:
            self.assertEqual(core.get_scan("s1")["error"], "network_error")

    def test_non_json_response_is_reported(self):
        patcher, _ = self._urlopen(body=b"<html>bad gateway</html>")
        with patcher:
            self.assertEqual(core.scan("example.com")["error"], "invalid_response")

    def test_http_error_keeps_api_json_or_falls_back_to_status(self):
        err = urllib.error.HTTPError("u", 404, "nf", {}, io.BytesIO(b'{"error": "scan_not_found"}'))
        patcher, _ = self._urlopen(exc=err)
        with patcher:
            self.assertEqual(core.get_scan("missing")["error"], "scan_not_found")
        err = urllib.error.HTTPError("u", 502, "bg", {}, io.BytesIO(b"<html>"))
        patcher, _ = self._urlopen(exc=err)
        with patcher:
            self.assertEqual(core.order_status("o1")["error"], "http_502")

    def test_ids_and_domain_are_path_encoded(self):
        patcher, calls = self._urlopen(body=b'{"scan_id": "x"}')
        with patcher:
            core.get_scan("../admin?x=1")
            core.order_status("o/1")
            core.scan("example.com/../x")
        urls = [c.full_url for c in calls]
        self.assertTrue(urls[0].endswith("/api/scan/..%2Fadmin%3Fx%3D1"))
        self.assertTrue(urls[1].endswith("/api/v1/orders/o%2F1"))
        self.assertTrue(urls[2].endswith("/api/v1/scan?domain=example.com%2F..%2Fx"))
        self.assertTrue(all(c.get_header("User-agent") == f"quantum-aether-mcp/{core.__version__}" for c in calls))

    def test_empty_inputs_never_hit_the_network(self):
        patcher, calls = self._urlopen()
        with patcher:
            self.assertEqual(core.scan("  ")["error"], "invalid_domain")
            self.assertEqual(core.get_scan("")["error"], "scan_id_required")
            self.assertEqual(core.order_status(None)["error"], "order_id_required")
            self.assertEqual(core.prepare_report_purchase("", True)["error"], "scan_id_required")
            self.assertEqual(core.start_monitoring("a@b.co", "gold", True)["error"], "invalid_plan")
        self.assertEqual(calls, [])

    def test_purchase_posts_json_with_consent(self):
        patcher, calls = self._urlopen(body=b'{"order_id": "O1"}')
        with patcher:
            self.assertEqual(core.prepare_report_purchase("s1", True)["order_id"], "O1")
        self.assertEqual(calls[0].get_method(), "POST")
        self.assertEqual(json.loads(calls[0].data), {"scan_id": "s1", "consent_immediate_delivery": True})


class McpPackageMetadataTest(unittest.TestCase):
    ROOT = os.path.join(os.path.dirname(__file__), "..", "mcp")

    def test_versions_agree(self):
        with open(os.path.join(self.ROOT, "pyproject.toml"), encoding="utf-8") as f:
            pyproject = re.search(r'^version = "([^"]+)"', f.read(), re.M).group(1)
        with open(os.path.join(self.ROOT, "server.json"), encoding="utf-8") as f:
            server = json.load(f)
        self.assertEqual(core.__version__, pyproject)
        self.assertEqual(server["packages"][0]["version"], pyproject)


if __name__ == "__main__":
    unittest.main()
