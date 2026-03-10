# anySQL Monorepo + Proxy Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the repo into a monorepo (SDK → `sdk/`) and implement `anysql-proxy` — a local HTTP proxy that intercepts IDE LLM calls, logs them to DuckDB, and streams responses back with zero added latency.

**Architecture:** aiohttp server on `localhost:4242` intercepts OpenAI-compatible and Anthropic-native requests from IDEs, logs metadata to a local DuckDB file (`~/.anysql/ide.duckdb`), and transparently forwards + streams the response back. DuckDB writes happen in a background thread via a stdlib queue — the async handler never blocks on DB I/O.

**Tech Stack:** Python 3.10+, aiohttp 3.9+, duckdb 0.10+, click 8+, cryptography 41+, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-10-anysql-monorepo-proxy-design.md`

---

## Chunk 1: SDK Migration

Mechanical restructure only — no logic changes. Move `anysql/` → `sdk/src/anysql_sdk/`, update all imports, verify tests still pass.

### Task 1: Create SDK directory structure

**Files:**
- Create: `sdk/src/anysql_sdk/` (directory)
- Create: `sdk/tests/` (directory)
- Create: `sdk/pyproject.toml`

- [ ] **Step 1: Create directory layout**

```bash
mkdir -p sdk/src/anysql_sdk
mkdir -p sdk/tests
```

- [ ] **Step 2: Copy source files into new location**

```bash
cp anysql/__init__.py sdk/src/anysql_sdk/__init__.py
cp anysql/engine.py   sdk/src/anysql_sdk/engine.py
cp anysql/schema.py   sdk/src/anysql_sdk/schema.py
cp anysql/storage.py  sdk/src/anysql_sdk/storage.py
cp anysql/context.py  sdk/src/anysql_sdk/context.py
cp anysql/cli.py      sdk/src/anysql_sdk/cli.py
cp -r anysql/adapters sdk/src/anysql_sdk/adapters
cp -r anysql/tracers  sdk/src/anysql_sdk/tracers
cp tests/*.py         sdk/tests/
```

- [ ] **Step 3: Create sdk/pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "anysql-sdk"
version = "0.1.0"
description = "SQL analytics for AI systems — query LLM responses, agent traces, and RAG pipelines like a database"
readme = "README.md"
license = { text = "Apache-2.0" }
requires-python = ">=3.10"
keywords = ["llm", "observability", "sql", "duckdb", "ai", "agents", "rag"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]
dependencies = [
    "duckdb>=0.10.0",
    "pyarrow>=14.0.0",
    "pandas>=2.0.0",
]

[project.optional-dependencies]
openai    = ["openai>=1.0.0"]
anthropic = ["anthropic>=0.25.0"]
dev       = ["pytest>=8.0.0", "pytest-asyncio", "black", "ruff"]

[project.urls]
Homepage   = "https://anysql.org"
Repository = "https://github.com/sadayamuthu/anySQL"

[project.scripts]
anysql-sdk = "anysql_sdk.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/anysql_sdk"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths    = ["tests"]
```

- [ ] **Step 4: Commit scaffold**

```bash
git add sdk/
git commit -m "chore: scaffold sdk/ directory for monorepo restructure"
```

---

### Task 2: Update imports from `anysql` to `anysql_sdk`

Every `from anysql.` and `import anysql` in the moved files must become `from anysql_sdk.` and `import anysql_sdk`.

**Files to update** (all inside `sdk/src/anysql_sdk/`):
- `__init__.py`
- `engine.py`
- `schema.py`
- `storage.py`
- `context.py`
- `cli.py`
- `adapters/claude.py`
- `adapters/openai.py`
- `adapters/generic.py`
- `tracers/agent.py`
- `tracers/rag.py`
- `sdk/tests/*.py`

- [ ] **Step 1: Bulk-replace imports in SDK source**

```bash
# Run from repo root
find sdk/src/anysql_sdk -name "*.py" -exec \
  sed -i '' 's/from anysql\./from anysql_sdk./g; s/import anysql$/import anysql_sdk/g' {} \;
```

- [ ] **Step 2: Bulk-replace imports in SDK tests**

```bash
find sdk/tests -name "*.py" -exec \
  sed -i '' 's/from anysql\./from anysql_sdk./g; s/import anysql$/import anysql_sdk/g' {} \;
```

- [ ] **Step 3: Verify no stale `anysql` references remain**

```bash
grep -r "from anysql\." sdk/src/ sdk/tests/ || echo "Clean"
grep -r "import anysql$" sdk/src/ sdk/tests/ || echo "Clean"
```

Expected: `Clean` on both lines.

- [ ] **Step 4: Install SDK in editable mode and run tests**

```bash
cd sdk
pip install -e ".[dev]"
pytest tests/ -v
cd ..
```

Expected: all existing tests pass.

- [ ] **Step 5: Commit**

```bash
git add sdk/src/anysql_sdk/ sdk/tests/
git commit -m "chore: rename anysql → anysql_sdk imports for monorepo layout"
```

---

### Task 3: Remove old root-level SDK files

Once SDK tests pass from `sdk/`, delete the old root-level `anysql/` and `tests/` directories.

- [ ] **Step 1: Remove old directories**

```bash
rm -rf anysql/ tests/ pyproject.toml
```

- [ ] **Step 2: Verify repo still builds from sdk/**

```bash
cd sdk && pip install -e ".[dev]" && pytest tests/ -v && cd ..
```

Expected: all tests pass.

- [ ] **Step 3: Update SDK GitHub Actions workflow**

The existing workflow is at `.github/workflows/release.yml`. Rename it to `release-sdk.yml` and update all paths:

```bash
mv .github/workflows/release.yml .github/workflows/release-sdk.yml
```

Then edit `.github/workflows/release-sdk.yml` to:
1. Trigger on `sdk/**` paths (not root)
2. Use `sdk-v` tag prefix (not `v`)
3. Run from `sdk/` working directory
4. Read version from `sdk/pyproject.toml`

```yaml
name: Release SDK

on:
  push:
    branches: [main]
    paths: ["sdk/**"]

permissions:
  contents: write
  id-token: write

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: sdk
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v

  release:
    needs: test
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: sdk
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Read version
        id: version
        run: |
          VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
          echo "version=$VERSION" >> $GITHUB_OUTPUT

      - name: Check tag does not exist
        run: |
          if git ls-remote --tags origin | grep -q "refs/tags/sdk-v${{ steps.version.outputs.version }}"; then
            echo "Tag sdk-v${{ steps.version.outputs.version }} already exists. Bump version to release."
            exit 1
          fi

      - run: pip install build
      - run: python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: sdk/dist/

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: sdk-v${{ steps.version.outputs.version }}
          generate_release_notes: true
          files: sdk/dist/*
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove root-level SDK files, monorepo restructure complete"
```

---

## Chunk 2: Proxy Package Scaffold + DuckDB Writer

### Task 4: Scaffold the proxy package

**Files:**
- Create: `proxy/pyproject.toml`
- Create: `proxy/src/anysql_proxy/__init__.py`
- Create: `proxy/tests/__init__.py`

- [ ] **Step 1: Create proxy directory layout**

```bash
mkdir -p proxy/src/anysql_proxy
mkdir -p proxy/tests
touch proxy/src/anysql_proxy/__init__.py
touch proxy/tests/__init__.py
```

- [ ] **Step 2: Create proxy/pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "anysql-proxy"
version = "0.1.0"
description = "Local IDE LLM proxy — intercept, log, and query your AI coding assistant usage"
readme = "README.md"
license = { text = "Apache-2.0" }
requires-python = ">=3.10"
keywords = ["llm", "proxy", "ide", "cursor", "claude-code", "observability", "duckdb"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
]
dependencies = [
    "aiohttp>=3.9.0",
    "duckdb>=0.10.0",
    "click>=8.0.0",
    "cryptography>=41.0.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0", "aiohttp[speedups]", "aioresponses>=0.7.6"]

[project.urls]
Homepage   = "https://anysql.org"
Repository = "https://github.com/sadayamuthu/anySQL"

[project.scripts]
anysql-proxy = "anysql_proxy.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/anysql_proxy"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths    = ["tests"]
```

- [ ] **Step 3: Install in editable mode**

```bash
cd proxy
pip install -e ".[dev]"
cd ..
```

Expected: installs cleanly, `anysql-proxy --help` shows an empty CLI (not yet implemented — that's fine, we just need the entry point to exist after Task 9).

- [ ] **Step 4: Commit**

```bash
git add proxy/
git commit -m "feat(proxy): scaffold anysql-proxy package"
```

---

### Task 5: DuckDB writer (writer.py)

The writer owns the DuckDB schema and all writes. It runs in a background thread so async request handlers never block on DB I/O. Batches up to 50 rows or flushes every 2 seconds.

**Files:**
- Create: `proxy/src/anysql_proxy/writer.py`
- Create: `proxy/tests/test_writer.py`

- [ ] **Step 1: Write the failing tests**

Create `proxy/tests/test_writer.py`:

```python
import time
import pytest
import duckdb
import tempfile
import os
from datetime import datetime, timezone
from anysql_proxy.writer import DBWriter


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.duckdb")


@pytest.fixture
def writer(db_path):
    w = DBWriter(db_path)
    w.start()
    yield w
    w.stop()


def make_response(response_id="r1"):
    return {
        "response_id": response_id,
        "model": "gpt-4o",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "cost_usd": 0.001,
        "latency_ms": 200,
        "created_at": datetime.now(timezone.utc),
    }


def make_context(response_id="r1", context_id="c1"):
    return {
        "context_id": context_id,
        "response_id": response_id,
        "ide_name": "cursor",
        "request_type": "chat",
        "file_path": "src/main.py",
        "language": "python",
        "git_repo": "myrepo",
        "git_branch": "main",
        "lines_of_context": 42,
        "has_error_context": False,
        "suggestion_length": 50,
        "created_at": datetime.now(timezone.utc),
    }


def test_writer_creates_tables(writer, db_path):
    time.sleep(0.1)
    conn = duckdb.connect(db_path, read_only=True)
    tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
    conn.close()
    assert "llm_responses" in tables
    assert "ide_context" in tables


def test_writer_stores_record(writer, db_path):
    writer.enqueue(make_response("r1"), make_context("r1", "c1"))
    time.sleep(3)  # wait for 2s flush + buffer

    conn = duckdb.connect(db_path, read_only=True)
    rows = conn.execute("SELECT response_id FROM llm_responses").fetchall()
    conn.close()
    assert any(r[0] == "r1" for r in rows)


def test_writer_stores_context(writer, db_path):
    writer.enqueue(make_response("r2"), make_context("r2", "c2"))
    time.sleep(3)

    conn = duckdb.connect(db_path, read_only=True)
    rows = conn.execute("SELECT ide_name, language FROM ide_context").fetchall()
    conn.close()
    assert any(r == ("cursor", "python") for r in rows)


def test_writer_batches_multiple_records(writer, db_path):
    for i in range(5):
        writer.enqueue(make_response(f"r{i}"), make_context(f"r{i}", f"c{i}"))
    time.sleep(3)

    conn = duckdb.connect(db_path, read_only=True)
    count = conn.execute("SELECT COUNT(*) FROM llm_responses").fetchone()[0]
    conn.close()
    assert count == 5
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd proxy && pytest tests/test_writer.py -v && cd ..
```

Expected: `ImportError: cannot import name 'DBWriter' from 'anysql_proxy.writer'`

- [ ] **Step 3: Implement writer.py**

Create `proxy/src/anysql_proxy/writer.py`:

```python
"""
DBWriter — background thread that batches DuckDB inserts.

The async request handler calls enqueue() which is non-blocking (< 1μs).
A stdlib queue bridges the async event loop and the writer thread.
The writer flushes every 50 rows or every 2 seconds, whichever comes first.
"""
import queue
import threading
import duckdb
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_responses (
    response_id       VARCHAR NOT NULL,
    model             VARCHAR,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    cost_usd          DOUBLE,
    latency_ms        INTEGER,
    created_at        TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS ide_context (
    context_id        VARCHAR NOT NULL,
    response_id       VARCHAR,
    ide_name          VARCHAR,
    request_type      VARCHAR,
    file_path         VARCHAR,
    language          VARCHAR,
    git_repo          VARCHAR,
    git_branch        VARCHAR,
    lines_of_context  INTEGER,
    has_error_context BOOLEAN,
    suggestion_length INTEGER,
    created_at        TIMESTAMPTZ NOT NULL
);
"""

_INSERT_RESPONSE = """
INSERT INTO llm_responses VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_CONTEXT = """
INSERT INTO ide_context VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class DBWriter:
    """
    Single-writer, background-thread DuckDB writer.

    Usage:
        writer = DBWriter("~/.anysql/ide.duckdb")
        writer.start()
        writer.enqueue(response_record, context_record)  # from async handler
        writer.stop()  # on shutdown — flushes remaining records
    """

    BATCH_SIZE = 50
    FLUSH_INTERVAL_S = 2.0

    def __init__(self, db_path: str):
        self._db_path = str(Path(db_path).expanduser())
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._conn: duckdb.DuckDBPyConnection | None = None

    def start(self) -> None:
        """Create DB file + tables, start background writer thread."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(self._db_path, read_only=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="anysql-writer")
        self._thread.start()

    def stop(self) -> None:
        """Signal stop and flush remaining records."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        if self._conn:
            self._conn.close()
            self._conn = None

    def enqueue(self, response_record: dict, context_record: dict) -> None:
        """Non-blocking. Call from async request handler."""
        self._queue.put_nowait((response_record, context_record))

    def _loop(self) -> None:
        import time
        batch = []
        last_flush = time.monotonic()

        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.1)
                batch.append(item)
                # Drain remaining items up to BATCH_SIZE
                while len(batch) < self.BATCH_SIZE:
                    try:
                        batch.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
            except queue.Empty:
                pass

            if batch and (
                len(batch) >= self.BATCH_SIZE
                or time.monotonic() - last_flush >= self.FLUSH_INTERVAL_S
            ):
                self._flush(batch)
                batch = []
                last_flush = time.monotonic()

        # Flush any remaining records before shutdown
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if batch:
            self._flush(batch)

    def _flush(self, batch: list) -> None:
        now = datetime.now(timezone.utc)
        for response_record, context_record in batch:
            r = response_record
            self._conn.execute(_INSERT_RESPONSE, [
                r["response_id"],
                r.get("model"),
                r.get("prompt_tokens"),
                r.get("completion_tokens"),
                r.get("total_tokens"),
                r.get("cost_usd"),
                r.get("latency_ms"),
                r.get("created_at", now),
            ])
            c = context_record
            self._conn.execute(_INSERT_CONTEXT, [
                c["context_id"],
                c.get("response_id"),
                c.get("ide_name"),
                c.get("request_type"),
                c.get("file_path"),
                c.get("language"),
                c.get("git_repo"),
                c.get("git_branch"),
                c.get("lines_of_context"),
                c.get("has_error_context"),
                c.get("suggestion_length"),
                c.get("created_at", now),
            ])
        self._conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd proxy && pytest tests/test_writer.py -v && cd ..
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add proxy/src/anysql_proxy/writer.py proxy/tests/test_writer.py
git commit -m "feat(proxy): add DBWriter — async-safe DuckDB batch writer"
```

---

## Chunk 3: IDE Detector + Context Extractor

### Task 6: IDE detector (detector.py)

Identifies which IDE is making the request from the `User-Agent` header. Returns a string like `"cursor"`, `"claude_code"`, `"windsurf"`, or `"unknown"`.

**Files:**
- Create: `proxy/src/anysql_proxy/detector.py`
- Create: `proxy/tests/test_detector.py`

- [ ] **Step 1: Write failing tests**

Create `proxy/tests/test_detector.py`:

```python
import pytest
from anysql_proxy.detector import detect_ide


@pytest.mark.parametrize("user_agent,expected", [
    ("cursor/1.0.0 (darwin)", "cursor"),
    ("cursor-ide/2.0 Electron", "cursor"),
    ("windsurf/0.9 codeium-client", "windsurf"),
    ("codeium-windsurf/1.0", "windsurf"),
    ("claude-code/1.2.3", "claude_code"),
    ("anthropic-code/0.5", "claude_code"),
    ("continue/0.9.1 VSCode", "vscode_continue"),
    ("continue-dev/1.0", "vscode_continue"),
    ("zed/0.131.0", "zed"),
    ("python-httpx/0.27.0", "unknown"),
    ("", "unknown"),
])
def test_detect_ide_from_user_agent(user_agent, expected):
    headers = {"user-agent": user_agent}
    assert detect_ide(headers) == expected


def test_detect_ide_case_insensitive():
    assert detect_ide({"user-agent": "CURSOR/1.0"}) == "cursor"


def test_detect_ide_missing_header():
    assert detect_ide({}) == "unknown"


def test_detect_ide_prefers_first_match():
    # If multiple fingerprints match (edge case), first IDE in map wins
    result = detect_ide({"user-agent": "cursor/1.0 continue/0.9"})
    assert result in ("cursor", "vscode_continue")  # deterministic, not "unknown"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd proxy && pytest tests/test_detector.py -v && cd ..
```

Expected: `ImportError: cannot import name 'detect_ide'`

- [ ] **Step 3: Implement detector.py**

Create `proxy/src/anysql_proxy/detector.py`:

```python
"""
IDE fingerprinting from HTTP request headers.

Every IDE coding assistant includes a recognizable string in its User-Agent
header. We match against known fingerprints to identify the caller.
"""

# Map IDE name → list of substrings to look for in User-Agent (lowercase)
_FINGERPRINTS: dict[str, list[str]] = {
    "cursor":          ["cursor/", "cursor-ide"],
    "windsurf":        ["windsurf", "codeium", "antigravity"],
    "claude_code":     ["claude-code", "anthropic-code"],
    "vscode_continue": ["continue/", "continue-dev"],
    "zed":             ["zed/"],
}


def detect_ide(headers: dict) -> str:
    """
    Return the IDE name from request headers, or 'unknown'.

    Args:
        headers: dict of HTTP headers (keys may be any case)

    Returns:
        One of: 'cursor', 'windsurf', 'claude_code', 'vscode_continue',
                'zed', 'unknown'
    """
    ua = (headers.get("user-agent") or headers.get("User-Agent") or "").lower()
    for ide, fingerprints in _FINGERPRINTS.items():
        if any(fp in ua for fp in fingerprints):
            return ide
    return "unknown"
```

- [ ] **Step 4: Run tests**

```bash
cd proxy && pytest tests/test_detector.py -v && cd ..
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add proxy/src/anysql_proxy/detector.py proxy/tests/test_detector.py
git commit -m "feat(proxy): add IDE detector from User-Agent fingerprinting"
```

---

### Task 7: Context extractor (extractor.py)

Pulls developer context out of the LLM request body: active file path, programming language, request type (chat/debug/explain), and git repo/branch from the file path.

**Files:**
- Create: `proxy/src/anysql_proxy/extractor.py`
- Create: `proxy/tests/test_extractor.py`

- [ ] **Step 1: Write failing tests**

Create `proxy/tests/test_extractor.py`:

```python
import pytest
from anysql_proxy.extractor import extract_context, get_git_context


# --- extract_context ---

def test_extracts_file_path_from_cursor_pattern():
    body = {
        "messages": [{"role": "user", "content": "Current file: src/main.py\nfix this"}]
    }
    ctx = extract_context(body, "cursor")
    assert ctx["file_path"] == "src/main.py"


def test_extracts_language_from_extension():
    body = {
        "messages": [{"role": "user", "content": "Current file: app/server.ts\n"}]
    }
    ctx = extract_context(body, "cursor")
    assert ctx["language"] == "typescript"


def test_extracts_language_from_fenced_code_block():
    body = {
        "messages": [{"role": "user", "content": "```python\ndef foo(): pass\n```"}]
    }
    ctx = extract_context(body, "unknown")
    assert ctx["language"] == "python"


def test_detects_error_context():
    body = {
        "messages": [{"role": "user", "content": "Traceback (most recent call last): ..."}]
    }
    ctx = extract_context(body, "cursor")
    assert ctx["has_error_context"] is True


def test_no_error_context():
    body = {
        "messages": [{"role": "user", "content": "explain this function"}]
    }
    ctx = extract_context(body, "cursor")
    assert ctx["has_error_context"] is False


def test_infers_request_type_debug():
    body = {"messages": [{"role": "user", "content": "fix this bug in my code"}]}
    ctx = extract_context(body, "cursor")
    assert ctx["request_type"] == "debug"


def test_infers_request_type_explain():
    body = {"messages": [{"role": "user", "content": "explain what this function does"}]}
    ctx = extract_context(body, "cursor")
    assert ctx["request_type"] == "explain"


def test_infers_request_type_chat_fallback():
    body = {"messages": [{"role": "user", "content": "hello there"}]}
    ctx = extract_context(body, "cursor")
    assert ctx["request_type"] == "chat"


def test_counts_lines_of_context():
    content = "line1\nline2\nline3"
    body = {"messages": [{"role": "user", "content": content}]}
    ctx = extract_context(body, "cursor")
    assert ctx["lines_of_context"] == 2  # 2 newlines = 2 line breaks


def test_handles_anthropic_system_prompt():
    body = {
        "system": "You are a coding assistant. Current file: lib/auth.rb",
        "messages": [{"role": "user", "content": "fix this"}],
    }
    ctx = extract_context(body, "claude_code")
    assert ctx["file_path"] == "lib/auth.rb"
    assert ctx["language"] == "ruby"


def test_handles_empty_body():
    ctx = extract_context({}, "unknown")
    assert ctx["file_path"] is None
    assert ctx["language"] is None
    assert ctx["has_error_context"] is False


# --- get_git_context ---

def test_get_git_context_returns_dict_for_none():
    result = get_git_context(None)
    assert result == {}


def test_get_git_context_returns_dict_for_nonexistent_path():
    result = get_git_context("/nonexistent/path/to/nowhere/file.py")
    assert isinstance(result, dict)
    # Should not raise — may return {} if not a git repo
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd proxy && pytest tests/test_extractor.py -v && cd ..
```

Expected: `ImportError`

- [ ] **Step 3: Implement extractor.py**

Create `proxy/src/anysql_proxy/extractor.py`:

```python
"""
Context extraction from LLM request bodies.

Pulls developer context from prompt text:
  - Active file path (from IDE-specific patterns in system prompt / user message)
  - Programming language (from file extension or fenced code block)
  - Request type (chat, debug, explain, review, generate, test, completion)
  - Line count of code context in the prompt
  - Whether the prompt contains an error/stack trace
  - Git repo and branch (from filesystem, using file path)
"""
import re
import subprocess
from pathlib import Path

# Ordered list of regex patterns to find the active file path in prompt text.
# Each IDE embeds it differently; we try them in order and take the first match.
_FILE_PATTERNS = [
    r'Current file:\s*([^\n]+)',         # Cursor
    r'Active document:\s*([^\n]+)',      # Continue
    r'(?:file:|path:)\s*[`"]?([^\s`"\n]+\.\w+)',
    r'(?:```\w+\n)?#\s*([^\s]+\.\w+)',  # comment with filename
]

_EXTENSION_TO_LANGUAGE = {
    ".py": "python",   ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".rs": "rust",
    ".go": "go",       ".rb": "ruby",       ".java": "java",
    ".cpp": "cpp",     ".c": "c",           ".cs": "csharp",
    ".sh": "bash",     ".sql": "sql",       ".md": "markdown",
    ".kt": "kotlin",   ".swift": "swift",   ".php": "php",
}

_ERROR_PATTERN = re.compile(
    r"(Traceback|Error:|Exception:|at line \d+|stack trace|stacktrace)",
    re.IGNORECASE,
)

_REQUEST_TYPE_KEYWORDS = [
    ("debug",    ["fix", "error", "bug", "traceback", "broken", "failing"]),
    ("explain",  ["explain", "what does", "how does", "what is", "describe"]),
    ("review",   ["review", "improve", "refactor", "optimize", "clean up"]),
    ("generate", ["write", "create", "implement", "generate", "build"]),
    ("test",     ["test", "unit test", "pytest", "spec", "write tests"]),
]


def extract_context(body: dict, ide: str) -> dict:
    """
    Extract developer context from an LLM request body.

    Args:
        body: Parsed JSON request body (OpenAI or Anthropic format)
        ide:  IDE name from detector.detect_ide()

    Returns:
        dict with keys: file_path, language, request_type,
                        lines_of_context, has_error_context
    """
    parts = _collect_text_parts(body)
    full_text = "\n".join(parts)

    file_path = _extract_file_path(full_text)
    language = _extract_language(file_path, full_text)
    request_type = _infer_request_type(full_text)
    has_error = bool(_ERROR_PATTERN.search(full_text))
    lines = full_text.count("\n")

    return {
        "file_path":         file_path,
        "language":          language,
        "request_type":      request_type,
        "lines_of_context":  lines,
        "has_error_context": has_error,
    }


def get_git_context(file_path: str | None) -> dict:
    """
    Return git_repo and git_branch for the given file path.
    Returns {} if not in a git repo or on any error.
    """
    if not file_path:
        return {}
    try:
        path = Path(file_path).resolve()
        search_dir = path if path.is_dir() else path.parent
        if not search_dir.exists():
            return {}
        repo_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=search_dir, stderr=subprocess.DEVNULL, text=True
        ).strip()
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=repo_root, stderr=subprocess.DEVNULL, text=True
        ).strip()
        return {
            "git_repo":   Path(repo_root).name,
            "git_branch": branch or None,
        }
    except Exception:
        return {}


# --- private helpers ---

def _collect_text_parts(body: dict) -> list[str]:
    parts = []
    system = body.get("system", "")
    if isinstance(system, str) and system:
        parts.append(system)
    elif isinstance(system, list):
        for block in system:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
    for msg in body.get("messages", []):
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
    return parts


def _extract_file_path(text: str) -> str | None:
    for pattern in _FILE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_language(file_path: str | None, text: str) -> str | None:
    if file_path:
        ext = Path(file_path).suffix.lower()
        lang = _EXTENSION_TO_LANGUAGE.get(ext)
        if lang:
            return lang
    # Fallback: first fenced code block language tag
    m = re.search(r"```(\w+)", text)
    if m:
        lang = m.group(1).lower()
        if lang not in ("text", "output", "bash", "shell", "sh", "plaintext"):
            return lang
    return None


def _infer_request_type(text: str) -> str:
    text_lower = text.lower()
    for request_type, keywords in _REQUEST_TYPE_KEYWORDS:
        if any(kw in text_lower for kw in keywords):
            return request_type
    if len(text) < 500 and "```" in text:
        return "completion"
    return "chat"
```

- [ ] **Step 4: Run tests**

```bash
cd proxy && pytest tests/test_extractor.py -v && cd ..
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add proxy/src/anysql_proxy/extractor.py proxy/tests/test_extractor.py
git commit -m "feat(proxy): add context extractor — file, language, git, request type"
```

---

## Chunk 4: Interceptor + Server

### Task 8: Request interceptor (interceptor.py)

Forwards the request to the real provider and streams the response back. Reads the real API key from config. Never blocks the event loop.

**Files:**
- Create: `proxy/src/anysql_proxy/interceptor.py`
- Create: `proxy/tests/test_interceptor.py`

- [ ] **Step 1: Write failing tests**

Create `proxy/tests/test_interceptor.py`:

```python
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from anysql_proxy.interceptor import (
    detect_provider,
    build_forward_headers,
    calculate_cost,
)


def test_detect_provider_openai_path():
    assert detect_provider("/v1/chat/completions") == "openai"


def test_detect_provider_anthropic_path():
    assert detect_provider("/v1/messages") == "anthropic"


def test_detect_provider_models_path():
    assert detect_provider("/v1/models") == "openai"


def test_build_forward_headers_strips_host():
    headers = {"host": "localhost:4242", "content-type": "application/json",
               "authorization": "Bearer anysql-proxy", "user-agent": "cursor/1.0"}
    result = build_forward_headers(headers, api_key="sk-real-key", provider="openai")
    assert "host" not in result
    assert result["authorization"] == "Bearer sk-real-key"
    assert result["content-type"] == "application/json"
    assert result["user-agent"] == "cursor/1.0"


def test_build_forward_headers_anthropic_uses_x_api_key():
    headers = {"content-type": "application/json", "authorization": "Bearer fake"}
    result = build_forward_headers(headers, api_key="sk-ant-real", provider="anthropic")
    assert result.get("x-api-key") == "sk-ant-real"
    assert "authorization" not in result


def test_calculate_cost_gpt4o():
    cost = calculate_cost("gpt-4o", prompt_tokens=1000, completion_tokens=500)
    assert cost > 0


def test_calculate_cost_unknown_model():
    cost = calculate_cost("unknown-model-xyz", prompt_tokens=1000, completion_tokens=500)
    assert cost == 0.0


def test_calculate_cost_claude_sonnet():
    cost = calculate_cost("claude-sonnet-4-6", prompt_tokens=1000, completion_tokens=500)
    assert cost > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd proxy && pytest tests/test_interceptor.py -v && cd ..
```

Expected: `ImportError`

- [ ] **Step 3: Implement interceptor.py**

Create `proxy/src/anysql_proxy/interceptor.py`:

```python
"""
Request forwarding and streaming passthrough.

The interceptor:
  1. Detects which provider to forward to (OpenAI vs Anthropic)
  2. Swaps the fake IDE API key for the real provider key
  3. Streams the response back to the IDE chunk by chunk
  4. Collects token counts + calculates cost for logging

Auth headers are never logged.
"""
import json
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

import aiohttp

_PROVIDER_BASE_URLS = {
    "openai":    "https://api.openai.com",
    "anthropic": "https://api.anthropic.com",
}

# Cost per 1M tokens in USD (prompt, completion)
# Update as provider pricing changes.
_MODEL_COSTS: dict[str, tuple[float, float]] = {
    "gpt-4o":              (5.00,  15.00),
    "gpt-4o-mini":         (0.15,   0.60),
    "gpt-4-turbo":         (10.00, 30.00),
    "gpt-3.5-turbo":       (0.50,   1.50),
    "claude-opus-4-6":     (15.00, 75.00),
    "claude-sonnet-4-6":   (3.00,  15.00),
    "claude-haiku-4-5":    (0.25,   1.25),
}

_HEADERS_TO_STRIP = {"host", "content-length", "transfer-encoding", "connection"}


def detect_provider(path: str) -> str:
    """Return 'anthropic' for /v1/messages, 'openai' for everything else."""
    if path.startswith("/v1/messages"):
        return "anthropic"
    return "openai"


def build_forward_headers(
    headers: dict,
    api_key: str,
    provider: str,
) -> dict:
    """
    Build headers for the upstream request.
    - Strips hop-by-hop headers and host
    - Substitutes the real API key (never logs it)
    - Uses x-api-key for Anthropic, Authorization Bearer for OpenAI
    """
    forward = {
        k: v for k, v in headers.items()
        if k.lower() not in _HEADERS_TO_STRIP | {"authorization", "x-api-key"}
    }
    if provider == "anthropic":
        forward["x-api-key"] = api_key
        forward.setdefault("anthropic-version", "2023-06-01")
    else:
        forward["authorization"] = f"Bearer {api_key}"
    return forward


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Return estimated cost in USD. Returns 0.0 for unknown models."""
    # Normalize model name — strip date suffixes like -20251001
    normalized = model.lower()
    for known_model, (prompt_rate, completion_rate) in _MODEL_COSTS.items():
        if known_model in normalized:
            return (
                prompt_tokens * prompt_rate / 1_000_000
                + completion_tokens * completion_rate / 1_000_000
            )
    return 0.0


async def forward_and_stream(
    method: str,
    path: str,
    headers: dict,
    body: bytes,
    provider: str,
    api_key: str,
) -> AsyncIterator[bytes]:
    """
    Forward request to provider and yield response chunks as they arrive.
    This is an async generator — the caller iterates it to stream chunks
    back to the IDE while collecting the full response for logging.
    """
    base_url = _PROVIDER_BASE_URLS[provider]
    url = f"{base_url}{path}"
    forward_headers = build_forward_headers(headers, api_key=api_key, provider=provider)

    async with aiohttp.ClientSession() as session:
        async with session.request(
            method, url, headers=forward_headers, data=body
        ) as resp:
            async for chunk in resp.content.iter_any():
                yield chunk


def parse_token_counts(body: dict, provider: str) -> tuple[int, int]:
    """
    Extract (prompt_tokens, completion_tokens) from a parsed response body.
    Returns (0, 0) if not parseable.
    """
    if provider == "openai":
        usage = body.get("usage", {})
        return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    elif provider == "anthropic":
        usage = body.get("usage", {})
        return usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    return 0, 0
```

- [ ] **Step 4: Run tests**

```bash
cd proxy && pytest tests/test_interceptor.py -v && cd ..
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add proxy/src/anysql_proxy/interceptor.py proxy/tests/test_interceptor.py
git commit -m "feat(proxy): add interceptor — streaming forward + cost calculation"
```

---

### Task 9: aiohttp server (server.py)

The aiohttp application. Two routes: `/v1/chat/completions` (OpenAI) and `/v1/messages` (Anthropic). Ties together detector, extractor, interceptor, and writer.

**Files:**
- Create: `proxy/src/anysql_proxy/server.py`

Note: server.py integrates all components — unit-tested through each component's own tests. We verify integration manually with `curl` after implementation.

- [ ] **Step 1: Implement server.py**

Create `proxy/src/anysql_proxy/server.py`:

```python
"""
aiohttp HTTP server — anySQL Proxy on port 4242.

Routes:
  POST /v1/chat/completions  — OpenAI-compatible (Cursor, Windsurf, Continue)
  POST /v1/messages          — Anthropic-native (Claude Code, Zed)
  GET  /v1/models            — Model list (IDE verification requests)
  OPTIONS /*                 — CORS preflight (required for Cursor/Electron)
"""
import json
import time
import uuid
from datetime import datetime, timezone

from aiohttp import web

from .detector import detect_ide
from .extractor import extract_context, get_git_context
from .interceptor import (
    detect_provider,
    forward_and_stream,
    parse_token_counts,
    calculate_cost,
)
from .writer import DBWriter

_CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type, anthropic-version, x-api-key",
}

_MODELS_RESPONSE = json.dumps({
    "object": "list",
    "data": [
        {"id": "gpt-4o",            "object": "model"},
        {"id": "gpt-4o-mini",       "object": "model"},
        {"id": "claude-sonnet-4-6", "object": "model"},
    ],
})


def create_app(writer: DBWriter, api_keys: dict) -> web.Application:
    """
    Create and return the aiohttp Application.

    Args:
        writer:   DBWriter instance (already started)
        api_keys: dict with keys 'openai' and/or 'anthropic' → real API keys
    """
    app = web.Application()
    handler = RequestHandler(writer=writer, api_keys=api_keys)
    app.router.add_route("OPTIONS", "/{path_info:.*}", handler.handle_cors)
    app.router.add_get("/v1/models", handler.handle_models)
    app.router.add_post("/v1/chat/completions", handler.handle_llm)
    app.router.add_post("/v1/messages", handler.handle_llm)
    return app


class RequestHandler:
    def __init__(self, writer: DBWriter, api_keys: dict):
        self._writer = writer
        self._api_keys = api_keys

    async def handle_cors(self, request: web.Request) -> web.Response:
        return web.Response(status=204, headers=_CORS_HEADERS)

    async def handle_models(self, request: web.Request) -> web.Response:
        return web.Response(
            body=_MODELS_RESPONSE,
            content_type="application/json",
            headers=_CORS_HEADERS,
        )

    async def handle_llm(self, request: web.Request) -> web.StreamResponse:
        body_bytes = await request.read()
        try:
            body = json.loads(body_bytes)
        except Exception:
            body = {}

        headers = dict(request.headers)
        path = request.path
        provider = detect_provider(path)
        api_key = self._api_keys.get(provider, "")

        ide = detect_ide(headers)
        ctx = extract_context(body, ide)
        git_ctx = get_git_context(ctx.get("file_path"))

        response_id = str(uuid.uuid4())
        context_id = str(uuid.uuid4())
        t0 = time.monotonic()

        # Stream response back to IDE
        stream_response = web.StreamResponse(headers=_CORS_HEADERS)
        await stream_response.prepare(request)

        chunks = []
        async for chunk in forward_and_stream(
            method=request.method,
            path=path,
            headers=headers,
            body=body_bytes,
            provider=provider,
            api_key=api_key,
        ):
            await stream_response.write(chunk)
            chunks.append(chunk)

        await stream_response.write_eof()
        latency_ms = int((time.monotonic() - t0) * 1000)

        # Parse response for token counts (best-effort)
        full_body = b"".join(chunks)
        try:
            resp_json = json.loads(full_body)
        except Exception:
            resp_json = {}

        prompt_tokens, completion_tokens = parse_token_counts(resp_json, provider)
        model = resp_json.get("model") or body.get("model", "unknown")
        cost_usd = calculate_cost(model, prompt_tokens, completion_tokens)
        now = datetime.now(timezone.utc)

        # Non-blocking write to DuckDB
        self._writer.enqueue(
            response_record={
                "response_id":       response_id,
                "model":             model,
                "prompt_tokens":     prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens":      prompt_tokens + completion_tokens,
                "cost_usd":          cost_usd,
                "latency_ms":        latency_ms,
                "created_at":        now,
            },
            context_record={
                "context_id":        context_id,
                "response_id":       response_id,
                "ide_name":          ide,
                "request_type":      ctx.get("request_type"),
                "file_path":         ctx.get("file_path"),
                "language":          ctx.get("language"),
                "git_repo":          git_ctx.get("git_repo"),
                "git_branch":        git_ctx.get("git_branch"),
                "lines_of_context":  ctx.get("lines_of_context"),
                "has_error_context": ctx.get("has_error_context"),
                "suggestion_length": completion_tokens,
                "created_at":        now,
            },
        )

        return stream_response
```

- [ ] **Step 2: Verify server imports cleanly**

```bash
cd proxy
python -c "from anysql_proxy.server import create_app; print('OK')"
cd ..
```

Expected: `OK`

- [ ] **Step 3: Smoke test with curl**

Start the proxy manually in one terminal:

```bash
cd proxy
python -c "
import asyncio
from aiohttp import web
from anysql_proxy.writer import DBWriter
from anysql_proxy.server import create_app

writer = DBWriter('/tmp/test-anysql.duckdb')
writer.start()
app = create_app(writer=writer, api_keys={'openai': 'sk-test'})
web.run_app(app, port=4242)
"
```

In another terminal:

```bash
curl -s http://localhost:4242/v1/models | python3 -m json.tool
```

Expected: JSON with model list.

```bash
curl -X OPTIONS http://localhost:4242/v1/chat/completions -v 2>&1 | grep "Access-Control"
```

Expected: CORS headers present.

- [ ] **Step 4: Commit**

```bash
git add proxy/src/anysql_proxy/server.py
git commit -m "feat(proxy): add aiohttp server — routes, CORS, streaming handler"
```

---

## Chunk 5: CLI + Automated Setup

### Task 10: CLI (cli.py)

Click-based CLI with `start`, `stop`, `status`, and `setup <ide>` subcommands. `setup` writes IDE config files automatically.

**Files:**
- Create: `proxy/src/anysql_proxy/cli.py`
- Create: `proxy/src/anysql_proxy/setup_writers.py`

- [ ] **Step 1: Implement cli.py**

Create `proxy/src/anysql_proxy/cli.py`:

```python
"""
anysql-proxy CLI entry point.

Commands:
  anysql-proxy start          — start proxy in foreground
  anysql-proxy stop           — stop background proxy
  anysql-proxy status         — show proxy status
  anysql-proxy setup <ide>    — configure IDE to use proxy
  anysql-proxy keys set <provider> <key>  — store API key
"""
import sys
import click
from .server_runner import run_server
from .setup_writers import setup_ide
from .keys import KeyStore


@click.group()
def main():
    """anySQL Proxy — intercept and log IDE LLM calls."""


@main.command()
@click.option("--port", default=4242, show_default=True, help="Proxy port")
@click.option("--db", default="~/.anysql/ide.duckdb", show_default=True, help="DuckDB path")
def start(port: int, db: str):
    """Start the proxy (foreground). Use a process manager for background."""
    click.echo(f"anySQL Proxy starting on http://localhost:{port}")
    click.echo(f"Database: {db}")
    run_server(port=port, db_path=db)


@main.command()
def stop():
    """Stop the proxy (sends SIGTERM to the stored PID)."""
    pid_file = Path.home() / ".anysql" / "proxy.pid"
    if not pid_file.exists():
        click.echo("No PID file found — proxy may not be running.")
        return
    import os, signal
    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        pid_file.unlink()
        click.echo(f"Sent SIGTERM to proxy (PID {pid}).")
    except ProcessLookupError:
        pid_file.unlink(missing_ok=True)
        click.echo("Proxy was not running (stale PID file removed).")


@main.command()
def status():
    """Check if the proxy is running."""
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:4242/v1/models", timeout=2)
        click.echo("anySQL Proxy  running  http://localhost:4242")
    except Exception:
        click.echo("anySQL Proxy  not running")


@main.command()
@click.argument("ide", type=click.Choice(["cursor", "claude-code", "windsurf", "vscode", "zed"]))
def setup(ide: str):
    """Configure IDE to route LLM calls through the proxy."""
    setup_ide(ide)


@main.group()
def keys():
    """Manage API keys."""


@keys.command("set")
@click.argument("provider", type=click.Choice(["openai", "anthropic"]))
@click.argument("api_key")
def keys_set(provider: str, api_key: str):
    """Store an API key (encrypted at rest)."""
    ks = KeyStore()
    ks.set(provider, api_key)
    click.echo(f"Stored {provider} key.")
```

- [ ] **Step 2: Create server_runner.py**

Create `proxy/src/anysql_proxy/server_runner.py`:

```python
"""Thin wrapper to start aiohttp server with DBWriter."""
import os
from pathlib import Path
from aiohttp import web
from .writer import DBWriter
from .server import create_app
from .keys import KeyStore

_PID_FILE = Path.home() / ".anysql" / "proxy.pid"


def run_server(port: int = 4242, db_path: str = "~/.anysql/ide.duckdb") -> None:
    ks = KeyStore()
    api_keys = {
        "openai":    ks.get("openai") or "",
        "anthropic": ks.get("anthropic") or "",
    }
    writer = DBWriter(db_path)
    writer.start()
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(os.getpid()))
    app = create_app(writer=writer, api_keys=api_keys)
    try:
        web.run_app(app, port=port)
    finally:
        writer.stop()
        _PID_FILE.unlink(missing_ok=True)
```

- [ ] **Step 3: Create keys.py**

Create `proxy/src/anysql_proxy/keys.py`:

```python
"""
Encrypted API key storage.

Keys are stored in ~/.anysql/keys.toml, encrypted with a machine-local
key derived from a randomly generated secret stored in ~/.anysql/.secret.
"""
import os
import base64
import tomllib
import tomli_w
from pathlib import Path
from cryptography.fernet import Fernet


_CONFIG_DIR = Path.home() / ".anysql"
_SECRET_FILE = _CONFIG_DIR / ".secret"
_KEYS_FILE = _CONFIG_DIR / "keys.toml"


class KeyStore:
    def __init__(self):
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if not _SECRET_FILE.exists():
            _SECRET_FILE.write_bytes(Fernet.generate_key())
            _SECRET_FILE.chmod(0o600)
        self._fernet = Fernet(_SECRET_FILE.read_bytes())

    def set(self, provider: str, api_key: str) -> None:
        keys = self._load()
        keys[provider] = self._fernet.encrypt(api_key.encode()).decode()
        _KEYS_FILE.write_text(tomli_w.dumps(keys))
        _KEYS_FILE.chmod(0o600)

    def get(self, provider: str) -> str | None:
        keys = self._load()
        encrypted = keys.get(provider)
        if not encrypted:
            return os.environ.get(f"{provider.upper()}_API_KEY")
        try:
            return self._fernet.decrypt(encrypted.encode()).decode()
        except Exception:
            return None

    def _load(self) -> dict:
        if not _KEYS_FILE.exists():
            return {}
        return tomllib.loads(_KEYS_FILE.read_text())
```

- [ ] **Step 3a: Add tomli-w to proxy/pyproject.toml and reinstall**

`keys.py` uses `tomli_w` which is not yet in the dependencies. Update the `dependencies` list in `proxy/pyproject.toml`:

```toml
dependencies = [
    "aiohttp>=3.9.0",
    "duckdb>=0.10.0",
    "click>=8.0.0",
    "cryptography>=41.0.0",
    "tomli-w>=1.0.0",
]
```

Then reinstall:

```bash
cd proxy && pip install -e ".[dev]" && cd ..
```

Expected: installs cleanly including `tomli-w`.

- [ ] **Step 4: Create setup_writers.py**

Create `proxy/src/anysql_proxy/setup_writers.py`:

```python
"""
Per-IDE configuration writers.

Each function modifies the IDE's config file to point its LLM base URL
to the anySQL proxy at http://localhost:4242.
"""
import json
import os
import click
from pathlib import Path


def setup_ide(ide: str) -> None:
    handlers = {
        "cursor":     _setup_cursor,
        "claude-code": _setup_claude_code,
        "windsurf":   _setup_windsurf,
        "vscode":     _setup_vscode_continue,
        "zed":        _setup_zed,
    }
    handlers[ide]()


def _setup_cursor() -> None:
    settings_path = Path.home() / ".cursor" / "settings.json"
    _update_json(settings_path, {
        "cursor.openAIApiBaseUrl": "http://localhost:4242",
    })
    click.echo(f"Cursor configured. Restart Cursor to apply.")
    click.echo(f"Updated: {settings_path}")


def _setup_claude_code() -> None:
    rc_file = _find_shell_rc()
    line = 'export ANTHROPIC_BASE_URL=http://localhost:4242'
    content = rc_file.read_text() if rc_file.exists() else ""
    if line not in content:
        rc_file.write_text(content + f"\n{line}\n")
    click.echo(f"Added to {rc_file}:")
    click.echo(f"  {line}")
    click.echo("Run: source ~/.zshrc  (or restart terminal)")


def _setup_windsurf() -> None:
    settings_path = Path.home() / ".windsurf" / "settings.json"
    _update_json(settings_path, {
        "windsurf.apiBaseUrl": "http://localhost:4242",
    })
    click.echo(f"Windsurf configured. Restart Windsurf to apply.")
    click.echo(f"Updated: {settings_path}")


def _setup_vscode_continue() -> None:
    config_path = Path.home() / ".continue" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    config.setdefault("models", [])
    # Add anySQL-proxied entry if not already present
    if not any(m.get("apiBase") == "http://localhost:4242" for m in config["models"]):
        config["models"].append({
            "title": "GPT-4o (via anySQL)",
            "provider": "openai",
            "model": "gpt-4o",
            "apiBase": "http://localhost:4242",
            "apiKey": "anysql-proxy",
        })
    config_path.write_text(json.dumps(config, indent=2))
    click.echo(f"Continue configured: {config_path}")


def _setup_zed() -> None:
    settings_path = Path.home() / ".config" / "zed" / "settings.json"
    _update_json(settings_path, {
        "assistant": {
            "version": "2",
            "openai_api_url": "http://localhost:4242",
        }
    })
    click.echo(f"Zed configured. Restart Zed to apply.")
    click.echo(f"Updated: {settings_path}")


def _update_json(path: Path, updates: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(path.read_text()) if path.exists() else {}
    config.update(updates)
    path.write_text(json.dumps(config, indent=2))


def _find_shell_rc() -> Path:
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return Path.home() / ".zshrc"
    return Path.home() / ".bashrc"
```

- [ ] **Step 5: Reinstall and verify CLI works**

```bash
cd proxy
pip install -e ".[dev]"
anysql-proxy --help
anysql-proxy status
cd ..
```

Expected:
```
Usage: anysql-proxy [OPTIONS] COMMAND [ARGS]...

  anySQL Proxy — intercept and log IDE LLM calls.

Commands:
  keys    Manage API keys.
  setup   Configure IDE to route LLM calls through the proxy.
  start   Start the proxy (foreground).
  status  Check if the proxy is running.
  stop    Stop the proxy (sends SIGTERM to the stored PID).
```

- [ ] **Step 6: Run full test suite**

```bash
cd proxy && pytest tests/ -v && cd ..
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add proxy/src/anysql_proxy/
git commit -m "feat(proxy): add CLI — start, status, setup, keys commands"
```

---

## Chunk 6: CI/CD

### Task 11: GitHub Actions for proxy

**Files:**
- Create: `.github/workflows/release-proxy.yml`
- Modify: `.github/workflows/release-sdk.yml` (update paths for sdk/)
- Create: `.github/workflows/check-version.yml`

- [ ] **Step 1: Create release-proxy.yml**

Create `.github/workflows/release-proxy.yml`:

```yaml
name: Release Proxy

on:
  push:
    branches: [main]
    paths: ["proxy/**"]

permissions:
  contents: write
  id-token: write

jobs:
  test:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: proxy
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v

  release:
    needs: test
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: proxy
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Read version
        id: version
        run: |
          VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
          echo "version=$VERSION" >> $GITHUB_OUTPUT

      - name: Check tag does not exist
        run: |
          if git ls-remote --tags origin | grep -q "refs/tags/proxy-v${{ steps.version.outputs.version }}"; then
            echo "Tag proxy-v${{ steps.version.outputs.version }} already exists. Bump version to release."
            exit 1
          fi

      - run: pip install build
      - run: python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: proxy/dist/

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: proxy-v${{ steps.version.outputs.version }}
          generate_release_notes: true
          files: proxy/dist/*
```

- [ ] **Step 2: Verify release-sdk.yml is complete**

This was done in Chunk 1, Task 3, Step 3 — the full `release-sdk.yml` YAML was written there including the rename from `release.yml`. Confirm the file exists and contains `paths: ["sdk/**"]` and tag prefix `sdk-v`:

```bash
grep -E "sdk/\*\*|sdk-v" .github/workflows/release-sdk.yml
```

Expected output includes both `sdk/**` and `sdk-v${{ steps.version.outputs.version }}`.

- [ ] **Step 3: Create check-version.yml**

Create `.github/workflows/check-version.yml`.

Note: `github.event.pull_request.changed_files` is not a valid GHA context field. Use `dorny/paths-filter` to detect which packages changed.

```yaml
name: Check Version Bump

on:
  pull_request:
    branches: [main]

jobs:
  filter:
    runs-on: ubuntu-latest
    outputs:
      sdk:   ${{ steps.filter.outputs.sdk }}
      proxy: ${{ steps.filter.outputs.proxy }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            sdk:
              - 'sdk/**'
            proxy:
              - 'proxy/**'

  check-sdk:
    needs: filter
    if: needs.filter.outputs.sdk == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Verify SDK version bumped
        run: |
          CURRENT=$(python -c "import tomllib; print(tomllib.load(open('sdk/pyproject.toml','rb'))['project']['version'])")
          git checkout origin/main -- sdk/pyproject.toml
          MAIN=$(python -c "import tomllib; print(tomllib.load(open('sdk/pyproject.toml','rb'))['project']['version'])")
          git checkout HEAD -- sdk/pyproject.toml
          python -c "
          from packaging.version import Version
          assert Version('$CURRENT') > Version('$MAIN'), f'Version {CURRENT!r} must be > {MAIN!r}'
          print(f'Version OK: {MAIN} -> {CURRENT}')
          "

  check-proxy:
    needs: filter
    if: needs.filter.outputs.proxy == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Verify proxy version bumped
        run: |
          CURRENT=$(python -c "import tomllib; print(tomllib.load(open('proxy/pyproject.toml','rb'))['project']['version'])")
          git checkout origin/main -- proxy/pyproject.toml
          MAIN=$(python -c "import tomllib; print(tomllib.load(open('proxy/pyproject.toml','rb'))['project']['version'])")
          git checkout HEAD -- proxy/pyproject.toml
          python -c "
          from packaging.version import Version
          assert Version('$CURRENT') > Version('$MAIN'), f'Version {CURRENT!r} must be > {MAIN!r}'
          print(f'Version OK: {MAIN} -> {CURRENT}')
          "
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/
git commit -m "ci: add release-proxy and check-version workflows"
```

---

## Summary

| Chunk | What ships | Commit count |
|---|---|---|
| 1 — SDK Migration | `sdk/` with anysql_sdk imports, tests passing | 4 |
| 2 — Proxy Scaffold + Writer | `proxy/` package, DuckDB writer | 2 |
| 3 — Detector + Extractor | IDE fingerprinting, context extraction | 2 |
| 4 — Interceptor + Server | Streaming proxy, aiohttp server | 2 |
| 5 — CLI | `anysql-proxy start/setup/status/keys` | 1 |
| 6 — CI/CD | GitHub Actions per-package release | 1 |

**Verify end-to-end after Chunk 5:**
```bash
# Terminal 1
cd proxy && anysql-proxy keys set anthropic sk-ant-...
anysql-proxy start

# Terminal 2 (simulates Claude Code)
export ANTHROPIC_BASE_URL=http://localhost:4242
claude  # or any claude-code command

# Terminal 3
duckdb ~/.anysql/ide.duckdb "SELECT ide_name, model, latency_ms FROM llm_responses ORDER BY created_at DESC LIMIT 5"
```
