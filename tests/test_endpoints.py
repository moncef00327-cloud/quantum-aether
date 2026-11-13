"""Every public address of a domain is probed (not only the first), and disagreement between them is reported."""
import shutil
import socket
import tempfile
import unittest
from unittest import mock

import i18n
import monitor
import quantum_saas_app
import quantum_vuln_scanner as qs
from tests.test_app import RESULT

PQ_KX = {"version": "TLSv1.3", "group": "X25519MLKEM768", "pq": True, "hrr": False, "pq_hello_ok": True,
         "cipher": "TLS_AES_128_GCM_SHA256", "kx": "TLS1.3", "error": None}
CL_KX = dict(PQ_KX, group="x25519", pq=False)
CERT = {"verified": True, "days_left": 60, "key_algorithm": "ECDSA", "key_bits": 256, "negotiated_version": "TLSv1.3"}


def addrinfo(*ips):
    return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in ips]


class ResolveTests(unittest.TestCase):
    def test_all_public_addresses_ipv4_first_deduplicated_and_capped(self):
        ips = ["2606:4700::1", "104.16.1.1", "104.16.1.1"] + [f"104.16.2.{i}" for i in range(1, 10)]
        with mock.patch("socket.getaddrinfo", return_value=addrinfo(*ips)):
            got = qs.resolve_public_ips("example.com")
        self.assertEqual(got[0], "104.16.1.1")
        self.assertEqual(len(got), len(set(got)))
        self.assertLessEqual(len(got), qs.MAX_ENDPOINTS)
        self.assertIn("2606:4700::1", got)  # one IPv6 address is kept even when IPv4 fills the cap

    def test_private_address_anywhere_still_rejects_domain(self):
        with mock.patch("socket.getaddrinfo", return_value=addrinfo("104.16.1.1", "10.0.0.1")):
            with self.assertRaises(qs.ScanError):
                qs.resolve_public_ips("example.com")


class ScanEndpointsTests(unittest.TestCase):
    def run_scan(self, kx_by_ip, all_endpoints=True):
        ips = list(kx_by_ip)

        def probe(ip, host, timeout=qs.TIMEOUT):
            value = kx_by_ip[ip]
            if isinstance(value, Exception):
                raise value
            return dict(value)

        with mock.patch("socket.getaddrinfo", return_value=addrinfo(*ips)), \
                mock.patch.object(qs, "probe_key_exchange", side_effect=probe), \
                mock.patch.object(qs, "probe_certificate", return_value=dict(CERT)):
            return qs.scan("example.com", all_endpoints=all_endpoints)

    def test_single_mode_unchanged_for_tracker(self):
        r = self.run_scan({"104.16.1.1": PQ_KX, "104.16.1.2": CL_KX}, all_endpoints=False)
        self.assertNotIn("endpoints", r)
        self.assertEqual(r["grade"], "A")

    def test_consistent_endpoints(self):
        r = self.run_scan({"104.16.1.1": PQ_KX, "104.16.1.2": PQ_KX, "2606:4700::1": PQ_KX})
        s = r["endpoint_summary"]
        self.assertEqual((s["total"], s["pq"], s["classical"], s["mixed"]), (3, 3, 0, False))
        self.assertEqual([e["family"] for e in r["endpoints"]], [4, 4, 6])
        self.assertNotIn("ENDPOINTS_MIXED", [f["code"] for f in r["findings"]])
        self.assertEqual(r["grade"], "A")

    def test_mixed_endpoints_add_a_warning_but_keep_primary_grade(self):
        r = self.run_scan({"104.16.1.1": PQ_KX, "104.16.1.2": CL_KX, "104.16.1.3": PQ_KX})
        s = r["endpoint_summary"]
        self.assertEqual((s["total"], s["pq"], s["classical"], s["mixed"]), (3, 2, 1, True))
        f = next(f for f in r["findings"] if f["code"] == "ENDPOINTS_MIXED")
        self.assertEqual(f["status"], "warning")
        self.assertEqual(f["params"], {"pq": 2, "total": 3, "ips": "104.16.1.2"})
        self.assertEqual(r["grade"], "A")
        for lang in ("en", "ar"):
            title, detail = i18n.finding_text(f, lang)
            self.assertIn("2", title)
            self.assertIn("104.16.1.2", detail)

    def test_unreachable_extra_endpoint_is_reported_not_fatal(self):
        r = self.run_scan({"104.16.1.1": PQ_KX, "104.16.1.2": dict(PQ_KX, error="timed out", group=None, pq=None)})
        s = r["endpoint_summary"]
        self.assertEqual((s["total"], s["pq"], s["failed"], s["mixed"]), (2, 1, 1, False))

    def test_probe_exception_on_extra_endpoint_is_caught(self):
        r = self.run_scan({"104.16.1.1": CL_KX, "104.16.1.2": OSError("refused")})
        self.assertEqual(r["endpoint_summary"]["failed"], 1)
        self.assertEqual(r["endpoints"][1]["error"], "refused")


class MonitorAndPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @staticmethod
    def result(mixed):
        eps = [{"ip": "104.16.1.1", "family": 4, "group": "X25519MLKEM768", "pq": True, "version": "TLSv1.3", "error": None, "undetermined": False},
               {"ip": "104.16.1.2", "family": 4, "group": "x25519" if mixed else "X25519MLKEM768", "pq": not mixed,
                "version": "TLSv1.3", "error": None, "undetermined": False}]
        r = dict(RESULT, grade="A", key_exchange=dict(RESULT["key_exchange"], pq=True, group="X25519MLKEM768"))
        r["endpoints"] = eps
        r["endpoint_summary"] = qs.endpoint_summary(eps)
        return r

    def test_monitor_alerts_when_endpoints_start_to_disagree(self):
        prev = {"grade": "A", "pq": 1, "days_left": 60, "error": None, "result": self.result(False)}
        kinds = [k for k, _ in monitor.diff(prev, self.result(True))]
        self.assertEqual(kinds, ["ENDPOINTS_MIXED"])
        params = dict(monitor.diff(prev, self.result(True)))["ENDPOINTS_MIXED"]
        for lang in ("en", "ar", "de"):
            self.assertIn("104.16.1.2", monitor.alert_text({"domain": "x.com", "kind": "ENDPOINTS_MIXED", "params": params}, lang))
        # still mixed next day: no repeat
        self.assertEqual(monitor.diff(dict(prev, result=self.result(True)), self.result(True)), [])

    def test_result_page_lists_endpoints(self):
        app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp}, scanner=lambda raw: self.result(True))
        client = app.test_client()
        sid = client.post("/api/scan", json={"domain": "example.com"}).get_json()["scan_id"]
        page = client.get(f"/scan/{sid}?lang=en").get_data(as_text=True)
        self.assertIn("104.16.1.2", page)
        self.assertIn("1 of 2", page)

    def test_tracker_job_uses_single_endpoint_scanner(self):
        import adoption_job
        self.assertIs(adoption_job.tracker_scanner(quantum_vuln_scanner_full()), qs.scan)


def quantum_vuln_scanner_full():
    return qs.scan_full


if __name__ == "__main__":
    unittest.main()
