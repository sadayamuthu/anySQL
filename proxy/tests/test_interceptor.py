import pytest
from anysql_proxy.interceptor import (
    detect_provider,
    build_forward_headers,
    calculate_cost,
    parse_token_counts,
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
    assert cost == pytest.approx(5.00 / 1_000_000 * 1000 + 15.00 / 1_000_000 * 500)


def test_calculate_cost_gpt4o_mini():
    cost = calculate_cost("gpt-4o-mini", prompt_tokens=1000, completion_tokens=500)
    assert cost == pytest.approx(0.15 / 1_000_000 * 1000 + 0.60 / 1_000_000 * 500)


def test_calculate_cost_unknown_model():
    cost = calculate_cost("unknown-model-xyz", prompt_tokens=1000, completion_tokens=500)
    assert cost == 0.0


def test_calculate_cost_claude_sonnet():
    cost = calculate_cost("claude-sonnet-4-6", prompt_tokens=1000, completion_tokens=500)
    assert cost > 0


def test_parse_token_counts_openai():
    body = {"usage": {"prompt_tokens": 100, "completion_tokens": 50}}
    assert parse_token_counts(body, "openai") == (100, 50)


def test_parse_token_counts_anthropic():
    body = {"usage": {"input_tokens": 200, "output_tokens": 80}}
    assert parse_token_counts(body, "anthropic") == (200, 80)


def test_parse_token_counts_missing_usage():
    assert parse_token_counts({}, "openai") == (0, 0)
    assert parse_token_counts({}, "anthropic") == (0, 0)
