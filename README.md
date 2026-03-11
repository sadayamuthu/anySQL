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
