"""Concurrency regression test for og_image.cached_png (multiple threads inside one worker PID)."""
from concurrent.futures import ThreadPoolExecutor
import os
import tempfile
import unittest

import og_image


class _FakeImage:
    def save(self, fp, fmt="PNG", optimize=True):
        with open(fp, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\nfake-png-data")


class OgCacheConcurrencyTest(unittest.TestCase):
    def test_concurrent_threads_do_not_collide_on_tmp_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            key = "v1|site|go.link|B|False|False|2026-11-24"
            with ThreadPoolExecutor(max_workers=8) as pool:
                paths = list(pool.map(lambda _: og_image.cached_png(tmpdir, key, _FakeImage), range(16)))
            self.assertEqual(len(set(paths)), 1)
            self.assertTrue(os.path.exists(paths[0]))
            leftover = [name for name in os.listdir(tmpdir) if name.endswith(".tmp")]
            self.assertEqual(leftover, [])


if __name__ == "__main__":
    unittest.main()
