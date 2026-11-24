"""Check that a pull request title follows Conventional Commits: `type(scope)!: description`.

The title is read from the PR_TITLE environment variable (never interpolated into the shell).
Usage: PR_TITLE="fix(eclo_nomina): ..." python3 pr_title.py [--types feat,fix,...]
"""

import argparse
import os
import re
import sys

DEFAULT_TYPES = ("feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert")


def is_valid(title, types=DEFAULT_TYPES):
    pattern = r"(?:%s)(?:\([^()\s][^()]*\))?!?: \S.*" % "|".join(re.escape(t) for t in types)
    return re.fullmatch(pattern, title.strip()) is not None


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
