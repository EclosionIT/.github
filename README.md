# EclosionIT/.github

Organization profile (`profile/README.md`) and the **reusable GitHub Actions workflows** of the Odoo module
repositories of EclosionIT, with the scripts and default configurations they use.

| Workflow | What it does |
| --- | --- |
| [`odoo-pipeline.yml`](.github/workflows/odoo-pipeline.yml) | **Single entry point.** Chains lint, pull request checks and Odoo tests, and sums them up in one `result` check. |
| [`odoo-lint.yml`](.github/workflows/odoo-lint.yml) | pre-commit (black, ruff, pylint-odoo, basic checks) with the repository's config or the defaults in `.github/configs/`. |
| [`odoo-pr.yml`](.github/workflows/odoo-pr.yml) | Pull requests only: Conventional Commits title, manifest version bump of every touched module, secret scan with gitleaks. |
| [`odoo-ci.yml`](.github/workflows/odoo-ci.yml) | Static checks of the modules, then install and test them on the official `odoo:<version>` image with Postgres. |

New repositories start from the template `EclosionIT/odoo-addons-template`, which already calls the
pipeline and sets up the branch ruleset.

## Usage

### `odoo-pipeline.yml` (recommended)

`.github/workflows/ci.yml` of the module repository:

```yaml
name: CI
on:
  pull_request:
  push:
    branches: ["20.0"]
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  ci:
    uses: EclosionIT/.github/.github/workflows/odoo-pipeline.yml@v1
    with:
      odoo_version: "20.0"
    secrets:
      ENTERPRISE_TOKEN: ${{ secrets.ENTERPRISE_TOKEN }}
```

Jobs: `lint` and `pr` run in parallel; `odoo` (the long one) starts after a green or disabled lint; `result`
fails if any of them failed. **Require only `ci / result`** (caller job id `ci` + job `result`) in the branch
ruleset: the set of checks behind it can change without touching the ruleset.

| Input | Type | Default | |
| --- | --- | --- | --- |
| `odoo_version` | string | **required** | Odoo series of the branch, e.g. `"20.0"`. |
| `lint` | boolean | `true` | Run `odoo-lint.yml`. |
| `pr_checks` | boolean | `true` | Run `odoo-pr.yml` (only on `pull_request` events). |
| `tests` | boolean | `true` | Run `odoo-ci.yml`. |
| `skip_modules` | string | `""` | Modules (comma or space separated) not to install and test on their own. |
| `lint_only_changed` | boolean | `false` | On pull requests, lint only the changed files (repositories with lint debt). |
| `lint_skip_hooks` | string | `""` | pre-commit hook ids to skip, e.g. `"pylint_odoo"`. |
| `python_version` | string | `"3.12"` | Python that runs pre-commit. |
| `version_ignore` | string | `""` | Globs that do not need a version bump (see `odoo-pr.yml`). |
| `ci_ref` | string | `""` | Ref of this repository for scripts and configs; empty = the commit of the workflow. |

| Secret | |
| --- | --- |
| `ENTERPRISE_TOKEN` | Optional. Read access to the repository in the variable `ENTERPRISE_REPO` (see `odoo-ci.yml`). |

### `odoo-lint.yml`

Runs `pre-commit` on the caller repository. If the repository has its own `.pre-commit-config.yaml`, it is
used as it is. Otherwise the defaults from [`.github/configs/`](.github/configs) are copied in
(`.pre-commit-config.yaml`, `pylintrc` as `.pylintrc`, `pyproject.toml`, each only if missing) and
`valid-odoo-versions` is set to `odoo_version`. `~/.cache/pre-commit` is cached by the hash of the config.

| Input | Default | |
| --- | --- | --- |
| `odoo_version` | `""` | Series for `valid-odoo-versions` when the default config is used. |
| `python_version` | `"3.12"` | |
| `only_changed` | `false` | On pull requests, `--from-ref <base> --to-ref HEAD` instead of `--all-files`. |
| `skip_hooks` | `""` | Passed as `SKIP` to pre-commit. |
| `ci_ref` | `""` | See below. |

### `odoo-pr.yml`

Call it only on `pull_request` (every job also checks the event).

- **title**: `scripts/pr_title.py`, `type(scope)!: description` with the types feat, fix, docs, style,
  refactor, perf, test, build, ci, chore, revert.
