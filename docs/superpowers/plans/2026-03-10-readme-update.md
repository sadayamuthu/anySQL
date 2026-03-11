# README Update Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite root `README.md` as monorepo index, update `sdk/README.md` with correct API and paths, and write `proxy/README.md` from scratch — all using a shared visual template.

**Architecture:** Three independent file writes. Root README becomes a brief monorepo overview with a packages table and architecture diagram. `sdk/README.md` gets the full SDK docs with the current `anysql_sdk` API (not the old stale `anysql` API). `proxy/README.md` is written from its single-line placeholder into a complete reference.

**Tech Stack:** Markdown only. No code changes. Verification via `grep`.

**Spec:** `docs/superpowers/specs/2026-03-10-readme-update-design.md`

---

## Chunk 1: All Three READMEs

### Task 1: Root README.md

**Files:**
- Modify: `README.md`

The root README becomes a monorepo index — brief, no code, links out to packages.

- [ ] **Step 1: Overwrite README.md with the following content**

```markdown
<div align="center">

# anySQL

<h3>SQL Analytics for AI Systems</h3>

<p>From vibes to queries.</p>

[![CI](https://img.shields.io/badge/CI-passing-brightgreen?style=flat-square)](https://github.com/sadayamuthu/anySQL/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue?style=flat-square)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green?style=flat-square)](LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-anysql--sdk-orange?style=flat-square)](https://pypi.org/project/anysql-sdk/)

---

[What is anySQL](#what-is-anysql) · [Packages](#packages) · [Architecture](#architecture) · [OpenAstra](https://openastra.org)

</div>

---

## What is anySQL?

anySQL is an open-source SQL analytics engine for AI systems — an [OpenAstra](https://openastra.org) initiative. It lets engineers query LLM responses, agent traces, and RAG pipelines with standard SQL, powered by DuckDB.

AI engineers debug with `print()` statements and pre-built dashboards that show what the tool designer thought you'd want to see. anySQL gives you raw SQL over normalized AI telemetry instead.

---

## Packages

| Package | PyPI | What it does |
|---------|------|--------------|
| [`sdk/`](sdk/README.md) | [`anysql-sdk`](https://pypi.org/project/anysql-sdk/) | Wrap LLM clients, trace agents/RAG, query with SQL |
| [`proxy/`](proxy/README.md) | [`anysql-proxy`](https://pypi.org/project/anysql-proxy/) | Intercept IDE LLM calls, log usage to local DuckDB |
| `server/` | coming soon | REST API over anySQL data |
| `ui/` | coming soon | Web dashboard |

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│                 Developer Tools                   │
│  Cursor · Claude Code · Windsurf · VS Code · Zed  │
└──────────────┬───────────────────────────────────┘
               │ anysql-proxy intercepts LLM calls
               ▼
┌──────────────────────────────────────────────────┐
│          anysql-proxy  (localhost:4242)            │
│  logs metadata → ~/.anysql/ide.duckdb            │
└──────────────┬───────────────────────────────────┘
               │ forwards to provider
               ▼
┌──────────────────────────────────────────────────┐
│             LLM Provider APIs                     │
│      api.openai.com · api.anthropic.com           │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────┐
│                  anysql-sdk                       │
│  wrap clients · trace agents/RAG · query SQL      │
│  → project.db  (DuckDB + SQLite)                  │
└──────────────────────────────────────────────────┘
```

---

<div align="center">

