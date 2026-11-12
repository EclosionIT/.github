"""Static checks of the Odoo modules of a repository. No Odoo needed; runs in seconds.

Errors (fail the job): manifest that is not a literal dict, missing 'name', 'depends' that is not a list,
files listed in data/demo that do not exist, Python that does not compile, malformed XML.
Warnings: manifest version that does not start with the Odoo version of the repository.

Usage: python3 odoo_checks.py <repo_root> <odoo_version>
"""

import csv
import os
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from odoo_modules import find_modules, read_manifest  # noqa: E402

errors = 0


def annotate(level, path, message):
    global errors
    if level == "error":
        errors += 1
    print(f"::{level} file={os.path.relpath(path)}::{message}")


def check_module(name, module_dir, odoo_version):
    manifest_path = os.path.join(module_dir, "__manifest__.py")
    try:
        manifest = read_manifest(module_dir)
    except (ValueError, SyntaxError) as exc:
        annotate("error", manifest_path, f"{name}: __manifest__.py is not a literal dict ({exc})")
        return
    if not manifest.get("name"):
        annotate("error", manifest_path, f"{name}: the manifest has no 'name'")
    depends = manifest.get("depends", [])
    if not isinstance(depends, list) or not all(isinstance(dep, str) for dep in depends):
        annotate("error", manifest_path, f"{name}: 'depends' must be a list of module names")
    version = str(manifest.get("version", ""))
    if version.count(".") >= 3 and not version.startswith(odoo_version + "."):
        annotate("warning", manifest_path, f"{name}: version {version} does not start with {odoo_version}")
    for key in ("data", "demo"):
        for relative in manifest.get(key, []) or []:
            if not os.path.isfile(os.path.join(module_dir, relative)):
                annotate("error", manifest_path, f"{name}: '{key}' lists {relative}, which does not exist")

    for current, dirs, files in os.walk(module_dir):
        # static/description (app store page) and static/lib (vendored libraries) are never loaded as data.
        relative_dir = "/" + os.path.relpath(current, module_dir).replace(os.sep, "/") + "/"
        if "/static/description/" in relative_dir or "/static/lib/" in relative_dir:
            dirs[:] = []
            continue
        for filename in files:
            path = os.path.join(current, filename)
            if filename.endswith(".py"):
                try:
                    with open(path, "rb") as handle:
                        compile(handle.read(), path, "exec")
                except (SyntaxError, ValueError) as exc:
                    annotate("error", path, f"Python does not compile: {exc}")
            elif filename.endswith(".xml"):
                try:
                    ET.parse(path)
                except ET.ParseError as exc:
                    annotate("error", path, f"malformed XML: {exc}")
            elif filename.endswith(".csv"):
                try:
                    with open(path, newline="", encoding="utf-8") as handle:
                        list(csv.reader(handle))
                except (csv.Error, UnicodeDecodeError) as exc:
                    annotate("warning", path, f"CSV could not be read: {exc}")


def main():
    root, odoo_version = sys.argv[1], sys.argv[2]
    modules = find_modules(root)
    print(f"{len(modules)} module(s) found")
    for name, module_dir in sorted(modules.items()):
        check_module(name, module_dir, odoo_version)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"### Static checks (Odoo {odoo_version})\n\n{len(modules)} module(s), {errors} error(s).\n")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
