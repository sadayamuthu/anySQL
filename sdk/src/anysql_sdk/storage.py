"""
anysql_sdk/storage.py
SQLite persistence layer — rows stored as JSON blobs.
Schema enforcement happens at the Arrow layer in engine.py, not here.
"""

import json
import sqlite3
from typing import Optional
from .schema import TABLE_NAMES


class Storage:
    def __init__(self, db_path: str = "anysql.db"):
        self._in_memory = (db_path == ":memory:")
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_tables()

    def save(self, table: str, records: list[dict]) -> None:
        if self._in_memory or not records:
            return
        sql_table = self._sql_table(table)
        cur = self._conn.cursor()
        cur.executemany(
            f"INSERT INTO {sql_table} (data) VALUES (?)",
            [(json.dumps(r, default=str),) for r in records],
        )
        self._conn.commit()

    def load(self, table: str) -> list[dict]:
        if self._in_memory:
            return []
        sql_table = self._sql_table(table)
        cur = self._conn.cursor()
        cur.execute(f"SELECT data FROM {sql_table}")
        return [json.loads(r[0]) for r in cur.fetchall()]

    def delete(self, table: str, where: Optional[str] = None) -> int:
        sql_table = self._sql_table(table)
        cur = self._conn.cursor()
        # NOTE: `where` is unparameterized — only pass internally with trusted values.
        if where:
            cur.execute(f"DELETE FROM {sql_table} WHERE {where}")
        else:
            cur.execute(f"DELETE FROM {sql_table}")
        self._conn.commit()
        return cur.rowcount

    def row_count(self, table: str) -> int:
        sql_table = self._sql_table(table)
        cur = self._conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {sql_table}")
        return cur.fetchone()[0]

    def _init_tables(self) -> None:
        cur = self._conn.cursor()
        for table in TABLE_NAMES:
            sql_table = self._sql_table(table)
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {sql_table} (
                    id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL
                )
            """)
        self._conn.commit()

    @staticmethod
    def _sql_table(table: str) -> str:
        return table.replace(".", "_")

    def close(self) -> None:
        self._conn.close()
