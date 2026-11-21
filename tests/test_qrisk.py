import copy
import json
import unittest
from contextlib import closing

import i18n
import qrisk
import sales_db
from tests.test_app import RESULT, AppTestCase

PQ = copy.deepcopy(RESULT)
PQ["key_exchange"].update(group="X25519MLKEM768", pq=True)
PQ["grade"] = "A"


class ScoreTests(unittest.TestCase):
    def codes(self, s):
        return {i["code"]: i["points"] for i in s["items"]}

    def test_classical_tls13(self):
        s = qrisk.score(RESULT)
        self.assertEqual(s["score"], 70)
        self.assertEqual(s["band"], "high")
        self.assertEqual(self.codes(s), {"kx_classical": 60, "cert_classical": 10})
        self.assertFalse(s["hosts_checked"])

    def test_tls12_scores_higher_than_classical_tls13(self):
        r = copy.deepcopy(RESULT)
        r["key_exchange"]["version"] = "TLSv1.2"
        r["certificate"]["negotiated_version"] = "TLSv1.2"
        self.assertEqual(qrisk.score(r)["score"], 80)

    def test_pq_only_unavoidable_certificate_point(self):
        s = qrisk.score(PQ, {"classical": []})
        self.assertEqual((s["score"], s["band"]), (10, "low"))
        self.assertTrue(s["hosts_checked"])

    def test_classical_subdomains_capped(self):
        hosts = [f"{p}.example.com" for p in ("www", "api", "mail", "auth", "login")]
        s = qrisk.score(PQ, {"classical": hosts})
        self.assertEqual(self.codes(s)["hosts_classical"], 20)
        self.assertEqual(s["score"], 30)
        self.assertEqual(s["band"], "moderate")

    def test_mixed_endpoints(self):
        r = dict(PQ, endpoint_summary={"mixed": True, "pq": 1, "total": 2})
        self.assertEqual(self.codes(qrisk.score(r))["endpoints_mixed"], 30)

    def test_never_exceeds_100(self):
        r = copy.deepcopy(RESULT)
        r["key_exchange"]["version"] = "TLSv1.2"
        r["certificate"]["negotiated_version"] = "TLSv1.2"
        s = qrisk.score(r, {"classical": ["a.x", "b.x", "c.x", "d.x", "e.x"]})
        self.assertEqual(s["score"], 100)

    def test_undetermined_has_no_number(self):
        r = copy.deepcopy(RESULT)
        r["key_exchange"] = {"error": "reset", "group": None, "pq": False}
        r["certificate"]["negotiated_version"] = "TLSv1.3"
        s = qrisk.score(r)
        self.assertIsNone(s["score"])
        self.assertEqual(s["band"], "undetermined")

    def test_every_item_code_translated_with_its_params(self):
        for lang in ("en", "ar", "de"):
            t = i18n.TEXTS[lang]
            self.assertEqual(set(t["qes_items"]), {"kx_tls12", "kx_classical", "endpoints_mixed", "hosts_classical", "cert_classical"})
            self.assertEqual(set(t["qes_bands"]), {"low", "moderate", "high"})


class CbomTests(unittest.TestCase):
    def test_cyclonedx_shape(self):
        doc = qrisk.cbom(PQ, {"classical": ["mail.example.com"]})
        self.assertEqual((doc["bomFormat"], doc["specVersion"]), ("CycloneDX", "1.6"))
        refs = {c["bom-ref"] for c in doc["components"]}
        self.assertTrue({"protocol-tls", "kx-x25519mlkem768", "cert-key", "certificate"} <= refs)
        kx = next(c for c in doc["components"] if c["bom-ref"] == "kx-x25519mlkem768")
        self.assertEqual(kx["cryptoProperties"]["algorithmProperties"]["primitive"], "kem")
        self.assertEqual(kx["cryptoProperties"]["algorithmProperties"]["nistQuantumSecurityLevel"], 3)
        props = {p["name"]: p["value"] for p in doc["metadata"]["properties"]}
        self.assertEqual(props["quantum-aether:exposure-score"], "15")
        self.assertIn("mail.example.com", json.dumps(doc))
        self.assertEqual(doc["dependencies"][0]["dependsOn"], [c["bom-ref"] for c in doc["components"]])

    def test_classical_key_agreement_level_zero(self):
        doc = qrisk.cbom(RESULT)
        kx = next(c for c in doc["components"] if c["bom-ref"] == "kx-x25519")
        self.assertEqual(kx["cryptoProperties"]["algorithmProperties"]["nistQuantumSecurityLevel"], 0)


class PageTests(AppTestCase):
    def test_result_page_shows_score_and_paid_cta(self):
        sid = self.scan()["scan_id"]
        for lang, word in (("en", "Quantum exposure score"), ("ar", "درجة التعرّض الكمّي")):
            html = self.client.get(f"/scan/{sid}?lang={lang}").get_data(as_text=True)
            self.assertIn(word, html)
            self.assertIn("<strong>70</strong>/100", html)
            self.assertIn('data-ev="qes_buy"', html)

    def test_insights_api_returns_rendered_score(self):
        sid = self.scan()["scan_id"]
        d = self.client.post(f"/api/scan/{sid}/insights?lang=en").get_json()
        self.assertEqual(d["state"], "done")
        self.assertIn("Quantum exposure score", d["exposure_html"])
        self.assertNotIn("Checking www/api", d["exposure_html"])

    def test_cbom_only_after_payment(self):
        sid = self.scan()["scan_id"]
        with closing(sales_db.connect(f"{self.data_dir}/quantum_saas.db")) as conn:
            token = sales_db.get_scan(conn, sid)["report_token"]
        self.assertEqual(self.client.get(f"/report/{token}/cbom.json").status_code, 404)
        report_url = self.pay(sid).get_json()["report_url"]
        page = self.client.get(report_url).get_data(as_text=True)
        self.assertIn("cbom.json", page)
        res = self.client.get(report_url.split("?")[0] + "/cbom.json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["bomFormat"], "CycloneDX")
        self.assertIn("attachment", res.headers["Content-Disposition"])

    def test_sample_cbom_public(self):
        self.assertIn("cbom.json", self.client.get("/sample-report").get_data(as_text=True))
        res = self.client.get("/sample-report/cbom.json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["specVersion"], "1.6")


if __name__ == "__main__":
    unittest.main()