**anySQL is an [OpenAstra](https://openastra.org) initiative**

[anysql.org](https://anysql.org) · [PyPI](https://pypi.org/project/anysql-sdk/) · [GitHub](https://github.com/sadayamuthu/anySQL) · [Docs](https://docs.anysql.org)

</div>
```

- [ ] **Step 2: Verify required strings are present**

```bash
grep -c "OpenAstra initiative" README.md        # expect 1
grep -c "sdk/README.md" README.md               # expect 1
grep -c "proxy/README.md" README.md             # expect 1
grep -c "coming soon" README.md                 # expect 2 (server, ui)
grep -c "anysql-proxy" README.md                # expect >=1
```

All should return non-zero. Fix any missing items before continuing.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite root README as monorepo index"
```

---

### Task 2: sdk/README.md

**Files:**
- Modify: `sdk/README.md`

Full SDK reference using the correct `anysql_sdk` API (not the stale `anysql` pre-rename API). Key differences from the old README:
- All `import anysql` → `import anysql_sdk`
- All `anysql.init()` → `anysql_sdk.init()`
- Adapter wrapping: `anysql_sdk.openai(db).wrap(openai.OpenAI())` (takes `db` first)
- Context manager: `with anysql_sdk.context_scope(...)` (not `@anysql.context`)
- `agent_tracer` and `rag_tracer` take `db` as first arg
- CLI command: `anysql-sdk` (not `anysql`)
- Repository structure block updated to monorepo layout
- Dev commands: `cd sdk && pip install -e ".[dev]"`, `ruff check src/anysql_sdk/`
- Footer: "anySQL is an [OpenAstra](https://openastra.org) initiative"

- [ ] **Step 1: Overwrite sdk/README.md with the following content**

```markdown
<div align="center">

# anysql-sdk

<h3>SQL Analytics for AI Systems</h3>

<p>From vibes to queries.</p>

[![CI](https://img.shields.io/badge/CI-passing-brightgreen?style=flat-square)](https://github.com/sadayamuthu/anySQL/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue?style=flat-square)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green?style=flat-square)](LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-anysql--sdk-orange?style=flat-square)](https://pypi.org/project/anysql-sdk/)

---

[Quick Start](#quick-start) · [How It Works](#how-it-works) · [Use Cases](#the-5-use-cases) · [Installation](#installation) · [CLI](#cli-usage) · [Examples](#examples)

</div>

---

## What is anysql-sdk?

anysql-sdk is an open-source SQL analytics engine for AI systems. It lets engineers query LLM responses, agent traces, and RAG pipelines with standard SQL — powered by DuckDB in-memory, persisted to SQLite, with zero configuration.

AI engineers debug with `print()` statements, JSON log files, and pre-built dashboards that show what the tool designer thought you'd want to see. What's missing is raw SQL over normalized AI telemetry data — specifically the cross-layer JOIN that lets you ask whether your RAG pipeline is failing at retrieval or generation.

---

## Quick Start

```bash
pip install anysql-sdk

# With provider support
pip install "anysql-sdk[openai]"
pip install "anysql-sdk[anthropic]"
pip install "anysql-sdk[all]"        # OpenAI + Anthropic + LangChain
```

```python
import anysql_sdk
import openai
import anthropic

# Initialize (in-memory by default, or pass a file path for persistence)
db = anysql_sdk.init()

# Wrap your OpenAI client — all calls are auto-logged
client = anysql_sdk.openai(db).wrap(openai.OpenAI())

# Wrap your Anthropic client
client = anysql_sdk.claude(db).wrap(anthropic.Anthropic())

# Tag pipeline runs for cost attribution
with anysql_sdk.context_scope(feature="search", version="v2"):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Summarize this article..."}]
    )

# Query anything with standard SQL
df = db.query("SELECT model, AVG(cost_usd) FROM llm_responses GROUP BY model")

# Or use built-in analytics methods
df = db.model_comparison()       # UC1: multi-model comparison
df = db.prompt_regressions()     # UC2: regression detection
df = db.cost_by_feature()        # UC3: cost attribution
df = db.tool_failure_rates()     # UC4: agent debugging
df = db.rag_failure_modes()      # UC5: RAG forensics
```

---

## How It Works

```
User Code
    │
    ├── anysql_sdk.context_scope(feature="x")  ← Python contextvars, sync+async safe
    ├── OpenAI/Claude wrapped client            ← transparent proxy, one-line swap
    ├── AgentTracer (LangChain callback)        ← manual or callback-based
    └── RAGTracer.after_retrieval()             ← auto-detects LangChain/LlamaIndex/dict
              │
              ▼ insert()
    anysql-sdk engine
    ├── in-memory buffer (dict lists per table)
    ├── SQLite persistence (JSON blobs, cross-session)
    └── DuckDB (Arrow views, SQL at query time)
              │
              ▼ query()
    6 PyArrow tables as DuckDB views:
    llm_responses, eval_results, pipeline_runs,
    agent_tool_calls, agent_trace, rag_chunks
```

**Key design decisions:**
- Schema enforcement at Arrow layer — SQLite stores raw JSON, validation happens at query time
- Dot-namespace tables (`llm.responses`) map to flat SQL view names (`llm_responses`)
- Contextvars for thread-safe and async-safe tagging — no manual pass-through required

---

## The 6 Canonical Tables

| Table | Use Cases | Join Keys |
|-------|-----------|-----------|
| `llm_responses` | UC1, UC2 | `response_id` |
| `eval_results` | UC1, UC2, UC5 | `response_id`, `run_id`, `query_id` |
| `pipeline_runs` | UC3 | `run_id`, `session_id` |
| `agent_tool_calls` | UC4 | `session_id` |
| `agent_trace` | UC4 | `session_id` |
| `rag_chunks` | UC5 | `query_id` ← cross-layer join key |

---

## The 5 Use Cases

| UC | Name | Key Methods | What It Answers |
|----|------|-------------|-----------------|
| UC1 | Multi-Model Comparison | `model_comparison()`, `model_by_task()` | Which model performs best on my task? |
| UC2 | Prompt Regression Detection | `prompt_regressions()`, `eval_debt()`, `silent_degradation()` | Did my last prompt change break something? |
| UC3 | Cost Attribution | `cost_by_feature()`, `cost_anomalies()` | Which feature is burning my LLM budget? |
| UC4 | Agent Debugging | `tool_failure_rates()`, `loop_detector()`, `session_diff()`, `human_intervention_points()` | Where is my agent getting stuck? |
| UC5 | RAG Forensics | `rag_failure_modes()`, `chunk_quality_ranking()`, `similarity_calibration()` | Is my RAG failing at retrieval or generation? |

The cross-layer join (UC5) is the killer feature — `query_id` threads RAG retrieval to eval results, enabling retrieval vs. generation failure classification.

---

## Installation

### From PyPI

```bash
pip install anysql-sdk
```

### Provider extras

```bash
pip install "anysql-sdk[openai]"      # + openai>=1.0.0
pip install "anysql-sdk[anthropic]"   # + anthropic>=0.25.0
pip install "anysql-sdk[langchain]"   # + langchain>=0.2.0
pip install "anysql-sdk[all]"         # everything
```

---

## CLI Usage

```bash
# Run a SQL query against a persisted database
anysql-sdk query "SELECT model, COUNT(*) FROM llm_responses GROUP BY model"

# Show table row counts and basic stats
anysql-sdk stats

# Query a specific database file
anysql-sdk query "SELECT * FROM eval_results LIMIT 10" --db ./myproject.db
```

---

## Examples

Three runnable demos are included in `examples/` at the repo root. All auto-detect missing API keys and fall back to mock mode — no downloads required.

| Demo | Dataset | Models |
|------|---------|--------|
| `realtime_openai_demo.py` | BBC News (2004–05), 12 articles | `gpt-4o`, `gpt-4o-mini` |
| `realtime_claude_demo.py` | AG News, 15 articles | `claude-sonnet-4-6`, `claude-haiku-4-5` |
| `realtime_combined_demo.py` | Reuters R8, 20 articles | All 4 models head-to-head |

```bash
# Clone repo, then from repo root:
python examples/realtime_combined_demo.py
```

---

## Adapter Usage

### OpenAI

```python
import openai
import anysql_sdk

db = anysql_sdk.init()
client = anysql_sdk.openai(db).wrap(openai.OpenAI())

# All calls now logged automatically
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Summarize this article..."}]
)
```

### Anthropic

```python
import anthropic
import anysql_sdk

