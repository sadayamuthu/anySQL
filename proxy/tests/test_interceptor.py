import pytest
from anysql_proxy.interceptor import (
    detect_provider,
    build_forward_headers,
    calculate_cost,
)


def test_detect_provider_openai_path():
    assert detect_provider("/v1/chat/completions") == "openai"


def test_detect_provider_anthropic_path():
    assert detect_provider("/v1/messages") == "anthropic"


def test_detect_provider_models_path():
    assert detect_provider("/v1/models") == "openai"


def test_build_forward_headers_strips_host():
    headers = {"host": "localhost:4242", "content-type": "application/json",
               "authorization": "Bearer anysql-proxy", "user-agent": "cursor/1.0"}
    result = build_forward_headers(headers, api_key="sk-real-key", provider="openai")
    assert "host" not in result
    assert result["authorization"] == "Bearer sk-real-key"
    assert result["content-type"] == "application/json"
    assert result["user-agent"] == "cursor/1.0"


def test_build_forward_headers_anthropic_uses_x_api_key():
    headers = {"content-type": "application/json", "authorization": "Bearer fake"}
    result = build_forward_headers(headers, api_key="sk-ant-real", provider="anthropic")
    assert result.get("x-api-key") == "sk-ant-real"
    assert "authorization" not in result


def test_calculate_cost_gpt4o():
    cost = calculate_cost("gpt-4o", prompt_tokens=1000, completion_tokens=500)
    assert cost > 0


def test_calculate_cost_unknown_model():
    cost = calculate_cost("unknown-model-xyz", prompt_tokens=1000, completion_tokens=500)
    assert cost == 0.0


def test_calculate_cost_claude_sonnet():
    cost = calculate_cost("claude-sonnet-4-6", prompt_tokens=1000, completion_tokens=500)
    assert cost > 0
