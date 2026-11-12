"""tools/build_audit.py: priority ranking and report rendering (no network, no Chromium)."""
import importlib.util
import os
import unittest

spec = importlib.util.spec_from_file_location(
    "build_audit", os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "build_audit.py"))
build_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_audit)

RESULT = {"source": "crt.sh", "names": 5, "responding": 4, "pq": 1, "not_pq": 2, "unknown": 1, "hosts": [
    {"host": "news.bank.example", "status": "not_pq", "version": "TLSv1.3", "group": "x25519", "network": "Hetzner"},
    {"host": "efxauth.bank.example", "status": "not_pq", "version": "TLSv1.2", "group": "secp256r1",
     "network": "Amazon.com, Inc."},
    {"host": "fw.bank.example", "status": "unknown", "version": None, "group": None, "network": "x"},
    {"host": "www.bank.example", "status": "pq", "version": "TLSv1.3", "group": "X25519MLKEM768", "network": "x"}]}


class BuildAuditTests(unittest.TestCase):
    def test_priority(self):
        p = build_audit.priority
        self.assertEqual(p("efxauth.bank.example", "bank.example"), "high")
        self.assertEqual(p("id.bank.example", "bank.example"), "high")
        self.assertEqual(p("ciamselfservice.bank.example", "bank.example"), "high")
        self.assertEqual(p("news.bank.example", "bank.example"), "normal")
        self.assertEqual(p("idea.bank.example", "bank.example"), "normal")  # "id" only as a whole label

    def test_render_orders_high_first_and_links_network_guide(self):
        for lang in ("en", "de"):
            page = build_audit.render("bank.example", "Bank <AG>", lang, RESULT, "2026-11-12 10:00 UTC")
            self.assertLess(page.index("efxauth.bank.example"), page.index("news.bank.example"))
            self.assertIn("/guides/aws-alb-cloudfront-post-quantum-tls", page)
            self.assertIn("Bank &lt;AG&gt;", page)
            self.assertIn("2024/1774", page)
            self.assertIn("fw.bank.example", page)


if __name__ == "__main__":
    unittest.main()
