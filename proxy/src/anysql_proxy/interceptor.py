"""
Request forwarding and streaming passthrough.

The interceptor:
  1. Detects which provider to forward to (OpenAI vs Anthropic)
  2. Swaps the fake IDE API key for the real provider key
  3. Streams the response back to the IDE chunk by chunk
  4. Collects token counts + calculates cost for logging

Auth headers are never logged.
"""
from typing import AsyncIterator

import aiohttp

_PROVIDER_BASE_URLS = {
    "openai":    "https://api.openai.com",
    "anthropic": "https://api.anthropic.com",
}

# Cost per 1M tokens in USD (prompt, completion)
# Update as provider pricing changes.
# IMPORTANT: more-specific names must come before general prefixes (e.g.
# "gpt-4o-mini" before "gpt-4o") because calculate_cost uses substring matching.
_MODEL_COSTS: dict[str, tuple[float, float]] = {
    "gpt-4o-mini":         (0.15,   0.60),   # must be before gpt-4o
    "gpt-4o":              (5.00,  15.00),
    "gpt-4-turbo":         (10.00, 30.00),
    "gpt-3.5-turbo":       (0.50,   1.50),
    "claude-opus-4-6":     (15.00, 75.00),
    "claude-sonnet-4-6":   (3.00,  15.00),
    "claude-haiku-4-5":    (0.25,   1.25),
}

_HEADERS_TO_STRIP = {"host", "content-length", "transfer-encoding", "connection"}


def detect_provider(path: str) -> str:
    """Return 'anthropic' for /v1/messages, 'openai' for everything else."""
    if path.startswith("/v1/messages"):
        return "anthropic"
    return "openai"


def build_forward_headers(
    headers: dict,
    api_key: str,
    provider: str,
) -> dict:
    """
    Build headers for the upstream request.
    - Strips hop-by-hop headers and host
    - Substitutes the real API key (never logs it)
    - Uses x-api-key for Anthropic, Authorization Bearer for OpenAI
    """
    forward = {
        k: v for k, v in headers.items()
        if k.lower() not in _HEADERS_TO_STRIP | {"authorization", "x-api-key"}
    }
    if provider == "anthropic":
        forward["x-api-key"] = api_key
        forward.setdefault("anthropic-version", "2023-06-01")
    else:
        forward["authorization"] = f"Bearer {api_key}"
    return forward


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Return estimated cost in USD. Returns 0.0 for unknown models."""
    # Normalize model name — strip date suffixes like -20251001
    normalized = model.lower()
    for known_model, (prompt_rate, completion_rate) in _MODEL_COSTS.items():
        if known_model in normalized:
            return (
                prompt_tokens * prompt_rate / 1_000_000
                + completion_tokens * completion_rate / 1_000_000
            )
    return 0.0


async def forward_and_stream(
    method: str,
    path: str,
    headers: dict,
    body: bytes,
    provider: str,
    api_key: str,
) -> AsyncIterator[bytes]:
    """
    Forward request to provider and yield response chunks as they arrive.
    This is an async generator — the caller iterates it to stream chunks
    back to the IDE while collecting the full response for logging.
    """
    base_url = _PROVIDER_BASE_URLS[provider]
    url = f"{base_url}{path}"
    forward_headers = build_forward_headers(headers, api_key=api_key, provider=provider)

    async with aiohttp.ClientSession() as session:
        async with session.request(
            method, url, headers=forward_headers, data=body
        ) as resp:
            async for chunk in resp.content.iter_any():
                yield chunk


def parse_token_counts(body: dict, provider: str) -> tuple[int, int]:
    """
    Extract (prompt_tokens, completion_tokens) from a parsed response body.
    Returns (0, 0) if not parseable.
    """
    if provider == "openai":
        usage = body.get("usage", {})
        return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    elif provider == "anthropic":
        usage = body.get("usage", {})
        return usage.get("input_tokens", 0), usage.get("output_tokens", 0)
    return 0, 0
