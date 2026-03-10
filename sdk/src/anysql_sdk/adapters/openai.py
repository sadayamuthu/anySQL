"""
anysql_sdk/adapters/openai.py
OpenAI transparent proxy wrapper.

Usage:
    from openai import OpenAI
    import anysql_sdk

    db = anysql_sdk.init("myproject.db")
    client = anysql_sdk.openai(db).wrap(OpenAI())

    # Use exactly as before — all calls auto-logged to llm.responses
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Summarize this article..."}]
    )
"""

import uuid
import time
from datetime import datetime, timezone
from typing import Optional

# Pricing: USD per 1M tokens
OPENAI_PRICING = {
    "gpt-4o":       {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":  {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":  {"input": 10.00, "output": 30.00},
    "gpt-4":        {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo":{"input": 0.50,  "output": 1.50},
    "o1":           {"input": 15.00, "output": 60.00},
    "o1-mini":      {"input": 3.00,  "output": 12.00},
    "o3-mini":      {"input": 1.10,  "output": 4.40},
}


def _calc_cost(model: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    # Match by prefix to handle dated version suffixes like "gpt-4o-2024-11-20"
    # Sort by key length descending so more-specific keys (e.g. "gpt-4o-mini") match before shorter ones (e.g. "gpt-4o")
    for key, pricing in sorted(OPENAI_PRICING.items(), key=lambda x: -len(x[0])):
        if model.startswith(key):
            return (prompt_tokens * pricing["input"] + completion_tokens * pricing["output"]) / 1_000_000
    return None


class _WrappedCompletions:
    def __init__(self, completions, db, task_type=None):
        self._completions = completions
        self._db = db
        self._task_type = task_type

    def create(self, **kwargs):
        from ..context import get_context
        start = time.monotonic()
        response = self._completions.create(**kwargs)
        latency_ms = int((time.monotonic() - start) * 1000)

        ctx = get_context()
        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages", [])
        prompt = messages[-1]["content"] if messages else ""

        usage = getattr(response, "usage", None)
        pt = getattr(usage, "prompt_tokens", 0) or 0
        ct = getattr(usage, "completion_tokens", 0) or 0

        choice = response.choices[0] if response.choices else None

        self._db.insert("llm.responses", [{
            "response_id":        response.id or str(uuid.uuid4()),
            "model":              model,
            "model_version":      getattr(response, "model", model),
            "prompt":             prompt if isinstance(prompt, str) else str(prompt),
            "content":            choice.message.content if choice else None,
            "prompt_tokens":      pt,
            "completion_tokens":  ct,
            "total_tokens":       pt + ct,
            "cost_usd":           _calc_cost(model, pt, ct),
            "latency_ms":         latency_ms,
            "stop_reason":        choice.finish_reason if choice else None,
            "task_type":          self._task_type or ctx.get("tags", {}).get("task_type"),
            "session_id":         ctx.get("session_id"),
            "created_at":         datetime.now(timezone.utc).isoformat(),
        }])
        return response


class _WrappedChat:
    def __init__(self, chat, db, task_type=None):
        self.completions = _WrappedCompletions(chat.completions, db, task_type)


class OpenAIAdapter:
    def __init__(self, db, task_type: Optional[str] = None):
        self._db = db
        self._task_type = task_type

    def wrap(self, client):
        return _WrappedOpenAIClient(client, self._db, self._task_type)


class _WrappedOpenAIClient:
    def __init__(self, client, db, task_type=None):
        self._client = client
        self.chat = _WrappedChat(client.chat, db, task_type)

    def __getattr__(self, name):
        return getattr(self._client, name)
