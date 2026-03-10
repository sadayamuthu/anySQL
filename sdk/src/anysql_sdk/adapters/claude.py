"""
anysql_sdk/adapters/claude.py
Anthropic Claude transparent proxy wrapper.

Usage:
    import anthropic
    import anysql_sdk

    db = anysql_sdk.init("myproject.db")
    client = anysql_sdk.claude(db).wrap(anthropic.Anthropic())

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Summarize this..."}]
    )
"""

import uuid
import time
from datetime import datetime, timezone
from typing import Optional

ANTHROPIC_PRICING = {
    "claude-opus-4-6":   {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-6": {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5":  {"input": 0.80,  "output": 4.00},
    "claude-3-5-sonnet": {"input": 3.00,  "output": 15.00},
    "claude-3-5-haiku":  {"input": 0.80,  "output": 4.00},
    "claude-3-opus":     {"input": 15.00, "output": 75.00},
}


def _calc_cost(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    for key, pricing in ANTHROPIC_PRICING.items():
        if key in model or model.startswith(key):
            return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
    return None


class _WrappedMessages:
    def __init__(self, messages, db, task_type=None):
        self._messages = messages
        self._db = db
        self._task_type = task_type

    def create(self, **kwargs):
        from ..context import get_context
        start = time.monotonic()
        response = self._messages.create(**kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)

        ctx = get_context()
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        prompt = messages[-1]["content"] if messages else ""
        if isinstance(prompt, list):
            prompt = " ".join(b.get("text","") if isinstance(b, dict) else str(b) for b in prompt)

        usage = getattr(response, "usage", None)
        it = getattr(usage, "input_tokens", 0) or 0
        ot = getattr(usage, "output_tokens", 0) or 0

        content = "".join(
            block.text for block in getattr(response, "content", [])
            if hasattr(block, "text")
        )

        self._db.insert("llm.responses", [{
            "response_id":        response.id or str(uuid.uuid4()),
            "model":              model,
            "model_version":      model,
            "prompt":             prompt,
            "content":            content,
            "prompt_tokens":      it,
            "completion_tokens":  ot,
            "total_tokens":       it + ot,
            "cost_usd":           _calc_cost(model, it, ot),
            "latency_ms":         latency_ms,
            "stop_reason":        getattr(response, "stop_reason", None),
            "task_type":          self._task_type or ctx.get("tags", {}).get("task_type"),
            "session_id":         ctx.get("session_id"),
            "created_at":         datetime.now(timezone.utc).isoformat(),
        }])
        return response


class ClaudeAdapter:
    def __init__(self, db, task_type: Optional[str] = None):
        self._db = db
        self._task_type = task_type

    def wrap(self, client):
        return _WrappedAnthropicClient(client, self._db, self._task_type)


class _WrappedAnthropicClient:
    def __init__(self, client, db, task_type=None):
        self._client = client
        self.messages = _WrappedMessages(client.messages, db, task_type)

    def __getattr__(self, name):
        return getattr(self._client, name)
