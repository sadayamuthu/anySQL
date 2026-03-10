import pytest
from anysql_proxy.extractor import extract_context, get_git_context


# --- extract_context ---

def test_extracts_file_path_from_cursor_pattern():
    body = {
        "messages": [{"role": "user", "content": "Current file: src/main.py\nfix this"}]
    }
    ctx = extract_context(body, "cursor")
    assert ctx["file_path"] == "src/main.py"


def test_extracts_language_from_extension():
    body = {
        "messages": [{"role": "user", "content": "Current file: app/server.ts\n"}]
    }
    ctx = extract_context(body, "cursor")
    assert ctx["language"] == "typescript"


def test_extracts_language_from_fenced_code_block():
    body = {
        "messages": [{"role": "user", "content": "```python\ndef foo(): pass\n```"}]
    }
    ctx = extract_context(body, "unknown")
    assert ctx["language"] == "python"


def test_detects_error_context():
    body = {
        "messages": [{"role": "user", "content": "Traceback (most recent call last): ..."}]
    }
    ctx = extract_context(body, "cursor")
    assert ctx["has_error_context"] is True


def test_no_error_context():
    body = {
        "messages": [{"role": "user", "content": "explain this function"}]
    }
    ctx = extract_context(body, "cursor")
    assert ctx["has_error_context"] is False


def test_infers_request_type_debug():
    body = {"messages": [{"role": "user", "content": "fix this bug in my code"}]}
    ctx = extract_context(body, "cursor")
    assert ctx["request_type"] == "debug"


def test_infers_request_type_explain():
    body = {"messages": [{"role": "user", "content": "explain what this function does"}]}
    ctx = extract_context(body, "cursor")
    assert ctx["request_type"] == "explain"


def test_infers_request_type_chat_fallback():
    body = {"messages": [{"role": "user", "content": "hello there"}]}
    ctx = extract_context(body, "cursor")
    assert ctx["request_type"] == "chat"


def test_counts_lines_of_context():
    content = "line1\nline2\nline3"
    body = {"messages": [{"role": "user", "content": content}]}
    ctx = extract_context(body, "cursor")
    assert ctx["lines_of_context"] == 2  # 2 newlines = 2 line breaks


def test_handles_anthropic_system_prompt():
    body = {
        "system": "You are a coding assistant. Current file: lib/auth.rb",
        "messages": [{"role": "user", "content": "fix this"}],
    }
    ctx = extract_context(body, "claude_code")
    assert ctx["file_path"] == "lib/auth.rb"
    assert ctx["language"] == "ruby"


def test_handles_empty_body():
    ctx = extract_context({}, "unknown")
    assert ctx["file_path"] is None
    assert ctx["language"] is None
    assert ctx["has_error_context"] is False


# --- get_git_context ---

def test_get_git_context_returns_dict_for_none():
    result = get_git_context(None)
    assert result == {}


def test_get_git_context_returns_dict_for_nonexistent_path():
    result = get_git_context("/nonexistent/path/to/nowhere/file.py")
    assert isinstance(result, dict)
    # Should not raise — may return {} if not a git repo
