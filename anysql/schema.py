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
