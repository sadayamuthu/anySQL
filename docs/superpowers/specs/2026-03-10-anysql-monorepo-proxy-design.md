# anySQL Monorepo + Proxy Design
**Date:** 2026-03-10
**Status:** Approved
**Scope:** Monorepo restructuring (SDK migration) + anysql-proxy package (Phase 1–3)

---

## 1. Monorepo Structure

No root `pyproject.toml`. Each package is fully independent — own versioning, own PyPI release, own CI/CD. Follows the opengpl pattern.

```
anysql/
├── sdk/
│   ├── src/anysql_sdk/     ← existing ./anysql/ code, moved here
│   ├── tests/              ← existing ./tests/, moved here
│   └── pyproject.toml      ← name = "anysql-sdk"
├── proxy/
│   ├── src/anysql_proxy/
│   ├── tests/
│   └── pyproject.toml      ← name = "anysql-proxy"
├── server/                 ← future
├── ui/                     ← future
├── docs/
└── .github/workflows/
    ├── release-sdk.yml
    ├── release-proxy.yml
    └── check-version.yml
```

**SDK migration:** Directory moves, import name changes from `anysql` → `anysql_sdk`. Internal code is otherwise unchanged. Acceptable at v0.1.0 alpha.

**Packages are independent:** proxy does not depend on anysql-sdk. Each has its own DuckDB schema, CLI entry point, and release tag.

---

## 2. Package Naming

| Package | PyPI name | Import | Entry point |
|---|---|---|---|
| SDK | `anysql-sdk` | `import anysql_sdk` | `anysql-sdk` CLI |
| Proxy | `anysql-proxy` | internal only | `anysql-proxy` CLI |
| Server | `anysql-server` | `import anysql_server` | future |
| UI | `anysql-ui` | internal only | future |

---

## 3. Proxy — How Intercept Works

The proxy runs on `localhost:4242`. IDEs are configured to point their LLM base URL to it. No IDE source changes required — just one URL setting per IDE.

```
IDE → POST http://localhost:4242/v1/chat/completions
              ↓
         anysql-proxy
              ↓ logs to ~/.anysql/ide.duckdb (non-blocking)
              ↓ forwards to api.openai.com or api.anthropic.com
              ↓ streams response back to IDE
IDE receives tokens with zero added latency
```

**IDE configuration:**
- Cursor: Settings → Override OpenAI Base URL → `http://localhost:4242`
- Claude Code: `export ANTHROPIC_BASE_URL=http://localhost:4242`
- Windsurf: Settings → Custom API Endpoint → `http://localhost:4242`
- Continue/VS Code: `config.json` → `apiBase: http://localhost:4242`

**Automated setup:**
```bash
anysql-proxy setup cursor
anysql-proxy setup claude-code   # appends to ~/.zshrc
anysql-proxy setup windsurf
anysql-proxy setup vscode
```

---

## 4. Proxy Internal Architecture

**Package layout:**
```
proxy/src/anysql_proxy/
├── __init__.py
├── cli.py          ← click CLI: start/stop/setup/status/test
├── server.py       ← aiohttp app, routes, ports 4242
├── interceptor.py  ← forward request + stream response back to IDE
├── detector.py     ← IDE fingerprinting from user-agent headers
├── extractor.py    ← file path, language, git branch from prompt body
├── writer.py       ← async queue → DuckDB batch writer (background thread)
└── keys.py         ← encrypted API key storage + passthrough logic
```

**HTTP framework:** aiohttp — chosen because the proxy needs async streaming in both directions simultaneously (receive from provider, forward to IDE). Single package provides both async server and async client.

**Request lifecycle:**
```
1. server.py       route POST /v1/chat/completions or /v1/messages
2. detector.py     identify IDE from User-Agent header
3. extractor.py    extract file, language, git context from prompt
4. interceptor.py  swap fake key → real key, open stream to provider
5.                 yield each chunk back to IDE as it arrives
6. writer.py       queue.put(record) — non-blocking < 1μs
7.                 background thread batches 50 rows / 2s → DuckDB
```

