"""
anysql/adapters/generic.py
Generic JSON/dict adapter for any LLM provider.
"""

import uuid
from datetime import datetime, timezone


class GenericAdapter:
    def __init__(self, db):
        self._db = db

    def log(
        self,
        model: str,
        prompt: str,
        content: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        cost_usd: float | None = None,
        latency_ms: int | None = None,
        task_type: str | None = None,
        session_id: str | None = None,
        **kwargs,
    ) -> str:
        from ..context import get_context

        ctx = get_context()
        response_id = str(uuid.uuid4())
        total = (prompt_tokens or 0) + (completion_tokens or 0)
        self._db.insert(
            "llm.responses",
            [
                {
                    "response_id": response_id,
                    "model": model,
                    "prompt": prompt,
                    "content": content,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total or None,
                    "cost_usd": cost_usd,
                    "latency_ms": latency_ms,
                    "task_type": task_type or ctx.get("tags", {}).get("task_type"),
                    "session_id": session_id or ctx.get("session_id"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            ],
        )
        return response_id
