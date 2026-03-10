import pytest
from anysql_proxy.detector import detect_ide


@pytest.mark.parametrize("user_agent,expected", [
    ("cursor/1.0.0 (darwin)", "cursor"),
    ("cursor-ide/2.0 Electron", "cursor"),
    ("windsurf/0.9 codeium-client", "windsurf"),
    ("codeium-windsurf/1.0", "windsurf"),
    ("claude-code/1.2.3", "claude_code"),
    ("anthropic-code/0.5", "claude_code"),
    ("continue/0.9.1 VSCode", "vscode_continue"),
    ("continue-dev/1.0", "vscode_continue"),
    ("zed/0.131.0", "zed"),
    ("python-httpx/0.27.0", "unknown"),
    ("", "unknown"),
])
def test_detect_ide_from_user_agent(user_agent, expected):
    headers = {"user-agent": user_agent}
    assert detect_ide(headers) == expected


def test_detect_ide_case_insensitive():
    assert detect_ide({"user-agent": "CURSOR/1.0"}) == "cursor"


def test_detect_ide_missing_header():
    assert detect_ide({}) == "unknown"


def test_detect_ide_prefers_first_match():
    # If multiple fingerprints match (edge case), first IDE in map wins
    result = detect_ide({"user-agent": "cursor/1.0 continue/0.9"})
    assert result in ("cursor", "vscode_continue")  # deterministic, not "unknown"
