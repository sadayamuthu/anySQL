<div align="center">

# anySQL

<h3>SQL Analytics for AI Systems</h3>

<p>From vibes to queries.</p>

[![CI](https://img.shields.io/github/actions/workflow/status/sadayamuthu/anySQL/pr-check.yml?event=pull_request&label=CI&style=flat-square)](https://github.com/sadayamuthu/anySQL/actions/workflows/pr-check.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue?style=flat-square)](https://www.python.org/downloads/)
[![License](https://img.shields.io/github/license/sadayamuthu/anySQL?style=flat-square)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/anysql-sdk?style=flat-square)](https://pypi.org/project/anysql-sdk/)

---

[Quick Start](#quick-start) · [How It Works](#how-it-works) · [5 Use Cases](#the-5-use-cases) · [Installation](#installation) · [CLI Usage](#cli-usage) · [Examples](#examples)

</div>

---

## What is anySQL?

anySQL is an open-source SQL analytics engine for AI systems. It lets engineers query LLM responses, agent traces, and RAG pipelines with standard SQL — powered by DuckDB in-memory, persisted to SQLite, with zero configuration.

AI engineers debug with `print()` statements, JSON log files, and pre-built dashboards that show what the tool designer thought you'd want to see. What's missing is raw SQL over normalized AI telemetry data — specifically the cross-layer JOIN that lets you ask whether your RAG pipeline is failing at retrieval or generation.

---

## Quick Start

```bash
# Install
pip install anysql-sdk

# Install with provider support
pip install "anysql-sdk[openai]"
pip install "anysql-sdk[anthropic]"
pip install "anysql-sdk[all]"        # OpenAI + Anthropic + LangChain
```

```python
import anysql

# Initialize (in-memory by default, or pass a file path for persistence)
db = anysql.init()

# Wrap your OpenAI client — chat.completions.create calls are auto-logged
client = anysql.openai(db).wrap(openai_client)

# Wrap your Anthropic client — messages.create calls are auto-logged
client = anysql.claude(db).wrap(anthropic_client)

# Tag pipeline runs for cost attribution
@anysql.context(feature="search", tags={"version": "v2"})
def run_search(query):
    ...

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
    ├── @anysql.context(feature="x")     ← Python contextvars, sync+async safe
    ├── OpenAI/Claude wrapped client      ← transparent proxy, one-line swap
    ├── AgentTracer                       ← manual tool-call and step tracing
    └── RAGTracer.after_retrieval()       ← auto-detects LangChain/LlamaIndex/dict
              │
              ▼ insert()
    AnySQL engine
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
- Contextvars for async-safe tagging — no manual pass-through required within a task (new threads start with an empty context unless you copy it with `contextvars.copy_context()`)

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
# Run a SQL query against a persisted database (default: ./anysql.db)
anysql query "SELECT model, COUNT(*) FROM llm_responses GROUP BY model"

# Show row counts for all tables
anysql stats

# Query a specific database file
anysql query "SELECT * FROM eval_results LIMIT 10" --db ./myproject.db
```

---

## Examples

Three runnable demos are included in `examples/`. All auto-detect missing API keys and fall back to mock mode. The articles are short samples embedded in each script, written in the style of each dataset's topics — no downloads required.

| Demo | Embedded sample articles | Models |
|------|---------|--------|
| `realtime_openai_demo.py` | 12, BBC News-style topics | `gpt-4o`, `gpt-4o-mini` |
| `realtime_claude_demo.py` | 15, AG News-style topics | `claude-sonnet-4-6`, `claude-haiku-4-5` |
| `realtime_combined_demo.py` | 20, Reuters R8-style topics | All 4 models head-to-head |

```bash
# Run combined demo (works without API keys)
python examples/realtime_combined_demo.py
```

---

## Adapter Usage

### OpenAI

```python
import openai
import anysql

db = anysql.init()
client = anysql.openai(db).wrap(openai.OpenAI())

# chat.completions.create calls are now logged automatically
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Summarize this article..."}]
)
```

### Anthropic

```python
import anthropic
import anysql

db = anysql.init()
client = anysql.claude(db).wrap(anthropic.Anthropic())

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Classify this text..."}]
)
```

### Agent Tracing

```python
tracer = anysql.agent_tracer(db, session_id="sess-001")

# Manual tracing
tracer.trace_tool_call(
    "web_search",
    input={"query": "latest news"},
    output={"results": [...]},
    status="success",
    latency_ms=320,
)
tracer.trace_step("llm_call", description="Summarize results")
```

`AgentTracer` also has `on_tool_start`, `on_tool_end`, `on_tool_error`, `on_agent_action` and `on_agent_finish` methods named after LangChain's callback hooks, which you can call from your own framework code. It does not subclass LangChain's `BaseCallbackHandler`, so passing it in `callbacks=[...]` to LangChain does not work in this release.

### RAG Tracing

```python
rag = anysql.rag_tracer(db)

query = "What is anySQL?"
query_id = rag.before_retrieval(query)
chunks = vectorstore.similarity_search_with_score(query)  # (doc, score) tuples
rag.after_retrieval(query_id=query_id, chunks=chunks)

# Record eval result with cross-layer join key (passed = score >= 0.7)
rag.record_eval(
    query_id=query_id,
    score=0.92,
    actual=answer,
    factuality=0.95,
)
```

---

## Development

```bash
pip install -e ".[dev]"

pytest tests/ -v --tb=short   # Run tests
ruff check anysql/            # Lint
ruff format --check anysql/   # Check formatting (ruff format anysql/ to fix)
```

---

## Repository Structure

```
anySQL/
├── anysql/
│   ├── __init__.py        # Public API surface
│   ├── engine.py          # DuckDB engine + UC analytics methods
│   ├── schema.py          # 6 PyArrow schemas
│   ├── storage.py         # SQLite persistence
│   ├── context.py         # @context decorator + context_scope()
│   ├── cli.py             # CLI entry point
│   ├── adapters/
│   │   ├── openai.py      # OpenAI transparent proxy
│   │   ├── claude.py      # Anthropic transparent proxy
│   │   └── generic.py     # Generic JSON/dict adapter
│   └── tracers/
│       ├── agent.py       # AgentTracer (manual tracing + LangChain-style hooks)
│       └── rag.py         # RAGTracer (LangChain/LlamaIndex/dict)
├── tests/                 # 94 pytest tests
├── examples/              # 3 runnable demos
└── docs/
    └── QUERIES.md         # Canonical SQL query library
```

---

## Contributing

Bug reports, adapters and fixes are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the development setup, the checks CI runs, and how to add an adapter.

---

## Security

Please report vulnerabilities privately through [GitHub security advisories](https://github.com/sadayamuthu/anySQL/security/advisories/new), not in a public issue. See [SECURITY.md](SECURITY.md) for what to include and what's in scope.

---

## License

[Apache License 2.0](LICENSE)

---

<div align="center">

**anySQL is an open-source SQL analytics engine for AI systems**

anySQL is managed by [OpenAstra](https://openastra.org) · [anysql.org](https://anysql.org)

[PyPI](https://pypi.org/project/anysql-sdk/) · [GitHub](https://github.com/sadayamuthu/anySQL) · [Docs](https://docs.anysql.org)

</div>

---