db = anysql_sdk.init()
client = anysql_sdk.claude(db).wrap(anthropic.Anthropic())

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Classify this text..."}]
)
```

### Agent Tracing

```python
tracer = anysql_sdk.agent_tracer(db)

# Manual tracing
tracer.trace_tool_call(
    session_id="sess-001",
    tool_name="web_search",
    input_data={"query": "latest news"},
    output_data={"results": [...]},
    success=True,
    latency_ms=320,
)

# LangChain callback (automatic)
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(callbacks=[tracer])
```

### RAG Tracing

```python
rag = anysql_sdk.rag_tracer(db)

query_id = rag.before_retrieval(query="What is anySQL?")
chunks = retriever.get_relevant_documents(query)
rag.after_retrieval(query_id=query_id, chunks=chunks)

# Record eval result with cross-layer join key
rag.record_eval(
    query_id=query_id,
    score=0.92,
    passed=True,
    eval_type="faithfulness",
)
```

---

## Development

```bash
cd sdk
pip install -e ".[dev]"

pytest tests/ -v           # Run tests
pytest tests/ --tb=short   # Short failure output
ruff check src/anysql_sdk/ # Lint
ruff format src/anysql_sdk/ # Format
```

---

## Repository Structure

```
anysql/
├── sdk/                        ← this package
│   ├── src/anysql_sdk/
│   │   ├── __init__.py         # Public API surface
│   │   ├── engine.py           # DuckDB engine + UC analytics methods
│   │   ├── schema.py           # 6 PyArrow schemas
│   │   ├── storage.py          # SQLite persistence
│   │   ├── context.py          # context_scope() + get_context()
│   │   ├── cli.py              # CLI entry point (anysql-sdk)
│   │   ├── adapters/
│   │   │   ├── openai.py       # OpenAI transparent proxy
│   │   │   ├── claude.py       # Anthropic transparent proxy
│   │   │   └── generic.py      # Generic JSON/dict adapter
│   │   └── tracers/
│   │       ├── agent.py        # AgentTracer (manual + LangChain)
│   │       └── rag.py          # RAGTracer (LangChain/LlamaIndex/dict)
│   └── tests/                  # 94 tests, all passing
├── proxy/                      # see proxy/README.md
├── examples/                   # 3 runnable demos (repo root)
└── docs/
    └── QUERIES.md              # Canonical SQL query library
