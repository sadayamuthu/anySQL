"""
aiohttp HTTP server — anySQL Proxy on port 4242.

Routes:
  POST /v1/chat/completions  — OpenAI-compatible (Cursor, Windsurf, Continue)
  POST /v1/messages          — Anthropic-native (Claude Code, Zed)
  GET  /v1/models            — Model list (IDE verification requests)
  OPTIONS /*                 — CORS preflight (required for Cursor/Electron)
"""
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import aiohttp
from aiohttp import web

from .detector import detect_ide
from .extractor import extract_context, get_git_context
from .interceptor import (
    detect_provider,
    forward_and_stream,
    parse_token_counts,
    calculate_cost,
)
from .writer import DBWriter

_CORS_HEADERS = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Authorization, Content-Type, anthropic-version, x-api-key",
}

_MODELS_RESPONSE = json.dumps({
    "object": "list",
    "data": [
        {"id": "gpt-4o",            "object": "model"},
        {"id": "gpt-4o-mini",       "object": "model"},
        {"id": "claude-sonnet-4-6", "object": "model"},
    ],
})


def create_app(writer: DBWriter, api_keys: dict) -> web.Application:
    """
    Create and return the aiohttp Application.

    Args:
        writer:   DBWriter instance (already started)
        api_keys: dict with keys 'openai' and/or 'anthropic' → real API keys
    """
    app = web.Application()
    handler = RequestHandler(writer=writer, api_keys=api_keys)
    app.router.add_route("OPTIONS", "/{path_info:.*}", handler.handle_cors)
    app.router.add_get("/v1/models", handler.handle_models)
    app.router.add_post("/v1/chat/completions", handler.handle_llm)
    app.router.add_post("/v1/messages", handler.handle_llm)

    async def on_cleanup(_app: web.Application) -> None:
        await handler.close()

    app.on_cleanup.append(on_cleanup)
    return app


class RequestHandler:
    def __init__(self, writer: DBWriter, api_keys: dict):
        self._writer = writer
        self._api_keys = api_keys
        self._session: Optional[aiohttp.ClientSession] = None  # shared aiohttp session

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return shared aiohttp ClientSession, creating it on first use."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the shared session on shutdown."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def handle_cors(self, request: web.Request) -> web.Response:
        return web.Response(status=204, headers=_CORS_HEADERS)

    async def handle_models(self, request: web.Request) -> web.Response:
        return web.Response(
            body=_MODELS_RESPONSE,
            content_type="application/json",
            headers=_CORS_HEADERS,
        )

    async def handle_llm(self, request: web.Request) -> web.StreamResponse:
        body_bytes = await request.read()
        try:
            body = json.loads(body_bytes)
        except Exception:
            body = {}

        headers = dict(request.headers)
        path = request.path
        provider = detect_provider(path)
        api_key = self._api_keys.get(provider, "")

        ide = detect_ide(headers)
        ctx = extract_context(body, ide)
        git_ctx = get_git_context(ctx.get("file_path"))

        response_id = str(uuid.uuid4())
        context_id = str(uuid.uuid4())
        t0 = time.monotonic()

        # Stream response back to IDE
        stream_response = web.StreamResponse(headers=_CORS_HEADERS)
        await stream_response.prepare(request)

        session = await self._get_session()
        chunks = []
        async for chunk in forward_and_stream(
            method=request.method,
            path=path,
            headers=headers,
            body=body_bytes,
            provider=provider,
            api_key=api_key,
            session=session,
        ):
            await stream_response.write(chunk)
            chunks.append(chunk)

        await stream_response.write_eof()
        latency_ms = int((time.monotonic() - t0) * 1000)

        # Parse response for token counts (best-effort)
        full_body = b"".join(chunks)
        try:
            resp_json = json.loads(full_body)
        except Exception:
            resp_json = {}

        prompt_tokens, completion_tokens = parse_token_counts(resp_json, provider)
        model = resp_json.get("model") or body.get("model", "unknown")
        cost_usd = calculate_cost(model, prompt_tokens, completion_tokens)
        now = datetime.now(timezone.utc)

        # Non-blocking write to DuckDB
        self._writer.enqueue(
            response_record={
                "response_id":       response_id,
                "model":             model,
                "prompt_tokens":     prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens":      prompt_tokens + completion_tokens,
                "cost_usd":          cost_usd,
                "latency_ms":        latency_ms,
                "created_at":        now,
            },
            context_record={
                "context_id":        context_id,
                "response_id":       response_id,
                "ide_name":          ide,
                "request_type":      ctx.get("request_type"),
                "file_path":         ctx.get("file_path"),
                "language":          ctx.get("language"),
                "git_repo":          git_ctx.get("git_repo"),
                "git_branch":        git_ctx.get("git_branch"),
                "lines_of_context":  ctx.get("lines_of_context"),
                "has_error_context": ctx.get("has_error_context"),
                "suggestion_length": completion_tokens,
                "created_at":        now,
            },
        )

        return stream_response
