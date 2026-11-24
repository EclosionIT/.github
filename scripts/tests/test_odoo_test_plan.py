"""Unit tests of the SKIP_MODULES option of odoo_test_plan.py."""

import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "odoo_test_plan.py")


class TestPlanSkipTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        for name in ("eclo_a", "eclo_b", "eclo_c"):
            os.makedirs(os.path.join(self.tmp.name, "repo", name))
            with open(os.path.join(self.tmp.name, "repo", name, "__manifest__.py"), "w") as handle:
                handle.write('{"name": "%s", "depends": []}' % name)
        self.output = os.path.join(self.tmp.name, "out")

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, skip=None):
        env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_STEP_SUMMARY", "SKIP_MODULES")}
        env["GITHUB_OUTPUT"] = self.output
        if skip is not None:
            env["SKIP_MODULES"] = skip
        open(self.output, "w").close()
        subprocess.run([sys.executable, SCRIPT, os.path.join(self.tmp.name, "repo"), ""],
                       check=True, capture_output=True, env=env)
        with open(self.output) as handle:
            return dict(line.split("=", 1) for line in handle.read().splitlines())

    def test_without_skip_tests_every_module(self):
        self.assertEqual(self.plan()["modules"], "eclo_a,eclo_b,eclo_c")

    def test_skip_accepts_commas_and_spaces(self):
        self.assertEqual(self.plan("eclo_a, eclo_c")["modules"], "eclo_b")
        self.assertEqual(self.plan("eclo_b eclo_unknown")["modules"], "eclo_a,eclo_c")


if __name__ == "__main__":
    unittest.main()
