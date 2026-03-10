# anySQL — Complete Design & Implementation Guide
> Execute this document in Claude Code to build the full anySQL package from scratch.

---

## Project Overview

**anySQL** is an open-source SQL analytics engine for AI systems.  
It lets engineers query LLM responses, agent traces, and RAG pipelines with standard SQL — powered by DuckDB in-memory, persisted to SQLite, with zero configuration.

**Tagline:** *"From vibes to queries."*

**Website:** anysql.org  
**License:** Apache 2.0  
**Stack:** Python 3.10+, DuckDB, PyArrow, SQLite (stdlib), Pandas

---

## Problem Statement

Every AI engineer today debugs with:
- `print()` statements on LLM outputs
- JSON log files grepped with `jq`
- Spreadsheets manually assembled from API usage dashboards
- Pre-built dashboards in Langfuse/Phoenix that show what the tool *designer* thought you'd want to know

**What's missing:** raw SQL over normalized AI telemetry data. Nobody exposes this.

The cross-layer JOIN nobody has built:
```sql
SELECT r.query_id, MAX(r.similarity_score) AS retrieval_quality, e.score AS answer_quality
FROM rag.chunks r
JOIN eval.results e ON r.query_id = e.query_id
GROUP BY r.query_id, e.score
```
This query reveals whether your RAG pipeline is failing at retrieval or generation. It requires joining two tables that no existing tool puts in the same queryable store.

---

## Architecture

```
User Code (Python)
    │
    ├── @anysql.context(feature="x")          ← context.py  (Python contextvars)
    ├── wrapped OpenAI / Claude client         ← adapters/   (proxy wrappers)
    ├── AgentTracer (LangChain callback)       ← tracers/agent.py
    └── RAGTracer.after_retrieval()            ← tracers/rag.py
              │
              ▼
    AnySQL.insert() ──→ SQLite (storage.py)   [persistence across sessions]
    AnySQL.query()  ──→ DuckDB (engine.py)    [in-memory SQL over Arrow tables]
              │
              ▼
    6 Canonical PyArrow Tables (schema.py)
    ├── llm.responses      (UC1, UC2)
    ├── eval.results       (UC1, UC2, UC5)
    ├── pipeline.runs      (UC3)
    ├── agent.tool_calls   (UC4)
    ├── agent.trace        (UC4)
    └── rag.chunks         (UC5)
```

---

## Repository Structure

```
anysql/
├── anysql/
│   ├── __init__.py          # Public API surface
│   ├── engine.py            # DuckDB wrapper + convenience query methods
│   ├── schema.py            # 6 PyArrow schema definitions
│   ├── storage.py           # SQLite persistence layer
│   ├── context.py           # @context decorator + contextvars
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── openai.py        # OpenAI client proxy wrapper
│   │   ├── claude.py        # Anthropic client proxy wrapper
│   │   └── generic.py       # Generic JSON/dict adapter
│   ├── tracers/
│   │   ├── __init__.py
│   │   ├── agent.py         # LangChain callback + manual tracer
│   │   └── rag.py           # RAG retrieval tracer
│   └── cli.py               # CLI: anysql query / anysql stats
├── tests/
│   ├── __init__.py
│   ├── test_engine.py
│   ├── test_schema.py
│   ├── test_storage.py
│   ├── test_adapters.py
│   └── test_tracers.py
├── examples/
│   ├── realtime_openai_demo.py    # BBC News dataset, all 5 UCs
│   ├── realtime_claude_demo.py    # AG News dataset, all 5 UCs
│   └── realtime_combined_demo.py  # Reuters R8, OpenAI vs Claude head-to-head
├── docs/
│   └── QUERIES.md           # Canonical SQL query library
├── pyproject.toml
├── README.md
└── ANYSQL_CLAUDE_CODE.md    # This file
```

---

## Dependencies

```toml
[project.dependencies]
duckdb   = ">=0.10.0"
pyarrow  = ">=14.0.0"
pandas   = ">=2.0.0"

[project.optional-dependencies]
openai    = ["openai>=1.0.0"]
anthropic = ["anthropic>=0.25.0"]
langchain = ["langchain>=0.2.0"]
all       = ["openai>=1.0.0", "anthropic>=0.25.0", "langchain>=0.2.0"]
dev       = ["pytest>=8.0.0", "pytest-asyncio", "black", "ruff"]
```

Install:
```bash
pip install duckdb pyarrow pandas openai anthropic
```

---

## File 1: `anysql/schema.py`

**Purpose:** Define the 6 canonical PyArrow schemas. These are the contracts all adapters must normalize to. Schema changes are versioned.

