"""Thin wrapper to start aiohttp server with DBWriter."""
import logging
import os
from pathlib import Path
from aiohttp import web
from .writer import DBWriter
from .server import create_app
from .keys import KeyStore

_PID_FILE = Path.home() / ".anysql" / "proxy.pid"


def run_server(port: int = 4242, db_path: str = "~/.anysql/ide.duckdb") -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        force=True,  # override any handlers already set by aiohttp/other libs
    )
    ks = KeyStore()
    api_keys = {
        "openai":    ks.get("openai") or "",
        "anthropic": ks.get("anthropic") or "",
    }
    writer = DBWriter(db_path)
    writer.start()
    _PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(os.getpid()))
    app = create_app(writer=writer, api_keys=api_keys)
    try:
        web.run_app(app, port=port)
    finally:
        writer.stop()
        _PID_FILE.unlink(missing_ok=True)
