"""
aiohttp HTTP server — anySQL Proxy on port 4242.

Routes:
  POST /v1/chat/completions  — OpenAI-compatible (Cursor, Windsurf, Continue)
  POST /v1/messages          — Anthropic-native (Claude Code, Zed)
  GET  /v1/models            — Model list (IDE verification requests)
  OPTIONS /*                 — CORS preflight (required for Cursor/Electron)
"""
import asyncio
import json
import logging
import time
import uuid
from datetime import datetime, timezone

import aiohttp
from aiohttp import web

log = logging.getLogger(__name__)

from .detector import detect_ide
from .extractor import extract_context, get_git_context
from .interceptor import (
    UpstreamMeta,
    detect_provider,
    forward_and_stream,
    parse_token_counts,
    parse_openai_sse,
    inject_stream_options,
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
        self._session: aiohttp.ClientSession | None = None  # shared aiohttp session

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

        # Inject stream_options so OpenAI includes usage in the final SSE chunk
        if provider == "openai":
            body_bytes = inject_stream_options(body_bytes)

        ide = detect_ide(headers)
        ctx = extract_context(body, ide)
        git_ctx = await asyncio.to_thread(get_git_context, ctx.get("file_path"))

        response_id = str(uuid.uuid4())
        context_id = str(uuid.uuid4())
        t0 = time.monotonic()

        # Stream response back to IDE
        session = await self._get_session()
        stream_response: web.StreamResponse | None = None
        chunks = []
        try:
            async for item in forward_and_stream(
                method=request.method,
                path=path,
                headers=headers,
                body=body_bytes,
                provider=provider,
                api_key=api_key,
                session=session,
            ):
                if isinstance(item, UpstreamMeta):
                    stream_response = web.StreamResponse(
                        status=item.status, headers=_CORS_HEADERS
                    )
                    stream_response.content_type = item.content_type
                    await stream_response.prepare(request)
                else:
                    await stream_response.write(item)
                    chunks.append(item)
        except Exception as exc:
            if stream_response is None:
                # prepare was never called; send a minimal error response
                stream_response = web.StreamResponse(status=502, headers=_CORS_HEADERS)
                stream_response.content_type = "text/plain"
                await stream_response.prepare(request)
            error_msg = f"data: {{\"error\": \"{type(exc).__name__}: {exc}\"}}\n\n"
            await stream_response.write(error_msg.encode())

        if stream_response is None:
            # forward_and_stream yielded nothing at all
            stream_response = web.StreamResponse(status=502, headers=_CORS_HEADERS)
            stream_response.content_type = "text/plain"
            await stream_response.prepare(request)

        await stream_response.write_eof()
        latency_ms = int((time.monotonic() - t0) * 1000)

        # Parse response for token counts (best-effort)
        full_body = b"".join(chunks)
        model_from_stream: str | None = None
        try:
            resp_json = json.loads(full_body)
        except Exception:
            resp_json = {}

        if not resp_json and provider == "openai":
            # Streaming SSE — parse line by line
            sse_usage, model_from_stream = parse_openai_sse(full_body)
            if sse_usage:
                resp_json = {"usage": sse_usage}
                log.debug("SSE usage parsed: %s model=%s", sse_usage, model_from_stream)

        prompt_tokens, completion_tokens = parse_token_counts(resp_json, provider)
        model = model_from_stream or resp_json.get("model") or body.get("model", "unknown")
        cost_usd = calculate_cost(model, prompt_tokens, completion_tokens)
        now = datetime.now(timezone.utc)

        # Non-blocking write to DuckDB
        log.info(
            "handle_llm enqueue provider=%s model=%s prompt_tokens=%d completion_tokens=%d latency_ms=%d",
            provider, model, prompt_tokens, completion_tokens, latency_ms,
        )
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