```python
"""
anysql/schema.py
Canonical PyArrow schema definitions for all 6 anySQL tables.
All adapters must normalize their provider-specific outputs to these schemas.
"""

import pyarrow as pa

# ─── UC1 + UC2: LLM Responses ────────────────────────────────────────────────
LLM_RESPONSES_SCHEMA = pa.schema([
    pa.field("response_id",       pa.string(),       nullable=False),  # UUID or provider ID
    pa.field("model",             pa.string(),       nullable=False),  # "gpt-4o", "claude-sonnet-4-6"
    pa.field("model_version",     pa.string(),       nullable=True),   # provider version string
    pa.field("prompt",            pa.string(),       nullable=False),  # last user message
    pa.field("content",           pa.string(),       nullable=True),   # assistant response text
    pa.field("prompt_tokens",     pa.int32(),        nullable=True),
    pa.field("completion_tokens", pa.int32(),        nullable=True),
    pa.field("total_tokens",      pa.int32(),        nullable=True),
    pa.field("cost_usd",          pa.float64(),      nullable=True),   # calculated from token pricing
    pa.field("latency_ms",        pa.int32(),        nullable=True),   # wall-clock time
    pa.field("stop_reason",       pa.string(),       nullable=True),   # "stop","length","tool_use","end_turn"
    pa.field("task_type",         pa.string(),       nullable=True),   # "summarization","code","classification"
    pa.field("session_id",        pa.string(),       nullable=True),
    pa.field("created_at",        pa.timestamp("ms"),nullable=False),
])

# ─── UC1 + UC2 + UC5: Eval Results ───────────────────────────────────────────
EVAL_RESULTS_SCHEMA = pa.schema([
    pa.field("eval_id",             pa.string(),       nullable=False),
    pa.field("response_id",         pa.string(),       nullable=True),  # FK → llm.responses
    pa.field("run_id",              pa.string(),       nullable=True),  # FK → pipeline.runs
    pa.field("query_id",            pa.string(),       nullable=True),  # FK → rag.chunks (UC5 join key)
    pa.field("prompt_id",           pa.string(),       nullable=True),  # logical prompt name
    pa.field("prompt_version",      pa.string(),       nullable=True),  # "v1","v2" for regression
    pa.field("prompt_hash",         pa.string(),       nullable=True),  # git-style hash of prompt text
    pa.field("model",               pa.string(),       nullable=True),
    pa.field("expected",            pa.string(),       nullable=True),
    pa.field("actual",              pa.string(),       nullable=True),
    pa.field("score",               pa.float64(),      nullable=True),  # 0.0–1.0
    pa.field("passed",              pa.bool_(),        nullable=True),
    pa.field("score_factuality",    pa.float64(),      nullable=True),  # dimensional scores
    pa.field("score_tone",          pa.float64(),      nullable=True),
    pa.field("score_safety",        pa.float64(),      nullable=True),
    pa.field("score_completeness",  pa.float64(),      nullable=True),
    pa.field("dimension",           pa.string(),       nullable=True),
    pa.field("query_topic_cluster", pa.string(),       nullable=True),  # for UC4 category analysis
    pa.field("evaluated_at",        pa.timestamp("ms"),nullable=False),
])

# ─── UC3: Pipeline Runs ───────────────────────────────────────────────────────
PIPELINE_RUNS_SCHEMA = pa.schema([
    pa.field("run_id",             pa.string(),       nullable=False),
    pa.field("session_id",         pa.string(),       nullable=True),
    pa.field("feature_flag",       pa.string(),       nullable=True),  # @context(feature="x") tag
    pa.field("user_segment",       pa.string(),       nullable=True),  # @context(segment="y") tag
    pa.field("pipeline_name",      pa.string(),       nullable=True),
    pa.field("total_tokens",       pa.int32(),        nullable=True),
    pa.field("total_cost_usd",     pa.float64(),      nullable=True),
    pa.field("total_latency_ms",   pa.int32(),        nullable=True),
    pa.field("step_count",         pa.int32(),        nullable=True),
    pa.field("status",             pa.string(),       nullable=True),  # "success","error","timeout"
    pa.field("revenue_attributed", pa.float64(),      nullable=True),  # optional business join
    pa.field("tags",               pa.map_(pa.string(), pa.string()), nullable=True),
    pa.field("started_at",         pa.timestamp("ms"),nullable=False),
    pa.field("ended_at",           pa.timestamp("ms"),nullable=True),
])

# ─── UC4: Agent Tool Calls ────────────────────────────────────────────────────
AGENT_TOOL_CALLS_SCHEMA = pa.schema([
    pa.field("call_id",        pa.string(),       nullable=False),
    pa.field("session_id",     pa.string(),       nullable=False),
    pa.field("step_order",     pa.int32(),        nullable=False),
    pa.field("tool_name",      pa.string(),       nullable=False),
    pa.field("tool_input",     pa.string(),       nullable=True),   # JSON string
    pa.field("tool_output",    pa.string(),       nullable=True),   # JSON string
    pa.field("status",         pa.string(),       nullable=False),  # "success","error","timeout"
    pa.field("error_message",  pa.string(),       nullable=True),
    pa.field("latency_ms",     pa.int32(),        nullable=True),
    pa.field("human_override", pa.bool_(),        nullable=True),
    pa.field("called_at",      pa.timestamp("ms"),nullable=False),
])

# ─── UC4: Agent Trace (full session replay) ───────────────────────────────────
AGENT_TRACE_SCHEMA = pa.schema([
    pa.field("trace_id",                  pa.string(),       nullable=False),
    pa.field("session_id",                pa.string(),       nullable=False),
    pa.field("step_order",                pa.int32(),        nullable=False),
    pa.field("step_type",                 pa.string(),       nullable=True),  # "llm_call","tool_call","human"
    pa.field("step_description",          pa.string(),       nullable=True),
    pa.field("input_summary",             pa.string(),       nullable=True),
    pa.field("output_summary",            pa.string(),       nullable=True),
    pa.field("human_override",            pa.bool_(),        nullable=True),
    pa.field("time_to_intervention_ms",   pa.int32(),        nullable=True),
    pa.field("timestamp",                 pa.timestamp("ms"),nullable=False),
])

# ─── UC5: RAG Chunks ──────────────────────────────────────────────────────────
RAG_CHUNKS_SCHEMA = pa.schema([
    pa.field("retrieval_id",    pa.string(),       nullable=False),
    pa.field("query_id",        pa.string(),       nullable=False),  # links to eval.results.query_id
    pa.field("session_id",      pa.string(),       nullable=True),
    pa.field("chunk_id",        pa.string(),       nullable=False),
    pa.field("source_doc",      pa.string(),       nullable=True),
    pa.field("chunk_text",      pa.string(),       nullable=True),
    pa.field("similarity_score",pa.float64(),      nullable=True),
    pa.field("rank",            pa.int32(),        nullable=True),
    pa.field("chunks_retrieved",pa.int32(),        nullable=True),
    pa.field("embedding_model", pa.string(),       nullable=True),
    pa.field("retrieved_at",    pa.timestamp("ms"),nullable=False),
])

# ─── Registry ─────────────────────────────────────────────────────────────────
SCHEMAS = {
    "llm.responses":    LLM_RESPONSES_SCHEMA,
    "eval.results":     EVAL_RESULTS_SCHEMA,
    "pipeline.runs":    PIPELINE_RUNS_SCHEMA,
    "agent.tool_calls": AGENT_TOOL_CALLS_SCHEMA,
    "agent.trace":      AGENT_TRACE_SCHEMA,
    "rag.chunks":       RAG_CHUNKS_SCHEMA,
}

TABLE_NAMES = list(SCHEMAS.keys())
```

---

## File 2: `anysql/storage.py`

**Purpose:** SQLite persistence. Rows stored as JSON. Enables cross-session prompt regression detection (UC2). Swap to Parquet/S3 in Phase 5.

```python
"""
anysql/storage.py
SQLite persistence layer — rows stored as JSON blobs.
Schema enforcement happens at the Arrow layer in engine.py, not here.
"""

import json
import sqlite3
from typing import Optional
from .schema import TABLE_NAMES


class Storage:
    def __init__(self, db_path: str = "anysql.db"):
        self._in_memory = (db_path == ":memory:")
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_tables()

    def save(self, table: str, records: list[dict]) -> None:
        if self._in_memory or not records:
            return
        sql_table = self._sql_table(table)
        cur = self._conn.cursor()
        cur.executemany(
            f"INSERT INTO {sql_table} (data) VALUES (?)",
            [(json.dumps(r, default=str),) for r in records],
        )
        self._conn.commit()

    def load(self, table: str) -> list[dict]:
        if self._in_memory:
            return []
        sql_table = self._sql_table(table)
        cur = self._conn.cursor()
        cur.execute(f"SELECT data FROM {sql_table}")
        return [json.loads(r[0]) for r in cur.fetchall()]

    def delete(self, table: str, where: Optional[str] = None) -> int:
        sql_table = self._sql_table(table)
        cur = self._conn.cursor()
        if where:
            cur.execute(f"DELETE FROM {sql_table} WHERE {where}")
        else:
            cur.execute(f"DELETE FROM {sql_table}")
        self._conn.commit()
        return cur.rowcount

    def row_count(self, table: str) -> int:
        sql_table = self._sql_table(table)
        cur = self._conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {sql_table}")
        return cur.fetchone()[0]

    def _init_tables(self) -> None:
        cur = self._conn.cursor()
        for table in TABLE_NAMES:
            sql_table = self._sql_table(table)
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {sql_table} (
                    id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                )
            """)
        self._conn.commit()

    @staticmethod
    def _sql_table(table: str) -> str:
        return table.replace(".", "_")

    def close(self) -> None:
        self._conn.close()
```

---

## File 3: `anysql/engine.py`

**Purpose:** DuckDB query engine. Registers Arrow tables as views. Exposes `query()` and convenience methods for all 5 UCs.

