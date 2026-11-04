# Contributing to anySQL

Thanks for helping. anySQL is a small Python package: adapters and tracers
normalise what your AI system does into six tables, and DuckDB lets you query
them with SQL. Most of this guide is about keeping those tables and the
queries over them correct, so every change in behaviour comes with a test.

- [Ways to help](#ways-to-help)
- [Reporting a bug](#reporting-a-bug)
- [Development setup](#development-setup)
- [Tests](#tests)
- [Code layout](#code-layout)
- [Adding an adapter](#adding-an-adapter)
- [Pull requests](#pull-requests)
- [Security](#security)
- [License](#license)

## Ways to help

- **Report a bug**, such as a provider response that is logged with the wrong
  tokens or cost, a tracer that drops fields, or an analytics method that
  returns the wrong rows. See the next section.
- **Run it on your own pipeline** and tell us what was missing, in an issue.
  Real-world use guides what to fix next.
- **Pick up an issue** labelled
  [`good first issue`](https://github.com/sadayamuthu/anySQL/labels/good%20first%20issue)
  or [`help wanted`](https://github.com/sadayamuthu/anySQL/labels/help%20wanted).
- **Add an adapter** for another LLM provider, or a chunk format to
  `RAGTracer`.

For anything larger than a small fix, open an issue first so we can agree on
the approach before you write the code.

## Reporting a bug

Please include:

1. The anySQL version (`python -c "import anysql; print(anysql.__version__)"`),
   your Python version, and the versions of `duckdb`, `pyarrow` and `pandas`
   (`pip show duckdb pyarrow pandas`).
2. The code or `anysql` command you ran, and its output or traceback.
3. What you expected instead, and why.
4. A minimal reproduction, ideally as a failing test: a few `db.insert(...)`
   calls or a mocked client, then the query or method that goes wrong. A test
   is the fastest way to get a fix.

If your prompts or traces are private, reduce them to made-up records that
still show the problem. Never paste API keys.

## Development setup

You need **Python 3.10** or newer. CI tests on 3.10, 3.11 and 3.12.

```sh
git clone https://github.com/sadayamuthu/anySQL.git
cd anySQL
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
anysql --help
```

Provider SDKs are optional extras and aren't needed for the tests, which use
mocked clients: `pip install -e ".[dev,all]"` if you want to run the examples
against real APIs.

Before pushing, run what CI runs
([`.github/workflows/pr-check.yml`](.github/workflows/pr-check.yml)):

```sh
pytest tests/ -v --tb=short
ruff check anysql/
ruff format --check anysql/
```

CI also checks that `version` in `pyproject.toml` differs from `main`, so a
pull request to `main` must bump it (see [Pull requests](#pull-requests)).

The examples run without API keys, using mocked clients:

```sh
python examples/realtime_combined_demo.py
```

## Tests

Tests live in [`tests/`](tests) and use pytest. Most build an in-memory engine
with `anysql.init(":memory:")`; persistence tests use a temporary SQLite file.

| File | What it covers |
|------|----------------|
| `test_schema.py` | The six PyArrow schemas and table names |
| `test_storage.py` | SQLite persistence: save, load, delete, row counts |
| `test_engine.py` | Inserts, `query()`, `count()`, `clear()` (including the SQLite copy), and the UC1 to UC5 analytics methods |
| `test_adapters.py` | OpenAI and Claude wrappers and cost calculation, with mocked clients |
| `test_tracers.py` | `AgentTracer` (manual tracing and its `on_tool_*`/`on_agent_*` hooks) and `RAGTracer` (dict, LangChain and LlamaIndex chunk formats, the UC5 join) |

Run one test while you work on it:

```sh
pytest tests/test_engine.py::test_insert_and_count -v
```

**Every behaviour change needs a test.** For a bug fix, add a test that fails
before your change and passes after it.

## Code layout

| Path | What it does |
|------|--------------|
| `anysql/__init__.py` | Public API: `init()`, `openai()`, `claude()`, `agent_tracer()`, `rag_tracer()`, `context`, `context_scope` |
| `anysql/engine.py` | `AnySQL`: in-memory buffers, DuckDB views over Arrow tables, `query()` and the UC1 to UC5 methods |
| `anysql/schema.py` | The six canonical PyArrow schemas (`llm.responses`, `eval.results`, `pipeline.runs`, `agent.tool_calls`, `agent.trace`, `rag.chunks`) |
| `anysql/storage.py` | SQLite persistence; each row is stored as a JSON blob |
| `anysql/context.py` | `@context` decorator and `context_scope()`, built on contextvars; writes `pipeline.runs` |
| `anysql/cli.py` | The `anysql query` and `anysql stats` commands |
| `anysql/adapters/openai.py`, `anysql/adapters/claude.py` | Wrappers that log `chat.completions.create` and `messages.create` calls, with per-model pricing tables |
| `anysql/adapters/generic.py` | `GenericAdapter.log()` for writing a response from any provider by hand |
| `anysql/tracers/agent.py` | `AgentTracer`: tool calls and agent steps |
| `anysql/tracers/rag.py` | `RAGTracer`: retrieved chunks and eval results, joined by `query_id` |
| `examples/` | Three demos that run with mocked clients when no API key is set |
| `docs/QUERIES.md` | Reference SQL queries |

## Adding an adapter

The OpenAI and Claude adapters show the pattern:

1. Add `anysql/adapters/<provider>.py` with an adapter class that takes the
   engine (`db`) and an optional `task_type`, and a `wrap(client)` method that
   returns a proxy. The proxy replaces only the call it logs and forwards
   every other attribute to the real client with `__getattr__`.
2. In the wrapped call, time the request, call the real client, and insert one
   record into `llm.responses` with `db.insert(...)`. The record must match
   `LLM_RESPONSES_SCHEMA` in `anysql/schema.py`; `response_id`, `model`,
   `prompt` and `created_at` are required. Take `session_id` and `task_type`
   from `get_context()` as the existing adapters do.
3. If you add a pricing table, prices are USD per million tokens. Return
   `None` for unknown models rather than guessing.
4. Expose it from `anysql/__init__.py`, add an optional dependency extra in
   `pyproject.toml` if it needs the provider's SDK, and add tests with a
   mocked client in `tests/test_adapters.py`. Tests must not call real APIs.
5. Document it in the README.

The wrapper must return the provider's response unchanged, and must not log
request fields other than the ones in the schema. In particular, never write
API keys, headers or client configuration to a table.

## Pull requests

- Keep each PR to one change; small PRs get reviewed faster.
- Use the commit message style in the history: `type: summary`, for example
  `fix: handle empty choices in the OpenAI adapter`. A scope is optional
  (`fix(engine): ...`). Types in use: `feat`, `fix`, `docs`, `ci`, `chore`.
- Bump `version` in `pyproject.toml` and `__version__` in
  `anysql/__init__.py` together. CI requires the bump, and merging a new
  version to `main` publishes it to PyPI and tags the release.
- CI must pass on Python 3.10, 3.11 and 3.12.
- Update the README when you change behaviour a user can see.

## Security

Please don't report security problems in a public issue. Use
[**Report a vulnerability**](https://github.com/sadayamuthu/anySQL/security/advisories/new)
on the repository's Security tab instead. See [SECURITY.md](SECURITY.md) for
what to include and what's in scope.

## License

anySQL is licensed under the [Apache License 2.0](LICENSE). By contributing,
you agree that your contributions are licensed under the same license.
