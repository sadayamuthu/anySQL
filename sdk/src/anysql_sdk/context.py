"""
anysql/context.py
Cost attribution via Python contextvars.
Works across sync, async, and threaded code without any setup.
"""

import uuid
import time
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from typing import Optional, Callable

_current_run_id     = ContextVar("run_id",      default=None)
_current_feature    = ContextVar("feature",     default=None)
_current_segment    = ContextVar("segment",     default=None)
_current_session_id = ContextVar("session_id",  default=None)
_current_pipeline   = ContextVar("pipeline",    default=None)
_current_tags       = ContextVar("tags",        default={})

_engine = None  # set by anysql.init()


def get_context() -> dict:
    return {
        "run_id":        _current_run_id.get(),
        "feature_flag":  _current_feature.get(),
        "user_segment":  _current_segment.get(),
        "session_id":    _current_session_id.get(),
        "pipeline_name": _current_pipeline.get(),
        "tags":          _current_tags.get(),
    }


def _set_context(feature=None, segment=None, session_id=None, pipeline=None, tags=None):
    tokens = {}
    if feature    is not None: tokens["feature"]    = _current_feature.set(feature)
    if segment    is not None: tokens["segment"]    = _current_segment.set(segment)
    if session_id is not None: tokens["session_id"] = _current_session_id.set(session_id)
    if pipeline   is not None: tokens["pipeline"]   = _current_pipeline.set(pipeline)
    if tags       is not None: tokens["tags"]       = _current_tags.set({**_current_tags.get(), **tags})
    tokens["run_id"] = _current_run_id.set(str(uuid.uuid4()))
    return tokens


def _reset_context(tokens):
    for key, token in tokens.items():
        var = dict(feature=_current_feature, segment=_current_segment,
                   session_id=_current_session_id, pipeline=_current_pipeline,
                   tags=_current_tags, run_id=_current_run_id).get(key)
        if var:
            var.reset(token)


def context(feature=None, segment=None, session_id=None, pipeline=None, tags=None):
    """
    Decorator — tags all LLM calls within the function for cost attribution.

    Usage:
        @anysql.context(feature="premium_summarizer", segment="enterprise")
        def summarize(text: str) -> str:
            return openai_client.chat.completions.create(...)
    """
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def sync_wrapper(*args, **kwargs):
            tokens = _set_context(feature, segment, session_id, pipeline, tags)
            start = time.monotonic()
            try:
                return fn(*args, **kwargs)
            finally:
                _flush_run(int((time.monotonic() - start) * 1000))
                _reset_context(tokens)

        @wraps(fn)
        async def async_wrapper(*args, **kwargs):
            tokens = _set_context(feature, segment, session_id, pipeline, tags)
            start = time.monotonic()
            try:
                return await fn(*args, **kwargs)
            finally:
                _flush_run(int((time.monotonic() - start) * 1000))
                _reset_context(tokens)

        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper

    return decorator


@contextmanager
def context_scope(feature=None, segment=None, session_id=None, pipeline=None, tags=None):
    """
    Context manager version — for notebooks and inline code.

    Usage:
        with anysql.context_scope(feature="rag_search", segment="free"):
            result = my_rag_pipeline(query)
    """
    tokens = _set_context(feature, segment, session_id, pipeline, tags)
    start = time.monotonic()
    try:
        yield get_context()
    finally:
        _flush_run(int((time.monotonic() - start) * 1000))
        _reset_context(tokens)


def _set_engine(engine):
    global _engine
    _engine = engine


def _flush_run(elapsed_ms: int):
    if _engine is None:
        return
    ctx = get_context()
    if not any([ctx["feature_flag"], ctx["pipeline_name"]]):
        return
    from datetime import datetime, timezone
    _engine.insert("pipeline.runs", [{
        "run_id":           ctx["run_id"] or str(uuid.uuid4()),
        "session_id":       ctx["session_id"],
        "feature_flag":     ctx["feature_flag"],
        "user_segment":     ctx["user_segment"],
        "pipeline_name":    ctx["pipeline_name"],
        "total_latency_ms": elapsed_ms,
        "status":           "success",
        "tags":             ctx["tags"],
        "started_at":       datetime.now(timezone.utc).isoformat(),
    }])
