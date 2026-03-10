"""
DBWriter — background thread that batches DuckDB inserts.

The async request handler calls enqueue() which is non-blocking (< 1μs).
A stdlib queue bridges the async event loop and the writer thread.
The writer flushes every 50 rows or every 2 seconds, whichever comes first.
"""
import logging
import queue
import threading
import time
import duckdb
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_responses (
    response_id       VARCHAR NOT NULL,
    model             VARCHAR,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    cost_usd          DOUBLE,
    latency_ms        INTEGER,
    created_at        TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS ide_context (
    context_id        VARCHAR NOT NULL,
    response_id       VARCHAR,
    ide_name          VARCHAR,
    request_type      VARCHAR,
    file_path         VARCHAR,
    language          VARCHAR,
    git_repo          VARCHAR,
    git_branch        VARCHAR,
    lines_of_context  INTEGER,
    has_error_context BOOLEAN,
    suggestion_length INTEGER,
    created_at        TIMESTAMPTZ NOT NULL
);
"""

_INSERT_RESPONSE = """
INSERT INTO llm_responses VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

_INSERT_CONTEXT = """
INSERT INTO ide_context VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class DBWriter:
    """
    Single-writer, background-thread DuckDB writer.

    Usage:
        writer = DBWriter("~/.anysql/ide.duckdb")
        writer.start()
        writer.enqueue(response_record, context_record)  # from async handler
        writer.stop()  # on shutdown — flushes remaining records
    """

    BATCH_SIZE = 50
    FLUSH_INTERVAL_S = 2.0

    def __init__(self, db_path: str):
        self._db_path = str(Path(db_path).expanduser())
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._conn: duckdb.DuckDBPyConnection | None = None

    def start(self) -> None:
        """Create DB file + tables, start background writer thread."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(self._db_path, read_only=False)
        self._conn.execute(_SCHEMA)
        self._conn.commit()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="anysql-writer")
        self._thread.start()

    def stop(self) -> None:
        """Signal stop and flush remaining records. Idempotent."""
        if self._stop.is_set() and self._thread is None:
            return
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                logging.getLogger(__name__).warning("anysql-writer thread did not exit within timeout")
            self._thread = None
        if self._conn:
            self._conn.close()
            self._conn = None

    def enqueue(self, response_record: dict, context_record: dict) -> None:
        """Non-blocking. Call from async request handler."""
        self._queue.put_nowait((response_record, context_record))

    def _loop(self) -> None:
        batch = []
        last_flush = time.monotonic()

        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.1)
                batch.append(item)
                # Drain remaining items up to BATCH_SIZE
                while len(batch) < self.BATCH_SIZE:
                    try:
                        batch.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
            except queue.Empty:
                pass

            if batch and (
                len(batch) >= self.BATCH_SIZE
                or time.monotonic() - last_flush >= self.FLUSH_INTERVAL_S
            ):
                try:
                    self._flush(batch)
                except Exception as exc:
                    logging.getLogger(__name__).error("DBWriter flush failed: %s", exc, exc_info=True)
                    # drop batch and continue — data loss is preferable to silent death
                batch = []
                last_flush = time.monotonic()

        # Flush any remaining records before shutdown
        while not self._queue.empty():
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if batch:
            try:
                self._flush(batch)
            except Exception as exc:
                logging.getLogger(__name__).error("DBWriter flush failed: %s", exc, exc_info=True)

    def _flush(self, batch: list) -> None:
        now = datetime.now(timezone.utc)
        for response_record, context_record in batch:
            r = response_record
            self._conn.execute(_INSERT_RESPONSE, [
                r["response_id"],
                r.get("model"),
                r.get("prompt_tokens"),
                r.get("completion_tokens"),
                r.get("total_tokens"),
                r.get("cost_usd"),
                r.get("latency_ms"),
                r.get("created_at", now),
            ])
            c = context_record
            self._conn.execute(_INSERT_CONTEXT, [
                c["context_id"],
                c.get("response_id"),
                c.get("ide_name"),
                c.get("request_type"),
                c.get("file_path"),
                c.get("language"),
                c.get("git_repo"),
                c.get("git_branch"),
                c.get("lines_of_context"),
                c.get("has_error_context"),
                c.get("suggestion_length"),
                c.get("created_at", now),
            ])
        self._conn.commit()
