"""Module discovery shared by the Odoo CI scripts.

A module is a directory with a __manifest__.py. Modules nested inside another module are ignored (Odoo
does not load them). The addons paths of a repository are the parent directories of its modules.
"""

import ast
import os

SKIP_DIRS = {".git", ".github", "node_modules", "__pycache__", "enterprise", "setup"}


def find_modules(root):
    """Return {module_name: module_dir} for every top-level Odoo module under root."""
    modules = {}
    for current, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        if "__manifest__.py" in files:
            modules.setdefault(os.path.basename(current), current)
            dirs[:] = []  # nothing inside a module is another module
    return modules


def addons_paths(modules):
    """Parent directories of the modules, sorted, absolute."""
    return sorted({os.path.abspath(os.path.dirname(path)) for path in modules.values()})


def read_manifest(module_dir):
    """Parse __manifest__.py as a Python literal. Raises ValueError/SyntaxError when it is not one."""
    with open(os.path.join(module_dir, "__manifest__.py"), encoding="utf-8") as handle:
        manifest = ast.literal_eval(handle.read())
    if not isinstance(manifest, dict):
        raise ValueError("the manifest is not a dict")
    return manifest
