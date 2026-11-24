"""Check that every Odoo module touched by a pull request bumps its manifest version.

Odoo.sh only runs the update of a module (data, views, migrations) when the version in its
__manifest__.py goes up, so a pull request that changes a module must:

  - declare a version of the form <series>.x.y.z (e.g. 20.0.1.2.3 on the 20.0 branch), and
  - raise it compared with the base branch (compared as numbers, not as text).

A module that does not exist on the base branch (new module) only needs a valid version. A module that the
pull request deletes is ignored. Changes that never need an update (documentation, the app store page and
tests by default; see --ignore) do not count as touching the module.

Usage:
  python3 odoo_version_bump.py --repo <path> --base <ref> --head <ref> --series 20.0 [--ignore GLOB ...]

The base and head refs must exist in the repository (check out with fetch-depth: 0). The comparison is made
against the merge base of base and head, as GitHub shows the pull request. Exit code 1 when a module fails;
errors are printed as GitHub annotations and summarised in $GITHUB_STEP_SUMMARY.
"""

import argparse
import ast
import fnmatch
import os
import re
import subprocess
import sys

DEFAULT_IGNORE = ("*.md", "*.rst", "static/description/*", "tests/*")


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", repo, *args], check=True, capture_output=True, text=True
    ).stdout


def file_at(repo, ref, path):
    """Content of path at ref, or None when it does not exist there."""
    result = subprocess.run(
        ["git", "-C", repo, "show", f"{ref}:{path}"], capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else None


def manifest_version(text):
    """Version of a manifest given as text. Raises ValueError when it is not a literal dict."""
    try:
        manifest = ast.literal_eval(text)
    except (SyntaxError, ValueError) as exc:
        reason = exc.msg if isinstance(exc, SyntaxError) else "it calls or names something"
        raise ValueError(f"__manifest__.py is not a literal dict ({reason})") from exc
    if not isinstance(manifest, dict):
        raise ValueError("__manifest__.py is not a dict")
    return str(manifest.get("version", ""))


def parse_version(version, series):
    """Tuple of ints of a <series>.x.y.z version, or None when it does not have that form."""
    if not re.fullmatch(re.escape(series) + r"\.\d+\.\d+\.\d+", version):
        return None
    return tuple(int(part) for part in version.split("."))


def as_numbers(version):
    """Numeric tuple of any dotted version, for the comparison with the base ('' -> ())."""
    parts = []
    for part in version.split("."):
        if not part.isdigit():
            break
        parts.append(int(part))
    return tuple(parts)


def module_of(path, manifests):
    """Directory of the module that contains path (deepest manifest wins), or None."""
    best = None
    for module_dir in manifests:
        prefix = module_dir + "/" if module_dir else ""
        if path.startswith(prefix) and (best is None or len(module_dir) > len(best)):
            best = module_dir
    return best


def is_ignored(relative, patterns):
    return any(fnmatch.fnmatch(relative, pattern) for pattern in patterns)


def touched_modules(repo, base, head, ignore):
    """{module_dir: [changed files]} of the modules touched between the merge base and head."""
    # -z: paths verbatim (no quoting of spaces or non-ASCII names). --no-renames: a file moved from one
    # module to another lists both paths, so the module it left is checked too.
    diff = git(repo, "diff", "-z", "--no-renames", "--name-only", f"{base}...{head}")
    changed = [p for p in diff.split("\0") if p]
    manifests = set()
    for ref in (base, head):
        for path in git(repo, "ls-tree", "-r", "-z", "--name-only", ref).split("\0"):
            if path == "__manifest__.py" or path.endswith("/__manifest__.py"):
                manifests.add(os.path.dirname(path))
    touched = {}
    for path in changed:
        module_dir = module_of(path, manifests)
        if module_dir is None:
            continue
        relative = path[len(module_dir) + 1:] if module_dir else path
        if relative != "__manifest__.py" and is_ignored(relative, ignore):
            continue
        touched.setdefault(module_dir, []).append(path)
    return touched


def check(repo, base, head, series, ignore=DEFAULT_IGNORE):
    """List of (manifest_path, message) errors and list of report lines."""
    merge_base = git(repo, "merge-base", base, head).strip()
    errors, report = [], []
    for module_dir, files in sorted(touched_modules(repo, merge_base, head, ignore).items()):
        name = os.path.basename(module_dir) or "."
        manifest_path = os.path.join(module_dir, "__manifest__.py") if module_dir else "__manifest__.py"
        head_text = file_at(repo, head, manifest_path)
        if head_text is None:
            report.append(f"| `{name}` | deleted | | ok |")
            continue
        try:
            new = manifest_version(head_text)
        except ValueError as exc:
            errors.append((manifest_path, f"{name}: {exc}"))
            report.append(f"| `{name}` | ? | ? | error |")
            continue
        base_text = file_at(repo, merge_base, manifest_path)
        old = None
        if base_text is not None:
            try:
                old = manifest_version(base_text)
            except ValueError:
                old = ""  # unreadable at the base: any valid version counts as a bump
        if parse_version(new, series) is None:
            errors.append((
                manifest_path,
                f"{name}: version '{new}' must be {series}.x.y.z (the series of this branch)",
            ))
            report.append(f"| `{name}` | {old or 'new'} | {new} | wrong series/format |")
            continue
        if old is not None and as_numbers(new) <= as_numbers(old):
            errors.append((
                manifest_path,
                f"{name}: version {new} must be greater than {old} on the base branch "
                f"(Odoo.sh only updates a module when its version goes up); "
                f"changed: {', '.join(files[:5])}{' ...' if len(files) > 5 else ''}",
            ))
            report.append(f"| `{name}` | {old} | {new} | not bumped |")
            continue
        report.append(f"| `{name}` | {old if old is not None else 'new'} | {new} | ok |")
    return errors, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--series", required=True, help="Odoo series of the branch, e.g. 20.0")
    parser.add_argument(
        "--ignore", action="append", default=None,
        help="glob, relative to the module, of files that do not need a bump (repeatable; "
             f"default: {' '.join(DEFAULT_IGNORE)}; pass --ignore '' to require a bump for every file)",
    )
    args = parser.parse_args(argv)
    ignore = DEFAULT_IGNORE if args.ignore is None else tuple(p for p in args.ignore if p)
    errors, report = check(args.repo, args.base, args.head, args.series, ignore)
    for path, message in errors:
        print(f"::error file={path}::{message}")
    text = f"### Module versions (Odoo {args.series})\n\n"
    if report:
        text += "| Module | Base | Pull request | Result |\n|---|---|---|---|\n" + "\n".join(report) + "\n"
    else:
        text += "The pull request does not touch any module.\n"
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
