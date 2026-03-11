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
