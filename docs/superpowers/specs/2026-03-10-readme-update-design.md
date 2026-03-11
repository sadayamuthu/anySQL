# anySQL README Update Design
**Date:** 2026-03-10
**Status:** Approved
**Scope:** Unify README format across root, sdk/, and proxy/

---

## 1. Goal

Bring all three READMEs to the same visual template, fix stale content from the monorepo migration, fill out the empty `proxy/README.md`, and make the OpenAstra attribution consistent everywhere.

---

## 2. Shared Template

All three READMEs use this skeleton:

```
<div align="center">
  # [package name]
  <h3>[tagline]</h3>
  <p>[sub-tagline]</p>
  [badges: CI · Python · License · PyPI]
  ---
  [nav links]
</div>

---

[Sections separated by ---]

---

<div align="center">
  [closing line]
  anySQL is an [OpenAstra](https://openastra.org) initiative · [anysql.org](https://anysql.org)
  [PyPI] · [GitHub] · [Docs]
</div>
```

Footer wording: **"anySQL is an [OpenAstra](https://openastra.org) initiative"** (consistent across all three).

---

## 3. Root README.md

**Role:** Monorepo index — brief overview, no code, links out to package READMEs.

**Badges:** CI · Python 3.10+ · License: Apache 2.0 · PyPI anysql-sdk

**Nav links:** What is anySQL · Packages · Architecture · OpenAstra

### Sections

**What is anySQL?**
Two sentences: SQL analytics engine for AI systems, an OpenAstra initiative. Covers the "why" — engineers need raw SQL over AI telemetry, not pre-built dashboards.

**Packages**

| Package | PyPI | What it does |
|---------|------|--------------|
| `sdk/` | `anysql-sdk` | Wrap LLM clients, trace agents/RAG, query with SQL |
| `proxy/` | `anysql-proxy` | Intercept IDE LLM calls, log usage to local DuckDB |
| `server/` | coming soon | REST API over anySQL data |
| `ui/` | coming soon | Web dashboard |

**Architecture**
One ASCII block showing how SDK + proxy + server + UI relate to each other.

**Footer**
"anySQL is an [OpenAstra](https://openastra.org) initiative"

---

## 4. sdk/README.md

**Role:** Complete standalone reference for `anysql-sdk` PyPI package readers.

**Content:** Same as current root README, with these fixes:
- Title → `anysql-sdk`
- `import anysql` → `import anysql_sdk` throughout Quick Start
- Repository Structure block updated to monorepo layout (`sdk/src/anysql_sdk/`, not old flat `anysql/`)
- Development commands: `cd sdk && pip install -e ".[dev]"`, `ruff check src/anysql_sdk/`
- Footer: "anySQL is an [OpenAstra](https://openastra.org) initiative"

**Sections (unchanged from current):**
What is anySQL · Quick Start · How It Works · 6 Canonical Tables · 5 Use Cases · Installation · CLI Usage · Examples · Adapter Usage · Development · Repository Structure

---

## 5. proxy/README.md

**Role:** Complete standalone reference for `anysql-proxy` PyPI package readers.

**Badges:** CI · Python 3.10+ · License: Apache 2.0 · PyPI anysql-proxy

**Nav links:** What is anysql-proxy · Quick Start · How It Works · IDE Setup · CLI · Querying Your Data

### Sections

**What is anysql-proxy?**
Local HTTP proxy on `localhost:4242`. Intercepts IDE LLM calls (Cursor, Claude Code, Windsurf, VS Code, Zed), logs metadata non-blocking to `~/.anysql/ide.duckdb`, and streams responses back with zero added latency.

**Quick Start**
```bash
pip install anysql-proxy
anysql-proxy keys set openai sk-...     # or anthropic
anysql-proxy start
# then point your IDE at http://localhost:4242
```

**How It Works**
ASCII intercept flow:
```
IDE → POST http://localhost:4242/v1/chat/completions
           ↓
      anysql-proxy
           ↓ logs to ~/.anysql/ide.duckdb (non-blocking)
           ↓ forwards to api.openai.com or api.anthropic.com
           ↓ streams response back
IDE receives tokens with zero added latency
```

**IDE Setup**

| IDE | Command |
|-----|---------|
| Cursor | `anysql-proxy setup cursor` |
| Claude Code | `anysql-proxy setup claude-code` |
| Windsurf | `anysql-proxy setup windsurf` |
| VS Code / Continue | `anysql-proxy setup vscode` |
| Zed | `anysql-proxy setup zed` |

**CLI**

| Command | Description |
|---------|-------------|
| `anysql-proxy start [--port 4242] [--db PATH]` | Start proxy (foreground) |
| `anysql-proxy stop` | Send SIGTERM to stored PID |
| `anysql-proxy status` | Check if proxy is running |
| `anysql-proxy setup <ide>` | Configure IDE automatically |
| `anysql-proxy keys set <provider> <key>` | Store encrypted API key |

**Querying Your Data**
2–3 example DuckDB SQL queries against `~/.anysql/ide.duckdb`:
```sql
-- Cost by IDE and model
SELECT ide_name, model, SUM(cost_usd) AS total_cost
FROM llm_responses
GROUP BY ide_name, model
ORDER BY total_cost DESC;

-- Latency trends by day
SELECT DATE_TRUNC('day', created_at) AS day, AVG(latency_ms) AS avg_latency_ms
FROM llm_responses
GROUP BY day ORDER BY day;
```

**Footer**
"anySQL is an [OpenAstra](https://openastra.org) initiative"

---

## 6. Files Changed

| File | Action |
|------|--------|
| `README.md` | Rewrite to monorepo index |
| `sdk/README.md` | Fix stale imports/paths, update footer |
| `proxy/README.md` | Full write from placeholder |