```python
"""
anysql/engine.py
DuckDB-powered SQL engine over canonical Arrow tables.
"""

import duckdb
import pyarrow as pa
import pandas as pd
from typing import Optional, Union

from .schema import SCHEMAS, TABLE_NAMES
from .storage import Storage


class AnySQL:
    def __init__(self, db_path: str = ":memory:", echo: bool = False):
        self._conn = duckdb.connect()
        self._storage = Storage(db_path)
        self._echo = echo
        self._buffers: dict[str, list[dict]] = {t: [] for t in TABLE_NAMES}
        self._arrow_tables: dict[str, pa.Table] = {}
        self._init_tables()
        self._load_persisted()

    # ── Public API ─────────────────────────────────────────────────────────────

    def query(self, sql: str, as_df: bool = True) -> Union[pd.DataFrame, duckdb.DuckDBPyRelation]:
        """
        Execute SQL over anySQL tables.

        Table names in SQL:
          llm_responses, eval_results, pipeline_runs,
          agent_tool_calls, agent_trace, rag_chunks

        Args:
            sql:   SQL string
            as_df: Return pandas DataFrame (True) or DuckDB relation (False)

        Example:
            db.query('''
              SELECT model, AVG(cost_usd) as avg_cost, AVG(score) as avg_score
              FROM llm_responses r
              JOIN eval_results e ON r.response_id = e.response_id
              GROUP BY model ORDER BY avg_score DESC
            ''')
        """
        if self._echo:
            print(f"[anySQL SQL] {sql.strip()}")
        self._refresh_views()
        rel = self._conn.sql(sql)
        return rel.df() if as_df else rel

    def insert(self, table: str, records: list[dict]) -> None:
        """Insert records into a canonical table. Persists to SQLite."""
        if table not in TABLE_NAMES:
            raise ValueError(f"Unknown table '{table}'. Valid: {TABLE_NAMES}")
        self._buffers[table].extend(records)
        self._storage.save(table, records)

    def tables(self) -> list[str]:
        return TABLE_NAMES

    def count(self, table: str) -> int:
        view = self._table_to_view(table)
        self._refresh_views()
        return self._conn.sql(f"SELECT COUNT(*) FROM {view}").fetchone()[0]

    def clear(self, table: Optional[str] = None) -> None:
        targets = [table] if table else TABLE_NAMES
        for t in targets:
            self._buffers[t] = []
            self._arrow_tables.pop(t, None)
        self._init_tables()

    # ── UC1: Multi-Model Comparison ────────────────────────────────────────────

    def model_comparison(self) -> pd.DataFrame:
        """Compare models by quality, cost, latency, and quality-per-dollar."""
        return self.query("""
            SELECT
                r.model,
                COUNT(*)                                              AS calls,
                ROUND(AVG(r.cost_usd), 6)                            AS avg_cost_usd,
                ROUND(AVG(r.latency_ms), 1)                          AS avg_latency_ms,
                ROUND(AVG(e.score), 3)                               AS avg_eval_score,
                ROUND(AVG(e.score) / NULLIF(AVG(r.cost_usd), 0), 2) AS quality_per_dollar
            FROM llm_responses r
            LEFT JOIN eval_results e ON r.response_id = e.response_id
            GROUP BY r.model
            ORDER BY avg_eval_score DESC
        """)

    def model_by_task(self) -> pd.DataFrame:
        """Best model per task type — generates empirical routing table."""
        return self.query("""
            SELECT r.model, r.task_type,
                   COUNT(*)                  AS calls,
                   ROUND(AVG(e.score), 3)    AS avg_score,
                   ROUND(AVG(r.cost_usd), 6) AS avg_cost
            FROM llm_responses r
            JOIN eval_results e ON r.response_id = e.response_id
            WHERE r.task_type IS NOT NULL
            GROUP BY r.model, r.task_type
            ORDER BY r.task_type, avg_score DESC
        """)

    # ── UC2: Prompt Regression Detection ──────────────────────────────────────

    def prompt_regressions(self, threshold: float = -0.10) -> pd.DataFrame:
        """Find prompts whose score dropped between versions."""
        return self.query(f"""
            WITH version_scores AS (
                SELECT prompt_id, prompt_version,
                       AVG(score) AS avg_score,
                       evaluated_at
                FROM eval_results
                WHERE prompt_id IS NOT NULL
                GROUP BY prompt_id, prompt_version, evaluated_at
            ),
            with_prev AS (
                SELECT *,
                    LAG(avg_score) OVER (
                        PARTITION BY prompt_id ORDER BY evaluated_at
                    ) AS prev_score
                FROM version_scores
            )
            SELECT prompt_id, prompt_version,
                   ROUND(avg_score, 3)              AS current_score,
                   ROUND(prev_score, 3)             AS previous_score,
                   ROUND(avg_score - prev_score, 3) AS delta
            FROM with_prev
            WHERE (avg_score - prev_score) < {threshold}
            ORDER BY delta ASC
        """)

    def eval_debt(self) -> pd.DataFrame:
        """Prompts modified after last eval — your unvalidated changes."""
        return self.query("""
            SELECT prompt_id,
                   MAX(evaluated_at)  AS last_evaluated,
                   COUNT(eval_id)     AS total_evals,
                   ROUND(AVG(score), 3) AS avg_score
            FROM eval_results
            WHERE prompt_id IS NOT NULL
            GROUP BY prompt_id
            ORDER BY last_evaluated ASC
        """)

    def silent_degradation(self) -> pd.DataFrame:
        """Detect slow score drift over 8-week rolling window."""
        return self.query("""
            SELECT prompt_id,
                   DATE_TRUNC('week', evaluated_at) AS week,
                   ROUND(AVG(score), 3)             AS weekly_score
            FROM eval_results
            WHERE prompt_id IS NOT NULL
            GROUP BY prompt_id, week
            ORDER BY prompt_id, week
        """)

    # ── UC3: Cost Attribution ──────────────────────────────────────────────────

    def cost_by_feature(self) -> pd.DataFrame:
        """Token spend and ROI broken down by feature flag and user segment."""
        return self.query("""
            SELECT feature_flag, user_segment,
                   COUNT(*)                                                    AS runs,
                   ROUND(SUM(total_cost_usd), 4)                              AS total_cost_usd,
                   ROUND(AVG(total_cost_usd), 6)                              AS avg_cost_per_run,
                   ROUND(SUM(revenue_attributed), 2)                          AS revenue,
                   ROUND(SUM(revenue_attributed) / NULLIF(SUM(total_cost_usd), 0), 2) AS roi
            FROM pipeline_runs
            GROUP BY feature_flag, user_segment
            ORDER BY total_cost_usd DESC
        """)

    def cost_anomalies(self, multiplier: float = 2.0) -> pd.DataFrame:
        """Features where cost doubled vs 7-day rolling average."""
        return self.query(f"""
            SELECT feature_flag,
                   DATE_TRUNC('day', started_at)  AS date,
                   ROUND(SUM(total_cost_usd), 6)  AS daily_cost,
                   ROUND(AVG(SUM(total_cost_usd)) OVER (
                       PARTITION BY feature_flag
                       ORDER BY DATE_TRUNC('day', started_at)
                       ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
                   ), 6)                          AS rolling_7d_avg,
                   ROUND(SUM(total_cost_usd) / NULLIF(AVG(SUM(total_cost_usd)) OVER (
                       PARTITION BY feature_flag
                       ORDER BY DATE_TRUNC('day', started_at)
                       ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
                   ), 0), 2)                      AS cost_ratio
            FROM pipeline_runs
            GROUP BY feature_flag, date
            HAVING cost_ratio > {multiplier}
            ORDER BY cost_ratio DESC
        """)

    # ── UC4: Agent Debugging ───────────────────────────────────────────────────

    def tool_failure_rates(self) -> pd.DataFrame:
        """Rank tools by failure rate and latency."""
        return self.query("""
            SELECT tool_name,
                   COUNT(*)                                                           AS invocations,
                   SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END)                 AS failures,
                   ROUND(100.0 * SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END)
                         / COUNT(*), 2)                                               AS failure_rate_pct,
                   ROUND(AVG(latency_ms), 1)                                          AS avg_latency_ms
            FROM agent_tool_calls
            GROUP BY tool_name
            ORDER BY failure_rate_pct DESC
        """)

    def loop_detector(self, min_calls: int = 5) -> pd.DataFrame:
        """Sessions where the same tool was called 5+ times — likely infinite loops."""
        return self.query(f"""
            SELECT session_id, tool_name,
                   COUNT(*)                              AS call_count,
                   MAX(step_order) - MIN(step_order)     AS step_span
            FROM agent_tool_calls
            GROUP BY session_id, tool_name
            HAVING call_count >= {min_calls}
            ORDER BY call_count DESC
        """)

    def session_diff(self, session_a: str, session_b: str) -> pd.DataFrame:
        """Where two sessions diverged — success vs failure path comparison."""
        return self.query(f"""
            SELECT a.step_order,
                   a.tool_name AS session_a_tool,
                   b.tool_name AS session_b_tool
            FROM agent_tool_calls a
            JOIN agent_tool_calls b ON a.step_order = b.step_order
            WHERE a.session_id = '{session_a}'
              AND b.session_id = '{session_b}'
              AND a.tool_name != b.tool_name
            ORDER BY a.step_order
        """)

    def human_intervention_points(self) -> pd.DataFrame:
        """Steps where humans override the agent most — fine-tuning targets."""
        return self.query("""
            SELECT step_description,
                   COUNT(*) AS overrides,
                   ROUND(AVG(time_to_intervention_ms), 0) AS avg_response_ms
            FROM agent_trace
            WHERE human_override = true
            GROUP BY step_description
            ORDER BY overrides DESC
        """)

    # ── UC5: RAG Forensics ─────────────────────────────────────────────────────

    def rag_failure_modes(self) -> pd.DataFrame:
        """
        Classify each query into:
          retrieval_failure  — bad chunks AND bad answer
          generation_failure — good chunks BUT bad answer
          lucky_generation   — bad chunks BUT good answer
          success            — good chunks AND good answer
        """
        return self.query("""
            SELECT failure_mode,
                   COUNT(*)                       AS queries,
                   ROUND(AVG(answer_quality), 3)  AS avg_quality
            FROM (
                SELECT r.query_id,
                       MAX(r.similarity_score)  AS best_chunk_score,
                       e.score                  AS answer_quality,
                       CASE
                         WHEN MAX(r.similarity_score) < 0.7 AND e.score < 0.6
                           THEN 'retrieval_failure'
                         WHEN MAX(r.similarity_score) >= 0.7 AND e.score < 0.6
                           THEN 'generation_failure'
                         WHEN MAX(r.similarity_score) < 0.7 AND e.score >= 0.8
                           THEN 'lucky_generation'
                         ELSE 'success'
                       END AS failure_mode
                FROM rag_chunks r
                JOIN eval_results e ON r.query_id = e.query_id
                GROUP BY r.query_id, e.score
            )
            GROUP BY failure_mode
            ORDER BY queries DESC
        """)

    def chunk_quality_ranking(self) -> pd.DataFrame:
        """Rank source documents by the answer quality they produce when retrieved."""
        return self.query("""
            SELECT r.source_doc,
                   COUNT(DISTINCT r.query_id)        AS queries,
                   ROUND(AVG(r.similarity_score), 3) AS avg_retrieval_score,
                   ROUND(AVG(e.score), 3)             AS avg_answer_quality
            FROM rag_chunks r
            JOIN eval_results e ON r.query_id = e.query_id
            GROUP BY r.source_doc
            ORDER BY avg_answer_quality ASC
        """)

    def similarity_calibration(self) -> pd.DataFrame:
        """Does high retrieval similarity actually predict good answers?"""
        return self.query("""
            SELECT ROUND(MAX(r.similarity_score), 1) AS score_bucket,
                   COUNT(*)                           AS queries,
                   ROUND(AVG(e.score), 3)             AS avg_answer_quality
            FROM rag_chunks r
            JOIN eval_results e ON r.query_id = e.query_id
            GROUP BY score_bucket
            ORDER BY score_bucket DESC
        """)

    # ── Internal ───────────────────────────────────────────────────────────────

    def _init_tables(self) -> None:
        for table_name, schema in SCHEMAS.items():
            empty = pa.table({f.name: pa.array([], type=f.type) for f in schema})
            self._arrow_tables[table_name] = empty
            view = self._table_to_view(table_name)
            self._conn.register(view, empty)

    def _load_persisted(self) -> None:
        for table in TABLE_NAMES:
            records = self._storage.load(table)
            if records:
                self._buffers[table].extend(records)
        self._refresh_views()

    def _refresh_views(self) -> None:
        for table_name, schema in SCHEMAS.items():
            rows = self._buffers[table_name]
            if not rows:
                continue
            try:
                arrow_table = pa.Table.from_pylist(rows, schema=schema)
                self._arrow_tables[table_name] = arrow_table
                view = self._table_to_view(table_name)
                self._conn.register(view, arrow_table)
            except Exception as e:
                print(f"[anySQL] Warning: {table_name}: {e}")

    @staticmethod
    def _table_to_view(table: str) -> str:
        return table.replace(".", "_")

    def __repr__(self) -> str:
        counts = {t: len(self._buffers[t]) for t in TABLE_NAMES}
        return f"AnySQL(rows={counts})"
```

