import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
import anysql_sdk
from anysql_sdk.tracers.agent import AgentTracer
from anysql_sdk.tracers.rag import RAGTracer


@pytest.fixture
def db():
    return anysql_sdk.init(":memory:")


def _now():
    return datetime.now(timezone.utc).isoformat()


# ── AgentTracer: manual API ─────────────────────────────────────────────────

def test_agent_tracer_trace_tool_call(db):
    tracer = AgentTracer(db, session_id="s1")
    call_id = tracer.trace_tool_call("search", input={"q": "FedRAMP"}, output="result", status="success")
    assert call_id is not None
    assert db.count("agent.tool_calls") == 1


def test_agent_tracer_trace_tool_call_error(db):
    tracer = AgentTracer(db, session_id="s1")
    tracer.trace_tool_call("search", status="error", error_message="timeout")
    result = db.query("SELECT status, error_message FROM agent_tool_calls")
    assert result.iloc[0]["status"] == "error"
    assert result.iloc[0]["error_message"] == "timeout"


def test_agent_tracer_step_order_increments(db):
    tracer = AgentTracer(db, session_id="s1")
    tracer.trace_tool_call("tool_a")
    tracer.trace_tool_call("tool_b")
    result = db.query("SELECT step_order FROM agent_tool_calls ORDER BY step_order")
    assert list(result["step_order"]) == [1, 2]


def test_agent_tracer_trace_step(db):
    tracer = AgentTracer(db, session_id="s1")
    trace_id = tracer.trace_step("llm_call", description="Summarize results")
    assert trace_id is not None
    assert db.count("agent.trace") == 1


def test_agent_tracer_human_override(db):
    tracer = AgentTracer(db, session_id="s1")
    tracer.trace_step("human", human_override=True, time_to_intervention_ms=3000)
    result = db.query("SELECT human_override, time_to_intervention_ms FROM agent_trace")
    assert result.iloc[0]["human_override"] == True
    assert result.iloc[0]["time_to_intervention_ms"] == 3000


def test_agent_tracer_session_context_manager(db):
    tracer = AgentTracer(db)
    with tracer.session("new-session-id"):
        assert tracer.session_id == "new-session-id"
        tracer.trace_tool_call("tool_a")
    result = db.query("SELECT session_id FROM agent_tool_calls")
    assert result.iloc[0]["session_id"] == "new-session-id"


# ── AgentTracer: LangChain callbacks ────────────────────────────────────────

def test_langchain_on_tool_start_and_end(db):
    tracer = AgentTracer(db, session_id="lc_session")
    tracer.on_tool_start({"name": "search"}, '{"q": "test"}')
    tracer.on_tool_end("search results here")
    assert db.count("agent.tool_calls") == 1
    result = db.query("SELECT tool_name, status FROM agent_tool_calls")
    assert result.iloc[0]["tool_name"] == "search"
    assert result.iloc[0]["status"] == "success"


def test_langchain_on_tool_error(db):
    tracer = AgentTracer(db, session_id="lc_session")
    tracer.on_tool_start({"name": "search"}, "query")
    tracer.on_tool_error(Exception("Connection refused"))
    result = db.query("SELECT status, error_message FROM agent_tool_calls")
    assert result.iloc[0]["status"] == "error"
    assert "Connection refused" in result.iloc[0]["error_message"]


def test_langchain_on_agent_action(db):
    tracer = AgentTracer(db, session_id="lc_session")
    action = MagicMock()
    action.tool = "calculator"
    action.tool_input = {"expression": "2+2"}
    tracer.on_agent_action(action)
    assert db.count("agent.trace") == 1


def test_langchain_on_agent_finish(db):
    tracer = AgentTracer(db, session_id="lc_session")
    finish = MagicMock()
    finish.return_values = {"output": "42"}
    tracer.on_agent_finish(finish)
    assert db.count("agent.trace") == 1


# ── RAGTracer ──────────────────────────────────────────────────────────────

def test_rag_tracer_before_retrieval_returns_uuid(db):
    rag = RAGTracer(db)
    query_id = rag.before_retrieval("What is FedRAMP?")
    assert isinstance(query_id, str)
    assert len(query_id) == 36  # UUID format


