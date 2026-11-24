"""Check that a pull request title follows Conventional Commits: `type(scope)!: description`.

Also accepted: the title of GitHub's Revert button (`Revert "<valid title>"`) and merges between Odoo
series (`Merge 19.0 into 20.0`, `Merge branch '19.0' into 20.0`).
The title is read from the PR_TITLE environment variable (never interpolated into the shell).
Usage: PR_TITLE="fix(eclo_nomina): ..." python3 pr_title.py [--types feat,fix,...]
"""

import argparse
import os
import re
import sys

DEFAULT_TYPES = ("feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert")


SERIES_MERGE = re.compile(r"Merge (?:branch )?('?)\d+\.0\1 into ('?)\d+\.0\2")
REVERT = re.compile(r'Revert "(.+)"')


def is_valid(title, types=DEFAULT_TYPES):
    title = title.strip()
    revert = REVERT.fullmatch(title)
    if revert:
        return is_valid(revert.group(1), types)
    if SERIES_MERGE.fullmatch(title):
        return True
    pattern = r"(?:%s)(?:\([^()\s][^()]*\))?!?: \S.*" % "|".join(re.escape(t) for t in types)
    return re.fullmatch(pattern, title) is not None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--types", default=",".join(DEFAULT_TYPES))
    args = parser.parse_args(argv)
    types = tuple(t.strip() for t in args.types.split(",") if t.strip())
    title = os.environ.get("PR_TITLE", "")
    if is_valid(title, types):
        print(f"PR title OK: {title}")
        return 0
    print(
        "::error::The pull request title must follow Conventional Commits, "
        f"'type(scope): description' with type in {', '.join(types)} "
        "(e.g. 'fix(eclo_nomina): intereses de cesantías proporcionales a los días'). "
        f"Got: {title!r}"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