- **versions**: `scripts/odoo_version_bump.py`. Every module with changed files (compared with the merge
  base) must have `version` `<series>.x.y.z` in `__manifest__.py` and raise it. New modules only need a valid
  version; deleted modules pass. Changes only to `*.md`, `*.rst`, `static/description/*` or `tests/*` do not
  need a bump (`version_ignore` replaces that list; `"none"` = every file needs a bump).
- **secrets**: gitleaks (MIT binary, checksum verified, no license key) over the commits of the pull
  request. Honours `.gitleaks.toml` and `.gitleaksignore` of the repository.

Inputs: `odoo_version` (required), `title`, `versions`, `secrets_scan` (booleans, default `true`),
`version_ignore`, `ci_ref`.

### `odoo-ci.yml`

Unchanged for the existing callers:

```yaml
jobs:
  odoo:
    uses: EclosionIT/.github/.github/workflows/odoo-ci.yml@v1
    with:
      odoo_version: "20.0"
    secrets: inherit
```

Inputs: `odoo_version` (required), `skip_modules` (`""`), `ci_ref` (`""`). Optional secret
`ENTERPRISE_TOKEN`; with the variable `ENTERPRISE_REPO` (e.g. `odoo/enterprise`) the Enterprise addons are
checked out at the series branch, otherwise only Community dependencies are available and modules that need
Enterprise are skipped and listed in the summary.

## Scripts and configs come from the same version as the workflow

A caller pinned to `@v1`, `@v1.1.0` or a SHA must not run scripts from `main`. Two mechanisms:

1. Every checkout of this repository inside a job uses
   `repository: ${{ job.workflow_repository }}` and `ref: ${{ inputs.ci_ref || job.workflow_sha }}`.
   `job.workflow_sha` is the commit of the reusable workflow file that the job is running, i.e. whatever the
   caller's `@ref` resolved to. (`github.workflow_sha` would be the caller's commit, which is why it is not
   used.)
2. `odoo-pipeline.yml` calls the other workflows with the self-repository syntax
   `uses: $/.github/workflows/odoo-lint.yml`, which resolves to this repository at the commit that is
   running. A pipeline at `v1.1.0` therefore never runs an `odoo-ci.yml` from another version.

`ci_ref` overrides the ref of the scripts and configs only (rarely needed: testing a script change while
the workflow stays put).

Requirements: GitHub.com (the `job.workflow_*` context is not on GitHub Enterprise Server) and runners
2.336.0 or newer for `$/` (GitHub-hosted runners are). actionlint 1.7.12 does not know either feature yet;
[`.github/actionlint.yaml`](.github/actionlint.yaml) ignores exactly those two messages.

## Versioning

- Immutable tags `v1.0.0`, `v1.1.0`, `v1.1.1`… for every release (semver).
- The major tag `v1` moves to the latest `v1.x.y` (the actions/checkout convention). Callers use `@v1`.
- Inside `v1` every change is backward compatible: new inputs always have a default, existing inputs,
  secrets and job names keep their meaning, so `odoo-ci.yml@v1` callers keep working without changes.
- A `v2` only for a change that breaks callers (required input, renamed job, removed input).

Release, after merging to `main`:

```bash
git switch main && git pull
git tag -a v1.1.0 -m "v1.1.0: odoo-pipeline, odoo-lint, odoo-pr"
git tag -f -a v1 -m "v1 -> v1.1.0"
git push origin v1.1.0
git push -f origin v1
```

Callers pinned to a SHA get updates through Dependabot (`github-actions` ecosystem).

## Testing a change from a branch

Push the branch here and point one module repository at it, in a branch of that repository:

```yaml
    uses: EclosionIT/.github/.github/workflows/odoo-pipeline.yml@feat/my-change
```

`job.workflow_sha` follows the branch, so the scripts, configs and nested workflows (`$/`) all come from it;
no `ci_ref` is needed. Open a pull request in the module repository to exercise `odoo-pr.yml` too. Do not
merge that pull request with the branch ref: switch back to `@v1` first.

## Development

The CI of this repository ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs actionlint,
zizmor and the unit tests of the scripts. Locally:

```bash
actionlint
uvx zizmor@1.33.1 .
python3 -m unittest discover -s scripts/tests -v
```

Rules for the workflows: `permissions: {}` at the top and the minimum per job, `timeout-minutes` on every
job, third-party actions pinned by SHA with the version in a comment, downloaded binaries verified by
checksum, and no `${{ }}` with user-controlled values inside `run:` (pass them through `env:`).

Dependabot updates the actions and the hooks in `.github/configs/.pre-commit-config.yaml`; keep the copy in
`odoo-addons-template` identical.
