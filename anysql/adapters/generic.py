"""
anysql/adapters/generic.py
Generic JSON/dict adapter for any LLM provider.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional


class GenericAdapter:
    def __init__(self, db):
        self._db = db

    def log(
        self,
        model: str,
        prompt: str,
        content: Optional[str] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        cost_usd: Optional[float] = None,
        latency_ms: Optional[int] = None,
        task_type: Optional[str] = None,
        session_id: Optional[str] = None,
        **kwargs,
    ) -> str:
        from ..context import get_context
        ctx = get_context()
        response_id = str(uuid.uuid4())
        total = (prompt_tokens or 0) + (completion_tokens or 0)
        self._db.insert("llm.responses", [{
            "response_id":        response_id,
            "model":              model,
            "prompt":             prompt,
            "content":            content,
            "prompt_tokens":      prompt_tokens,
            "completion_tokens":  completion_tokens,
            "total_tokens":       total or None,
            "cost_usd":           cost_usd,
            "latency_ms":         latency_ms,
            "task_type":          task_type or ctx.get("tags", {}).get("task_type"),
            "session_id":         session_id or ctx.get("session_id"),
            "created_at":         datetime.now(timezone.utc).isoformat(),
        }])
        return response_id
