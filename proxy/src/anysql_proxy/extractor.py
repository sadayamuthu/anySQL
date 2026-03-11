"""
Context extraction from LLM request bodies.

Pulls developer context from prompt text:
  - Active file path (from IDE-specific patterns in system prompt / user message)
  - Programming language (from file extension or fenced code block)
  - Request type (chat, debug, explain, review, generate, test, completion)
  - Line count of code context in the prompt
  - Whether the prompt contains an error/stack trace
  - Git repo and branch (from filesystem, using file path)
"""
import re
import subprocess
from pathlib import Path

# Ordered list of regex patterns to find the active file path in prompt text.
# Each IDE embeds it differently; we try them in order and take the first match.
_FILE_PATTERNS = [
    r'Current file:\s*([^\n]+)',         # Cursor
    r'Active document:\s*([^\n]+)',      # Continue
    r'(?:file:|path:)\s*[`"]?([^\s`"\n]+\.\w+)',
    r'(?:```\w+\n)?#\s*([^\s]+\.\w+)',  # comment with filename
]

_EXTENSION_TO_LANGUAGE = {
    ".py": "python",   ".ts": "typescript", ".tsx": "typescript",
    ".js": "javascript", ".jsx": "javascript", ".rs": "rust",
    ".go": "go",       ".rb": "ruby",       ".java": "java",
    ".cpp": "cpp",     ".c": "c",           ".cs": "csharp",
    ".sh": "bash",     ".sql": "sql",       ".md": "markdown",
    ".kt": "kotlin",   ".swift": "swift",   ".php": "php",
}

_ERROR_PATTERN = re.compile(
    r"(Traceback|Error:|Exception:|at line \d+|stack trace|stacktrace)",
    re.IGNORECASE,
)

_REQUEST_TYPE_KEYWORDS = [
    ("debug",    ["fix", "error", "bug", "traceback", "broken", "failing"]),
    ("explain",  ["explain", "what does", "how does", "what is", "describe"]),
    ("review",   ["review", "improve", "refactor", "optimize", "clean up"]),
    ("generate", ["write", "create", "implement", "generate", "build"]),
    ("test",     ["test", "unit test", "pytest", "spec", "write tests"]),
]


def extract_context(body: dict, _ide: str) -> dict:
    """
    Extract developer context from an LLM request body.

    Args:
        body: Parsed JSON request body (OpenAI or Anthropic format)
        _ide: IDE name from detector.detect_ide() (unused, reserved for future use)

    Returns:
        dict with keys: file_path, language, request_type,
                        lines_of_context, has_error_context
    """
    parts = _collect_text_parts(body)
    full_text = "\n".join(parts)

    file_path = _extract_file_path(full_text)
    language = _extract_language(file_path, full_text)
    request_type = _infer_request_type(full_text)
    has_error = bool(_ERROR_PATTERN.search(full_text))
    lines = full_text.count("\n")

    return {
        "file_path":         file_path,
        "language":          language,
        "request_type":      request_type,
        "lines_of_context":  lines,
        "has_error_context": has_error,
    }


def get_git_context(file_path: str | None) -> dict:
    """
    Return git_repo and git_branch for the given file path.
    Returns {} if not in a git repo or on any error.
    """
    if not file_path:
        return {}
    try:
        path = Path(file_path).resolve()
        search_dir = path if path.is_dir() else path.parent
        if not search_dir.exists():
            return {}
        repo_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=search_dir, stderr=subprocess.DEVNULL, text=True
        ).strip()
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=repo_root, stderr=subprocess.DEVNULL, text=True
        ).strip()
        return {
            "git_repo":   Path(repo_root).name,
            "git_branch": branch or None,
        }
    except Exception:
        return {}


# --- private helpers ---

def _collect_text_parts(body: dict) -> list[str]:
    parts = []
    system = body.get("system", "")
    if isinstance(system, str) and system:
        parts.append(system)
    elif isinstance(system, list):
        for block in system:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
    for msg in body.get("messages", []):
        content = msg.get("content", "")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))
    return parts


def _extract_file_path(text: str) -> str | None:
    for pattern in _FILE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_language(file_path: str | None, text: str) -> str | None:
    if file_path:
        ext = Path(file_path).suffix.lower()
        lang = _EXTENSION_TO_LANGUAGE.get(ext)
        if lang:
            return lang
    # Fallback: first fenced code block language tag
    m = re.search(r"```(\w+)", text)
    if m:
        lang = m.group(1).lower()
        if lang not in ("text", "output", "bash", "shell", "sh", "plaintext"):
            return lang
    return None


def _infer_request_type(text: str) -> str:
    text_lower = text.lower()
    for request_type, keywords in _REQUEST_TYPE_KEYWORDS:
        if any(kw in text_lower for kw in keywords):
            return request_type
    if len(text) < 500 and "```" in text:
        return "completion"
    return "chat"
