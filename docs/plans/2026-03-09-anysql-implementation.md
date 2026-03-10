# anySQL v0.1.0 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the complete anySQL package from scratch — a SQL analytics engine for AI systems that lets engineers query LLM responses, agent traces, and RAG pipelines with standard SQL.

**Architecture:** Three-layer stack: DuckDB (in-memory SQL over PyArrow views) on top of a SQLite persistence layer (JSON blobs), with a public API that wraps LLM clients as transparent proxies and provides contextvars-based tagging. Built in three phases with a validation gate after each.

**Tech Stack:** Python 3.10+, DuckDB ≥0.10, PyArrow ≥14, Pandas ≥2, SQLite (stdlib), pytest, hatchling

---

## Phase 1: Core Layer

**Gate:** `python -c "import anysql; db = anysql.init(); print(db)"` prints `AnySQL(rows={...})`

---

### Task 1: Project scaffolding

**Files:**
- Create: `anysql/__init__.py` (stub)
- Create: `anysql/adapters/__init__.py`
- Create: `anysql/tracers/__init__.py`
- Create: `tests/__init__.py`
- Create: `pyproject.toml` (minimal, enough to install)

**Step 1: Create directory structure**

```bash
mkdir -p anysql/adapters anysql/tracers tests examples docs/plans
touch anysql/__init__.py anysql/adapters/__init__.py anysql/tracers/__init__.py tests/__init__.py
```

**Step 2: Write minimal pyproject.toml**

Create `pyproject.toml`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "anysql"
version = "0.1.0"
description = "SQL analytics for AI systems"
requires-python = ">=3.10"
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

[project.scripts]
anysql = "anysql.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["anysql"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 3: Install dependencies**

```bash
pip install duckdb pyarrow pandas pytest pytest-asyncio
pip install -e .
```

Expected: no errors

**Step 4: Commit**

```bash
git add anysql/ tests/ examples/ docs/ pyproject.toml
git commit -m "chore: scaffold project structure and minimal pyproject.toml"
```

---

### Task 2: `anysql/schema.py` — 6 PyArrow schemas

**Files:**
- Create: `anysql/schema.py`
- Create: `tests/test_schema.py`

**Step 1: Write the failing tests**

Create `tests/test_schema.py`:
```python
import pyarrow as pa
import pytest
from anysql.schema import (
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
    # query_id is the UC5 cross-layer join key
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
    # query_id links rag.chunks → eval.results
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
```

**Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_schema.py -v
```
Expected: ImportError — `anysql.schema` does not exist yet

**Step 3: Implement `anysql/schema.py`**

Create `anysql/schema.py` with the exact content from `docs/ANYSQL_CLAUDE_CODE.md` (File 1, lines 133–256).

**Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_schema.py -v
```
Expected: all 12 tests PASS

**Step 5: Commit**

```bash
git add anysql/schema.py tests/test_schema.py
git commit -m "feat: add 6 canonical PyArrow schemas and registry"
```

---

### Task 3: `anysql/storage.py` — SQLite persistence

**Files:**
- Create: `anysql/storage.py`
- Create: `tests/test_storage.py`

**Step 1: Write the failing tests**

Create `tests/test_storage.py`:
```python
import pytest
from anysql.storage import Storage


@pytest.fixture
def mem_store():
    return Storage(":memory:")


@pytest.fixture
def disk_store(tmp_path):
    return Storage(str(tmp_path / "test.db"))


def test_in_memory_save_is_noop(mem_store):
    mem_store.save("llm.responses", [{"response_id": "r1", "model": "gpt-4o"}])
    # In-memory store never persists — load returns empty
    assert mem_store.load("llm.responses") == []


def test_in_memory_row_count_zero(mem_store):
    assert mem_store.row_count("llm.responses") == 0


def test_disk_save_and_load_roundtrip(disk_store):
    records = [{"response_id": "r1", "model": "gpt-4o"}, {"response_id": "r2", "model": "gpt-4o-mini"}]
    disk_store.save("llm.responses", records)
    loaded = disk_store.load("llm.responses")
    assert len(loaded) == 2
    assert loaded[0]["response_id"] == "r1"
    assert loaded[1]["model"] == "gpt-4o-mini"


def test_disk_row_count(disk_store):
    disk_store.save("llm.responses", [{"a": 1}, {"a": 2}, {"a": 3}])
    assert disk_store.row_count("llm.responses") == 3


def test_delete_all(disk_store):
    disk_store.save("llm.responses", [{"a": 1}, {"a": 2}])
    deleted = disk_store.delete("llm.responses")
    assert deleted == 2
    assert disk_store.row_count("llm.responses") == 0


def test_save_empty_list_is_noop(disk_store):
    disk_store.save("llm.responses", [])
    assert disk_store.row_count("llm.responses") == 0


def test_all_table_names_initialized(disk_store):
    # All 6 tables should be created and queryable
    from anysql.schema import TABLE_NAMES
    for table in TABLE_NAMES:
        assert disk_store.row_count(table) == 0


def test_table_name_with_dot_sanitized(disk_store):
    # "llm.responses" must map to "llm_responses" SQL table
    disk_store.save("llm.responses", [{"x": 1}])
    assert disk_store.row_count("llm.responses") == 1


def test_multiple_saves_accumulate(disk_store):
    disk_store.save("eval.results", [{"eval_id": "e1"}])
    disk_store.save("eval.results", [{"eval_id": "e2"}])
    assert disk_store.row_count("eval.results") == 2


def test_json_serialization_of_complex_types(disk_store):
    from datetime import datetime
    record = {"ts": datetime.now(), "nested": {"a": 1}}
    disk_store.save("llm.responses", [record])
    loaded = disk_store.load("llm.responses")
    assert loaded[0]["nested"] == {"a": 1}
```

**Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_storage.py -v
```
Expected: ImportError

**Step 3: Implement `anysql/storage.py`**

Create `anysql/storage.py` with the exact content from `docs/ANYSQL_CLAUDE_CODE.md` (File 2, lines 265–337).

**Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_storage.py -v
```
Expected: all 10 tests PASS

**Step 5: Commit**

```bash
git add anysql/storage.py tests/test_storage.py
git commit -m "feat: add SQLite persistence layer with JSON blob storage"
```

---

### Task 4: `anysql/engine.py` — DuckDB query engine

**Files:**
- Create: `anysql/engine.py`
- Create: `tests/test_engine.py`

**Step 1: Write the failing tests**

Create `tests/test_engine.py`:
```python
import pytest
import pandas as pd
from datetime import datetime, timezone
from anysql.engine import AnySQL
from anysql.schema import TABLE_NAMES


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
    from datetime import datetime, timezone
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
```

**Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_engine.py -v
```
Expected: ImportError

**Step 3: Implement `anysql/engine.py`**

Create `anysql/engine.py` with the exact content from `docs/ANYSQL_CLAUDE_CODE.md` (File 3, lines 345–694).

**Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_engine.py -v
```
Expected: all tests PASS

**Step 5: Commit**

```bash
git add anysql/engine.py tests/test_engine.py
git commit -m "feat: add DuckDB engine with 5 UC convenience query methods"
```

