"""Decide which modules of the repository can be installed and tested in CI.

A module is testable when it is installable and every module in its dependency tree exists in the addons
paths (Odoo core, the repository and, when available, Enterprise). The others are skipped with the missing
modules listed, so a module that needs Enterprise does not break CI when there is no Enterprise access.

Usage: python3 odoo_test_plan.py <repo_root> <extra_addons_path>[,<extra_addons_path>...]
Writes `modules` (comma separated) and `addons_path` to $GITHUB_OUTPUT and a report to the step summary.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from odoo_modules import addons_paths, find_modules, read_manifest  # noqa: E402


def available_modules(paths):
    found = {}
    for path in paths:
        if not os.path.isdir(path):
            continue
        for entry in sorted(os.listdir(path)):
            module_dir = os.path.join(path, entry)
            if os.path.isfile(os.path.join(module_dir, "__manifest__.py")):
                found.setdefault(entry, module_dir)
    return found


def main():
    root = sys.argv[1]
    extra = [path for path in sys.argv[2].split(",") if path]
    repo_modules = find_modules(root)
    repo_paths = addons_paths(repo_modules)
    available = available_modules(extra + repo_paths)

    manifests = {}

    def manifest(name):
        if name not in manifests:
            try:
                manifests[name] = read_manifest(available[name])
            except (ValueError, SyntaxError, OSError):
                manifests[name] = None
        return manifests[name]

    def missing_dependencies(name, seen):
        if name in seen:
            return set()
        seen.add(name)
        if name not in available:
            return {name}
        data = manifest(name)
        if data is None:
            return {f"{name} (unreadable manifest)"}
        missing = set()
        for dependency in data.get("depends", []) or []:
            missing |= missing_dependencies(dependency, seen)
        return missing

    testable, skipped = [], []
    for name in sorted(repo_modules):
        data = manifest(name)
        if data is None or not data.get("installable", True):
            skipped.append((name, "not installable"))
            continue
        missing = missing_dependencies(name, set())
        if missing:
            skipped.append((name, "missing: " + ", ".join(sorted(missing))))
        else:
            testable.append(name)

    addons_path = ",".join(extra + repo_paths)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"modules={','.join(testable)}\naddons_path={addons_path}\n")
    report = [f"### Odoo test plan\n\n{len(testable)} module(s) to install and test, {len(skipped)} skipped.\n"]
    if testable:
        report.append("\n**Tested:** " + ", ".join(f"`{name}`" for name in testable) + "\n")
    if skipped:
        report.append("\n| Skipped module | Reason |\n|---|---|\n")
        report.extend(f"| `{name}` | {reason} |\n" for name, reason in skipped)
    text = "".join(report)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text)


if __name__ == "__main__":
    main()