```

---

## License

Apache 2.0

---

<div align="center">

**anySQL is an [OpenAstra](https://openastra.org) initiative**

[anysql.org](https://anysql.org) · [PyPI](https://pypi.org/project/anysql-sdk/) · [GitHub](https://github.com/sadayamuthu/anySQL) · [Docs](https://docs.anysql.org)

</div>
```

- [ ] **Step 2: Verify required strings are present**

```bash
grep -c "anysql_sdk" sdk/README.md              # expect >=10 (many occurrences)
grep -c "import anysql$" sdk/README.md          # expect 0 (stale import gone)
grep -c "anysql-sdk" sdk/README.md              # expect >=3 (CLI, PyPI badge, install)
grep -c "OpenAstra initiative" sdk/README.md    # expect 1
grep -c "sdk/src/anysql_sdk" sdk/README.md      # expect >=1 (repo structure)
grep -c "anysql_sdk.openai(db).wrap" sdk/README.md  # expect >=1
```

All checks: first must be >=10, second must be 0, rest non-zero.

- [ ] **Step 3: Commit**

```bash
git add sdk/README.md
git commit -m "docs: update sdk/README.md — correct API, paths, monorepo structure"
```

---

### Task 3: proxy/README.md

**Files:**
- Modify: `proxy/README.md`

Full proxy reference written from scratch. The current file is a single placeholder line.

- [ ] **Step 1: Overwrite proxy/README.md with the following content**

```markdown
<div align="center">

# anysql-proxy

<h3>Intercept, Log, and Query Your IDE LLM Usage</h3>

<p>See exactly what your AI coding assistant costs — in SQL.</p>

[![CI](https://img.shields.io/badge/CI-passing-brightgreen?style=flat-square)](https://github.com/sadayamuthu/anySQL/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue?style=flat-square)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green?style=flat-square)](LICENSE)
[![PyPI](https://img.shields.io/badge/PyPI-anysql--proxy-orange?style=flat-square)](https://pypi.org/project/anysql-proxy/)

---

[What is anysql-proxy](#what-is-anysql-proxy) · [Quick Start](#quick-start) · [How It Works](#how-it-works) · [IDE Setup](#ide-setup) · [CLI](#cli) · [Querying Your Data](#querying-your-data)

</div>

---

## What is anysql-proxy?

anysql-proxy is a local HTTP proxy that sits between your IDE and LLM provider APIs. It intercepts every request, logs metadata (tokens, cost, latency, IDE, file context) non-blocking to a local DuckDB file at `~/.anysql/ide.duckdb`, and streams the response back to your IDE with zero added latency.

Works with Cursor, Claude Code, Windsurf, VS Code (Continue), and Zed — no IDE source changes required. One URL setting per IDE.

---

## Quick Start

```bash
pip install anysql-proxy

# Store your API key (encrypted at rest)
anysql-proxy keys set openai sk-...
# or
anysql-proxy keys set anthropic sk-ant-...

# Start the proxy
anysql-proxy start

# Configure your IDE (one-time)
anysql-proxy setup cursor        # or claude-code, windsurf, vscode, zed
```

Then restart your IDE. All LLM calls are now intercepted and logged.

---

## How It Works

```
IDE → POST http://localhost:4242/v1/chat/completions
           ↓
      anysql-proxy
           ↓ logs to ~/.anysql/ide.duckdb  (non-blocking, <1μs)
           ↓ forwards to api.openai.com or api.anthropic.com
           ↓ streams response back to IDE
