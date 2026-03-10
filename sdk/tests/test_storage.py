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


def test_delete_returns_zero_when_empty(disk_store):
    count = disk_store.delete("llm.responses")
    assert count == 0


def test_delete_with_where_filters_rows(disk_store):
    # The `where` parameter uses raw SQL interpolation — internal use only.
    disk_store.save("llm.responses", [{"a": 1}, {"a": 2}, {"a": 3}])
    assert disk_store.row_count("llm.responses") == 3
    # Delete only the rows whose JSON blob contains '"a": 2' (trusted internal value).
    deleted = disk_store.delete("llm.responses", where="json_extract(data, '$.a') = 2")
    assert deleted == 1
    assert disk_store.row_count("llm.responses") == 2


def test_close_does_not_raise(disk_store):
    disk_store.close()
    # After close, further operations would raise — just verify close() itself is safe
