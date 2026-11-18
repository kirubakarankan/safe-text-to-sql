from types import SimpleNamespace

import pytest

from db import connect_read_only, create_db
from sql_writer import build_prompt, extract_sql, read_schema, write_sql


class FakeLLM:
    """Stands in for ChatOllama: records the prompt, returns a fixed reply."""

    def __init__(self, reply):
        self.reply = reply
        self.prompt = None

    def invoke(self, prompt):
        self.prompt = prompt
        return SimpleNamespace(content=self.reply)


@pytest.mark.parametrize(
    "reply",
    [
        "```sql\nSELECT name FROM services\n```",
        "```\nSELECT name FROM services\n```",
        "SELECT name FROM services",
        "  SELECT name FROM services;  ",
        "Here is the query:\n```sql\nSELECT name FROM services;\n```\nIt lists every service.",
        "```sql\nSELECT name FROM services",  # model never closed the code block
    ],
)
def test_extract_sql_finds_the_query(reply):
    assert extract_sql(reply) == "SELECT name FROM services"


def test_schema_lists_every_table_with_comments(tmp_path):
    path = tmp_path / "ops.db"
    create_db(path)
    schema = read_schema(connect_read_only(path))
    for table in ("services", "deploys", "incidents", "costs"):
        assert f"CREATE TABLE {table}" in schema
    assert "sev1 = worst" in schema


def test_prompt_has_schema_question_and_date():
    prompt = build_prompt("How many open incidents?", "CREATE TABLE incidents (...)", "2026-11-18")
    assert "CREATE TABLE incidents (...)" in prompt
    assert "How many open incidents?" in prompt
    assert "2026-11-18" in prompt


def test_write_sql_sends_prompt_and_returns_clean_sql():
    llm = FakeLLM("```sql\nSELECT COUNT(*) FROM incidents WHERE resolved_at IS NULL;\n```")
    sql = write_sql("How many open incidents?", "CREATE TABLE incidents (...)", llm, today="2026-11-18")
    assert sql == "SELECT COUNT(*) FROM incidents WHERE resolved_at IS NULL"
    assert "How many open incidents?" in llm.prompt