---

## File 4: `anysql/context.py`

**Purpose:** `@context` decorator and `context_scope()` context manager using Python `contextvars`. Tags all LLM calls within scope for UC3 cost attribution. Thread-safe and async-safe.

```python
"""
anysql/context.py
Cost attribution via Python contextvars.
Works across sync, async, and threaded code without any setup.
"""

import uuid
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Optional, Callable

_current_run_id     = ContextVar("run_id",      default=None)
_current_feature    = ContextVar("feature",     default=None)
_current_segment    = ContextVar("segment",     default=None)
_current_session_id = ContextVar("session_id",  default=None)
_current_pipeline   = ContextVar("pipeline",    default=None)
_current_tags       = ContextVar("tags",        default={})

_engine = None  # set by anysql.init()


def get_context() -> dict:
    return {
        "run_id":        _current_run_id.get(),
        "feature_flag":  _current_feature.get(),
        "user_segment":  _current_segment.get(),
        "session_id":    _current_session_id.get(),
        "pipeline_name": _current_pipeline.get(),
        "tags":          _current_tags.get(),
    }


def _set_context(feature=None, segment=None, session_id=None, pipeline=None, tags=None):
    tokens = {}
    if feature    is not None: tokens["feature"]    = _current_feature.set(feature)
    if segment    is not None: tokens["segment"]    = _current_segment.set(segment)
    if session_id is not None: tokens["session_id"] = _current_session_id.set(session_id)
    if pipeline   is not None: tokens["pipeline"]   = _current_pipeline.set(pipeline)
    if tags       is not None: tokens["tags"]       = _current_tags.set({**_current_tags.get(), **tags})
    tokens["run_id"] = _current_run_id.set(str(uuid.uuid4()))
    return tokens


def _reset_context(tokens):
    for key, token in tokens.items():
        var = dict(feature=_current_feature, segment=_current_segment,
                   session_id=_current_session_id, pipeline=_current_pipeline,
                   tags=_current_tags, run_id=_current_run_id).get(key)
        if var:
            var.reset(token)


def context(feature=None, segment=None, session_id=None, pipeline=None, tags=None):
    """
    Decorator — tags all LLM calls within the function for cost attribution.

    Usage:
        @anysql.context(feature="premium_summarizer", segment="enterprise")
        def summarize(text: str) -> str:
            return openai_client.chat.completions.create(...)
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            tokens = _set_context(feature, segment, session_id, pipeline, tags)
            start = time.monotonic()
            try:
                return fn(*args, **kwargs)
            finally:
                _flush_run(int((time.monotonic() - start) * 1000))
                _reset_context(tokens)

        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            tokens = _set_context(feature, segment, session_id, pipeline, tags)
            start = time.monotonic()
            try:
                return await fn(*args, **kwargs)
            finally:
                _flush_run(int((time.monotonic() - start) * 1000))
                _reset_context(tokens)

        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper

    return decorator


@contextmanager
def context_scope(feature=None, segment=None, session_id=None, pipeline=None, tags=None):
    """
    Context manager version — for notebooks and inline code.

    Usage:
        with anysql.context_scope(feature="rag_search", segment="free"):
            result = my_rag_pipeline(query)
    """
    tokens = _set_context(feature, segment, session_id, pipeline, tags)
    start = time.monotonic()
    try:
        yield get_context()
    finally:
        _flush_run(int((time.monotonic() - start) * 1000))
        _reset_context(tokens)


def _set_engine(engine):
    global _engine
    _engine = engine


def _flush_run(elapsed_ms: int):
    if _engine is None:
        return
    ctx = get_context()
    if not any([ctx["feature_flag"], ctx["pipeline_name"]]):
        return
    from datetime import datetime, timezone
    _engine.insert("pipeline.runs", [{
        "run_id":           ctx["run_id"] or str(uuid.uuid4()),
        "session_id":       ctx["session_id"],
        "feature_flag":     ctx["feature_flag"],
        "user_segment":     ctx["user_segment"],
        "pipeline_name":    ctx["pipeline_name"],
        "total_latency_ms": elapsed_ms,
        "status":           "success",
        "tags":             ctx["tags"],
        "started_at":       datetime.now(timezone.utc).isoformat(),
    }])
```

