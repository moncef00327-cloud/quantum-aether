"""متتبّع التبنّي الأسبوعي: الزرع من الدراسة، الفحص الأسبوعي، المقارنة، والصفحة وملفات البيانات."""
import csv
import datetime as dt
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import closing

import adoption
import adoption_job
import quantum_saas_app
import quantum_vuln_scanner
import sales_db
from tests.test_app import RESULT

STUDY_DAY = dt.date(2026, 11, 3)      # يوم الدراسة المنشورة: الأسبوع 2026-W45
NEXT_MONDAY = dt.date(2026, 11, 9)    # أول فحص أسبوعي: الأسبوع 2026-W46


def result(domain, pq=True, grade=None, group=None):
    r = dict(RESULT, domain=domain, grade=grade or ("A" if pq else "B"))
    r["key_exchange"] = dict(RESULT["key_exchange"], pq=pq, group=group or ("X25519MLKEM768" if pq else "x25519"))
    return r


class WeekScanner:
    """ماسح وهمي: يعيد نتيجة الدراسة لكل نطاق، إلا ما نغيّره في overrides."""

    def __init__(self, overrides=None):
        self.study = {}
        with open(adoption.RAW_STUDY_FILE, encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                self.study[row["domain"]] = row
        self.overrides = overrides or {}
        self.calls = 0

    def __call__(self, raw):
        self.calls += 1
        domain = quantum_vuln_scanner.normalize_domain(raw)
        outcome = self.overrides.get(domain)
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is not None:
            return outcome
        row = self.study.get(domain)
        if row is None:  # نطاقات قوائم المراقبة: نعتبرها جاهزة
            return result(domain)
        if not row["ok"]:
            raise quantum_vuln_scanner.ScanError("dns_failure", "could not resolve")
        return row


class UnitTests(unittest.TestCase):
    def test_week_keys(self):
        self.assertEqual(adoption.week_of(STUDY_DAY), "2026-W45")
        self.assertEqual(adoption.week_monday("2026-W45"), dt.date(2026, 11, 2))
        self.assertEqual(adoption.week_of(dt.date(2027, 1, 1)), "2026-W53")

    def test_changes_ignore_sites_that_did_not_answer(self):
        prev = [{"domain": "a.com", "ok": 1, "pq": 0, "grade": "B", "grp": "x25519"},
                {"domain": "b.com", "ok": 1, "pq": 1, "grade": "A", "grp": "X25519MLKEM768"},
                {"domain": "c.com", "ok": 1, "pq": 1, "grade": "A", "grp": "X25519MLKEM768"},
                {"domain": "d.com", "ok": 1, "pq": 0, "grade": "B", "grp": "x25519"}]
        cur = [{"domain": "a.com", "ok": 1, "pq": 1, "grade": "A", "grp": "X25519MLKEM768"},   # انتقل
               {"domain": "b.com", "ok": 1, "pq": 0, "grade": "B", "grp": "x25519"},           # فقده
               {"domain": "c.com", "ok": 0, "pq": 0, "grade": None, "grp": None},              # لم يُجب: ليس تراجعاً
               {"domain": "d.com", "ok": 1, "pq": 0, "grade": "C", "grp": "x25519"},           # تغيّر الدرجة
               {"domain": "new.com", "ok": 1, "pq": 1, "grade": "A", "grp": "X25519MLKEM768"}]  # جديد: لا مقارنة
        diff = adoption.changes(prev, cur)
        self.assertEqual([r["domain"] for r in diff["adopted"]], ["a.com"])
        self.assertEqual(diff["adopted"][0]["grade_before"], "B")
        self.assertEqual([r["domain"] for r in diff["dropped"]], ["b.com"])
        self.assertEqual([r["domain"] for r in diff["regraded"]], ["d.com"])

    def test_targets_cover_study_and_watchlists_once(self):
        targets = adoption.load_targets()
        domains = [t["domain"] for t in targets]
        self.assertEqual(len(domains), len(set(domains)))
        self.assertEqual(sum(1 for t in targets if t["rank"]), adoption.WEEKLY_TOP)
        study = [json.loads(l)["domain"] for l in open(adoption.RAW_STUDY_FILE)]
        self.assertEqual([t["domain"] for t in targets[:1000]], study)   # الأكبر 1000 هي قائمة الدراسة نفسها
        watch = {d for s in adoption.load_watchlists().values() for d in s["domains"]}
        self.assertTrue(watch <= set(domains))
        for domain in watch:  # كل اسم في قوائم المراقبة صالح للماسح
            self.assertEqual(quantum_vuln_scanner.normalize_domain(domain), domain)

    def test_csv_export(self):
        rows = list(csv.DictReader(io.StringIO(adoption.to_csv([{"week": "2026-W45", "domain": "a.com", "ok": 1, "pq": 1}]))))
        self.assertEqual(rows[0]["domain"], "a.com")
        self.assertEqual(list(rows[0].keys()), adoption.EXPORT_FIELDS)


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.scanner = WeekScanner()
        self.app = quantum_saas_app.create_app({"TESTING": True, "DATA_DIR": self.tmp, "TRUSTED_PROXIES": 0},
                                               scanner=self.scanner)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def conn(self):
        return closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db")))

    def test_seed_matches_published_study_and_runs_once(self):
        with self.conn() as c:
            self.assertEqual(adoption.seed_from_study(c), 1000)
            self.assertEqual(adoption.seed_from_study(c), 0)
            snap = adoption.snapshot(c)
        study = quantum_saas_app.study_data()
        self.assertEqual(snap["week"], "2026-W45")
        with open(adoption.RAW_STUDY_FILE, encoding='utf-8') as source:
            rows = (json.loads(line) for line in source)
            retries = sum(bool(row.get('ok') and row.get('key_exchange', {}).get('hrr')) for row in rows)
        # Preserve the archive; the new tracker excludes retry-only evidence from its denominator.
        self.assertEqual((snap["reachable"], snap["pq"]), (study["reachable"] - retries, study["pq"]))
        self.assertIsNone(snap["changes"])

    def test_page_before_any_weekly_run(self):
        for lang in ("en", "ar", "de"):
            r = self.client.get(f"/adoption?lang={lang}")
            self.assertEqual(r.status_code, 200)
            body = r.get_data(as_text=True)
            self.assertIn("2026-W45", body)
            self.assertIn(adoption_texts(lang)["adoption_first_week"], body)
            self.assertNotIn("Traceback", body)

    def test_weekly_run_shows_who_switched_and_who_lost(self):
        # github.com كان بلا PQ في الدراسة، وgoogle.com كان معه
        self.scanner.overrides = {"github.com": result("github.com", pq=True),
                                  "google.com": result("google.com", pq=False)}
        outcome = adoption_job.run(self.app, day=NEXT_MONDAY, workers=4, asn_lookup=None)
        self.assertEqual(outcome["week"], "2026-W46")
        self.assertGreater(outcome["targets"], 1000)
        body = self.client.get("/adoption?lang=en").get_data(as_text=True)
        adopted_section = body.split("Switched to post-quantum")[1].split("Stopped negotiating")[0]
        lost_section = body.split("Stopped negotiating")[1]
        self.assertIn("github.com", adopted_section)
        self.assertNotIn("google.com", adopted_section)
        self.assertIn("google.com", lost_section.split("</table>")[0])
        self.assertIn("Watchlists", body)
        self.assertIn("www.bundesbank.de", body)
        self.assertIn("since 2026-W46", body)
        data = self.client.get("/adoption.json").get_json()
        self.assertEqual(data["week"], "2026-W46")
        self.assertEqual(data["previous_week"], "2026-W45")
        self.assertEqual([r["domain"] for r in data["changes"]["adopted"]], ["github.com"])
        self.assertEqual([r["domain"] for r in data["changes"]["dropped"]], ["google.com"])
        self.assertEqual([p["week"] for p in data["timeline"]], ["2026-W45", "2026-W46"])
        self.assertEqual(data["license"], "CC BY 4.0")

    def test_blocked_probe_is_undetermined_not_published_as_off(self):
        # Firewall resets our ClientHello, the certificate handshake still says TLS 1.3: PQ status is unknown.
        blocked = dict(RESULT, domain="www.bundesbank.de", grade="B")
        blocked["key_exchange"] = {"pq_hello_ok": False, "error": "[Errno 104] Connection reset by peer"}
        blocked["certificate"] = dict(RESULT["certificate"], negotiated_version="TLSv1.3")
        self.scanner.overrides = {"www.bundesbank.de": blocked}
        adoption_job.run(self.app, day=NEXT_MONDAY, workers=4, asn_lookup=None)
        with self.conn() as c:
            rows = adoption.rows_for(c, "2026-W46")
            snap = adoption.snapshot(c)
        row = next(r for r in rows if r["domain"] == "www.bundesbank.de")
        self.assertEqual((row["ok"], row["pq"], row["unsure"]), (1, 0, 1))
        self.assertNotIn("www.bundesbank.de", [r["domain"] for r in snap["changes"]["dropped"]])
        bank = next(sec for sec in snap["sectors"] if any(r["domain"] == "www.bundesbank.de" for r in sec["rows"]))
        self.assertEqual(bank["unsure"], 1)
        self.assertEqual(bank["reachable"], sum(1 for r in bank["rows"] if r["ok"]) - 1)
        for lang, text in (("en", "Undetermined, will be rescanned"), ("ar", "غير محسوم، يُعاد فحصه")):
            body = self.client.get(f"/adoption?lang={lang}").get_data(as_text=True)
            bank_row = body.split("www.bundesbank.de</a>")[1].split("</tr>")[0]
            self.assertIn(text, bank_row)
            self.assertNotIn(adoption_texts(lang)["adoption_status_off"], bank_row)

    def test_scanning_page(self):
        for lang in ("en", "ar", "de"):
            body = self.client.get(f"/scanning?lang={lang}").get_data(as_text=True)
            self.assertIn("95.179.195.150", body)
            self.assertIn("mailto:", body)
        self.assertIn("/scanning", self.client.get("/adoption?lang=en").get_data(as_text=True))

    def test_csv_and_discovery_files(self):
        r = self.client.get("/adoption.csv")
        self.assertEqual(r.mimetype, "text/csv")
        self.assertEqual(r.headers["Access-Control-Allow-Origin"], "*")
        rows = list(csv.DictReader(io.StringIO(r.get_data(as_text=True))))
        self.assertEqual(len(rows), 1000)
        self.assertIn("/adoption?lang=de", self.client.get("/sitemap-pages.xml").get_data(as_text=True))
        self.assertIn("/adoption#2026-W45", self.client.get("/feed.xml").get_data(as_text=True))
        self.assertIn("/adoption.json", self.client.get("/llms.txt").get_data(as_text=True))
        self.assertIn("/adoption?lang=en", self.client.get("/?lang=en").get_data(as_text=True))


class ScaleAndProviderTests(unittest.TestCase):
    def setUp(self):
        import sqlite3
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        adoption.init(self.conn)

    def lookup(self, ip):
        return {"1.1.1.1": (13335, "Cloudflare, Inc."), "2.2.2.2": (24940, "Hetzner Online GmbH")}.get(ip, (None, None))

    def test_optout_excludes_domain_and_subdomains(self):
        out = {"example.com"}
        self.assertTrue(adoption.opted_out("example.com", out))
        self.assertTrue(adoption.opted_out("www.example.com", out))
        self.assertFalse(adoption.opted_out("notexample.com", out))
        targets = adoption.load_targets(limit=50, watchlists={}, optout={"google.com"})
        self.assertNotIn("google.com", [t["domain"] for t in targets])

    def test_providers_and_top10k_tier(self):
        targets = [{"domain": f"site{i}.test", "rank": i + 1, "sector": None} for i in range(60)]
        def scanner(domain):
            i = int(domain[4:-5])
            ip = "1.1.1.1" if i % 2 == 0 else "2.2.2.2"
            return result(domain, pq=(ip == "1.1.1.1")) | {"ip": ip}
        adoption.run_week(self.conn, scanner, targets, day=NEXT_MONDAY, workers=4, asn_lookup=self.lookup)
        prov = adoption.providers(self.conn)
        by = {p["name"]: p for p in prov["rows"]}
        self.assertEqual((by["Cloudflare, Inc."]["reachable"], by["Cloudflare, Inc."]["pct"]), (30, 100.0))
        self.assertEqual((by["Hetzner Online GmbH"]["pq"], by["Hetzner Online GmbH"]["pct"]), (0, 0.0))
        self.assertFalse(prov["monthly"])
        self.assertEqual(adoption.tier_stats(adoption.rows_for(self.conn, "2026-W46"), 60)["pct"], 50.0)
        self.assertIsNone(adoption.tier_stats(adoption.rows_for(self.conn, "2026-W46"), 10000))  # لم يُفحص هذا العدد

    def test_is_unsure_only_for_unknown_group_on_tls13(self):
        self.assertTrue(adoption.is_unsure({"error": "reset"}, "TLSv1.3"))
        self.assertTrue(adoption.is_unsure({"error": "reset"}, None))
        self.assertFalse(adoption.is_unsure({"error": "reset"}, "TLSv1.2"))  # TLS 1.2 cannot do ML-KEM
        self.assertFalse(adoption.is_unsure({"group": "x25519", "pq": False}, "TLSv1.3"))
        self.assertFalse(adoption.is_unsure({"group": "X25519MLKEM768", "pq": True}, "TLSv1.3"))

    def test_monthly_run_feeds_providers_and_timeline_stays_top1000(self):
        targets = [{"domain": f"m{i}.test", "rank": 5000 + i, "sector": None} for i in range(25)]
        adoption.run_month(self.conn, lambda d: result(d, pq=True) | {"ip": "1.1.1.1"}, targets,
                           day=NEXT_MONDAY, workers=4, asn_lookup=self.lookup)
        prov = adoption.providers(self.conn)
        self.assertTrue(prov["monthly"])
        self.assertEqual(prov["period"], "2026-11")
        self.assertEqual(prov["rows"][0]["reachable"], 25)
        self.assertEqual(adoption.timeline(self.conn), [])   # الشهري لا يدخل الخط الزمني الأسبوعي

    def test_provider_names_are_readable_and_stable(self):
        import asn
        for raw, clean in (("HETZNER-AS Hetzner Online GmbH", "Hetzner Online GmbH"), ("OVH OVH SAS", "OVH SAS"),
                           ("AKAMAI-ASN1 Akamai International B.V.", "Akamai International B.V."),
                           ("Google LLC", "Google LLC"), ("CLOUDFLARENET - Cloudflare, Inc.", "Cloudflare, Inc.")):
            self.assertEqual(asn.provider_name(raw), clean)
            self.assertEqual(asn.provider_name(clean), clean)

    def test_asn_lookup(self):
        import gzip, tempfile, asn
        path = tempfile.mktemp(suffix=".tsv.gz")
        with gzip.open(path, "wt") as f:
            f.write("1.0.0.0\t1.0.0.255\t13335\tUS\tCLOUDFLARENET - Cloudflare, Inc.\n1.0.1.0\t1.0.3.255\t0\tNone\tNot routed\n")
        lookup = asn.AsnLookup(path).lookup
        self.assertEqual(lookup("1.0.0.7"), (13335, "Cloudflare, Inc."))
        self.assertEqual(lookup("1.0.2.1"), (None, None))
        self.assertEqual(lookup("not-an-ip"), (None, None))
        os.remove(path)


def adoption_texts(lang):
    import i18n
    return i18n.TEXTS[lang]
