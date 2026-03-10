import pytest
import pandas as pd
from datetime import datetime, timezone
from anysql_sdk.engine import AnySQL
from anysql_sdk.schema import TABLE_NAMES


@pytest.fixture
def db():
    return AnySQL(db_path=":memory:")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _llm_record(**kwargs):
    base = {
        "response_id": "r1", "model": "gpt-4o", "prompt": "Hello",
        "created_at": _now(), "prompt_tokens": 10, "completion_tokens": 20,
        "total_tokens": 30, "cost_usd": 0.0001, "latency_ms": 500,
    }
    return {**base, **kwargs}


def _eval_record(**kwargs):
    base = {
        "eval_id": "e1", "response_id": "r1", "score": 0.9,
        "evaluated_at": _now(),
    }
    return {**base, **kwargs}


def test_init_creates_empty_tables(db):
    for t in TABLE_NAMES:
        assert db.count(t) == 0


def test_insert_and_count(db):
    db.insert("llm.responses", [_llm_record()])
    assert db.count("llm.responses") == 1


def test_insert_multiple_records(db):
    db.insert("llm.responses", [_llm_record(response_id="r1"), _llm_record(response_id="r2")])
    assert db.count("llm.responses") == 2


def test_query_returns_dataframe(db):
    db.insert("llm.responses", [_llm_record()])
    result = db.query("SELECT model FROM llm_responses")
    assert isinstance(result, pd.DataFrame)
    assert list(result["model"]) == ["gpt-4o"]


def test_query_as_df_false_returns_relation(db):
    db.insert("llm.responses", [_llm_record()])
    import duckdb
    result = db.query("SELECT model FROM llm_responses", as_df=False)
    assert hasattr(result, "fetchall")


def test_insert_unknown_table_raises(db):
    with pytest.raises(ValueError, match="Unknown table"):
        db.insert("bad.table", [{"x": 1}])


def test_clear_single_table(db):
    db.insert("llm.responses", [_llm_record()])
    db.clear("llm.responses")
    assert db.count("llm.responses") == 0


def test_clear_all_tables(db):
    db.insert("llm.responses", [_llm_record()])
    db.insert("eval.results", [_eval_record()])
    db.clear()
    for t in TABLE_NAMES:
        assert db.count(t) == 0


def test_tables_returns_all_names(db):
    assert set(db.tables()) == set(TABLE_NAMES)


def test_repr(db):
    r = repr(db)
    assert "AnySQL" in r
    assert "rows" in r


# UC1: model_comparison
def test_model_comparison_empty(db):
    result = db.model_comparison()
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0


def test_model_comparison_with_data(db):
    db.insert("llm.responses", [
        _llm_record(response_id="r1", model="gpt-4o", cost_usd=0.001),
        _llm_record(response_id="r2", model="gpt-4o-mini", cost_usd=0.0001),
    ])
    db.insert("eval.results", [
        _eval_record(eval_id="e1", response_id="r1", score=0.9),
        _eval_record(eval_id="e2", response_id="r2", score=0.7),
    ])
    result = db.model_comparison()
    assert set(result["model"]) == {"gpt-4o", "gpt-4o-mini"}


def test_model_by_task(db):
    db.insert("llm.responses", [
        _llm_record(response_id="r1", model="gpt-4o", task_type="summarization"),
    ])
    db.insert("eval.results", [_eval_record(eval_id="e1", response_id="r1", score=0.9)])
    result = db.model_by_task()
    assert isinstance(result, pd.DataFrame)


# UC2: prompt regressions
def test_prompt_regressions_empty(db):
    result = db.prompt_regressions()
    assert isinstance(result, pd.DataFrame)


def test_eval_debt(db):
    result = db.eval_debt()
    assert isinstance(result, pd.DataFrame)


def test_silent_degradation(db):
    result = db.silent_degradation()
    assert isinstance(result, pd.DataFrame)


# UC3: cost attribution
def test_cost_by_feature_empty(db):
    result = db.cost_by_feature()
    assert isinstance(result, pd.DataFrame)


def test_cost_by_feature_with_data(db):
    db.insert("pipeline.runs", [{
        "run_id": "run1", "feature_flag": "premium", "user_segment": "enterprise",
        "total_cost_usd": 0.05, "status": "success",
        "started_at": _now(),
    }])
    result = db.cost_by_feature()
    assert len(result) == 1
    assert result.iloc[0]["feature_flag"] == "premium"


def test_cost_anomalies_empty(db):
    result = db.cost_anomalies()
    assert isinstance(result, pd.DataFrame)


# UC4: agent debugging
def test_tool_failure_rates_empty(db):
    result = db.tool_failure_rates()
    assert isinstance(result, pd.DataFrame)


def test_tool_failure_rates_with_data(db):
    db.insert("agent.tool_calls", [
        {"call_id": "c1", "session_id": "s1", "step_order": 1,
         "tool_name": "search", "status": "success", "called_at": _now()},
        {"call_id": "c2", "session_id": "s1", "step_order": 2,
         "tool_name": "search", "status": "error", "called_at": _now()},
    ])
    result = db.tool_failure_rates()
    assert len(result) == 1
    assert result.iloc[0]["tool_name"] == "search"
    assert result.iloc[0]["failures"] == 1


def test_loop_detector(db):
    for i in range(6):
        db.insert("agent.tool_calls", [{
            "call_id": f"c{i}", "session_id": "s1", "step_order": i,
            "tool_name": "search", "status": "success", "called_at": _now(),
        }])
    result = db.loop_detector(min_calls=5)
    assert len(result) >= 1


def test_session_diff(db):
    result = db.session_diff("session_a", "session_b")
    assert isinstance(result, pd.DataFrame)


def test_human_intervention_points(db):
    result = db.human_intervention_points()
    assert isinstance(result, pd.DataFrame)


# UC5: RAG forensics
def test_rag_failure_modes_empty(db):
    result = db.rag_failure_modes()
    assert isinstance(result, pd.DataFrame)


def test_rag_failure_modes_with_data(db):
    db.insert("rag.chunks", [{
        "retrieval_id": "ret1", "query_id": "q1", "chunk_id": "ch1",
        "similarity_score": 0.8, "rank": 1, "retrieved_at": _now(),
    }])
    db.insert("eval.results", [{
        "eval_id": "ev1", "query_id": "q1", "score": 0.4,
        "evaluated_at": _now(),
    }])
    result = db.rag_failure_modes()
    assert len(result) >= 1


def test_chunk_quality_ranking(db):
    result = db.chunk_quality_ranking()
    assert isinstance(result, pd.DataFrame)


def test_similarity_calibration(db):
    result = db.similarity_calibration()
    assert isinstance(result, pd.DataFrame)


def test_clear_also_clears_sqlite(tmp_path):
    """clear() must flush SQLite so reopening the DB doesn't reload cleared rows."""
    db_path = str(tmp_path / "test.db")
    db1 = AnySQL(db_path=db_path)
    db1.insert("llm.responses", [_llm_record()])
    assert db1.count("llm.responses") == 1
    db1.clear("llm.responses")
    db1._storage.close()

    # Reopen — should be empty
    db2 = AnySQL(db_path=db_path)
    assert db2.count("llm.responses") == 0
    db2._storage.close()