---

## File 5: `anysql/adapters/openai.py`

**Purpose:** Transparent proxy wrapper for the OpenAI client. One-line swap, all calls auto-logged.

```python
"""
anysql/adapters/openai.py
OpenAI transparent proxy wrapper.

Usage:
    from openai import OpenAI
    import anysql

    db = anysql.init("myproject.db")
    client = anysql.openai(db).wrap(OpenAI())

    # Use exactly as before — all calls auto-logged to llm.responses
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Summarize this article..."}]
    )
"""

import uuid
import time
from datetime import datetime, timezone
from typing import Optional

# Pricing: USD per 1M tokens
OPENAI_PRICING = {
    "gpt-4o":       {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":  {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":  {"input": 10.00, "output": 30.00},
    "gpt-4":        {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo":{"input": 0.50,  "output": 1.50},
    "o1":           {"input": 15.00, "output": 60.00},
    "o1-mini":      {"input": 3.00,  "output": 12.00},
    "o3-mini":      {"input": 1.10,  "output": 4.40},
}


def _calc_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    # Match by prefix to handle dated version suffixes like "gpt-4o-2024-11-20"
    for key, pricing in OPENAI_PRICING.items():
        if model.startswith(key):
            return (prompt_tokens * pricing["input"] + completion_tokens * pricing["output"]) / 1_000_000
    return None


class _WrappedCompletions:
    def __init__(self, completions, db, task_type=None):
        self._completions = completions
        self._db = db
        self._task_type = task_type

    def create(self, **kwargs):
        from ..context import get_context
        start = time.monotonic()
        response = self._completions.create(**kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)

        ctx = get_context()
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        prompt = messages[-1]["content"] if messages else ""

        usage = getattr(response, "usage", None)
        pt = getattr(usage, "prompt_tokens", 0) or 0
        ct = getattr(usage, "completion_tokens", 0) or 0

        choice = response.choices[0] if response.choices else None

        self._db.insert("llm.responses", [{
            "response_id":        response.id or str(uuid.uuid4()),
            "model":              model,
            "model_version":      getattr(response, "model", model),
            "prompt":             prompt if isinstance(prompt, str) else str(prompt),
            "content":            choice.message.content if choice else None,
            "prompt_tokens":      pt,
            "completion_tokens":  ct,
            "total_tokens":       pt + ct,
            "cost_usd":           _calc_cost(model, pt, ct),
            "latency_ms":         latency_ms,
            "stop_reason":        choice.finish_reason if choice else None,
            "task_type":          self._task_type or ctx.get("tags", {}).get("task_type"),
            "session_id":         ctx.get("session_id"),
            "created_at":         datetime.now(timezone.utc).isoformat(),
        }])
        return response


class _WrappedChat:
    def __init__(self, chat, db, task_type=None):
        self.completions = _WrappedCompletions(chat.completions, db, task_type)


class OpenAIAdapter:
    def __init__(self, db, task_type: Optional[str] = None):
        self._db = db
        self._task_type = task_type

    def wrap(self, client):
        return _WrappedOpenAIClient(client, self._db, self._task_type)


class _WrappedOpenAIClient:
    def __init__(self, client, db, task_type=None):
        self._client = client
        self.chat = _WrappedChat(client.chat, db, task_type)

    def __getattr__(self, name):
        return getattr(self._client, name)
```

---

## File 6: `anysql/adapters/claude.py`

**Purpose:** Transparent proxy wrapper for the Anthropic client.

