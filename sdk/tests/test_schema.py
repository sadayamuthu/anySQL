import pyarrow as pa
from anysql_sdk.schema import (
    SCHEMAS, TABLE_NAMES,
    LLM_RESPONSES_SCHEMA, EVAL_RESULTS_SCHEMA, PIPELINE_RUNS_SCHEMA,
    AGENT_TOOL_CALLS_SCHEMA, AGENT_TRACE_SCHEMA, RAG_CHUNKS_SCHEMA,
)

def test_table_names_count():
    assert len(TABLE_NAMES) == 6

def test_table_names_values():
    assert set(TABLE_NAMES) == {
        "llm.responses", "eval.results", "pipeline.runs",
        "agent.tool_calls", "agent.trace", "rag.chunks",
    }

def test_schemas_registry_keys():
    assert set(SCHEMAS.keys()) == set(TABLE_NAMES)

def test_llm_responses_required_fields():
    fields = {f.name: f for f in LLM_RESPONSES_SCHEMA}
    assert "response_id" in fields
    assert not fields["response_id"].nullable
    assert "model" in fields
    assert not fields["model"].nullable
    assert "created_at" in fields
    assert fields["created_at"].type == pa.timestamp("ms")

def test_llm_responses_nullable_fields():
    fields = {f.name: f for f in LLM_RESPONSES_SCHEMA}
    assert fields["cost_usd"].nullable
    assert fields["latency_ms"].nullable
    assert fields["content"].nullable

def test_eval_results_has_query_id():
    fields = {f.name for f in EVAL_RESULTS_SCHEMA}
    assert "query_id" in fields
    assert "prompt_id" in fields
    assert "score" in fields

def test_pipeline_runs_has_feature_flag():
    fields = {f.name for f in PIPELINE_RUNS_SCHEMA}
    assert "feature_flag" in fields
    assert "user_segment" in fields
    assert "revenue_attributed" in fields

def test_agent_tool_calls_required_fields():
    fields = {f.name: f for f in AGENT_TOOL_CALLS_SCHEMA}
    assert not fields["call_id"].nullable
    assert not fields["session_id"].nullable
    assert not fields["tool_name"].nullable

def test_agent_trace_has_human_override():
    fields = {f.name for f in AGENT_TRACE_SCHEMA}
    assert "human_override" in fields
    assert "time_to_intervention_ms" in fields

def test_rag_chunks_has_query_id():
    fields = {f.name: f for f in RAG_CHUNKS_SCHEMA}
    assert "query_id" in fields
    assert not fields["query_id"].nullable
    assert "similarity_score" in fields

def test_all_schemas_are_pyarrow_schemas():
    for name, schema in SCHEMAS.items():
        assert isinstance(schema, pa.Schema), f"{name} is not a pa.Schema"

def test_can_create_empty_table_from_each_schema():
    for name, schema in SCHEMAS.items():
        table = pa.table({f.name: pa.array([], type=f.type) for f in schema})
        assert isinstance(table, pa.Table)
        assert table.num_rows == 0

def test_eval_results_primary_key_not_null():
    fields = {f.name: f for f in EVAL_RESULTS_SCHEMA}
    assert not fields["eval_id"].nullable

def test_pipeline_runs_primary_key_not_null():
    fields = {f.name: f for f in PIPELINE_RUNS_SCHEMA}
    assert not fields["run_id"].nullable

def test_agent_trace_required_fields():
    fields = {f.name: f for f in AGENT_TRACE_SCHEMA}
    assert not fields["trace_id"].nullable
    assert not fields["session_id"].nullable
    assert not fields["step_order"].nullable

def test_rag_chunks_required_fields():
    fields = {f.name: f for f in RAG_CHUNKS_SCHEMA}
    assert not fields["retrieval_id"].nullable
    assert not fields["chunk_id"].nullable
