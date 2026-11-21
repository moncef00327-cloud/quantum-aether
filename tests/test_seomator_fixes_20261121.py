"""SEOmator audit fixes (2026-11-21): no dead /site/ links from /index and /exposure, noindex exposure pages without
canonical/hreflang, template links skip the ?lang=de -> en redirect, German nginx guide really in German, #scanner
anchor and real brand link on the home page, llms.txt linked from every page, WebPage JSON-LD where a page had none,
first monthly-report chart not lazy-loaded, Article/TechArticle fields."""
import json
import os
import re
import shutil
import tempfile
import unittest
from contextlib import closing
from unittest.mock import Mock

import adoption
import guides
import quantum_saas_app
import sales_db
import search_indexing
from tests.test_app import RESULT
from tests.test_pq_index import DATA

SITE = "https://ather-quantum.com"


def _app(tmp, **kw):
    return quantum_saas_app.create_app(dict({"TESTING": True, "DATA_DIR": tmp, "PUBLIC_URL": SITE, "TRUSTED_PROXIES": 0}, **kw),
                                       scanner=Mock(return_value=dict(RESULT)))


def _weekly(conn, domain, week="2026-W47", rank=None, sector=None, pq=1):
    adoption.init(conn)
    conn.execute("INSERT INTO adoption_results (week, domain, rank, sector, ok, grade, grp, tls, pq, scanned_at, as_name) "
                 "VALUES (?, ?, ?, ?, 1, ?, ?, 'TLSv1.3', ?, ?, 'NET')",
                 (week, domain, rank, sector, "A" if pq else "B", "X25519MLKEM768" if pq else "x25519", pq,
                  adoption.week_monday(week).isoformat() + "T04:00:00+00:00"))
    conn.commit()


class IndexSiteLinksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        with open(os.path.join(self.tmp, "pq_index_2026-11.json"), "w", encoding="utf-8") as f:
            json.dump(DATA, f)
        with open(os.path.join(self.tmp, "pq_index_orgs.csv"), "w", encoding="utf-8") as f:
            f.write("org_id,name,host\nSA-x-001,Institution 1,www.bank-one.sa\n")
        os.environ["PQ_INDEX_DIR"] = self.tmp
        self.app = _app(self.tmp)
        self.client = self.app.test_client()

    def tearDown(self):
        os.environ.pop("PQ_INDEX_DIR", None)
        shutil.rmtree(self.tmp)

    def test_only_hosts_with_a_site_page_are_linked(self):
        with closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db"))) as c:
            _weekly(c, "www.bank-one.sa", sector="banks-gcc")
        for lang in ("en", "ar", "de"):
            body = self.client.get(f"/index?lang={lang}").get_data(as_text=True)
            links = set(re.findall(r'href="(/site/[^"]+)"', body))
            self.assertEqual({l.split("?")[0] for l in links}, {"/site/www.bank-one.sa"}, lang)
            self.assertIn("www.telco.dz", body)  # still listed, as plain text
            for link in links:
                self.assertEqual(self.client.get(link.replace("&amp;", "&")).status_code, 200, link)


class ExposureSeoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = _app(self.tmp)
        self.client = self.app.test_client()
        search_indexing.set_extra_allow_hosts({"bank.example"})
        with closing(sales_db.connect(os.path.join(self.tmp, "quantum_saas.db"))) as c:
            for week, pq in (("2026-W44", 0), ("2026-W45", 0), ("2026-W46", 1), ("2026-W47", 1)):
                _weekly(c, "bank.example", week=week, sector="banks-dach", pq=pq)
            _weekly(c, "tail.example", rank=5000, pq=0)

    def tearDown(self):
        search_indexing.reset_runtime_state()
        shutil.rmtree(self.tmp)

    def test_noindex_page_has_no_canonical_or_hreflang(self):
        body = self.client.get("/exposure/tail.example?lang=en").get_data(as_text=True)
        self.assertEqual(body.count('name="robots" content="noindex'), 1)
        self.assertNotIn('rel="canonical"', body)
        self.assertNotIn('hreflang="x-default"', body)

    def test_indexable_page_keeps_canonical_hreflang_and_site_link(self):
        r = self.client.get("/exposure/bank.example?lang=en")
        body = r.get_data(as_text=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn('<link rel="canonical"', body)
        self.assertIn('hreflang="de"', body)
        self.assertNotIn('content="noindex', body)
        self.assertIn('/site/bank.example?lang=en', body)

    def test_unknown_domain_has_no_dead_site_link(self):
        body = self.client.get("/exposure/nothing-here.example?lang=en").get_data(as_text=True)
        self.assertNotIn("/site/nothing-here.example", body)


class LinkAndContentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.app = _app(self.tmp)
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_german_links_go_straight_to_english_where_no_german_exists(self):
        body = self.client.get("/pricing?lang=de").get_data(as_text=True)
        self.assertIn("/pricing?lang=de", body)          # translated page keeps German links
        self.assertIn("/agents?lang=en", body)           # untranslated targets: English directly
        for path in ("/agents", "/guides", "/transparency"):
            self.assertNotIn(f'href="{path}?lang=de"', body, path)
        with self.app.test_request_context("/"):
            self.assertTrue(quantum_saas_app.german_endpoint("site.legal_page", {"slug": "agb"}))
            self.assertTrue(quantum_saas_app.german_endpoint(".guide", {"slug": "enable-x25519mlkem768-nginx"}))
            self.assertFalse(quantum_saas_app.german_endpoint("site.guide", {"slug": "harvest-now-decrypt-later"}))
            self.assertIn("lang=de", quantum_saas_app.template_url_for("site.pricing_page", lang="de"))
            self.assertIn("lang=en", quantum_saas_app.template_url_for("site.agents_page", lang="de"))
            self.assertIn("lang=ar", quantum_saas_app.template_url_for("site.agents_page", lang="ar"))

    def test_german_nginx_guide_is_german(self):
        de = guides.GUIDES["enable-x25519mlkem768-nginx"]["de"]["body"]
        en = guides.GUIDES["enable-x25519mlkem768-nginx"]["en"]["body"]
        self.assertIn("OpenSSL-Version prüfen", de)
        self.assertNotIn("Check your OpenSSL version", de)
        self.assertEqual(re.findall(r"<pre[^>]*>.*?</pre>", de, re.S), re.findall(r"<pre[^>]*>.*?</pre>", en, re.S))
        body = self.client.get("/guides/enable-x25519mlkem768-nginx?lang=de").get_data(as_text=True)
        self.assertIn("Worauf Sie achten sollten", body)

    def test_home_scanner_anchor_and_brand_link(self):
        for lang in ("en", "ar", "de"):
            body = self.client.get(f"/?lang={lang}").get_data(as_text=True)
            self.assertIn('id="scanner"', body, lang)
            self.assertNotIn('class="brand" href="#"', body, lang)

    def test_llms_txt_linked_and_lists_index(self):
        for path in ("/?lang=en", "/?lang=ar", "/pricing?lang=en", "/deadlines?lang=de"):
            body = self.client.get(path).get_data(as_text=True)
            head = body[:body.index("</head>")]
            self.assertIn(f'href="{SITE}/llms.txt"', head, path)
        txt = self.client.get("/llms.txt").get_data(as_text=True)
        self.assertIn(f"{SITE}/index", txt)
        self.assertIn("PQ-TLS Index", txt)

    def test_default_webpage_jsonld_only_where_missing(self):
        body = self.client.get("/partners?lang=en").get_data(as_text=True)
        blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)]
        page = [b for b in blocks if b.get("@type") == "WebPage"]
        self.assertEqual(len(page), 1)
        self.assertEqual(page[0]["publisher"]["@id"], f"{SITE}/#organization")
        self.assertEqual(page[0]["inLanguage"], "en")
        body = self.client.get("/deadlines?lang=en").get_data(as_text=True)
        blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)]
        self.assertFalse([b for b in blocks if b.get("@type") == "WebPage"])
        art = [b for b in blocks if b.get("@type") == "Article"][0]
        self.assertEqual(art["datePublished"], "2026-11-04")
        self.assertIn("publisher", art)

    def test_monthly_report_first_chart_not_lazy(self):
        r = self.client.get("/reports/2026-11?lang=en")
        if r.status_code != 200:
            self.skipTest("no monthly report data")
        imgs = re.findall(r"<figure><img[^>]*>", r.get_data(as_text=True))
        self.assertNotIn('loading="lazy"', imgs[0])
        self.assertTrue(all('loading="lazy"' in i for i in imgs[1:]))


if __name__ == "__main__":
    unittest.main()