```python
"""
anysql/adapters/claude.py
Anthropic Claude transparent proxy wrapper.

Usage:
    import anthropic
    import anysql

    db = anysql.init("myproject.db")
    client = anysql.claude(db).wrap(anthropic.Anthropic())

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Summarize this..."}]
    )
"""

import uuid
import time
from datetime import datetime, timezone
from typing import Optional

ANTHROPIC_PRICING = {
    "claude-opus-4-6":   {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6": {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5":  {"input": 0.80,  "output": 4.00},
    "claude-3-5-sonnet": {"input": 3.00,  "output": 15.00},
    "claude-3-5-haiku":  {"input": 0.80,  "output": 4.00},
    "claude-3-opus":     {"input": 15.00, "output": 75.00},
}


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    for key, pricing in ANTHROPIC_PRICING.items():
        if key in model or model.startswith(key):
            return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    return None


class _WrappedMessages:
    def __init__(self, messages, db, task_type=None):
        self._messages = messages
        self._db = db
        self._task_type = task_type

    def create(self, **kwargs):
        from ..context import get_context
        start = time.monotonic()
        response = self._messages.create(**kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)

        ctx = get_context()
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        prompt = messages[-1]["content"] if messages else ""
        if isinstance(prompt, list):
            prompt = " ".join(b.get("text","") if isinstance(b, dict) else str(b) for b in prompt)

        usage = getattr(response, "usage", None)
        it = getattr(usage, "input_tokens", 0) or 0
        ot = getattr(usage, "output_tokens", 0) or 0

        content = "".join(
            block.text for block in getattr(response, "content", [])
            if hasattr(block, "text")
        )

        self._db.insert("llm.responses", [{
            "response_id":        response.id or str(uuid.uuid4()),
            "model":              model,
            "model_version":      model,
            "prompt":             prompt,
            "content":            content,
            "prompt_tokens":      it,
            "completion_tokens":  ot,
            "total_tokens":       it + ot,
            "cost_usd":           _calc_cost(model, it, ot),
            "latency_ms":         latency_ms,
            "stop_reason":        getattr(response, "stop_reason", None),
            "task_type":          self._task_type or ctx.get("tags", {}).get("task_type"),
            "session_id":         ctx.get("session_id"),
            "created_at":         datetime.now(timezone.utc).isoformat(),
        }])
        return response


class ClaudeAdapter:
    def __init__(self, db, task_type: Optional[str] = None):
        self._db = db
        self._task_type = task_type

    def wrap(self, client):
        return _WrappedAnthropicClient(client, self._db, self._task_type)


class _WrappedAnthropicClient:
    def __init__(self, client, db, task_type=None):
        self._client = client
        self.messages = _WrappedMessages(client.messages, db, task_type)

    def __getattr__(self, name):
        return getattr(self._client, name)
```

---

## File 7: `anysql/tracers/agent.py`

**Purpose:** LangChain-compatible callback handler + manual tracer API for UC4. Works with LangChain, LangGraph, CrewAI, AutoGen, and raw agents.

```python
"""
anysql/tracers/agent.py
Agent tracer for UC4 — Cross-Session Agent Debugging.

LangChain usage:
    tracer = AgentTracer(db, session_id="session-123")
    agent_executor.invoke({"input": "..."}, config={"callbacks": [tracer]})

Manual usage (any framework):
    tracer = AgentTracer(db, session_id="session-xyz")
    tracer.trace_tool_call("search", input={"q": "..."}, output="...", status="success")
    tracer.trace_step("llm_call", description="Summarize results")
"""

import uuid
import time
import json
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Optional, Any


class AgentTracer:
    def __init__(self, db, session_id: Optional[str] = None):
        self._db = db
        self.session_id = session_id or str(uuid.uuid4())
        self._step_counter = 0
        self._pending_tool = {}

    @contextmanager
    def session(self, session_id: Optional[str] = None):
        if session_id:
            self.session_id = session_id
        self._step_counter = 0
        yield self

    def trace_tool_call(
        self, tool_name: str,
        input: Any = None, output: Any = None,
        status: str = "success",
        error_message: Optional[str] = None,
        latency_ms: Optional[int] = None,
        human_override: bool = False,
    ) -> str:
        self._step_counter += 1
        call_id = str(uuid.uuid4())
        self._db.insert("agent.tool_calls", [{
            "call_id":       call_id,
            "session_id":    self.session_id,
            "step_order":    self._step_counter,
            "tool_name":     tool_name,
            "tool_input":    json.dumps(input, default=str) if input is not None else None,
            "tool_output":   json.dumps(output, default=str) if output is not None else None,
            "status":        status,
            "error_message": error_message,
            "latency_ms":    latency_ms,
            "human_override": human_override,
            "called_at":     datetime.now(timezone.utc).isoformat(),
        }])
        return call_id

    def trace_step(
        self, step_type: str,
        description: Optional[str] = None,
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
        human_override: bool = False,
        time_to_intervention_ms: Optional[int] = None,
    ) -> str:
        self._step_counter += 1
        trace_id = str(uuid.uuid4())
        self._db.insert("agent.trace", [{
            "trace_id":                  trace_id,
            "session_id":                self.session_id,
            "step_order":                self._step_counter,
            "step_type":                 step_type,
            "step_description":          description,
            "input_summary":             input_summary,
            "output_summary":            output_summary,
            "human_override":            human_override,
            "time_to_intervention_ms":   time_to_intervention_ms,
            "timestamp":                 datetime.now(timezone.utc).isoformat(),
        }])
        return trace_id

    # LangChain BaseCallbackHandler interface
    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        self._pending_tool = {
            "tool_name": serialized.get("name", "unknown"),
            "input": input_str,
            "start": time.monotonic(),
            "step_order": self._step_counter + 1,
        }
        self._step_counter += 1

    def on_tool_end(self, output: str, **kwargs) -> None:
        p = self._pending_tool
        elapsed = int((time.monotonic() - p.get("start", time.monotonic())) * 1000)
        self._db.insert("agent.tool_calls", [{
            "call_id": str(uuid.uuid4()), "session_id": self.session_id,
            "step_order": p.get("step_order", self._step_counter),
            "tool_name": p.get("tool_name", "unknown"),
            "tool_input": p.get("input"), "tool_output": output,
            "status": "success", "latency_ms": elapsed,
            "human_override": False,
            "called_at": datetime.now(timezone.utc).isoformat(),
        }])
        self._pending_tool = {}

    def on_tool_error(self, error: Exception, **kwargs) -> None:
        p = self._pending_tool
        elapsed = int((time.monotonic() - p.get("start", time.monotonic())) * 1000)
        self._db.insert("agent.tool_calls", [{
            "call_id": str(uuid.uuid4()), "session_id": self.session_id,
            "step_order": p.get("step_order", self._step_counter),
            "tool_name": p.get("tool_name", "unknown"),
            "tool_input": p.get("input"), "tool_output": None,
            "status": "error", "error_message": str(error),
            "latency_ms": elapsed, "human_override": False,
            "called_at": datetime.now(timezone.utc).isoformat(),
        }])
        self._pending_tool = {}

    def on_agent_action(self, action, **kwargs) -> None:
        self.trace_step("tool_call",
            description=f"Action: {getattr(action, 'tool', 'unknown')}",
            input_summary=str(getattr(action, "tool_input", ""))[:500])

    def on_agent_finish(self, finish, **kwargs) -> None:
        self.trace_step("finish", description="Agent finished",
            output_summary=str(getattr(finish, "return_values", ""))[:500])
```

---

## File 8: `anysql/tracers/rag.py`

**Purpose:** RAG retrieval tracer for UC5. Auto-detects LangChain, LlamaIndex, and plain dict chunk formats. `query_id` is the cross-layer join key.

