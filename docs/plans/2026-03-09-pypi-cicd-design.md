# anySQL PyPI CI/CD — Design Document

**Date:** 2026-03-09
**Status:** Approved

---

## Goal

Add GitHub Actions workflows to enforce PR quality gates and automatically publish anySQL to PyPI + create a GitHub release on every push to `main`.

---

## Workflows

### 1. `pr-check.yml` — PR Validation

**Trigger:** `pull_request` targeting `main`

**Jobs (parallel):**

| Job | Command | Purpose |
|-----|---------|---------|
| `test` | `pytest tests/ -v` | Run all 94 unit tests on Python 3.10, 3.11, 3.12 |
| `lint` | `ruff check anysql/` + `ruff format --check anysql/` | Enforce code style |
| `version-check` | Compare `version` in PR vs `main` | Fail if version not bumped |

Version check logic:
- Fetch `pyproject.toml` from `main` branch via `git show origin/main:pyproject.toml`
- Parse both versions with `grep`/`python`
- Fail with message: `"Version X.Y.Z already exists on main — bump the version in pyproject.toml"`

---

### 2. `release.yml` — Publish & Release

**Trigger:** `push` to `main`

**Jobs (sequential):**

1. **`build`** — `pip install hatchling build` → `python -m build` → upload `dist/` as artifact
2. **`publish`** — PyPI Trusted Publishing (OIDC) via `pypa/gh-action-pypi-publish@release/v1`. No token required.
3. **`release`** — Read version from `pyproject.toml`, create git tag `v{version}` and GitHub release titled `anySQL v{version}` via `softprops/action-gh-release`

---

## PyPI Trusted Publishing Setup (one-time, manual)

On PyPI, configure a Trusted Publisher for `anysql`:
- Owner: `sadayamuthu`
- Repository: `anySQL`
- Workflow: `release.yml`
- Environment: `pypi` (optional)

---

## Repository Structure

```
.github/
└── workflows/
    ├── pr-check.yml
    └── release.yml
```

---

*anySQL PyPI CI/CD — Apache 2.0*
