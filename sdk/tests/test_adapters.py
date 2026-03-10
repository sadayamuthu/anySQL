import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone
import anysql
from anysql.adapters.openai import OpenAIAdapter, _calc_cost as openai_calc_cost
from anysql.adapters.claude import ClaudeAdapter, _calc_cost as claude_calc_cost


@pytest.fixture
def db():
    return anysql.init(":memory:")


# ── OpenAI cost calculation ─────────────────────────────────────────────────

def test_openai_cost_gpt4o():
    cost = openai_calc_cost("gpt-4o", 1000, 500)
    # 1000 * 2.50/1M + 500 * 10.00/1M
    expected = (1000 * 2.50 + 500 * 10.00) / 1_000_000
    assert abs(cost - expected) < 1e-10


def test_openai_cost_gpt4o_mini():
    cost = openai_calc_cost("gpt-4o-mini", 1000, 500)
    expected = (1000 * 0.15 + 500 * 0.60) / 1_000_000
    assert abs(cost - expected) < 1e-10


def test_openai_cost_unknown_model_returns_none():
    assert openai_calc_cost("unknown-model-xyz", 100, 50) is None


def test_openai_cost_versioned_suffix():
    # "gpt-4o-2024-11-20" should match "gpt-4o" prefix
    cost = openai_calc_cost("gpt-4o-2024-11-20", 1000, 500)
    assert cost is not None
    assert cost > 0


# ── OpenAI adapter wrapping ─────────────────────────────────────────────────

def _make_openai_response(model="gpt-4o", content="Hello", prompt_tokens=10, completion_tokens=20):
    mock = MagicMock()
    mock.id = "chatcmpl-test123"
    mock.model = model
    mock.choices = [MagicMock()]
    mock.choices[0].message.content = content
    mock.choices[0].finish_reason = "stop"
    mock.usage.prompt_tokens = prompt_tokens
    mock.usage.completion_tokens = completion_tokens
    return mock


def test_openai_wrap_inserts_llm_response(db):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_openai_response()
    client = anysql.openai(db).wrap(mock_client)
    client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Summarize this"}]
    )
    assert db.count("llm.responses") == 1


def test_openai_wrap_records_correct_model(db):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_openai_response(model="gpt-4o-mini")
    client = anysql.openai(db).wrap(mock_client)
    client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": "Hi"}])
    result = db.query("SELECT model FROM llm_responses")
    assert result.iloc[0]["model"] == "gpt-4o-mini"


def test_openai_wrap_records_tokens(db):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_openai_response(
        prompt_tokens=15, completion_tokens=25
    )
    client = anysql.openai(db).wrap(mock_client)
    client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "Hi"}])
    result = db.query("SELECT prompt_tokens, completion_tokens, total_tokens FROM llm_responses")
    assert result.iloc[0]["prompt_tokens"] == 15
    assert result.iloc[0]["completion_tokens"] == 25
    assert result.iloc[0]["total_tokens"] == 40


def test_openai_wrap_records_cost(db):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_openai_response(
        model="gpt-4o", prompt_tokens=1000, completion_tokens=500
    )
    client = anysql.openai(db).wrap(mock_client)
    client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "Hi"}])
    result = db.query("SELECT cost_usd FROM llm_responses")
    assert result.iloc[0]["cost_usd"] > 0


def test_openai_wrap_passes_through_response(db):
    mock_response = _make_openai_response(content="Summary here")
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response
    client = anysql.openai(db).wrap(mock_client)
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "Hi"}])
    assert response.choices[0].message.content == "Summary here"


def test_openai_adapter_with_task_type(db):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _make_openai_response()
    client = anysql.openai(db, task_type="summarization").wrap(mock_client)
    client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "Hi"}])
    result = db.query("SELECT task_type FROM llm_responses")
    assert result.iloc[0]["task_type"] == "summarization"


# ── Claude cost calculation ─────────────────────────────────────────────────

def test_claude_cost_sonnet():
    cost = claude_calc_cost("claude-sonnet-4-6", 1000, 500)
    expected = (1000 * 3.00 + 500 * 15.00) / 1_000_000
    assert abs(cost - expected) < 1e-10


def test_claude_cost_haiku():
    cost = claude_calc_cost("claude-haiku-4-5", 1000, 500)
    expected = (1000 * 0.80 + 500 * 4.00) / 1_000_000
    assert abs(cost - expected) < 1e-10


def test_claude_cost_unknown_returns_none():
    assert claude_calc_cost("some-unknown-model", 100, 50) is None


# ── Claude adapter wrapping ─────────────────────────────────────────────────

def _make_claude_response(model="claude-sonnet-4-6", content="Summary", input_tokens=10, output_tokens=20):
    mock = MagicMock()
    mock.id = "msg_test123"
    mock.stop_reason = "end_turn"
    block = MagicMock()
    block.text = content
    mock.content = [block]
    mock.usage.input_tokens = input_tokens
    mock.usage.output_tokens = output_tokens
    return mock


def test_claude_wrap_inserts_llm_response(db):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_claude_response()
    client = anysql.claude(db).wrap(mock_client)
    client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello"}]
    )
    assert db.count("llm.responses") == 1


def test_claude_wrap_records_tokens(db):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _make_claude_response(
        input_tokens=15, output_tokens=25
    )
    client = anysql.claude(db).wrap(mock_client)
    client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hi"}]
    )
    result = db.query("SELECT prompt_tokens, completion_tokens FROM llm_responses")
    assert result.iloc[0]["prompt_tokens"] == 15
    assert result.iloc[0]["completion_tokens"] == 25


def test_claude_wrap_passes_through_response(db):
    mock_response = _make_claude_response(content="Claude reply")
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_response
    client = anysql.claude(db).wrap(mock_client)
    response = client.messages.create(
        model="claude-sonnet-4-6", max_tokens=100,
        messages=[{"role": "user", "content": "Hi"}]
    )
    assert response.content[0].text == "Claude reply"


def test_openai_getattr_passthrough(db):
    mock_client = MagicMock()
    mock_client.models = "models_attr"
    client = anysql.openai(db).wrap(mock_client)
    assert client.models == "models_attr"


def test_claude_getattr_passthrough(db):
    mock_client = MagicMock()
    mock_client.beta = "beta_attr"
    client = anysql.claude(db).wrap(mock_client)
    assert client.beta == "beta_attr"