```python
"""
anysql/tracers/rag.py
RAG tracer for UC5 — RAG Quality Forensics.

Usage:
    rag = RAGTracer(db)

    query_id = rag.before_retrieval("What is FedRAMP?")
    chunks = vector_db.search(query, top_k=5)
    rag.after_retrieval(query_id, chunks)

    # ... generate answer ...

    rag.record_eval(query_id=query_id, score=0.85, actual=answer)

    # Now query:
    db.rag_failure_modes()    # retrieval vs generation failure analysis
    db.chunk_quality_ranking() # which source docs produce bad answers?
    db.similarity_calibration() # does high cosine score = good answer?
"""

import uuid
from datetime import datetime, timezone
from typing import Optional


class RAGTracer:
    def __init__(self, db):
        self._db = db

    def before_retrieval(self, query: str, session_id: Optional[str] = None) -> str:
        """Returns a query_id — pass to after_retrieval() and record_eval()."""
        return str(uuid.uuid4())

    def after_retrieval(
        self, query_id: str, chunks: list,
        session_id: Optional[str] = None,
        embedding_model: Optional[str] = None,
        normalize_fn=None,
    ) -> None:
        """
        Record retrieved chunks into rag.chunks.
        Auto-detects: LangChain (doc, score) tuples, LlamaIndex NodeWithScore, plain dicts.
        Pass normalize_fn(chunk) -> dict for custom formats.
        """
        records = []
        for rank, chunk in enumerate(chunks):
            n = self._normalize(chunk, normalize_fn)
            records.append({
                "retrieval_id":    str(uuid.uuid4()),
                "query_id":        query_id,
                "session_id":      session_id,
                "chunk_id":        n.get("chunk_id", str(uuid.uuid4())),
                "source_doc":      n.get("source_doc"),
                "chunk_text":      n.get("chunk_text"),
                "similarity_score": n.get("similarity_score"),
                "rank":            rank + 1,
                "chunks_retrieved": len(chunks),
                "embedding_model": embedding_model,
                "retrieved_at":    datetime.now(timezone.utc).isoformat(),
            })
        if records:
            self._db.insert("rag.chunks", records)

    def record_eval(
        self, query_id: str, score: float,
        expected: Optional[str] = None, actual: Optional[str] = None,
        model: Optional[str] = None,
        prompt_id: Optional[str] = None,
        prompt_version: Optional[str] = None,
        **dim_scores,
    ) -> str:
        eval_id = str(uuid.uuid4())
        self._db.insert("eval.results", [{
            "eval_id":        eval_id,
            "query_id":       query_id,
            "prompt_id":      prompt_id,
            "prompt_version": prompt_version,
            "model":          model,
            "expected":       expected,
            "actual":         actual,
            "score":          score,
            "passed":         score >= 0.7,
            "score_factuality":   dim_scores.get("factuality"),
            "score_tone":         dim_scores.get("tone"),
            "score_safety":       dim_scores.get("safety"),
            "score_completeness": dim_scores.get("completeness"),
            "evaluated_at":   datetime.now(timezone.utc).isoformat(),
        }])
        return eval_id

    def _normalize(self, chunk, normalize_fn) -> dict:
        if normalize_fn:
            return normalize_fn(chunk)
        # LangChain: (Document, score) tuple
        if isinstance(chunk, tuple) and len(chunk) == 2:
            doc, score = chunk
            return {"chunk_id": getattr(doc, "id", str(uuid.uuid4())),
                    "chunk_text": getattr(doc, "page_content", str(doc)),
                    "similarity_score": float(score) if score is not None else None,
                    "source_doc": (getattr(doc, "metadata", {}) or {}).get("source")}
        # LlamaIndex: NodeWithScore
        if hasattr(chunk, "node") and hasattr(chunk, "score"):
            node = chunk.node
            return {"chunk_id": getattr(node, "node_id", str(uuid.uuid4())),
                    "chunk_text": getattr(node, "text", None),
                    "similarity_score": float(chunk.score) if chunk.score is not None else None,
                    "source_doc": (getattr(node, "metadata", {}) or {}).get("file_name")}
        # Plain dict
        if isinstance(chunk, dict):
            return {"chunk_id": chunk.get("id", chunk.get("chunk_id", str(uuid.uuid4()))),
                    "chunk_text": chunk.get("text", chunk.get("content", chunk.get("page_content"))),
                    "similarity_score": chunk.get("score", chunk.get("similarity_score")),
                    "source_doc": chunk.get("source", chunk.get("source_doc"))}
        return {"chunk_id": str(uuid.uuid4()), "chunk_text": str(chunk),
                "similarity_score": None, "source_doc": None}
```

---

## File 9: `anysql/__init__.py`

**Purpose:** Public API surface. Everything a user needs is importable from `anysql` directly.

```python
"""
anySQL — SQL analytics for AI systems.

Quick start:
    import anysql

    db = anysql.init("myproject.db")

    # Wrap your LLM client (one line change)
    client = anysql.openai(db).wrap(OpenAI())
    client = anysql.claude(db).wrap(anthropic.Anthropic())

    # Tag calls for cost attribution
    with anysql.context_scope(feature="summarizer", segment="enterprise"):
        response = client.chat.completions.create(...)

    # Query with SQL
    db.query("SELECT model, AVG(cost_usd) FROM llm_responses GROUP BY model")

    # Or use built-in queries
    db.model_comparison()          # UC1: quality vs cost vs latency
    db.prompt_regressions()        # UC2: version-to-version score drops
    db.cost_by_feature()           # UC3: spend per feature flag
    db.tool_failure_rates()        # UC4: which tools break most often
    db.rag_failure_modes()         # UC5: retrieval vs generation failures
"""

from .engine  import AnySQL
from .context import context, context_scope, get_context
from .adapters.openai import OpenAIAdapter
from .adapters.claude  import ClaudeAdapter
from .tracers.agent    import AgentTracer
from .tracers.rag      import RAGTracer
from . import context as _ctx_module

__version__ = "0.1.0"


def init(
    db_path: str = ":memory:",
    echo: bool = False,
    enable_context_tracking: bool = True,
) -> AnySQL:
    """
    Create anySQL engine.

    Args:
        db_path:  ":memory:" (ephemeral) or path to SQLite file (persistent).
        echo:     Print SQL before executing (debug mode).
        enable_context_tracking: Wire @context decorator to auto-write pipeline.runs.
    """
    db = AnySQL(db_path=db_path, echo=echo)
    if enable_context_tracking:
        _ctx_module._set_engine(db)
    return db


def openai(db: AnySQL, task_type: str = None) -> OpenAIAdapter:
    """Return OpenAI adapter for auto-logging."""
    return OpenAIAdapter(db, task_type=task_type)


def claude(db: AnySQL, task_type: str = None) -> ClaudeAdapter:
    """Return Claude adapter for auto-logging."""
    return ClaudeAdapter(db, task_type=task_type)


def agent_tracer(db: AnySQL, session_id: str = None) -> AgentTracer:
    """Return agent tracer for UC4 session debugging."""
    return AgentTracer(db, session_id=session_id)


def rag_tracer(db: AnySQL) -> RAGTracer:
    """Return RAG tracer for UC5 forensics."""
    return RAGTracer(db)


__all__ = [
    "init", "openai", "claude", "agent_tracer", "rag_tracer",
    "context", "context_scope", "get_context",
    "AnySQL", "OpenAIAdapter", "ClaudeAdapter", "AgentTracer", "RAGTracer",
]
```

---

