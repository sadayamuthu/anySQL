"""
Per-IDE configuration writers.

Each function modifies the IDE's config file to point its LLM base URL
to the anySQL proxy at http://localhost:4242.
"""
import json
import os
from pathlib import Path

import click


def setup_ide(ide: str) -> None:
    handlers = {
        "cursor":      _setup_cursor,
        "claude-code": _setup_claude_code,
        "windsurf":    _setup_windsurf,
        "vscode":      _setup_vscode_continue,
        "zed":         _setup_zed,
    }
    handlers[ide]()


def _setup_cursor() -> None:
    settings_path = Path.home() / ".cursor" / "settings.json"
    _update_json(settings_path, {
        "cursor.openAIApiBaseUrl": "http://localhost:4242",
    })
    click.echo("Cursor configured. Restart Cursor to apply.")
    click.echo(f"Updated: {settings_path}")


def _setup_claude_code() -> None:
    rc_file = _find_shell_rc()
    line = "export ANTHROPIC_BASE_URL=http://localhost:4242"
    content = rc_file.read_text() if rc_file.exists() else ""
    if line not in content:
        rc_file.write_text(content + f"\n{line}\n")
    click.echo(f"Added to {rc_file}:")
    click.echo(f"  {line}")
    click.echo("Run: source ~/.zshrc  (or restart terminal)")


def _setup_windsurf() -> None:
    settings_path = Path.home() / ".windsurf" / "settings.json"
    _update_json(settings_path, {
        "windsurf.apiBaseUrl": "http://localhost:4242",
    })
    click.echo("Windsurf configured. Restart Windsurf to apply.")
    click.echo(f"Updated: {settings_path}")


def _setup_vscode_continue() -> None:
    config_path = Path.home() / ".continue" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    config.setdefault("models", [])
    if not any(m.get("apiBase") == "http://localhost:4242" for m in config["models"]):
        config["models"].append({
            "title": "GPT-4o (via anySQL)",
            "provider": "openai",
            "model": "gpt-4o",
            "apiBase": "http://localhost:4242",
            "apiKey": "anysql-proxy",
        })
    config_path.write_text(json.dumps(config, indent=2))
    click.echo(f"Continue configured: {config_path}")


def _setup_zed() -> None:
    settings_path = Path.home() / ".config" / "zed" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    assistant = config.setdefault("assistant", {})
    assistant["version"] = "2"
    assistant["openai_api_url"] = "http://localhost:4242"
    settings_path.write_text(json.dumps(config, indent=2))
    click.echo("Zed configured. Restart Zed to apply.")
    click.echo(f"Updated: {settings_path}")


def _update_json(path: Path, updates: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    config = json.loads(path.read_text()) if path.exists() else {}
    config.update(updates)
    path.write_text(json.dumps(config, indent=2))


def _find_shell_rc() -> Path:
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return Path.home() / ".zshrc"
    return Path.home() / ".bashrc"
