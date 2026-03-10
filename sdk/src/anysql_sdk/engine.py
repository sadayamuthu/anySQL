"""
anysql_sdk/engine.py
DuckDB-powered SQL engine over canonical Arrow tables.
"""

import warnings
import duckdb
import pyarrow as pa
import pandas as pd
from datetime import datetime
from typing import Optional, Union

from .schema import SCHEMAS, TABLE_NAMES
from .storage import Storage

# Pre-computed map of table -> set of timestamp field names for fast coercion
_TIMESTAMP_FIELDS: dict[str, set[str]] = {
    table: {f.name for f in schema if pa.types.is_timestamp(f.type)}
    for table, schema in SCHEMAS.items()
}


def _coerce_record(record: dict, ts_fields: set[str]) -> dict:
    """Return a copy of record with ISO timestamp strings converted to datetime."""
    if not ts_fields:
        return record
    out = {}
    for k, v in record.items():
        if k in ts_fields and isinstance(v, str):
            try:
                out[k] = datetime.fromisoformat(v)
            except ValueError:
                out[k] = v
        else:
            out[k] = v
    return out


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
            self._storage.delete(t)
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
            WITH daily AS (
                SELECT feature_flag,
                       DATE_TRUNC('day', started_at)  AS date,
                       SUM(total_cost_usd)             AS daily_cost
                FROM pipeline_runs
                GROUP BY feature_flag, date
            ),
            with_rolling AS (
                SELECT feature_flag,
                       date,
                       ROUND(daily_cost, 6)  AS daily_cost,
                       ROUND(AVG(daily_cost) OVER (
                           PARTITION BY feature_flag
                           ORDER BY date
                           ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
                       ), 6)                AS rolling_7d_avg,
                       ROUND(daily_cost / NULLIF(AVG(daily_cost) OVER (
                           PARTITION BY feature_flag
                           ORDER BY date
                           ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
                       ), 0), 2)            AS cost_ratio
                FROM daily
            )
            SELECT *
            FROM with_rolling
            WHERE cost_ratio > {multiplier}
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
        self._refresh_views()
        rel = self._conn.execute("""
            SELECT a.step_order,
                   a.tool_name AS session_a_tool,
                   b.tool_name AS session_b_tool
            FROM agent_tool_calls a
            JOIN agent_tool_calls b ON a.step_order = b.step_order
            WHERE a.session_id = ?
              AND b.session_id = ?
              AND a.tool_name != b.tool_name
            ORDER BY a.step_order
        """, [session_a, session_b])
        return rel.df()

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
            WITH per_query AS (
                SELECT r.query_id,
                       MAX(r.similarity_score) AS max_sim,
                       e.score
                FROM rag_chunks r
                JOIN eval_results e ON r.query_id = e.query_id
                GROUP BY r.query_id, e.score
            )
            SELECT ROUND(max_sim, 1)  AS score_bucket,
                   COUNT(*)           AS queries,
                   ROUND(AVG(score), 3) AS avg_answer_quality
            FROM per_query
            GROUP BY ROUND(max_sim, 1)
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
                ts_fields = _TIMESTAMP_FIELDS[table_name]
                coerced = [_coerce_record(r, ts_fields) for r in rows]
                arrow_table = pa.Table.from_pylist(coerced, schema=schema)
                self._arrow_tables[table_name] = arrow_table
                view = self._table_to_view(table_name)
                self._conn.register(view, arrow_table)
            except Exception as e:
                warnings.warn(f"[anySQL] {table_name}: {e}", stacklevel=2)

    @staticmethod
    def _table_to_view(table: str) -> str:
        return table.replace(".", "_")

    def __repr__(self) -> str:
        counts = {t: len(self._buffers[t]) for t in TABLE_NAMES}
        return f"AnySQL(rows={counts})"
