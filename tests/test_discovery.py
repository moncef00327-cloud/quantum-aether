import re
import shutil
import tempfile
import unittest

import discovery
import quantum_saas_app
import sales_db


class _Resp:
    def __init__(self, data, fail=False):
        self.data, self.fail = data, fail

    def raise_for_status(self):
        if self.fail:
            raise RuntimeError("502 Bad Gateway")

    def json(self):
        return self.data


NAMES = ["www.example.com", "old.example.com", "fw.example.com", "dead.example.com", "skip.example.com", "*.example.com"]


class FakeHTTP:
    def __init__(self, crtsh_fail=False, certspotter_fail=False):
        self.crtsh_fail, self.certspotter_fail = crtsh_fail, certspotter_fail

    def get(self, url, params=None, timeout=None, headers=None):
        if "crt.sh" in url:
            return _Resp([{"name_value": "\n".join(NAMES), "common_name": "example.com"}], self.crtsh_fail)
        return _Resp([{"dns_names": NAMES}], self.certspotter_fail)


def fake_probe(host):
    if host.startswith("dead."):
        return None
    status = {"old": "not_pq", "fw": "unknown"}.get(host.split(".")[0], "pq")
    return {"host": host, "status": status, "group": "X25519MLKEM768" if status == "pq" else None, "version": "TLSv1.3"}


class FakeMailer:
    enabled = True

    def __init__(self):
        self.sent = []

    def send(self, to, subject, text, html=None):
        self.sent.append((to, subject, text))
        return True


class DiscoveryUnitTests(unittest.TestCase):
    def test_base_domain_and_email_match(self):
        self.assertEqual(discovery.base_domain("www.dkb.de"), "dkb.de")
        self.assertEqual(discovery.base_domain("www.de"), "www.de")
        self.assertTrue(discovery.email_matches("a@dkb.de", "dkb.de"))
        self.assertTrue(discovery.email_matches("a@dkb.de", "business.dkb.de"))
        self.assertTrue(discovery.email_matches("a@mail.dkb.de", "dkb.de"))
        self.assertFalse(discovery.email_matches("a@gmail.com", "dkb.de"))
        self.assertFalse(discovery.email_matches("a@notdkb.de", "dkb.de"))

    def test_clean_drops_wildcards_and_foreign_names(self):
        self.assertEqual(discovery._clean(["*.dkb.de", "API.dkb.de.", "evil.com", "x.notdkb.de", "dkb.de"], "dkb.de"),
                         {"api.dkb.de", "dkb.de"})

    def test_falls_back_to_certspotter_and_respects_optout(self):
        http = FakeHTTP(crtsh_fail=True)
        result = discovery.run_discovery("example.com", http, probe=fake_probe, optout={"skip.example.com"})
        self.assertEqual(result["source"], "certspotter")
        hosts = [h["host"] for h in result["hosts"]]
        self.assertNotIn("skip.example.com", hosts)
        self.assertNotIn("dead.example.com", hosts)
        self.assertEqual(hosts[0], "old.example.com")  # not-PQ first
        self.assertEqual((result["pq"], result["not_pq"], result["unknown"]), (1, 1, 1))


class DiscoveryFlowTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.mailer = FakeMailer()
        self.app = quantum_saas_app.create_app(
            {"DATA_DIR": self.dir, "TESTING": True, "TRUSTED_PROXIES": 0, "OWNER_EMAIL": "owner@example.org"},
            scanner=lambda raw: dict(_result(), domain=raw), mailer=self.mailer,
            discovery_http=FakeHTTP(), discovery_probe=fake_probe)
        self.client = self.app.test_client()
        self.scan_id = self.client.post("/api/scan", json={"domain": "www.example.com"}).get_json()["scan_id"]

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_public_numbers_only_then_private_list_after_confirmation(self):
        page = self.client.get(f"/scan/{self.scan_id}?lang=en").get_data(as_text=True)
        self.assertIn('id="discovery"', page)
        start = self.client.post(f"/api/discovery/{self.scan_id}")
        self.assertEqual(start.status_code, 200)
        data = start.get_json()
        self.assertEqual((data["status"], data["base"], data["responding"], data["not_pq"]), ("DONE", "example.com", 5, 1))  # www, old, fw, skip + apex (dead excluded)
        self.assertNotIn("old.example.com", start.get_data(as_text=True))  # names never in public API
        self.assertEqual(self.client.post(f"/api/discovery/{self.scan_id}").get_json()["state"], "cached")

        wrong = self.client.post("/discovery/request", data={"scan_id": self.scan_id, "email": "me@gmail.com", "consent": "1"})
        self.assertEqual(wrong.status_code, 400)
        self.assertEqual(self.mailer.sent, [])
        ok = self.client.post("/discovery/request?lang=en",
                              data={"scan_id": self.scan_id, "email": "it@example.com", "consent": "1"})
        self.assertEqual(ok.status_code, 200)
        to, subject, text = self.mailer.sent[-1]
        self.assertEqual(to, "it@example.com")
        link = re.search(r"https?://\S+/discovery/list/\S+", text).group(0)
        path = link.split("://", 1)[1].split("/", 1)[1]

        prompt = self.client.get("/" + path)  # link scanners only see a button
        self.assertNotIn("old.example.com", prompt.get_data(as_text=True))
        self.assertIn("noindex", prompt.headers.get("X-Robots-Tag", ""))
        listing = self.client.post("/" + path)
        body = listing.get_data(as_text=True)
        self.assertIn("old.example.com", body)
        self.assertIn("no-store", listing.headers.get("Cache-Control", ""))
        self.assertEqual(self.mailer.sent[-1][0], "owner@example.org")  # lead notification
        self.assertIn("old.example.com", self.client.get("/" + path).get_data(as_text=True))

    def test_consent_required_and_rate_limit(self):
        self.client.post(f"/api/discovery/{self.scan_id}")
        r = self.client.post("/discovery/request", data={"scan_id": self.scan_id, "email": "it@example.com"})
        self.assertEqual(r.status_code, 400)
        conn = sales_db.connect(self.dir + "/quantum_saas.db")
        try:
            for _ in range(discovery.RUNS_PER_CLIENT_PER_DAY):
                conn.execute("INSERT INTO discovery_runs VALUES ('x', strftime('%Y-%m-%dT%H:%M:%SZ','now'))")
            conn.commit()
            self.assertEqual(discovery.start(conn, "other.example", "x"), "rate_limited")
        finally:
            conn.close()

    def test_failed_ct_lookup_is_reported(self):
        self.app.extensions["discovery_http"] = FakeHTTP(crtsh_fail=True, certspotter_fail=True)
        self.assertEqual(self.client.post(f"/api/discovery/{self.scan_id}").get_json()["status"], "FAILED")


def _result():
    return {"domain": "", "ip": "93.184.215.14", "port": 443, "scanned_at": "2026-11-10T10:00:00+00:00",
            "scanner_version": "2.0", "grade": "A", "findings": [],
            "key_exchange": {"version": "TLSv1.3", "group": "X25519MLKEM768", "pq": True, "pq_hello_ok": True, "hrr": False,
                             "cipher": "TLS_AES_128_GCM_SHA256", "kx": "TLS1.3"},
            "certificate": {"verified": True, "verify_error": None, "key_algorithm": "ECDSA", "key_bits": 256,
                            "curve": "secp256r1", "signature_algorithm": "ecdsa-with-SHA256", "subject": "x",
                            "issuer": "Test CA", "not_after": "2027-01-01T00:00:00+00:00", "days_left": 60,
                            "san_count": 1, "sans": ["x"], "negotiated_version": "TLSv1.3",
                            "negotiated_cipher": "TLS_AES_128_GCM_SHA256"}}


if __name__ == "__main__":
    unittest.main()
