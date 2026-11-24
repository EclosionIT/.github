"""Unit tests of pr_title.py. Run: python3 -m unittest discover -s scripts/tests -v"""

import contextlib
import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pr_title  # noqa: E402


class PrTitleTest(unittest.TestCase):
    def test_valid_titles(self):
        for title in (
            "fix(eclo_nomina): intereses de cesantías proporcionales a los días",
            "feat: portal de autogestión",
            "feat(eclo_a, eclo_b)!: cambio que rompe",
            "chore(deps): bump actions/checkout",
            "refactor(eclo_nomina/models): separar cálculos",
        ):
            with self.subTest(title=title):
                self.assertTrue(pr_title.is_valid(title))

    def test_invalid_titles(self):
        for title in (
            "",
            "Update README.md",
            "fix:no space",
            "fix(): empty scope",
            "Fix(eclo): capitalised type",
            "feature(eclo): unknown type",
            "fix(eclo) missing colon",
        ):
            with self.subTest(title=title):
                self.assertFalse(pr_title.is_valid(title))

    def test_custom_types(self):
        self.assertTrue(pr_title.is_valid("mig(eclo): x", ("mig",)))
        self.assertFalse(pr_title.is_valid("feat(eclo): x", ("mig",)))

    def test_main_reads_the_environment(self):
        for title, code in (("fix: a", 0), ("$(touch /tmp/x)", 1)):
            out = io.StringIO()
            with mock.patch.dict(os.environ, {"PR_TITLE": title}), contextlib.redirect_stdout(out):
                self.assertEqual(pr_title.main([]), code)


if __name__ == "__main__":
    unittest.main()
