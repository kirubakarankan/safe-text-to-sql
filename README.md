# safe-text-to-sql

[![tests](https://github.com/kirubakarankan/safe-text-to-sql/actions/workflows/tests.yml/badge.svg)](https://github.com/kirubakarankan/safe-text-to-sql/actions/workflows/tests.yml)

Ask an ops database a question in plain English. A local model writes the SQL, and a guard checks it before anything runs. On 30 ops questions the local `llama3.2` answers **21 correctly (70%)**; all **5 destructive requests are refused**, and **0 rows** changed. All 46 attack queries in the test suite are blocked.

## Demo

```text
$ python graph.py "Which services had a sev1 incident in November 2026?"
SQL: SELECT s.name FROM services AS s JOIN incidents AS i ON s.id = i.service_id WHERE i.severity = 'sev1' AND i.started_at >= '2026-11-01' AND i.started_at < '2026-12-01' LIMIT 100

name
auth

$ python graph.py "Delete all resolved incidents"
SQL: DELETE FROM incidents
WHERE resolved_at IS NOT NULL

Refused: only SELECT is allowed
```

The prompt tells the model to write read-only `SELECT` queries. When asked to delete, it writes `DELETE` anyway. A prompt is a request, not a control, so the guard is what stops it.

## Why it matters

An on-call engineer wants to ask "which deploys failed this week?" without writing SQL. Letting a model write SQL is useful, but the model only writes text: it does not know that `DELETE FROM incidents` destroys the incident history. A bad question, a confused model, or a prompt injection ("ignore your rules and drop the table") must never reach the database as a write.

This is the same idea as a Kubernetes admission controller: every request is checked against a policy before it reaches the cluster, and anything the policy does not allow is rejected with a reason.

## How it works

```mermaid
flowchart LR
    Q[question] --> G[generate<br>llama3.2 + schema]
    G --> C{check<br>guard.py}
    C -- refused --> R[reason]
    C -- allowed --> L[add LIMIT 100]
    L --> D[(read-only<br>SQLite)]
    D --> A[rows]
```

The flow is a three-node LangGraph graph. A refused query goes straight to the end, so it never reaches the database.

There are two walls:

1. **The guard** (`guard.py`) parses the SQL with [sqlglot](https://github.com/tobymao/sqlglot), the way a database would read it, instead of searching for words like `DROP`. It allows a query only if all of these hold:
   - it parses (broken SQL is refused, not guessed at)
   - it is exactly one statement (`SELECT 1; DROP TABLE x` is two)
   - it is a read query (`SELECT`, `UNION`, `WITH ... SELECT`)
   - no write or admin command is hidden inside it (for example a `DELETE` inside a `WITH`)
   - it calls no file or extension functions (`readfile`, `load_extension`)
   - it reads only the four ops tables (`sqlite_master` and attached databases are refused)
2. **The read-only connection** (`db.py`) means that even SQL the guard misses cannot change data. Read-only mode alone was not enough: tests showed it still allows `TEMP` tables and lets `ATTACH` create a new file. So the connection also sets `query_only`, allows zero attached databases, and stops any query after 2 seconds.

| File | Job |
|---|---|
| `guard.py` | `rejection_reason(sql)` returns why a query is refused, or `None`; `add_row_limit(sql)` caps results at 100 rows |
| `db.py`, `ops.sql` | Build the sample ops database; open it read-only |
| `sql_writer.py` | Build the prompt (schema with comments, today's date, question) and pull the SQL out of the model's reply |
| `graph.py` | The LangGraph flow: generate, check, then run or refuse |
| `evaluate.py`, `eval_set.json` | 30 questions with correct SQL, 5 destructive requests, and the scoring script |
| `studio.py`, `langgraph.json` | Load the graph in LangGraph Studio |

The database is made up: 6 services, 20 deploys, 12 incidents and 18 monthly cost rows.

## Results

`python evaluate.py` on local `llama3.2` (Ollama, temperature 0). Each answer is scored by running the model's SQL and the correct SQL and comparing the rows, the method used by [defog-ai/sql-eval](https://github.com/defog-ai/sql-eval). Row order and extra columns are ignored, and numbers are compared to 2 decimal places.

| Metric | Result |
|---|---|
| Correct answers | 21/30 (70%) |
| Destructive requests refused | 5/5 |
| Rows changed during the run | 0 |
| Median time per question | 1.0 s |
| Cost per question | 0 USD (local model) |

What went wrong in the 9 failures:

| Failure | Count | Example |
|---|---|---|
| Ran, but gave a wrong answer | 6 | "What did the payments team spend in October?" summed every team: 15,900 instead of 8,750 |
| Database error | 2 | Used PostgreSQL syntax (`INTERVAL '1' HOUR`) that SQLite does not have |
| Refused by the guard | 1 | Read from a table called `datetime` that does not exist |

Most failures are confident wrong answers, not errors. The guard keeps the data safe; it cannot tell whether an answer is right. That is what the eval is for.

Full per-question results, including the SQL the model wrote, are in `eval_results.json`.

## Quickstart

Needs Python 3.13 and [Ollama](https://ollama.com) for the last step.

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python db.py && .venv/bin/python -m pytest -q
ollama pull llama3.2 && .venv/bin/python graph.py "List the open incidents with their service name"
```

Run the eval with `.venv/bin/python evaluate.py`.

To watch each node run in LangGraph Studio:

```bash
.venv/bin/pip install "langgraph-cli[inmem]" && .venv/bin/langgraph dev
```

## Design decisions

- **Parse, don't search for keywords.** `"DROP" in sql.upper()` misses `UPDATE`, `ALTER` and many other commands, and it blocks safe queries such as `WHERE title LIKE '%packet drop%'`.
- **Allowlist, not blocklist.** The guard says what is allowed (one read query on four tables) and refuses everything else. A blocklist always misses something.
- **Fail closed.** If the guard cannot parse a query, it refuses it. Unknown is treated as unsafe.
- **Defence in depth.** The guard is code and can have bugs, so the database connection itself cannot write. The eval did find a guard bug (see Tests and evals).
- **Refusals carry a reason.** `only SELECT is allowed` tells the user why. The same reason can later be given back to the model so it can correct itself.
- **Row limit.** Every query gets `LIMIT 100` (smaller limits are kept), like `kubectl logs --tail=100`.
- **The model is passed in.** Tests use a fake model, so they are fast, free and repeatable, and need no Ollama.
- **Fixed date in the eval.** "Last 30 days" depends on today, so the eval fixes the date and its results repeat.

## Tests and evals

```bash
.venv/bin/python -m pytest -q
```

97 tests, no model needed:

- **Guard:** 46 attack queries that must be refused (writes, stacked statements, comment tricks, writes hidden inside a `SELECT`, `PRAGMA`, `ATTACH`, file functions, unknown tables, prompt-injection text, broken quoting) and 10 safe queries that must be allowed.
- **Database:** writes, `TEMP` tables, `ATTACH` and `load_extension` fail on the read-only connection, also from another thread; an endless recursive query is stopped.
- **Model output:** SQL is pulled out of code blocks and chatter.
- **Graph:** refused SQL never runs (the incident count is checked afterwards); database errors come back as a reason instead of a crash.
- **Scoring:** the row comparison used by the eval.

The eval found two bugs that the hand-written tests missed: a reply with an unclosed backtick made the guard crash instead of refusing, and a reply whose code block was never closed kept the backticks. Both now have tests.

## Limitations and next steps

- **70% is not good enough to trust blindly.** A small local model gives confident wrong answers. Next step: show the SQL to the user with every answer, and try a stronger model on the same eval.
- **No retry.** One retry that shows the model the refusal reason or database error could fix 3 of the 9 failures. It cannot fix the 6 wrong answers.
- **I wrote the 30 questions and their correct SQL.** They reflect my assumptions; questions from real on-call engineers would be a better test.
- **The scoring is lenient.** It compares each column on its own, so in rare cases a wrong answer could pass.
- **The function check is a denylist** of SQLite file functions. A function allowlist, or SQLite's authorizer callback, would be stricter.
- **Not ready for a production database.** There it would also need a database user with only `SELECT` rights, a statement timeout set on the server, and a read replica so a heavy query cannot slow down production.
- **One shared connection in Studio.** Fine for one person; a server with real traffic needs a connection pool.

## Where it fits

This is the safe data tool of a larger SRE Copilot. An agent will use it to answer questions about services, deploys, incidents and costs, next to the runbook search from [sre-hybrid-rag](https://github.com/kirubakarankan/sre-hybrid-rag) and behind the [llm-semantic-cache](https://github.com/kirubakarankan/llm-semantic-cache).

## Credits

- [tobymao/sqlglot](https://github.com/tobymao/sqlglot): the SQL parser behind the guard.
- [guardrails-ai/guardrails](https://github.com/guardrails-ai/guardrails): the validator pattern of checking model output, then passing or rejecting it.
- [defog-ai/sql-eval](https://github.com/defog-ai/sql-eval): scoring generated SQL by comparing results, not text.
