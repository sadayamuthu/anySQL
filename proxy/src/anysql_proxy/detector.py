"""
IDE fingerprinting from HTTP request headers.

Every IDE coding assistant includes a recognizable string in its User-Agent
header. We match against known fingerprints to identify the caller.
"""

# Map IDE name → list of substrings to look for in User-Agent (lowercase)
_FINGERPRINTS: dict[str, list[str]] = {
    "cursor":          ["cursor/", "cursor-ide"],
    "windsurf":        ["windsurf", "codeium", "antigravity"],
    "claude_code":     ["claude-code", "anthropic-code"],
    "vscode_continue": ["continue/", "continue-dev"],
    "zed":             ["zed/"],
}


def detect_ide(headers: dict) -> str:
    """
    Return the IDE name from request headers, or 'unknown'.

    Args:
        headers: dict of HTTP headers (keys may be any case)

    Returns:
        One of: 'cursor', 'windsurf', 'claude_code', 'vscode_continue',
                'zed', 'unknown'
    """
    ua = (headers.get("user-agent") or headers.get("User-Agent") or "").lower()
    for ide, fingerprints in _FINGERPRINTS.items():
        if any(fp in ua for fp in fingerprints):
            return ide
    return "unknown"