IDE receives tokens with zero added latency
```

**Supported endpoints:**
- `POST /v1/chat/completions` — OpenAI-compatible (Cursor, Windsurf, Continue)
- `POST /v1/messages` — Anthropic-native (Claude Code, Zed)
- `GET /v1/models` — Model list (IDE verification)
- `OPTIONS /*` — CORS preflight

**API keys:** Stored encrypted at `~/.anysql/keys.toml` using Fernet encryption. The IDE is configured with a passthrough key; the proxy substitutes the real key before forwarding. Auth headers are never logged.

---

## IDE Setup

| IDE | Command | What it does |
|-----|---------|--------------|
| Cursor | `anysql-proxy setup cursor` | Sets Override OpenAI Base URL in `~/.cursor/settings.json` |
| Claude Code | `anysql-proxy setup claude-code` | Appends `export ANTHROPIC_BASE_URL=http://localhost:4242` to shell RC |
| Windsurf | `anysql-proxy setup windsurf` | Sets Custom API Endpoint in `~/.windsurf/settings.json` |
| VS Code / Continue | `anysql-proxy setup vscode` | Adds proxied model entry to `~/.continue/config.json` |
| Zed | `anysql-proxy setup zed` | Sets `assistant.openai_api_url` in `~/.config/zed/settings.json` |

Restart your IDE after running setup.

---

## CLI

```bash
# Start proxy (foreground — use a process manager for background)
anysql-proxy start
anysql-proxy start --port 4242 --db ~/.anysql/ide.duckdb

# Stop proxy
anysql-proxy stop

# Check status
anysql-proxy status

# Configure IDE
anysql-proxy setup <ide>   # cursor | claude-code | windsurf | vscode | zed

# Manage API keys (encrypted at rest)
anysql-proxy keys set openai     sk-...
anysql-proxy keys set anthropic  sk-ant-...
```

---

## Querying Your Data

Data is stored in `~/.anysql/ide.duckdb`. Query it with any DuckDB client:

```bash
# Install DuckDB CLI
pip install duckdb

# Open the database
duckdb ~/.anysql/ide.duckdb
```

```sql
-- Cost by IDE and model
SELECT ide_name, model, SUM(cost_usd) AS total_cost, COUNT(*) AS requests
FROM llm_responses
GROUP BY ide_name, model
ORDER BY total_cost DESC;

-- Latency trends by day
SELECT DATE_TRUNC('day', created_at) AS day,
       AVG(latency_ms)              AS avg_latency_ms,
       COUNT(*)                     AS requests
FROM llm_responses
GROUP BY day
ORDER BY day;

-- Most active files
SELECT file_path, COUNT(*) AS llm_calls
FROM ide_context
WHERE file_path IS NOT NULL
GROUP BY file_path
ORDER BY llm_calls DESC
LIMIT 10;
```

**Schema:**

`llm_responses` — one row per request:
`response_id`, `model`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost_usd`, `latency_ms`, `created_at`

`ide_context` — developer workflow context:
`context_id`, `response_id`, `ide_name`, `request_type`, `file_path`, `language`, `git_repo`, `git_branch`, `lines_of_context`, `has_error_context`, `suggestion_length`, `created_at`

---

## License

Apache 2.0

---

<div align="center">

**anySQL is an [OpenAstra](https://openastra.org) initiative**

[anysql.org](https://anysql.org) · [PyPI](https://pypi.org/project/anysql-proxy/) · [GitHub](https://github.com/sadayamuthu/anySQL) · [Docs](https://docs.anysql.org)

</div>
```

- [ ] **Step 2: Verify required strings are present**

```bash
grep -c "OpenAstra initiative" proxy/README.md  # expect 1
grep -c "localhost:4242" proxy/README.md        # expect >=3
grep -c "anysql-proxy setup" proxy/README.md    # expect >=5 (one per IDE)
grep -c "ide.duckdb" proxy/README.md            # expect >=2
grep -c "anysql-proxy keys set" proxy/README.md # expect >=2
```

All should return non-zero.

- [ ] **Step 3: Commit**

```bash
git add proxy/README.md
git commit -m "docs: write proxy/README.md from placeholder"
```

---

## Summary

| Task | File | Type |
|------|------|------|
| 1 | `README.md` | Rewrite — monorepo index |
| 2 | `sdk/README.md` | Rewrite — correct API + monorepo paths |
| 3 | `proxy/README.md` | New — full proxy reference |
