"""Decide whether an Odoo install + test run failed, looking only at what the repository is responsible for.

Fails when:
- odoo exited with a non-zero code,
- the database could not be initialized (registry failed to load, a module could not be loaded),
- the test summary reports failed tests or errors,
- an ERROR/CRITICAL line was logged by one of the repository modules (odoo.addons.<module>...).

ERROR lines from other modules (e.g. "Error while posting demo data" in account's demo) are reported as
warnings: they are Odoo's own noise and do not depend on the repository.

Usage: python3 odoo_verdict.py <odoo.log> <exit_code> <module,module,...>
Writes a report to the step summary and exits 1 on failure.
"""

import os
import re
import sys

LINE = re.compile(r"^\d{4}-\d{2}-\d{2} [\d:,]+ \d+ (ERROR|CRITICAL) \S+ (\S+): (.*)$")
RESULT = re.compile(r"(\d+) failed, (\d+) error\(s\) of (\d+) tests")
FATAL = ("Failed to load registry", "Failed to initialize database", "Couldn't load module")


def main():
    log_path, exit_code, modules = sys.argv[1], int(sys.argv[2]), [m for m in sys.argv[3].split(",") if m]
    own_prefixes = tuple(f"odoo.addons.{module}" for module in modules)
    own, foreign, fatal = [], [], []
    failed = errors = total = 0
    with open(log_path, encoding="utf-8", errors="replace") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            result = RESULT.search(line)
            if result and "odoo.tests.result" in line:
                failed, errors, total = (int(value) for value in result.groups())
            match = LINE.match(line)
            if not match:
                continue
            logger, message = match.group(2), match.group(3)
            if any(text in message for text in FATAL) or logger in ("odoo.modules.registry", "odoo.registry",
                                                                     "odoo.service.server", "odoo.modules.module"):
                fatal.append(line)
            elif any(logger == prefix or logger.startswith(prefix + ".") for prefix in own_prefixes):
                own.append(line)
            elif logger == "odoo.tests.result":
                continue  # summarized through failed/errors
            else:
                foreign.append(line)

    failure = exit_code != 0 or fatal or failed or errors or own
    report = ["### Odoo install and tests\n\n",
              f"Exit code {exit_code} · tests: {total} run, {failed} failed, {errors} error(s).\n"]
    for title, lines in (("Fatal (installation did not finish)", fatal), ("Errors in the repository modules", own),
                         ("Errors from other modules (not counted)", foreign)):
        if lines:
            report.append(f"\n**{title}:**\n\n```\n" + "\n".join(l[:300] for l in lines[:30]) + "\n```\n")
    text = "".join(report)
    print(text)
    for line in fatal + own:
        print(f"::error::{line[:500]}")
    for line in foreign[:10]:
        print(f"::warning::{line[:500]}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text)
    sys.exit(1 if failure else 0)


if __name__ == "__main__":
    main()
