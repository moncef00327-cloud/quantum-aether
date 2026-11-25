"""Tests for L1+L2 sitemap bundle caching, ETag/304 conditional requests, and DB/opt-out invalidation."""
import os
import tempfile
import unittest
from unittest import mock

import adoption
import quantum_saas_app


class SitemapCacheTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        quantum_saas_app._SITEMAP_CACHE.clear()
        self.app = quantum_saas_app.create_app({
            "TESTING": True,
            "DATA_DIR": self.tmp.name,
            "PUBLIC_URL": "https://ather-quantum.com",
            "SITEMAP_CACHE_ENABLED": True,
            "SITEMAP_CACHE_TTL": 1800,
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            conn = quantum_saas_app.db()
            adoption.init(conn)
            conn.execute(
                "INSERT INTO adoption_results (week, domain, rank, sector, ok, grade, grp, tls, pq, scanned_at, as_name) "
                "VALUES (?, ?, ?, ?, 1, 'A', 'X25519MLKEM768', 'TLSv1.3', 1, ?, 'NET')",
                ("2026-W47", "alpha.example", 1, "tech", "2026-11-24T10:00:00+00:00"),
            )
            conn.commit()

    def tearDown(self):
        quantum_saas_app._SITEMAP_CACHE.clear()
        self.tmp.cleanup()

    def test_bundle_cached_across_all_sitemap_routes_and_disk_l2(self):
        orig_build = quantum_saas_app._build_sitemap_bundle
        with mock.patch.object(quantum_saas_app, "_build_sitemap_bundle", side_effect=orig_build) as spy:
            r1 = self.client.get("/sitemap.xml")
            self.assertEqual(r1.status_code, 200)
            self.assertEqual(r1.mimetype, "application/xml")
            self.assertIn("public, max-age=1800", r1.headers.get("Cache-Control", ""))
            self.assertTrue(r1.headers.get("ETag"))
            self.assertEqual(spy.call_count, 1)

            # All child sitemaps served from the same L1 bundle without rebuilding
            for path in ("/sitemap-pages.xml", "/sitemap-sites-1.xml", "/sitemap-exposure-1.xml"):
                rc = self.client.get(path)
                self.assertEqual(rc.status_code, 200, path)
                self.assertEqual(rc.mimetype, "application/xml")
                self.assertTrue(rc.headers.get("ETag"))
            self.assertEqual(spy.call_count, 1)

            # Out-of-range chunk returns 404 without rebuilding
            self.assertEqual(self.client.get("/sitemap-sites-99.xml").status_code, 404)
            self.assertEqual(self.client.get("/sitemap-exposure-99.xml").status_code, 404)
            self.assertEqual(spy.call_count, 1)

            # Conditional ETag returns 304 Not Modified
            r304 = self.client.get("/sitemap.xml", headers={"If-None-Match": r1.headers["ETag"]})
            self.assertEqual(r304.status_code, 304)
            self.assertEqual(spy.call_count, 1)

            # Clear L1 (simulating another gunicorn worker / restart) -> hits L2 disk cache
            self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "sitemap_cache.json")))
            quantum_saas_app._SITEMAP_CACHE.clear()
            r2 = self.client.get("/sitemap.xml")
            self.assertEqual(r2.status_code, 200)
            self.assertEqual(r2.data, r1.data)
            self.assertEqual(spy.call_count, 1)

    def test_optout_invalidates_cache_immediately(self):
        r1 = self.client.get("/sitemap-exposure-1.xml")
        self.assertEqual(r1.status_code, 200)
        self.assertIn("alpha.example", r1.get_data(as_text=True))

        with self.app.app_context():
            conn = quantum_saas_app.db()
            conn.execute("INSERT OR IGNORE INTO adoption_optout(domain, verified_at, method) VALUES (?, ?, ?)",
                         ("alpha.example", "2026-11-25T17:00:00Z", "dns_txt"))
            conn.commit()

        r2 = self.client.get("/sitemap-exposure-1.xml")
        self.assertEqual(r2.status_code, 404)


if __name__ == "__main__":
    unittest.main()