def test_rag_tracer_after_retrieval_plain_dicts(db):
    rag = RAGTracer(db)
    query_id = rag.before_retrieval("test query")
    chunks = [
        {"id": "c1", "text": "chunk text 1", "score": 0.9, "source": "doc_a.pdf"},
        {"id": "c2", "text": "chunk text 2", "score": 0.7, "source": "doc_b.pdf"},
    ]
    rag.after_retrieval(query_id, chunks)
    assert db.count("rag.chunks") == 2
    result = db.query("SELECT query_id, similarity_score, rank FROM rag_chunks ORDER BY rank")
    assert result.iloc[0]["query_id"] == query_id
    assert result.iloc[0]["similarity_score"] == pytest.approx(0.9)
    assert result.iloc[0]["rank"] == 1
    assert result.iloc[1]["rank"] == 2


def test_rag_tracer_langchain_tuple_format(db):
    rag = RAGTracer(db)
    query_id = rag.before_retrieval("query")
    doc = MagicMock()
    doc.page_content = "langchain chunk"
    doc.metadata = {"source": "lc_doc.pdf"}
    doc.id = "lc_chunk_1"
    chunks = [(doc, 0.85)]
    rag.after_retrieval(query_id, chunks)
    assert db.count("rag.chunks") == 1
    result = db.query("SELECT chunk_text, similarity_score, source_doc FROM rag_chunks")
    assert result.iloc[0]["chunk_text"] == "langchain chunk"
    assert result.iloc[0]["similarity_score"] == pytest.approx(0.85)
    assert result.iloc[0]["source_doc"] == "lc_doc.pdf"


def test_rag_tracer_llamaindex_format(db):
    rag = RAGTracer(db)
    query_id = rag.before_retrieval("query")
    node = MagicMock()
    node.node_id = "li_node_1"
    node.text = "llamaindex chunk"
    node.metadata = {"file_name": "li_doc.pdf"}
    node_with_score = MagicMock()
    node_with_score.node = node
    node_with_score.score = 0.75
    rag.after_retrieval(query_id, [node_with_score])
    assert db.count("rag.chunks") == 1
    result = db.query("SELECT chunk_text, similarity_score FROM rag_chunks")
    assert result.iloc[0]["chunk_text"] == "llamaindex chunk"
    assert result.iloc[0]["similarity_score"] == pytest.approx(0.75)


def test_rag_tracer_custom_normalize_fn(db):
    rag = RAGTracer(db)
    query_id = rag.before_retrieval("query")

    def custom_normalize(chunk):
        return {
            "chunk_id": chunk["my_id"],
            "chunk_text": chunk["my_text"],
            "similarity_score": chunk["my_score"],
            "source_doc": "custom_source",
        }

    chunks = [{"my_id": "x1", "my_text": "custom text", "my_score": 0.6}]
    rag.after_retrieval(query_id, chunks, normalize_fn=custom_normalize)
    result = db.query("SELECT chunk_text, similarity_score FROM rag_chunks")
    assert result.iloc[0]["chunk_text"] == "custom text"


def test_rag_tracer_record_eval(db):
    rag = RAGTracer(db)
    query_id = rag.before_retrieval("query")
    eval_id = rag.record_eval(query_id=query_id, score=0.85, actual="the answer")
    assert eval_id is not None
    assert db.count("eval.results") == 1
    result = db.query("SELECT score, passed FROM eval_results")
    assert result.iloc[0]["score"] == pytest.approx(0.85)
    assert result.iloc[0]["passed"] == True


def test_rag_tracer_record_eval_failed(db):
    rag = RAGTracer(db)
    query_id = rag.before_retrieval("query")
    rag.record_eval(query_id=query_id, score=0.5)
    result = db.query("SELECT passed FROM eval_results")
    assert result.iloc[0]["passed"] == False


def test_rag_uc5_cross_join(db):
    """The killer feature: join rag.chunks to eval.results via query_id."""
    rag = RAGTracer(db)
    query_id = rag.before_retrieval("What is the capital?")
    rag.after_retrieval(query_id, [{"text": "Paris is the capital", "score": 0.9, "source": "wiki.pdf"}])
    rag.record_eval(query_id=query_id, score=0.95)
    result = db.rag_failure_modes()
    assert len(result) >= 1
    assert "success" in result["failure_mode"].values
