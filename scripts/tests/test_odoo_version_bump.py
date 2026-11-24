"""Unit tests of odoo_version_bump.py on throwaway git repositories.

Run from the repository root: python3 -m unittest discover -s scripts/tests -v
"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import odoo_version_bump as bump  # noqa: E402

GIT_ENV = {
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}


def manifest(version, name="Module"):
    return f'{{"name": "{name}", "version": "{version}", "depends": ["base"], "license": "OPL-1"}}\n'


class Repo:
    """A git repository with a `base` branch and a `pr` branch created from it."""

    def __init__(self, path):
        self.path = path
        self.git("init", "-q", "-b", "base")

    def git(self, *args):
        env = dict(os.environ, **GIT_ENV)
        subprocess.run(["git", "-C", self.path, *args], check=True, capture_output=True, env=env)

    def write(self, relative, text):
        full = os.path.join(self.path, relative)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)

    def remove(self, relative):
        self.git("rm", "-q", "-r", relative)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)


class VersionBumpTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Repo(self.tmp.name)
        self.repo.write("eclo_a/__manifest__.py", manifest("20.0.1.0.0"))
        self.repo.write("eclo_a/models/a.py", "A = 1\n")
        self.repo.write("eclo_b/__manifest__.py", manifest("20.0.2.3.4"))
        self.repo.write("eclo_b/models/b.py", "B = 1\n")
        self.repo.write("README.md", "# repo\n")
        self.repo.commit("base")
        self.repo.git("checkout", "-q", "-b", "pr")

    def tearDown(self):
        self.tmp.cleanup()

    def run_check(self, series="20.0", **kwargs):
        self.repo.commit("pr")
        return bump.check(self.tmp.name, "base", "pr", series, **kwargs)

    def messages(self, errors):
        return " | ".join(message for _path, message in errors)

    # --- cases asked for -------------------------------------------------------------------------------

    def test_new_module_with_valid_version_passes(self):
        self.repo.write("eclo_new/__manifest__.py", manifest("20.0.1.0.0"))
        self.repo.write("eclo_new/__init__.py", "")
        errors, report = self.run_check()
        self.assertEqual(errors, [])
        self.assertIn("| `eclo_new` | new | 20.0.1.0.0 | ok |", report)

    def test_new_module_with_wrong_series_fails(self):
        self.repo.write("eclo_new/__manifest__.py", manifest("19.0.1.0.0"))
        errors, _report = self.run_check()
        self.assertEqual([path for path, _m in errors], ["eclo_new/__manifest__.py"])
        self.assertIn("must be 20.0.x.y.z", self.messages(errors))

    def test_change_without_bump_fails(self):
        self.repo.write("eclo_a/models/a.py", "A = 2\n")
        errors, report = self.run_check()
        self.assertEqual([path for path, _m in errors], ["eclo_a/__manifest__.py"])
        self.assertIn("must be greater than 20.0.1.0.0", self.messages(errors))
        self.assertIn("eclo_a/models/a.py", self.messages(errors))
        self.assertIn("| `eclo_a` | 20.0.1.0.0 | 20.0.1.0.0 | not bumped |", report)

    def test_correct_bump_passes(self):
        self.repo.write("eclo_a/models/a.py", "A = 2\n")
        self.repo.write("eclo_a/__manifest__.py", manifest("20.0.1.0.1"))
        errors, report = self.run_check()
        self.assertEqual(errors, [])
        self.assertIn("| `eclo_a` | 20.0.1.0.0 | 20.0.1.0.1 | ok |", report)

    def test_bump_with_wrong_series_fails(self):
        self.repo.write("eclo_a/models/a.py", "A = 2\n")
        self.repo.write("eclo_a/__manifest__.py", manifest("19.0.1.0.1"))
        errors, _report = self.run_check()
        self.assertIn("version '19.0.1.0.1' must be 20.0.x.y.z", self.messages(errors))

    # --- other rules -----------------------------------------------------------------------------------

    def test_versions_compare_as_numbers_not_text(self):
        self.repo.write("eclo_a/__manifest__.py", manifest("20.0.1.0.9"))
        self.repo.commit("9")
        self.repo.git("checkout", "-q", "base")
        self.repo.git("merge", "-q", "pr")
        self.repo.git("checkout", "-q", "-b", "pr2")
        self.repo.write("eclo_a/__manifest__.py", manifest("20.0.1.0.10"))
        self.repo.commit("10")
        errors, _report = bump.check(self.tmp.name, "base", "pr2", "20.0")
        self.assertEqual(errors, [])

    def test_lower_version_fails(self):
        self.repo.write("eclo_b/__manifest__.py", manifest("20.0.2.3.3"))
        errors, _report = self.run_check()
        self.assertIn("must be greater than 20.0.2.3.4", self.messages(errors))

    def test_short_version_fails(self):
        self.repo.write("eclo_a/__manifest__.py", manifest("1.0.1"))
        errors, _report = self.run_check()
        self.assertIn("must be 20.0.x.y.z", self.messages(errors))

    def test_port_from_previous_series_counts_as_bump(self):
        self.repo.write("eclo_b/__manifest__.py", manifest("19.0.2.3.4"))
        self.repo.commit("old series on base")
        self.repo.git("checkout", "-q", "base")
        self.repo.git("merge", "-q", "pr")
        self.repo.git("checkout", "-q", "-b", "pr2")
        self.repo.write("eclo_b/__manifest__.py", manifest("20.0.1.0.0"))
        self.repo.commit("port")
        errors, _report = bump.check(self.tmp.name, "base", "pr2", "20.0")
        self.assertEqual(errors, [])

    def test_untouched_modules_and_root_files_are_not_checked(self):
        self.repo.write("README.md", "# repo, changed\n")
        errors, report = self.run_check()
        self.assertEqual((errors, report), ([], []))

    def test_docs_and_tests_only_do_not_need_a_bump(self):
        self.repo.write("eclo_a/README.md", "doc\n")
        self.repo.write("eclo_a/tests/test_a.py", "X = 1\n")
        self.repo.write("eclo_a/static/description/index.html", "<p/>\n")
        errors, report = self.run_check()
        self.assertEqual((errors, report), ([], []))

    def test_empty_ignore_requires_a_bump_for_any_file(self):
        self.repo.write("eclo_a/README.md", "doc\n")
        errors, _report = self.run_check(ignore=())
        self.assertIn("eclo_a", self.messages(errors))

    def test_deleted_module_is_ignored(self):
        self.repo.remove("eclo_b")
        errors, report = self.run_check()
        self.assertEqual(errors, [])
        self.assertIn("| `eclo_b` | deleted | | ok |", report)

    def test_manifest_that_is_not_a_literal_fails(self):
        self.repo.write("eclo_a/__manifest__.py", "dict(name='x')\n")
        errors, _report = self.run_check()
        self.assertIn("not a literal dict", self.messages(errors))

    def test_compares_with_the_merge_base(self):
        # The base branch moves on after the PR branched: its new bump of eclo_b must not count.
        self.repo.write("eclo_a/models/a.py", "A = 2\n")
        self.repo.write("eclo_a/__manifest__.py", manifest("20.0.1.0.1"))
        self.repo.commit("pr")
        self.repo.git("checkout", "-q", "base")
        self.repo.write("eclo_b/__manifest__.py", manifest("20.0.9.0.0"))
        self.repo.commit("base moves")
        errors, report = bump.check(self.tmp.name, "base", "pr", "20.0")
        self.assertEqual(errors, [])
        self.assertEqual(len(report), 1)

    def test_paths_with_spaces_and_accents(self):
        self.repo.write("eclo_a/data/datos de nómina.xml", "<odoo/>\n")
        errors, _report = self.run_check()
        self.assertIn("datos de nómina.xml", self.messages(errors))

    def test_main_exit_code_and_annotations(self):
        self.repo.write("eclo_a/models/a.py", "A = 2\n")
        self.repo.commit("pr")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = bump.main(["--repo", self.tmp.name, "--base", "base", "--head", "pr", "--series", "20.0"])
        self.assertEqual(code, 1)
        self.assertIn("::error file=eclo_a/__manifest__.py::", out.getvalue())


class ParseTest(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(bump.parse_version("20.0.1.2.3", "20.0"), (20, 0, 1, 2, 3))
        self.assertIsNone(bump.parse_version("20.0.1.2", "20.0"))
        self.assertIsNone(bump.parse_version("20.0.1.2.x", "20.0"))
        self.assertIsNone(bump.parse_version("200.0.1.2.3", "20.0"))
        self.assertIsNone(bump.parse_version("saas~20.1.1.0.0", "20.0"))


if __name__ == "__main__":
    unittest.main()
