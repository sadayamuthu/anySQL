import time
import pytest
import duckdb
import tempfile
import os
from datetime import datetime, timezone
from anysql_proxy.writer import DBWriter


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test.duckdb")


@pytest.fixture
def writer(db_path):
    w = DBWriter(db_path)
    w.start()
    yield w
    w.stop()


def make_response(response_id="r1"):
    return {
        "response_id": response_id,
        "model": "gpt-4o",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "cost_usd": 0.001,
        "latency_ms": 200,
        "created_at": datetime.now(timezone.utc),
    }


def make_context(response_id="r1", context_id="c1"):
    return {
        "context_id": context_id,
        "response_id": response_id,
        "ide_name": "cursor",
        "request_type": "chat",
        "file_path": "src/main.py",
        "language": "python",
        "git_repo": "myrepo",
        "git_branch": "main",
        "lines_of_context": 42,
        "has_error_context": False,
        "suggestion_length": 50,
        "created_at": datetime.now(timezone.utc),
    }


def test_writer_creates_tables(writer, db_path):
    time.sleep(0.1)
    writer.stop()  # close write connection before opening read-only (DuckDB limitation)
    conn = duckdb.connect(db_path, read_only=True)
    tables = {r[0] for r in conn.execute("SHOW TABLES").fetchall()}
    conn.close()
    assert "llm_responses" in tables
    assert "ide_context" in tables


def test_writer_stores_record(writer, db_path):
    writer.enqueue(make_response("r1"), make_context("r1", "c1"))
    time.sleep(3)  # wait for 2s flush + buffer
    writer.stop()  # close write connection before opening read-only (DuckDB limitation)

    conn = duckdb.connect(db_path, read_only=True)
    rows = conn.execute("SELECT response_id FROM llm_responses").fetchall()
    conn.close()
    assert any(r[0] == "r1" for r in rows)


def test_writer_stores_context(writer, db_path):
    writer.enqueue(make_response("r2"), make_context("r2", "c2"))
    time.sleep(3)
    writer.stop()  # close write connection before opening read-only (DuckDB limitation)

    conn = duckdb.connect(db_path, read_only=True)
    rows = conn.execute("SELECT ide_name, language FROM ide_context").fetchall()
    conn.close()
    assert any(r == ("cursor", "python") for r in rows)


def test_writer_batches_multiple_records(writer, db_path):
    for i in range(5):
        writer.enqueue(make_response(f"r{i}"), make_context(f"r{i}", f"c{i}"))
    time.sleep(3)
    writer.stop()  # close write connection before opening read-only (DuckDB limitation)

    conn = duckdb.connect(db_path, read_only=True)
    count = conn.execute("SELECT COUNT(*) FROM llm_responses").fetchone()[0]
    conn.close()
    assert count == 5
