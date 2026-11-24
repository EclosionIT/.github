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

    def test_github_revert_button(self):
        self.assertTrue(pr_title.is_valid('Revert "fix(eclo_nomina): intereses de cesantías"'))
        self.assertTrue(pr_title.is_valid('Revert "Revert "feat: portal""'))
        for title in ('Revert "Update README.md"', 'Revert "Feat: x"', "Revert fix: x", 'Revert ""'):
            with self.subTest(title=title):
                self.assertFalse(pr_title.is_valid(title))

    def test_merges_between_series(self):
        for title in (
            "Merge 19.0 into 20.0",
            "Merge branch '19.0' into 20.0",
            "Merge branch '19.0' into '20.0'",
            "Merge branch 19.0 into 20.0",
        ):
            with self.subTest(title=title):
                self.assertTrue(pr_title.is_valid(title))
        for title in (
            "Merge main into 20.0",
            "Merge branch 'feat/x' into 20.0",
            "Merge 19.0 into 20.0 and more",
            "merge 19.0 into 20.0",
        ):
            with self.subTest(title=title):
                self.assertFalse(pr_title.is_valid(title))

    def test_capitalised_type_is_still_rejected(self):
        self.assertFalse(pr_title.is_valid("Feat: algo"))
        self.assertFalse(pr_title.is_valid("Feat(eclo): algo"))

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
