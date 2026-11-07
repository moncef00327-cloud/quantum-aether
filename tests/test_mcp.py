import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp"))
from quantum_aether_mcp import core  # noqa: E402


class McpCoreTest(unittest.TestCase):
    def test_describe_safe_site_has_no_upsell(self):
        msg = core.describe({"domain": "safe.example", "grade": "A", "key_exchange_group": "X25519MLKEM768",
                             "post_quantum_key_exchange": True, "scan_url": "https://ather-quatum.cloud/scan/x"})
        self.assertIn("already negotiates post-quantum", msg)
        self.assertIn("not a comprehensive security assessment", msg)
        self.assertIn("Re-check periodically", msg)
        self.assertNotIn("$49", msg)        # لا بيع لموقع آمن
        self.assertNotIn("$29", msg)

    def test_describe_vulnerable_site_states_problem_and_solution(self):
        msg = core.describe({"domain": "weak.example", "grade": "B", "key_exchange_group": "x25519",
                             "post_quantum_key_exchange": False, "scan_url": "https://ather-quatum.cloud/scan/y",
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


if __name__ == "__main__":
    unittest.main()
