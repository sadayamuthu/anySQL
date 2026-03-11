"""
anysql-proxy CLI entry point.

Commands:
  anysql-proxy start          — start proxy in foreground
  anysql-proxy stop           — stop background proxy
  anysql-proxy status         — show proxy status
  anysql-proxy setup <ide>    — configure IDE to use proxy
  anysql-proxy keys set <provider> <key>  — store API key
"""
import os
import signal
import sys
from pathlib import Path

import click

from .keys import KeyStore
from .server_runner import run_server
from .setup_writers import setup_ide


@click.group()
def main():
    """anySQL Proxy — intercept and log IDE LLM calls."""


@main.command()
@click.option("--port", default=4242, show_default=True, help="Proxy port")
@click.option("--db", default="~/.anysql/ide.duckdb", show_default=True, help="DuckDB path")
def start(port: int, db: str):
    """Start the proxy (foreground). Use a process manager for background."""
    click.echo(f"anySQL Proxy starting on http://localhost:{port}")
    click.echo(f"Database: {db}")
    run_server(port=port, db_path=db)


@main.command()
def stop():
    """Stop the proxy (sends SIGTERM to the stored PID)."""
    pid_file = Path.home() / ".anysql" / "proxy.pid"
    if not pid_file.exists():
        click.echo("No PID file found — proxy may not be running.")
        return
    pid = int(pid_file.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        pid_file.unlink()
        click.echo(f"Sent SIGTERM to proxy (PID {pid}).")
    except ProcessLookupError:
        pid_file.unlink(missing_ok=True)
        click.echo("Proxy was not running (stale PID file removed).")


@main.command()
def status():
    """Check if the proxy is running."""
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:4242/v1/models", timeout=2)
        click.echo("anySQL Proxy  running  http://localhost:4242")
    except Exception:
        click.echo("anySQL Proxy  not running")


@main.command()
@click.argument("ide", type=click.Choice(["cursor", "claude-code", "windsurf", "vscode", "zed"]))
def setup(ide: str):
    """Configure IDE to route LLM calls through the proxy."""
    setup_ide(ide)


@main.group()
def keys():
    """Manage API keys."""


@keys.command("set")
@click.argument("provider", type=click.Choice(["openai", "anthropic"]))
@click.argument("api_key")
def keys_set(provider: str, api_key: str):
    """Store an API key (encrypted at rest)."""
    ks = KeyStore()
    ks.set(provider, api_key)
    click.echo(f"Stored {provider} key.")
