import sqlite3
from types import SimpleNamespace

import pytest

from db import connect_read_only, create_db
from graph import build_graph


class FakeLLM:
    def __init__(self, reply):
        self.reply = reply

    def invoke(self, prompt):
        return SimpleNamespace(content=self.reply)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "ops.db"
    create_db(path)
    return path


def ask(db_path, model_reply, question="any question"):
    app = build_graph(FakeLLM(model_reply), connect_read_only(db_path))
    return app.invoke({"question": question})


def test_safe_question_returns_rows(db_path):
    result = ask(db_path, "SELECT COUNT(*) AS open FROM incidents WHERE resolved_at IS NULL")
    assert result["reason"] is None
    assert result["columns"] == ["open"]
    assert result["rows"] == [(3,)]


def test_row_limit_is_added_before_running(db_path):
    result = ask(db_path, "SELECT * FROM deploys")
    assert result["sql"].endswith("LIMIT 100")
    assert len(result["rows"]) == 20


def test_destructive_sql_is_refused_and_never_runs(db_path):
    result = ask(db_path, "DELETE FROM incidents")
    assert result["reason"] == "only SELECT is allowed"
    assert "rows" not in result
    count = sqlite3.connect(db_path).execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    assert count == 12


def test_database_error_is_reported_not_raised(db_path):
    result = ask(db_path, "SELECT no_such_column FROM incidents")
    assert result["reason"].startswith("database error: no such column")
    assert "rows" not in result
