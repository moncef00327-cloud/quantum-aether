"""يشغّل اختبارات إضافة WordPress (بايثون يستدعي PHP) إن كان PHP مثبّتاً."""
import os
import shutil
import subprocess
import unittest

HERE = os.path.dirname(__file__)
PLUGIN = os.path.join(HERE, "..", "wordpress-plugin")


@unittest.skipUnless(shutil.which("php"), "php not installed")
class WordPressPluginTest(unittest.TestCase):
    def test_php_syntax(self):
        for root, _, files in os.walk(os.path.join(PLUGIN, "quantum-ready")):
            for name in files:
                if name.endswith(".php"):
                    r = subprocess.run(["php", "-l", os.path.join(root, name)], capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_plugin_behaviour(self):
        r = subprocess.run(["php", os.path.join(PLUGIN, "tests", "run-tests.php")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 failed", r.stdout)


if __name__ == "__main__":
    unittest.main()