**DuckDB concurrency:**
- One write connection in background thread (writer.py)
- One read-only connection for future UI `/api/query`
- DuckDB supports 1 writer + N readers on same file — no locking issues
- Database location: `~/.anysql/ide.duckdb`

**API key handling (Pattern A — recommended):**
```toml
# ~/.anysql/proxy.toml
[providers]
openai.api_key    = "sk-..."       # encrypted at rest
anthropic.api_key = "sk-ant-..."
```
IDE is configured with fake key (`anysql-proxy`). Proxy substitutes real key before forwarding. Auth headers are never logged.

---

## 5. Proxy Dependencies

```toml
[project]
name = "anysql-proxy"
dependencies = [
    "aiohttp>=3.9.0",        # async HTTP server + client
    "duckdb>=0.10.0",        # local analytics storage
    "click>=8.0.0",          # CLI framework
    "cryptography>=41.0.0",  # API key encryption at rest
]

[project.scripts]
anysql-proxy = "anysql_proxy.cli:main"
```

---

## 6. DuckDB Schema (Proxy-owned)

Two tables written by the proxy:

**`llm_responses`** — every request/response
```sql
CREATE TABLE llm_responses (
    response_id       VARCHAR NOT NULL,
    model             VARCHAR,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    cost_usd          DOUBLE,
    latency_ms        INTEGER,
    created_at        TIMESTAMP NOT NULL
);
```

**`ide_context`** — developer workflow context
```sql
CREATE TABLE ide_context (
    context_id        VARCHAR NOT NULL,
    response_id       VARCHAR,
    ide_name          VARCHAR,   -- cursor | claude_code | windsurf | vscode_continue | zed
    request_type      VARCHAR,   -- chat | completion | debug | explain | review | generate
    file_path         VARCHAR,
    language          VARCHAR,
    git_repo          VARCHAR,
    git_branch        VARCHAR,
    lines_of_context  INTEGER,
    has_error_context BOOLEAN,
    suggestion_length INTEGER,
    created_at        TIMESTAMP NOT NULL
);
```

---

## 7. CI/CD

**`release-proxy.yml`** — triggers on changes to `proxy/**` on main:
1. Run tests (`pytest proxy/tests/`)
2. Validate semver from `proxy/pyproject.toml`
3. Check tag `proxy-vX.Y.Z` doesn't exist
4. Build wheel + sdist
5. Publish to PyPI (OIDC)
6. Create GitHub Release

**`release-sdk.yml`** — updated to trigger on `sdk/**`, tag `sdk-vX.Y.Z`

**`check-version.yml`** — PR gate: validates version bump for whichever package changed

---

## 8. Build Phases

### Phase 1 — Core Proxy
`server.py` + `interceptor.py` + `detector.py` + `writer.py`
Tables: `llm_responses` + `ide_context`
Manual IDE setup only
**Deliverable:** Proxy works with Cursor + Claude Code. Requests logged to local DuckDB.

### Phase 2 — Context Extraction
`extractor.py` + `keys.py`
Full `ide_context` table populated with file/language/git
**Deliverable:** SQL queries over file/language/repo dimensions work.

### Phase 3 — CLI + Automated Setup
`cli.py` with `start/stop/status/setup/test`
Per-IDE config writers
**Deliverable:** `anysql-proxy setup cursor` just works.

### Phase 4 — UI (separate package, later)
`ui/` package, port 4243, Monaco SQL editor, pre-built dashboards

---

## 9. Testing Strategy

```
proxy/tests/
├── test_detector.py     unit: IDE fingerprinting from user-agent strings
├── test_extractor.py    unit: file/language/git extraction from prompt bodies
├── test_interceptor.py  integration: mock provider, assert stream passthrough
└── test_writer.py       unit: queue drains correctly, DuckDB rows written
```
