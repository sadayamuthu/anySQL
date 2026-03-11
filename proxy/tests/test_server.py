"""
Integration tests for server.py using pytest-asyncio + aiohttp TestClient/TestServer.
"""
import json
from unittest.mock import MagicMock, patch

import pytest
from aiohttp.test_utils import TestClient, TestServer

from anysql_proxy.interceptor import UpstreamMeta
from anysql_proxy.server import create_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_writer():
    """Return a MagicMock that satisfies DBWriter's interface."""
    writer = MagicMock()
    writer.enqueue = MagicMock()
    return writer


def make_app(writer=None, api_keys=None):
    if writer is None:
        writer = make_writer()
    if api_keys is None:
        api_keys = {"openai": "sk-test", "anthropic": "sk-ant-test"}
    return create_app(writer=writer, api_keys=api_keys)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_get_models_returns_json_and_cors():
    """GET /v1/models returns a JSON model list with CORS headers."""
    app = make_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/v1/models")
        assert resp.status == 200
        assert resp.headers["Content-Type"].startswith("application/json")
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"

        data = await resp.json()
        assert data["object"] == "list"
        model_ids = {m["id"] for m in data["data"]}
        assert "gpt-4o" in model_ids
        assert "gpt-4o-mini" in model_ids
        assert "claude-sonnet-4-6" in model_ids


async def test_options_returns_204_and_cors():
    """OPTIONS /* returns 204 with CORS headers."""
    app = make_app()
    async with TestClient(TestServer(app)) as client:
        resp = await client.options("/v1/chat/completions")
        assert resp.status == 204
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
        assert "POST" in resp.headers.get("Access-Control-Allow-Methods", "")


async def test_post_chat_completions_streams_chunk():
    """
    POST /v1/chat/completions — mock forward_and_stream to yield UpstreamMeta
    then a bytes chunk; verify the chunk is written to the response and
    writer.enqueue is called once.
    """
    chunk_data = b'data: {"id":"chatcmpl-1","object":"chat.completion.chunk"}\n\n'

    async def fake_forward_and_stream(**kwargs):
        yield UpstreamMeta(status=200, content_type="text/event-stream")
        yield chunk_data

    writer = make_writer()
    app = make_app(writer=writer)

    with patch("anysql_proxy.server.forward_and_stream", side_effect=fake_forward_and_stream):
        async with TestClient(TestServer(app)) as client:
            payload = json.dumps(
                {"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]}
            )
            resp = await client.post(
                "/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
            )

            assert resp.status == 200
            assert "text/event-stream" in resp.headers.get("Content-Type", "")
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"

            body = await resp.read()
            assert chunk_data in body

    # writer.enqueue should have been called exactly once
    writer.enqueue.assert_called_once()
