# Security Policy

## Reporting a vulnerability

Please don't report security problems in a public issue, pull request or
discussion. Use
[**Report a vulnerability**](https://github.com/sadayamuthu/anySQL/security/advisories/new)
on the repository's Security tab instead. Only the maintainer can see the
report.

Include what you can of:

- the anySQL version (`python -c "import anysql; print(anysql.__version__)"`),
  your Python version and OS
- how anySQL was used: the Python API, an adapter (`anysql.openai`,
  `anysql.claude`), a tracer, or the `anysql` CLI
- steps to reproduce, ideally a short script
- what happened and what you expected

You'll get a reply when the report has been read, and again when a fix is
ready. A fix ships as a patch release; the advisory names you unless you'd
rather it didn't.

## Supported versions

anySQL is pre-1.0. Fixes land in the latest release only; please upgrade
before reporting.

## What counts

anySQL runs inside your process. Its adapters wrap your OpenAI or Anthropic
client and record each call; its tracers record agent steps and RAG
retrievals. Records are held in memory and queried with an in-memory DuckDB
connection. If you pass a file path to `anysql.init()`, or use the CLI, they
are also written to that SQLite file as JSON. That file is the only thing
anySQL writes, and anySQL itself makes no network calls; the wrapped client
makes the same requests it would make without anySQL.

Anything that breaks one of these promises is a security issue:

- **Recorded data never becomes SQL.** Prompts, responses, tool inputs and
  outputs, error messages and chunk text are written with parameterised
  SQLite statements and read back into Arrow tables. A recorded value that
  changes a query, or runs SQL of its own, is in scope.
- **Credentials aren't recorded.** The adapters store the model name, the
  last message's content, the response text, token usage, latency, stop
  reason, and the session id and task type from the current context. A path
  by which an API key, request header or client setting ends up in a table,
  the SQLite file, a warning or printed output is in scope.
- **Data goes only where you put it.** A path by which anySQL writes outside
  the database file you chose, or sends recorded data over the network, is in
  scope.
- **The wrapper is transparent.** A way for anySQL to alter, drop or replay a
  provider request or response is in scope.

These are by design, and not vulnerabilities:

- **`db.query()` and `anysql query` run the SQL you give them**, with the full
  power of DuckDB, which can read and write local files and load extensions.
  Treat them like a database shell, and don't pass them SQL from people you
  don't trust.
- **The analytics helpers aren't an input boundary.** `prompt_regressions()`,
  `cost_anomalies()` and `loop_detector()` format their numeric arguments into
  the query text, `count()` formats its table name, and `Storage.delete()`
  takes a raw `WHERE` clause. Pass them values from your own code, not from
  untrusted input. `session_diff()` uses bound parameters.
- **The SQLite file holds your prompts and responses in plain text**, with
  your operating system's default permissions. The CLI's default is
  `anysql.db` in the current directory, and it is created if it doesn't
  exist. Protect it like any other file holding that data, and don't commit
  it (`*.db` is in this repository's `.gitignore`).
- **What you pass to a tracer is stored as given.** Tool inputs and outputs,
  exception messages, and chunk text are recorded verbatim, so a secret in
  them is stored too.

A wrong number, such as a miscalculated cost or a misclassified RAG failure,
is a bug, not a vulnerability. Report it in a normal issue; see
[CONTRIBUTING.md](CONTRIBUTING.md).
