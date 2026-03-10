"""
anySQL — SQL analytics for AI systems.

Quick start:
    import anysql_sdk

    db = anysql_sdk.init("myproject.db")

    # Wrap your LLM client (one line change)
    client = anysql_sdk.openai(db).wrap(OpenAI())
    client = anysql_sdk.claude(db).wrap(anthropic.Anthropic())

    # Tag calls for cost attribution
    with anysql_sdk.context_scope(feature="summarizer", segment="enterprise"):
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
from .adapters.openai import OpenAIAdapter
from .adapters.claude  import ClaudeAdapter
from .tracers.agent    import AgentTracer
from .tracers.rag      import RAGTracer
from . import context as _ctx_module
from .context import context, context_scope, get_context

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