---

### Task 5: Stub `anysql/__init__.py` + Phase 1 gate

**Files:**
- Modify: `anysql/__init__.py`

**Step 1: Write minimal `__init__.py`**

```python
from .engine import AnySQL

__version__ = "0.1.0"

def init(db_path: str = ":memory:", echo: bool = False) -> AnySQL:
    return AnySQL(db_path=db_path, echo=echo)
```

**Step 2: Validate Phase 1 gate**

```bash
python -c "import anysql; db = anysql.init(); print(db)"
```
Expected output: `AnySQL(rows={'llm.responses': 0, 'eval.results': 0, ...})`

**Step 3: Run all Phase 1 tests**

```bash
pytest tests/test_schema.py tests/test_storage.py tests/test_engine.py -v
```
Expected: all tests PASS

**Step 4: Commit**

```bash
git add anysql/__init__.py
git commit -m "feat: Phase 1 complete — core layer working"
```

---

## Phase 2: Integration Layer

**Gate:** Mock inserts via all adapters + tracers, all 5 UC queries return non-empty DataFrames

---

### Task 6: `anysql/context.py` — contextvars cost attribution

**Files:**
- Create: `anysql/context.py`

**Step 1: Implement `anysql/context.py`**

Create `anysql/context.py` with the exact content from `docs/ANYSQL_CLAUDE_CODE.md` (File 4, lines 702–834).

**Step 2: Validate context decorator works**

```bash
python -c "
import anysql
db = anysql.init()
from anysql.context import context, context_scope, get_context
print('context module OK')
"
```
Expected: `context module OK`

**Step 3: Commit**

```bash
git add anysql/context.py
git commit -m "feat: add contextvars-based cost attribution (context decorator + scope)"
```

---

### Task 7: `anysql/adapters/openai.py` — OpenAI transparent proxy

**Files:**
- Create: `anysql/adapters/openai.py`
- Create: `tests/test_adapters.py` (OpenAI section)

**Step 1: Write the failing tests**

Create `tests/test_adapters.py`:
```python
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
import anysql
from anysql.adapters.openai import OpenAIAdapter, _calc_cost as openai_calc_cost
from anysql.adapters.claude import ClaudeAdapter, _calc_cost as claude_calc_cost


@pytest.fixture
def db():
    return anysql.init(":memory:")


# ── OpenAI cost calculation ─────────────────────────────────────────────────

def test_openai_cost_gpt4o():
    cost = openai_calc_cost("gpt-4o", 1000, 500)
    # 1000 * 2.50/1M + 500 * 10.00/1M
    expected = (1000 * 2.50 + 500 * 10.00) / 1_000_000
    assert abs(cost - expected) < 1e-10


def test_openai_cost_gpt4o_mini():
    cost = openai_calc_cost("gpt-4o-mini", 1000, 500)
    expected = (1000 * 0.15 + 500 * 0.60) / 1_000_000
    assert abs(cost - expected) < 1e-10


def test_openai_cost_unknown_model_returns_none():
    assert openai_calc_cost("unknown-model-xyz", 100, 50) is None


def test_openai_cost_versioned_suffix():
    # "gpt-4o-2024-11-20" should match "gpt-4o" prefix
    cost = openai_calc_cost("gpt-4o-2024-11-20", 1000, 500)
    assert cost is not None
    assert cost > 0


# ── OpenAI adapter wrapping ─────────────────────────────────────────────────

def _make_openai_response(model="gpt-4o", content="Hello", prompt_tokens=10, completion_tokens=20):
    mock = MagicMock()
    mock.id = "chatcmpl-test123"
    mock.model = model
    mock.choices = [MagicMock()]
    mock.choices[0].message.content = content
    mock.choices[0].finish_reason = "stop"
    mock.usage.prompt_tokens = prompt_tokens
    mock.usage.completion_tokens = completion_tokens
    return mock


def test_openai_wrap_inserts_llm_response(db):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_openai_response()
    client = anysql.openai(db).wrap(mock_client)
    client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Summarize this"}]
    )
    assert db.count("llm.responses") == 1


def test_openai_wrap_records_correct_model(db):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_openai_response(model="gpt-4o-mini")
    client = anysql.openai(db).wrap(mock_client)
    client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "Hi"}])
    result = db.query("SELECT model FROM llm_responses")
    assert result.iloc[0]["model"] == "gpt-4o-mini"


def test_openai_wrap_records_tokens(db):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_openai_response(
        prompt_tokens=15, completion_tokens=25
    )
    client = anysql.openai(db).wrap(mock_client)
    client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "Hi"}])
    result = db.query("SELECT prompt_tokens, completion_tokens, total_tokens FROM llm_responses")
    assert result.iloc[0]["prompt_tokens"] == 15
    assert result.iloc[0]["completion_tokens"] == 25
    assert result.iloc[0]["total_tokens"] == 40


def test_openai_wrap_records_cost(db):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_openai_response(
        model="gpt-4o", prompt_tokens=1000, completion_tokens=500
    )
    client = anysql.openai(db).wrap(mock_client)
    client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "Hi"}])
    result = db.query("SELECT cost_usd FROM llm_responses")
    assert result.iloc[0]["cost_usd"] > 0


def test_openai_wrap_passes_through_response(db):
    mock_response = _make_openai_response(content="Summary here")
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    client = anysql.openai(db).wrap(mock_client)
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "Hi"}])
    assert response.choices[0].message.content == "Summary here"


def test_openai_adapter_with_task_type(db):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_openai_response()
    client = anysql.openai(db, task_type="summarization").wrap(mock_client)
    client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "Hi"}])
    result = db.query("SELECT task_type FROM llm_responses")
    assert result.iloc[0]["task_type"] == "summarization"


# ── Claude cost calculation ─────────────────────────────────────────────────

def test_claude_cost_sonnet():
    cost = claude_calc_cost("claude-sonnet-4-6", 1000, 500)
    expected = (1000 * 3.00 + 500 * 15.00) / 1_000_000
    assert abs(cost - expected) < 1e-10


def test_claude_cost_haiku():
    cost = claude_calc_cost("claude-haiku-4-5", 1000, 500)
    expected = (1000 * 0.80 + 500 * 4.00) / 1_000_000
    assert abs(cost - expected) < 1e-10


def test_claude_cost_unknown_returns_none():
    assert claude_calc_cost("some-unknown-model", 100, 50) is None


# ── Claude adapter wrapping ─────────────────────────────────────────────────

def _make_claude_response(model="claude-sonnet-4-6", content="Summary", input_tokens=10, output_tokens=20):
    mock = MagicMock()
    mock.id = "msg_test123"
    mock.stop_reason = "end_turn"
    block = MagicMock()
    block.text = content
    mock.content = [block]
    mock.usage.input_tokens = input_tokens
    mock.usage.output_tokens = output_tokens
    return mock


def test_claude_wrap_inserts_llm_response(db):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_claude_response()
    client = anysql.claude(db).wrap(mock_client)
    client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello"}]
    )
    assert db.count("llm.responses") == 1


def test_claude_wrap_records_tokens(db):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_claude_response(
        input_tokens=15, output_tokens=25
    )
    client = anysql.claude(db).wrap(mock_client)
    client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hi"}]
    )
    result = db.query("SELECT prompt_tokens, completion_tokens FROM llm_responses")
    assert result.iloc[0]["prompt_tokens"] == 15
    assert result.iloc[0]["completion_tokens"] == 25


def test_claude_wrap_passes_through_response(db):
    mock_response = _make_claude_response(content="Claude reply")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    client = anysql.claude(db).wrap(mock_client)
    response = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=100,
        messages=[{"role": "user", "content": "Hi"}]
    )
    assert response.content[0].text == "Claude reply"


def test_openai_getattr_passthrough(db):
    mock_client = MagicMock()
    mock_client.models = "models_attr"
    client = anysql.openai(db).wrap(mock_client)
    assert client.models == "models_attr"


def test_claude_getattr_passthrough(db):
    mock_client = MagicMock()
    mock_client.beta = "beta_attr"
    client = anysql.claude(db).wrap(mock_client)
    assert client.beta == "beta_attr"
```

**Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_adapters.py -v
```
Expected: ImportError on claude adapter

**Step 3: Implement `anysql/adapters/openai.py`**

Create from `docs/ANYSQL_CLAUDE_CODE.md` (File 5, lines 842–950).

**Step 4: Implement `anysql/adapters/claude.py`**

Create from `docs/ANYSQL_CLAUDE_CODE.md` (File 6, lines 954–1062).

**Step 5: Create `anysql/adapters/generic.py`**

```python
"""
anysql/adapters/generic.py
Generic JSON/dict adapter for any LLM provider.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional


class GenericAdapter:
    def __init__(self, db):
        self._db = db

    def log(
        self,
        model: str,
        prompt: str,
        content: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        cost_usd: Optional[float] = None,
        latency_ms: Optional[int] = None,
        task_type: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        from ..context import get_context
        ctx = get_context()
        response_id = str(uuid.uuid4())
        total = (prompt_tokens or 0) + (completion_tokens or 0)
        self._db.insert("llm.responses", [{
            "response_id":        response_id,
            "model":              model,
            "prompt":             prompt,
            "content":            content,
            "prompt_tokens":      prompt_tokens,
            "completion_tokens":  completion_tokens,
            "total_tokens":       total or None,
            "cost_usd":           cost_usd,
            "latency_ms":         latency_ms,
            "task_type":          task_type or ctx.get("tags", {}).get("task_type"),
            "session_id":         session_id or ctx.get("session_id"),
            "created_at":         datetime.now(timezone.utc).isoformat(),
        }])
        return response_id
```

**Step 6: Run tests to confirm they pass**

```bash
pytest tests/test_adapters.py -v
```
Expected: all tests PASS

**Step 7: Commit**

```bash
git add anysql/adapters/openai.py anysql/adapters/claude.py anysql/adapters/generic.py tests/test_adapters.py
git commit -m "feat: add OpenAI and Claude transparent proxy adapters"
```

---

### Task 8: `anysql/tracers/agent.py` + `anysql/tracers/rag.py`

**Files:**
- Create: `anysql/tracers/agent.py`
- Create: `anysql/tracers/rag.py`
- Create: `tests/test_tracers.py`

**Step 1: Write the failing tests**

Create `tests/test_tracers.py`:
```python
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
import anysql
from anysql.tracers.agent import AgentTracer
from anysql.tracers.rag import RAGTracer


@pytest.fixture
def db():
    return anysql.init(":memory:")


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
```

**Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_tracers.py -v
```
Expected: ImportError

**Step 3: Implement `anysql/tracers/agent.py`**

Create from `docs/ANYSQL_CLAUDE_CODE.md` (File 7, lines 1070–1202).

**Step 4: Implement `anysql/tracers/rag.py`**

Create from `docs/ANYSQL_CLAUDE_CODE.md` (File 8, lines 1206–1327).

**Step 5: Run tests to confirm they pass**

```bash
pytest tests/test_tracers.py -v
```
Expected: all tests PASS

**Step 6: Commit**

```bash
git add anysql/tracers/agent.py anysql/tracers/rag.py tests/test_tracers.py
git commit -m "feat: add AgentTracer (LangChain + manual) and RAGTracer with format auto-detection"
```

---

### Task 9: Full `anysql/__init__.py` + `anysql/cli.py`

**Files:**
- Modify: `anysql/__init__.py`
- Create: `anysql/cli.py`

**Step 1: Replace `__init__.py` with full public API**

Replace `anysql/__init__.py` with the exact content from `docs/ANYSQL_CLAUDE_CODE.md` (File 9, lines 1335–1418).

**Step 2: Create `anysql/cli.py`**

```python
"""
anysql/cli.py
CLI entry point: anysql query "SELECT ..." / anysql stats
"""
import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="anysql",
        description="anySQL — SQL analytics for AI systems",
    )
    subparsers = parser.add_subparsers(dest="command")

    # anysql query "SELECT ..."
    query_parser = subparsers.add_parser("query", help="Run SQL against anysql.db")
    query_parser.add_argument("sql", help="SQL query string")
    query_parser.add_argument("--db", default="anysql.db", help="Path to SQLite database")

    # anysql stats
    stats_parser = subparsers.add_parser("stats", help="Show row counts for all tables")
    stats_parser.add_argument("--db", default="anysql.db", help="Path to SQLite database")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    import anysql
    db = anysql.init(args.db)

    if args.command == "query":
        result = db.query(args.sql)
        print(result.to_string(index=False))

    elif args.command == "stats":
        from anysql.schema import TABLE_NAMES
        print("\nanySQL table row counts:")
        for table in TABLE_NAMES:
            count = db.count(table)
            print(f"  {table:<25} {count:>6} rows")
        print()
```

**Step 3: Validate Phase 2 gate**

```bash
python -c "
import anysql
from unittest.mock import MagicMock

db = anysql.init(':memory:')

# OpenAI adapter
mock = MagicMock()
resp = MagicMock()
resp.id = 'r1'
resp.choices = [MagicMock()]
resp.choices[0].message.content = 'test'
resp.choices[0].finish_reason = 'stop'
resp.usage.prompt_tokens = 10
resp.usage.completion_tokens = 20
mock.chat.completions.create.return_value = resp
client = anysql.openai(db).wrap(mock)
client.chat.completions.create(model='gpt-4o', messages=[{'role':'user','content':'Hi'}])

# RAGTracer
rag = anysql.rag_tracer(db)
qid = rag.before_retrieval('test')
rag.after_retrieval(qid, [{'text': 'chunk', 'score': 0.9}])
rag.record_eval(qid, score=0.8)

# Queries
print(db.model_comparison())
print(db.rag_failure_modes())
print('Phase 2 gate: PASS')
"
```
Expected: prints DataFrames then `Phase 2 gate: PASS`

**Step 4: Run all tests**

```bash
pytest tests/ -v
```
Expected: all tests PASS

**Step 5: Commit**

```bash
git add anysql/__init__.py anysql/cli.py
git commit -m "feat: Phase 2 complete — full public API and CLI working"
```

---

## Phase 3: Validation & Distribution

**Gate:** `pytest tests/` passes; `python examples/realtime_combined_demo.py` runs in mock mode

---

### Task 10: Demo file — `examples/realtime_openai_demo.py`

**Files:**
- Create: `examples/realtime_openai_demo.py`

**Step 1: Create the OpenAI demo**

The demo must:
1. Define 12 BBC News articles inline (no download)
2. Auto-detect `OPENAI_API_KEY` — use real client if set, mock client if not
3. Wrap client with `anysql.openai(db, task_type="summarization")`
4. Tag each article batch with `@anysql.context(feature="bbc_summarizer", segment="demo")`
5. Run all 5 UC queries and print results
6. Mock client returns realistic responses (varied tokens, latencies, scores)

```python
"""
examples/realtime_openai_demo.py
BBC News dataset — OpenAI (gpt-4o vs gpt-4o-mini), all 5 use cases.
Runs in mock mode automatically if OPENAI_API_KEY is not set.
"""
import os
import uuid
import time
import random
from datetime import datetime, timezone
from unittest.mock import MagicMock
import anysql

# ── Embedded BBC News articles (no download required) ─────────────────────
BBC_ARTICLES = [
    {"id": "bbc_001", "topic": "technology", "title": "AI advances in 2024",
     "text": "Artificial intelligence systems have made remarkable progress this year, with large language models demonstrating capabilities that were previously considered years away. Researchers at major labs report breakthrough results in reasoning, coding, and multimodal understanding."},
    {"id": "bbc_002", "topic": "politics", "title": "Election results reshape parliament",
     "text": "The general election produced a hung parliament for the first time in over a decade, with the leading party falling short of an outright majority. Coalition negotiations are expected to last several weeks as party leaders weigh their options."},
    {"id": "bbc_003", "topic": "business", "title": "Markets rally on rate cut hopes",
     "text": "Stock markets surged to record highs after the central bank signaled it may begin cutting interest rates sooner than expected. The FTSE 100 rose 2.3% while the S&P 500 hit a new all-time high in early trading."},
    {"id": "bbc_004", "topic": "science", "title": "New exoplanet discovered in habitable zone",
     "text": "Astronomers have announced the discovery of an Earth-sized exoplanet orbiting within the habitable zone of a nearby star. The planet, located just 12 light-years away, shows signs of a rocky surface and is considered a prime candidate for further study."},
    {"id": "bbc_005", "topic": "health", "title": "Study links sleep patterns to longevity",
     "text": "A large-scale study following 500,000 participants over 25 years found strong correlations between consistent sleep schedules and longer lifespans. Researchers recommend seven to nine hours per night for optimal health outcomes."},
    {"id": "bbc_006", "topic": "technology", "title": "Chip shortages ease as new fabs come online",
     "text": "The global semiconductor shortage that plagued industries from automotive to consumer electronics is finally easing, as new fabrication plants in the United States and Europe reach production capacity."},
    {"id": "bbc_007", "topic": "environment", "title": "Arctic ice reaches record low",
     "text": "Sea ice extent in the Arctic reached a new record minimum this September, scientists confirmed. The decline is consistent with climate model projections and raises concerns about accelerating feedback loops in the global climate system."},
    {"id": "bbc_008", "topic": "sports", "title": "England wins cricket series",
     "text": "England secured the test cricket series with a dominant final-match performance, completing a dramatic comeback after losing the first two matches. The victory is celebrated as one of the greatest series reversals in modern cricket history."},
    {"id": "bbc_009", "topic": "business", "title": "Startup raises record seed round",
     "text": "A London-based fintech startup raised £45 million in what analysts are calling the largest seed round in European fintech history. The company plans to use the funds to expand its payment infrastructure to 15 new markets."},
    {"id": "bbc_010", "topic": "health", "title": "New cancer therapy shows promise",
     "text": "Clinical trials for a novel CAR-T cell therapy targeting solid tumors have shown a 60% response rate in patients who had exhausted other treatment options. The therapy is expected to seek regulatory approval within 18 months."},
    {"id": "bbc_011", "topic": "politics", "title": "Trade deal signed after years of talks",
     "text": "After three years of negotiations, a comprehensive trade agreement was signed between the UK and India. The deal covers goods, services, and investment, and is expected to add £28 billion to bilateral trade within a decade."},
    {"id": "bbc_012", "topic": "science", "title": "Quantum computer breaks encryption record",
     "text": "A quantum computer has factored a 2048-bit RSA key for the first time, a milestone that cryptographers had long anticipated. Security experts are urging organizations to accelerate the transition to post-quantum cryptography standards."},
]

MODELS = ["gpt-4o", "gpt-4o-mini"]
MOCK_SUMMARIES = {
    "gpt-4o": "A comprehensive and accurate summary covering all key points with appropriate nuance.",
    "gpt-4o-mini": "A concise summary covering the main points efficiently.",
}


def build_mock_client(model: str):
    mock = MagicMock()
    def create(**kwargs):
        r = MagicMock()
        r.id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        r.model = model
        r.choices = [MagicMock()]
        r.choices[0].message.content = MOCK_SUMMARIES[model]
        r.choices[0].finish_reason = "stop"
        # Realistic token counts
        r.usage.prompt_tokens = random.randint(80, 150)
        r.usage.completion_tokens = random.randint(40, 80)
        time.sleep(random.uniform(0.01, 0.05))  # simulate latency
        return r
    mock.chat.completions.create.side_effect = create
    return mock


def run_demo():
    print("=" * 60)
    print("anySQL — BBC News OpenAI Demo")
    print("=" * 60)

    use_real = bool(os.environ.get("OPENAI_API_KEY"))
    mode = "LIVE API" if use_real else "MOCK MODE"
    print(f"\nRunning in {mode}\n")

    db = anysql.init(":memory:", echo=False)

    for model in MODELS:
        if use_real:
            from openai import OpenAI
            raw_client = OpenAI()
        else:
            raw_client = build_mock_client(model)

        client = anysql.openai(db, task_type="summarization").wrap(raw_client)

        @anysql.context(feature="bbc_summarizer", segment="demo")
        def summarize_batch(articles, model_name):
            for article in articles:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{
                        "role": "user",
                        "content": f"Summarize in 2 sentences: {article['text']}"
                    }]
                )
                # Record eval (mock scoring based on topic)
                topic_scores = {"technology": 0.92, "science": 0.88, "health": 0.85,
                                "business": 0.80, "politics": 0.75, "sports": 0.78,
                                "environment": 0.82}
                score = topic_scores.get(article["topic"], 0.80)
                if model == "gpt-4o-mini":
                    score *= 0.92  # mini slightly lower quality
                score += random.uniform(-0.05, 0.05)

                rag = anysql.rag_tracer(db)
                qid = rag.before_retrieval(article["title"])
                rag.after_retrieval(qid, [
                    {"id": f"{article['id']}_chunk_1", "text": article["text"][:200],
                     "score": random.uniform(0.75, 0.95), "source": f"{article['topic']}_corpus.txt"},
                ])
                rag.record_eval(
                    query_id=qid,
                    score=round(min(max(score, 0.0), 1.0), 3),
                    actual=response.choices[0].message.content,
                    model=model_name,
                    prompt_id=f"summarizer_{article['topic']}",
                    prompt_version="v1",
                )

        summarize_batch(BBC_ARTICLES, model)
        print(f"Processed {len(BBC_ARTICLES)} articles with {model}")

    print("\n" + "=" * 60)
    print("UC1: Multi-Model Comparison")
    print("=" * 60)
    print(db.model_comparison().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC2: Eval Debt (prompts by last evaluation date)")
    print("=" * 60)
    print(db.eval_debt().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC3: Cost by Feature Flag")
    print("=" * 60)
    print(db.cost_by_feature().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC4: Tool Failure Rates (no agent tools in this demo)")
    print("=" * 60)
    print(db.tool_failure_rates().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC5: RAG Failure Mode Classification")
    print("=" * 60)
    print(db.rag_failure_modes().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC5: Chunk Quality Ranking by Source Document")
    print("=" * 60)
    print(db.chunk_quality_ranking().to_string(index=False))

    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()
```

**Step 2: Run demo in mock mode**

```bash
python examples/realtime_openai_demo.py
```
Expected: prints results for all 5 UCs, ends with "Demo complete."

**Step 3: Commit**

```bash
git add examples/realtime_openai_demo.py
git commit -m "feat: add BBC News OpenAI demo with mock mode"
```

---

### Task 11: Demo file — `examples/realtime_claude_demo.py`

**Files:**
- Create: `examples/realtime_claude_demo.py`

**Step 1: Create the Claude demo**

Follow the same structure as Task 10 but with:
- 15 AG News articles (tech, sports, business, science categories)
- Models: `claude-sonnet-4-6`, `claude-haiku-4-5`
- Mock client uses `mock.messages.create.side_effect`
- Mock response structure: `mock.id`, `mock.content[0].text`, `mock.usage.input_tokens`, `mock.usage.output_tokens`, `mock.stop_reason`

```python
"""
examples/realtime_claude_demo.py
AG News dataset — Claude (sonnet-4-6 vs haiku-4-5), all 5 use cases.
Runs in mock mode automatically if ANTHROPIC_API_KEY is not set.
"""
import os
import uuid
import time
import random
from unittest.mock import MagicMock
import anysql

AG_ARTICLES = [
    {"id": "ag_001", "topic": "technology", "title": "Tech giants report record profits",
     "text": "The largest technology companies reported combined quarterly profits exceeding $100 billion for the first time, driven by cloud computing and advertising revenue growth that outpaced analyst expectations significantly."},
    {"id": "ag_002", "topic": "sports", "title": "World Cup host city announced",
     "text": "FIFA announced the host cities for the upcoming World Cup, with the tournament to be spread across three continents for the first time. The decision follows years of bidding competition and infrastructure assessments by the governing body."},
    {"id": "ag_003", "topic": "business", "title": "Oil prices hit six-month high",
     "text": "Crude oil prices climbed to a six-month high after OPEC+ announced an unexpected extension of production cuts. Brent crude rose 4% to $94 per barrel as traders priced in tighter supply through the end of the year."},
    {"id": "ag_004", "topic": "science", "title": "Mars water discovery confirmed",
     "text": "NASA scientists confirmed the discovery of large underground water ice deposits near the Martian equator, a finding that significantly changes the calculus for future human missions and potential in-situ resource utilization."},
    {"id": "ag_005", "topic": "technology", "title": "Open source LLM matches GPT-4",
     "text": "A research team released an open-source large language model that matches GPT-4 performance on standard benchmarks while requiring significantly less compute to run. The release has sparked debate about the pace of AI democratization."},
    {"id": "ag_006", "topic": "business", "title": "Merger creates largest bank in Asia",
     "text": "Two of Asia's largest financial institutions completed their merger, creating the continent's biggest bank by assets. The combined entity will have over $4 trillion in assets and operations across 40 countries."},
    {"id": "ag_007", "topic": "sports", "title": "Olympic records broken in swimming",
     "text": "Three world records were broken on a single day at the World Swimming Championships, with athletes crediting improved training methods, advanced swimsuit technology, and high-altitude preparation camps for the unprecedented performances."},
    {"id": "ag_008", "topic": "science", "title": "Antibiotic resistance breakthrough",
     "text": "Researchers discovered a novel compound that kills antibiotic-resistant bacteria through a previously unknown mechanism, offering hope in the fight against superbugs that currently kill over a million people annually worldwide."},
    {"id": "ag_009", "topic": "technology", "title": "Self-driving trucks begin highway routes",
     "text": "The first fully autonomous commercial freight trucks began operating on a major interstate highway corridor, marking a milestone for the logistics industry. The trucks operate without safety drivers during daytime hours on approved routes."},
    {"id": "ag_010", "topic": "business", "title": "Luxury goods demand surges in Southeast Asia",
     "text": "Sales of luxury goods in Southeast Asia grew 35% year-over-year, outpacing all other global regions. Analysts attribute the boom to a growing affluent middle class and increased spending among younger consumers under 35."},
    {"id": "ag_011", "topic": "sports", "title": "Historic tennis comeback at Wimbledon",
     "text": "A player staged the most remarkable comeback in Wimbledon history, winning from two sets down and a match point deficit to claim the championship in a five-set final that lasted over four hours."},
    {"id": "ag_012", "topic": "technology", "title": "Cybersecurity breach affects millions",
     "text": "A major data breach at a US healthcare provider exposed the personal and medical records of 47 million patients, making it one of the largest healthcare data breaches in history and prompting congressional hearings."},
    {"id": "ag_013", "topic": "science", "title": "Brain-computer interface allows speech",
     "text": "A paralyzed patient spoke using a brain-computer interface that decoded neural signals and converted them to synthesized speech at near-natural rates. The clinical trial results represent a major advance for assistive communication technology."},
    {"id": "ag_014", "topic": "business", "title": "Shipping costs return to pre-pandemic levels",
     "text": "Global container shipping rates have fallen back to 2019 levels after three years of extraordinary volatility, providing relief to manufacturers and retailers who pass on lower logistics costs to consumers."},
    {"id": "ag_015", "topic": "sports", "title": "Football league expands to new markets",
     "text": "A major professional football league announced expansion franchises in two new cities, bringing total league membership to 36 teams. The expansion fees of $2 billion each set a new record for professional sports franchise valuations."},
]

MODELS = ["claude-sonnet-4-6", "claude-haiku-4-5"]
MOCK_SUMMARIES = {
    "claude-sonnet-4-6": "A thorough and nuanced summary capturing key context and implications.",
    "claude-haiku-4-5": "A focused, efficient summary of the core facts.",
}


def build_mock_client(model: str):
    mock = MagicMock()
    def create(**kwargs):
        r = MagicMock()
        r.id = f"msg_{uuid.uuid4().hex[:8]}"
        r.stop_reason = "end_turn"
        block = MagicMock()
        block.text = MOCK_SUMMARIES[model]
        r.content = [block]
        r.usage.input_tokens = random.randint(80, 150)
        r.usage.output_tokens = random.randint(40, 80)
        time.sleep(random.uniform(0.01, 0.05))
        return r
    mock.messages.create.side_effect = create
    return mock


def run_demo():
    print("=" * 60)
    print("anySQL — AG News Claude Demo")
    print("=" * 60)

    use_real = bool(os.environ.get("ANTHROPIC_API_KEY"))
    mode = "LIVE API" if use_real else "MOCK MODE"
    print(f"\nRunning in {mode}\n")

    db = anysql.init(":memory:")

    topic_scores = {"technology": 0.90, "science": 0.87, "business": 0.82, "sports": 0.78}

    for model in MODELS:
        if use_real:
            import anthropic
            raw_client = anthropic.Anthropic()
        else:
            raw_client = build_mock_client(model)

        client = anysql.claude(db, task_type="summarization").wrap(raw_client)

        @anysql.context(feature="ag_summarizer", segment="demo")
        def summarize_batch(articles, model_name):
            for article in articles:
                response = client.messages.create(
                    model=model_name,
                    max_tokens=200,
                    messages=[{"role": "user", "content": f"Summarize: {article['text']}"}]
                )
                score = topic_scores.get(article["topic"], 0.80)
                if "haiku" in model_name:
                    score *= 0.93
                score += random.uniform(-0.04, 0.04)

                rag = anysql.rag_tracer(db)
                qid = rag.before_retrieval(article["title"])
                rag.after_retrieval(qid, [
                    {"id": f"{article['id']}_c1", "text": article["text"][:200],
                     "score": random.uniform(0.72, 0.96), "source": f"{article['topic']}_news.txt"},
                ])
                rag.record_eval(
                    query_id=qid,
                    score=round(min(max(score, 0.0), 1.0), 3),
                    actual=response.content[0].text,
                    model=model_name,
                    prompt_id=f"summarizer_{article['topic']}",
                    prompt_version="v1",
                )

        summarize_batch(AG_ARTICLES, model)
        print(f"Processed {len(AG_ARTICLES)} articles with {model}")

    print("\n" + "=" * 60)
    print("UC1: Multi-Model Comparison (Sonnet vs Haiku)")
    print("=" * 60)
    print(db.model_comparison().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC2: Prompt Regressions (none expected — single version)")
    print("=" * 60)
    print(db.eval_debt().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC3: Cost by Feature")
    print("=" * 60)
    print(db.cost_by_feature().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC5: RAG Failure Modes")
    print("=" * 60)
    print(db.rag_failure_modes().to_string(index=False))

    print("\n" + "=" * 60)
    print("UC5: Similarity Calibration")
    print("=" * 60)
    print(db.similarity_calibration().to_string(index=False))

    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()
```

**Step 2: Run demo**

```bash
python examples/realtime_claude_demo.py
```
Expected: prints results, ends with "Demo complete."

**Step 3: Commit**

```bash
git add examples/realtime_claude_demo.py
git commit -m "feat: add AG News Claude demo with mock mode"
```

---

### Task 12: Demo file — `examples/realtime_combined_demo.py`

**Files:**
- Create: `examples/realtime_combined_demo.py`

**Step 1: Create the combined head-to-head demo**

This demo:
- Uses 20 Reuters R8 articles across 8 categories
- Runs all 4 models (gpt-4o, gpt-4o-mini, claude-sonnet-4-6, claude-haiku-4-5)
- Uses `AgentTracer` to simulate a multi-step agent workflow for UC4
- Records two prompt versions (v1, v2) to trigger `prompt_regressions()` for UC2
- Prints all 5 UC analyses with model head-to-head comparison

```python
"""
examples/realtime_combined_demo.py
Reuters R8 dataset — All 4 models head-to-head, all 5 use cases.
Runs in mock mode automatically if API keys are not set.
"""
import os
import uuid
import time
import random
from unittest.mock import MagicMock
import anysql

REUTERS_ARTICLES = [
    {"id": "r_001", "topic": "earn", "title": "Company reports strong quarterly earnings",
     "text": "The company posted quarterly earnings of $3.2 billion, beating analyst expectations by 12%. Revenue grew 18% year-over-year to $24.5 billion, driven primarily by subscription services and enterprise software sales. Management raised full-year guidance."},
    {"id": "r_002", "topic": "acq", "title": "Acquisition reshapes pharmaceutical sector",
     "text": "A major pharmaceutical company completed its $68 billion acquisition of a mid-size biotech firm, gaining control of a promising pipeline of oncology drugs. The deal required divestitures in three overlapping therapeutic areas to satisfy regulators."},
    {"id": "r_003", "topic": "money-fx", "title": "Dollar strengthens on Fed signals",
     "text": "The US dollar strengthened against a basket of major currencies after Federal Reserve officials signaled a willingness to keep interest rates higher for longer than previously anticipated, citing persistent services inflation."},
    {"id": "r_004", "topic": "grain", "title": "Drought threatens global wheat harvest",
     "text": "A prolonged drought across key wheat-growing regions in North America and central Asia is expected to reduce global wheat production by 8% this year, pushing prices to a two-year high and raising food security concerns in import-dependent nations."},
    {"id": "r_005", "topic": "crude", "title": "Refinery outages tighten US fuel supply",
     "text": "Unexpected refinery outages across the Gulf Coast have tightened gasoline and diesel supplies in the United States, pushing retail fuel prices up 15 cents per gallon in two weeks and prompting the Department of Energy to monitor inventory levels."},
    {"id": "r_006", "topic": "trade", "title": "Trade deficit narrows unexpectedly",
     "text": "The US trade deficit narrowed more than expected in the latest month, as goods exports hit a record high while imports declined for the third consecutive month. Economists say the trend may be temporary given strong domestic consumption."},
    {"id": "r_007", "topic": "interest", "title": "Central bank holds rates steady",
     "text": "The central bank held its benchmark interest rate steady for the third consecutive meeting, citing balanced risks to inflation and employment. The decision was unanimous and the accompanying statement offered few clues about the timing of future moves."},
    {"id": "r_008", "topic": "ship", "title": "New container shipping route opens",
     "text": "A major shipping alliance announced a new direct container route connecting Southeast Asian manufacturing hubs to European ports, cutting transit times by four days compared to existing routes and offering weekly sailings from day one."},
    {"id": "r_009", "topic": "earn", "title": "Retailer misses profit forecasts",
     "text": "A major retailer reported quarterly profits below analyst estimates after a surprise increase in inventory write-downs and rising labor costs compressed margins. The company warned that full-year earnings would come in at the low end of its guidance range."},
    {"id": "r_010", "topic": "acq", "title": "Tech buyout raises competition concerns",
     "text": "Antitrust regulators in the US and EU opened parallel investigations into a proposed $45 billion technology acquisition, citing concerns about market concentration in cloud infrastructure and potential harm to startup competitors."},
    {"id": "r_011", "topic": "money-fx", "title": "Emerging market currencies under pressure",
     "text": "Several emerging market currencies hit multi-year lows against the US dollar as rising US Treasury yields triggered capital outflows. Central banks in three countries intervened in currency markets while one raised interest rates by 50 basis points."},
    {"id": "r_012", "topic": "grain", "title": "Record corn surplus weighs on prices",
     "text": "US corn production reached a record high this harvest season, with total output 15% above last year's crop. The surplus has pushed corn futures to a three-year low, squeezing farm incomes but benefiting food manufacturers and livestock producers."},
    {"id": "r_013", "topic": "crude", "title": "OPEC output deal extended",
     "text": "OPEC and its allies agreed to extend existing oil production cuts for a further six months, citing uncertain demand growth and high inventories in consuming nations. Several members lobbied unsuccessfully for deeper cuts during the ministerial meeting."},
    {"id": "r_014", "topic": "trade", "title": "Steel tariffs spark retaliation threats",
     "text": "The United States announced new tariffs on imported steel and aluminum, citing national security concerns, prompting immediate retaliation threats from the European Union, Canada, and Mexico. Industry groups warned the tariffs would raise costs for domestic manufacturers."},
    {"id": "r_015", "topic": "interest", "title": "Mortgage rates hit 20-year high",
     "text": "The average 30-year fixed mortgage rate climbed above 8% for the first time in over two decades, dealing a severe blow to housing affordability and pushing existing home sales to their lowest level since 2010 as potential buyers wait on the sidelines."},
    {"id": "r_016", "topic": "ship", "title": "Port congestion eases at major hubs",
     "text": "Congestion at the world's busiest container ports has eased significantly compared to the pandemic peak, with vessel wait times at major Asian hubs returning to pre-2020 norms. Shipping executives credit new berth capacity and improved scheduling coordination."},
    {"id": "r_017", "topic": "earn", "title": "Bank profits rise on interest income",
     "text": "Major US banks reported sharp increases in quarterly profits as rising interest rates boosted net interest income, more than offsetting higher loan loss provisions. Investment banking fees remained subdued amid cautious deal activity."},
    {"id": "r_018", "topic": "acq", "title": "Airline merger approved with conditions",
     "text": "Regulators approved a merger between two major domestic airlines, but required the combined carrier to divest slots at six congested airports and maintain existing service to 52 smaller communities as conditions for clearance."},
    {"id": "r_019", "topic": "grain", "title": "Soybean exports break records",
     "text": "US soybean exports hit a quarterly record, driven by strong demand from China and concerns about crop shortfalls in South America. The surge has helped narrow the agricultural trade deficit and boosted farm income projections for the year."},
    {"id": "r_020", "topic": "crude", "title": "EV adoption slows oil demand growth",
     "text": "The International Energy Agency revised down its long-term oil demand forecast for the fourth consecutive year, citing faster-than-expected electric vehicle adoption in China and Europe as the primary driver of slower demand growth through 2030."},
]

OPENAI_MODELS = ["gpt-4o", "gpt-4o-mini"]
CLAUDE_MODELS = ["claude-sonnet-4-6", "claude-haiku-4-5"]

TOPIC_SCORES = {
    "earn": 0.88, "acq": 0.85, "money-fx": 0.83,
    "grain": 0.80, "crude": 0.82, "trade": 0.81,
    "interest": 0.84, "ship": 0.79,
}
MODEL_QUALITY = {
    "gpt-4o": 1.00, "gpt-4o-mini": 0.91,
    "claude-sonnet-4-6": 0.99, "claude-haiku-4-5": 0.90,
}


def make_openai_mock(model):
    mock = MagicMock()
    def create(**kwargs):
        r = MagicMock()
        r.id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        r.model = model
        r.choices = [MagicMock()]
        r.choices[0].message.content = f"[{model}] Summary of the article content."
        r.choices[0].finish_reason = "stop"
        r.usage.prompt_tokens = random.randint(90, 160)
        r.usage.completion_tokens = random.randint(35, 75)
        time.sleep(random.uniform(0.01, 0.03))
        return r
    mock.chat.completions.create.side_effect = create
    return mock


def make_claude_mock(model):
    mock = MagicMock()
    def create(**kwargs):
        r = MagicMock()
        r.id = f"msg_{uuid.uuid4().hex[:8]}"
        r.stop_reason = "end_turn"
        block = MagicMock()
        block.text = f"[{model}] Concise summary of the Reuters article."
        r.content = [block]
        r.usage.input_tokens = random.randint(90, 160)
        r.usage.output_tokens = random.randint(35, 75)
        time.sleep(random.uniform(0.01, 0.03))
        return r
    mock.messages.create.side_effect = create
    return mock


def run_demo():
    print("=" * 70)
    print("anySQL — Reuters R8 Combined Demo (All 4 Models Head-to-Head)")
    print("=" * 70)

    use_openai = bool(os.environ.get("OPENAI_API_KEY"))
    use_claude = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"\nOpenAI: {'LIVE' if use_openai else 'MOCK'} | Claude: {'LIVE' if use_claude else 'MOCK'}\n")

    db = anysql.init(":memory:")
    agent_tracer = anysql.agent_tracer(db, session_id="demo_agent_session")

    # ── Run OpenAI models ───────────────────────────────────────────────────
    for model in OPENAI_MODELS:
        if use_openai:
            from openai import OpenAI
            raw = OpenAI()
        else:
            raw = make_openai_mock(model)

        client = anysql.openai(db, task_type="summarization").wrap(raw)

        @anysql.context(feature=f"reuters_{model.replace('-','_')}", segment="research")
        def run_openai_batch(articles, m):
            for version in ["v1", "v2"]:
                for article in articles[:10]:  # first 10 articles per version
                    response = client.chat.completions.create(
                        model=m,
                        messages=[{"role": "user", "content": f"Summarize: {article['text']}"}]
                    )
                    base_score = TOPIC_SCORES.get(article["topic"], 0.80) * MODEL_QUALITY[m]
                    # v2 has slight quality drop to trigger regression detection
                    if version == "v2":
                        base_score *= 0.88
                    score = base_score + random.uniform(-0.03, 0.03)

                    rag = anysql.rag_tracer(db)
                    qid = rag.before_retrieval(article["title"])
                    rag.after_retrieval(qid, [
                        {"id": f"{article['id']}_c1", "text": article["text"][:200],
                         "score": random.uniform(0.70, 0.95), "source": f"reuters_{article['topic']}.txt"},
                    ])
                    rag.record_eval(
                        query_id=qid,
                        score=round(min(max(score, 0.0), 1.0), 3),
                        actual=response.choices[0].message.content,
                        model=m, prompt_id=f"reuters_{article['topic']}", prompt_version=version,
                    )

        run_openai_batch(REUTERS_ARTICLES, model)
        print(f"OpenAI {model}: {10 * 2} calls (v1+v2)")

    # ── Run Claude models ───────────────────────────────────────────────────
    for model in CLAUDE_MODELS:
        if use_claude:
            import anthropic
            raw = anthropic.Anthropic()
        else:
            raw = make_claude_mock(model)

        client = anysql.claude(db, task_type="summarization").wrap(raw)

        @anysql.context(feature=f"reuters_{model.replace('-','_').replace('.','_')}", segment="research")
        def run_claude_batch(articles, m):
            for version in ["v1", "v2"]:
                for article in articles[10:20]:  # last 10 articles per version
                    response = client.messages.create(
                        model=m, max_tokens=200,
                        messages=[{"role": "user", "content": f"Summarize: {article['text']}"}]
                    )
                    base_score = TOPIC_SCORES.get(article["topic"], 0.80) * MODEL_QUALITY[m]
                    if version == "v2":
                        base_score *= 0.89
                    score = base_score + random.uniform(-0.03, 0.03)

                    rag = anysql.rag_tracer(db)
                    qid = rag.before_retrieval(article["title"])
                    rag.after_retrieval(qid, [
                        {"id": f"{article['id']}_c1", "text": article["text"][:200],
                         "score": random.uniform(0.70, 0.95), "source": f"reuters_{article['topic']}.txt"},
                    ])
                    rag.record_eval(
                        query_id=qid, score=round(min(max(score, 0.0), 1.0), 3),
                        actual=response.content[0].text,
                        model=m, prompt_id=f"reuters_{article['topic']}", prompt_version=version,
                    )

        run_claude_batch(REUTERS_ARTICLES, model)
        print(f"Claude {model}: {10 * 2} calls (v1+v2)")

    # ── UC4: Simulate agent tool calls ──────────────────────────────────────
    print("\nSimulating agent tool calls for UC4...")
    tools = ["web_search", "doc_retrieval", "fact_checker", "summarizer", "citation_finder"]
    for session_num in range(5):
        session_id = f"agent_session_{session_num:03d}"
        tracer = anysql.agent_tracer(db, session_id=session_id)
        for step, tool in enumerate(random.sample(tools, random.randint(3, 5))):
            # Introduce some failures
            status = "error" if (tool == "fact_checker" and random.random() < 0.4) else "success"
            tracer.trace_tool_call(
                tool, input={"query": "Reuters article context"},
                output="tool result" if status == "success" else None,
                status=status,
                error_message="API timeout" if status == "error" else None,
                latency_ms=random.randint(50, 800),
            )
            tracer.trace_step("tool_call", description=f"Execute {tool}")

    print("\n" + "=" * 70)
    print("UC1: Multi-Model Comparison (All 4 Models)")
    print("=" * 70)
    print(db.model_comparison().to_string(index=False))

    print("\n" + "=" * 70)
    print("UC2: Prompt Regressions (v1→v2 score drops)")
    print("=" * 70)
    regressions = db.prompt_regressions(threshold=-0.05)
    print(regressions.to_string(index=False) if len(regressions) > 0 else "(none detected)")

    print("\n" + "=" * 70)
    print("UC3: Cost by Feature Flag (per model/pipeline)")
    print("=" * 70)
    print(db.cost_by_feature().to_string(index=False))

    print("\n" + "=" * 70)
    print("UC4: Tool Failure Rates")
    print("=" * 70)
    print(db.tool_failure_rates().to_string(index=False))

    print("\n" + "=" * 70)
    print("UC5: RAG Failure Modes")
    print("=" * 70)
    print(db.rag_failure_modes().to_string(index=False))

    print("\n" + "=" * 70)
    print("UC5: Similarity Score Calibration")
    print("=" * 70)
    print(db.similarity_calibration().to_string(index=False))

    print(f"\nTotal rows: {repr(db)}")
    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()
```

**Step 2: Run demo**

```bash
python examples/realtime_combined_demo.py
```
Expected: full output for all 5 UCs, ends with "Demo complete."

**Step 3: Commit**

```bash
git add examples/realtime_combined_demo.py
git commit -m "feat: add Reuters R8 combined demo with all 4 models and all 5 UCs"
```

---

### Task 13: Complete `pyproject.toml` + `docs/QUERIES.md`

**Files:**
- Modify: `pyproject.toml`
- Create: `docs/QUERIES.md`

**Step 1: Replace pyproject.toml with full version**

Replace `pyproject.toml` with the exact content from `docs/ANYSQL_CLAUDE_CODE.md` (File 10, lines 1424–1477).

**Step 2: Create `docs/QUERIES.md`**

```markdown
# anySQL Canonical SQL Query Library

## UC1 — Model Cost/Quality Tradeoff

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

## UC2 — Prompt Regression Detection

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
       ROUND(avg_score, 3), ROUND(prev_score, 3),
       ROUND(avg_score - prev_score, 3) AS delta
FROM with_prev
WHERE (avg_score - prev_score) < -0.10
ORDER BY delta ASC;
```

## UC3 — Cost Attribution by Feature

```sql
SELECT feature_flag, user_segment,
       COUNT(*) AS runs,
       ROUND(SUM(total_cost_usd), 4) AS total_cost_usd,
       ROUND(SUM(revenue_attributed) / NULLIF(SUM(total_cost_usd), 0), 2) AS roi
FROM pipeline_runs
GROUP BY feature_flag, user_segment
ORDER BY total_cost_usd DESC;
```

## UC4 — Tool Failure Analysis

```sql
SELECT tool_name,
       COUNT(*) AS calls,
       SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS failures,
       ROUND(100.0 * SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) / COUNT(*), 2) AS failure_pct,
       ROUND(AVG(latency_ms), 0) AS avg_ms
FROM agent_tool_calls
GROUP BY tool_name
ORDER BY failure_pct DESC;
```

## UC5 — RAG Failure Mode Classification

```sql
SELECT failure_mode, COUNT(*) AS queries, ROUND(AVG(answer_quality), 3) AS avg_quality
FROM (
    SELECT r.query_id,
           MAX(r.similarity_score) AS best_retrieval,
           e.score AS answer_quality,
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
```

**Step 3: Commit**

```bash
git add pyproject.toml docs/QUERIES.md
git commit -m "chore: finalize pyproject.toml and add canonical SQL query library"
```

---

### Task 14: Phase 3 gate — run full test suite

**Step 1: Run all tests**

```bash
pytest tests/ -v --tb=short
```
Expected: all tests PASS, 0 failures

**Step 2: Run combined demo end-to-end**

```bash
python examples/realtime_combined_demo.py
```
Expected: UC1–UC5 output printed, ends with "Demo complete."

**Step 3: Run OpenAI and Claude demos**

```bash
python examples/realtime_openai_demo.py
python examples/realtime_claude_demo.py
```
Expected: both complete without errors

**Step 4: Test CLI**

```bash
# Validate CLI entry point loads
python -m anysql.cli --help
```
Expected: help text with `query` and `stats` subcommands

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: Phase 3 complete — tests, demos, and full distribution ready"
```

---

## Summary

| Phase | Files | Gate |
|-------|-------|------|
| Phase 1 — Core | schema, storage, engine, `__init__` stub | `import anysql; db = anysql.init(); print(db)` |
| Phase 2 — Integration | context, adapters, tracers, `__init__` full, cli | All 5 UCs return DataFrames with mock data |
| Phase 3 — Validation | tests (5 files), demos (3 files), pyproject, docs | `pytest tests/` passes; demo runs in mock mode |

Total tasks: 14 | Total commits: ~14
