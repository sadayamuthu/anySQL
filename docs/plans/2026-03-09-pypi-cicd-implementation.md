# anySQL PyPI CI/CD Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add two GitHub Actions workflows — PR validation (CI + lint + version check) and automatic PyPI publish + GitHub release on push to main.

**Architecture:** Two focused workflow files under `.github/workflows/`. `pr-check.yml` runs three parallel jobs on every PR. `release.yml` runs three sequential jobs on every push to main — build → PyPI publish (OIDC trusted publishing) → GitHub release tag.

**Tech Stack:** GitHub Actions, `pypa/gh-action-pypi-publish`, `softprops/action-gh-release`, hatchling, ruff, pytest

---

### Task 1: PR Check Workflow

**Files:**
- Create: `.github/workflows/pr-check.yml`

**Step 1: Create the `.github/workflows/` directory and `pr-check.yml`**

```yaml
# .github/workflows/pr-check.yml
name: PR Checks

on:
  pull_request:
    branches: [main]

jobs:
  test:
    name: Tests (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run tests
        run: pytest tests/ -v --tb=short

  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install ruff
        run: pip install ruff
      - name: Check lint
        run: ruff check anysql/
      - name: Check format
        run: ruff format --check anysql/

  version-check:
    name: Version Bump Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Check version was bumped
        run: |
          MAIN_VERSION=$(git show origin/main:pyproject.toml | python3 -c "
          import sys, re
          content = sys.stdin.read()
          match = re.search(r'^version\s*=\s*\"([^\"]+)\"', content, re.MULTILINE)
          print(match.group(1))
          ")
          PR_VERSION=$(python3 -c "
          import re
          content = open('pyproject.toml').read()
          match = re.search(r'^version\s*=\s*\"([^\"]+)\"', content, re.MULTILINE)
          print(match.group(1))
          ")
          echo "main version: $MAIN_VERSION"
          echo "PR version:   $PR_VERSION"
          if [ "$MAIN_VERSION" = "$PR_VERSION" ]; then
            echo "ERROR: Version $PR_VERSION already exists on main — bump the version in pyproject.toml"
            exit 1
          fi
          echo "OK: version bumped $MAIN_VERSION → $PR_VERSION"
```

**Step 2: Validate the workflow file is valid YAML**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/pr-check.yml'))" && echo "VALID"
```
Expected: `VALID`

**Step 3: Commit**

```bash
git add .github/workflows/pr-check.yml
git commit -m "ci: add PR validation workflow (tests, lint, version check)"
```

---

### Task 2: Release Workflow

**Files:**
- Create: `.github/workflows/release.yml`

**Step 1: Create `release.yml`**

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    branches: [main]

permissions:
  contents: write
  id-token: write

jobs:
  build:
    name: Build distribution
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install build tools
        run: pip install hatchling build
      - name: Build wheel and sdist
        run: python -m build
      - name: Upload dist artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish:
    name: Publish to PyPI
    needs: build
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - name: Download dist artifacts
        uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1

  release:
    name: Create GitHub Release
    needs: publish
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - name: Get version
        id: version
        run: |
          VERSION=$(python3 -c "
          import re
          content = open('pyproject.toml').read()
          match = re.search(r'^version\s*=\s*\"([^\"]+)\"', content, re.MULTILINE)
          print(match.group(1))
          ")
          echo "version=$VERSION" >> $GITHUB_OUTPUT
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: v${{ steps.version.outputs.version }}
          name: anySQL v${{ steps.version.outputs.version }}
          generate_release_notes: true
```

**Step 2: Validate the workflow file is valid YAML**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))" && echo "VALID"
```
Expected: `VALID`

**Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add release workflow (build, PyPI publish, GitHub release)"
```

---

### Task 3: Push and verify

**Step 1: Push both workflows to main**

```bash
git push
```

**Step 2: Verify workflows appear on GitHub**

Go to `https://github.com/sadayamuthu/anySQL/actions` — you should see the `Release` workflow triggered by the push.

**Step 3: PyPI Trusted Publishing setup reminder**

The `publish` job uses OIDC (no token needed), but requires a one-time setup on PyPI:

1. Go to https://pypi.org/manage/account/publishing/
2. Add a new publisher:
   - PyPI project name: `anysql`
   - Owner: `sadayamuthu`
   - Repository: `anySQL`
   - Workflow filename: `release.yml`
   - Environment: `pypi`
3. On GitHub, create an environment named `pypi` at `https://github.com/sadayamuthu/anySQL/settings/environments`

---

*anySQL PyPI CI/CD — Apache 2.0*