## File 10: `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "anysql"
version = "0.1.0"
description = "SQL analytics for AI systems — query LLM responses, agent traces, and RAG pipelines like a database"
readme = "README.md"
license = { text = "Apache-2.0" }
requires-python = ">=3.10"
keywords = ["llm", "observability", "sql", "duckdb", "ai", "agents", "rag", "eval", "openai", "anthropic"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries",
]
dependencies = [
    "duckdb>=0.10.0",
    "pyarrow>=14.0.0",
    "pandas>=2.0.0",
]

[project.optional-dependencies]
openai    = ["openai>=1.0.0"]
anthropic = ["anthropic>=0.25.0"]
langchain = ["langchain>=0.2.0"]
all = ["openai>=1.0.0", "anthropic>=0.25.0", "langchain>=0.2.0"]
dev = ["pytest>=8.0.0", "pytest-asyncio", "black", "ruff"]

[project.urls]
Homepage      = "https://anysql.org"
Repository    = "https://github.com/karthik/anysql"
Documentation = "https://docs.anysql.org"

[project.scripts]
anysql = "anysql.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["anysql"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## The 5 Canonical SQL Queries (UC1–UC5)

### UC1 — Model Cost/Quality Tradeoff
```sql
SELECT model,
       COUNT(*)                                              AS calls,
       ROUND(AVG(cost_usd), 6)                              AS avg_cost_usd,
       ROUND(AVG(latency_ms), 0)                            AS avg_latency_ms,
       ROUND(AVG(score), 3)                                 AS avg_quality,
       ROUND(AVG(score) / NULLIF(AVG(cost_usd), 0), 2)     AS quality_per_dollar
FROM llm_responses r
LEFT JOIN eval_results e ON r.response_id = e.response_id
GROUP BY model
ORDER BY quality_per_dollar DESC;
```

### UC2 — Prompt Regression Detection
```sql
WITH version_scores AS (
    SELECT prompt_id, prompt_version,
           AVG(score) AS avg_score, evaluated_at
    FROM eval_results
    WHERE prompt_id IS NOT NULL
    GROUP BY prompt_id, prompt_version, evaluated_at
),
with_prev AS (
    SELECT *,
        LAG(avg_score) OVER (PARTITION BY prompt_id ORDER BY evaluated_at) AS prev_score
    FROM version_scores
)
SELECT prompt_id, prompt_version,
       ROUND(avg_score, 3)              AS current_score,
       ROUND(prev_score, 3)             AS previous_score,
       ROUND(avg_score - prev_score, 3) AS delta
FROM with_prev
WHERE (avg_score - prev_score) < -0.10
ORDER BY delta ASC;
```

### UC3 — Cost Attribution by Feature
```sql
SELECT feature_flag, user_segment,
       COUNT(*)                                                    AS runs,
       ROUND(SUM(total_cost_usd), 4)                              AS total_cost_usd,
       ROUND(SUM(revenue_attributed) / NULLIF(SUM(total_cost_usd), 0), 2) AS roi
FROM pipeline_runs
GROUP BY feature_flag, user_segment
ORDER BY total_cost_usd DESC;
```

### UC4 — Tool Failure Analysis
```sql
SELECT tool_name,
       COUNT(*)                                                           AS calls,
       SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END)                 AS failures,
       ROUND(100.0 * SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END)
             / COUNT(*), 2)                                               AS failure_pct,
       ROUND(AVG(latency_ms), 0)                                          AS avg_ms
FROM agent_tool_calls
GROUP BY tool_name
ORDER BY failure_pct DESC;
```

### UC5 — RAG Failure Mode Classification
```sql
SELECT failure_mode, COUNT(*) AS queries, ROUND(AVG(answer_quality), 3) AS avg_quality
FROM (
    SELECT r.query_id,
           MAX(r.similarity_score) AS best_retrieval,
           e.score                 AS answer_quality,
           CASE
             WHEN MAX(r.similarity_score) < 0.7 AND e.score < 0.6 THEN 'retrieval_failure'
             WHEN MAX(r.similarity_score) >= 0.7 AND e.score < 0.6 THEN 'generation_failure'
             WHEN MAX(r.similarity_score) < 0.7 AND e.score >= 0.8 THEN 'lucky_generation'
             ELSE 'success'
           END AS failure_mode
    FROM rag_chunks r
    JOIN eval_results e ON r.query_id = e.query_id
    GROUP BY r.query_id, e.score
)
GROUP BY failure_mode ORDER BY queries DESC;
```

---

## Real-Time Demo Files

Three demo scripts using public NLP benchmark datasets (no download required — articles embedded):

| File | Dataset | Articles | Models |
|------|---------|----------|--------|
| `examples/realtime_openai_demo.py` | BBC News (2004–05 corpus) | 12 | gpt-4o, gpt-4o-mini |
| `examples/realtime_claude_demo.py` | AG News (Zhang et al., 2015) | 15 | claude-sonnet-4-6, claude-haiku-4-5 |
| `examples/realtime_combined_demo.py` | Reuters-21578 R8 | 20 | All 4 models, head-to-head |

Run any demo:
```bash
pip install openai anthropic duckdb pyarrow pandas

export OPENAI_API_KEY=sk-...           # or skip for mock mode
export ANTHROPIC_API_KEY=sk-ant-...    # or skip for mock mode

python examples/realtime_openai_demo.py
python examples/realtime_claude_demo.py
python examples/realtime_combined_demo.py
```

All demos fall back to mock mode automatically when API keys are not set.

---

## Claude Code Execution Instructions

When executing this document in Claude Code, perform the following steps in order:

1. **Create directory structure:**
   ```bash
   mkdir -p anysql/anysql/adapters anysql/anysql/tracers anysql/tests anysql/examples anysql/docs
   touch anysql/anysql/__init__.py anysql/anysql/adapters/__init__.py anysql/anysql/tracers/__init__.py
   touch anysql/tests/__init__.py
   ```

2. **Create all source files** using the code blocks above (Files 1–9 → respective paths, File 10 → `pyproject.toml`)

3. **Create the three demo files** from the session context:
   - `examples/realtime_openai_demo.py` (BBC News, 5 UCs)
   - `examples/realtime_claude_demo.py` (AG News, 5 UCs)
   - `examples/realtime_combined_demo.py` (Reuters R8, head-to-head)

4. **Install dependencies:**
   ```bash
   pip install duckdb pyarrow pandas openai anthropic
   ```

5. **Validate:**
   ```bash
   python -c "import anysql; db = anysql.init(); print(db)"
   ```

6. **Run demo (mock mode, no API key needed):**
   ```bash
   python examples/realtime_combined_demo.py
   ```

7. **Run with live API:**
   ```bash
   export OPENAI_API_KEY=sk-...
   export ANTHROPIC_API_KEY=sk-ant-...
   python examples/realtime_combined_demo.py
   ```

---

## Strategic Context

**anySQL standalone** — useful OSS tool, good for GitHub stars and developer adoption.

**anySQL + ControlGate** — defensible product. anySQL provides the SQL-queryable telemetry store; ControlGate enforces policy against it. The combination answers:
- *What are my AI systems doing?* (anySQL)
- *Are they doing what they're supposed to do?* (ControlGate policies)
- *Can I prove it to a regulator?* (EU AI Act evidence store — Phase 2 of anySQL)

**Positioning:** "SQL for AI systems" not "AI observability tool."  
**Distribution:** OSS core → ControlGate Enterprise integration → EU AI Act compliance module.

---

*anySQL v0.1.0 — anysql.org — Apache 2.0*
