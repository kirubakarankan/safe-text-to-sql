"""Ask the model to turn a question into one SQLite SELECT query."""
import re
import sys
from datetime import date

INSTRUCTIONS = """You write SQLite queries for on-call engineers.
Write exactly one read-only SELECT query that answers the question, using only the tables below.
Times are ISO 8601 text in UTC, like '2026-11-12T07:40:00Z'; use SQLite date() and datetime() for date maths.
Reply with the SQL only, inside a ```sql code block. No explanation."""

FENCED = re.compile(r"```(?:sql)?\s*(.*?)(?:```|$)", re.DOTALL | re.IGNORECASE)  # closing fence optional


def read_schema(conn) -> str:
    """The CREATE TABLE statements, comments included, straight from the database."""
    rows = conn.execute("SELECT sql FROM sqlite_master WHERE type = 'table' ORDER BY rowid").fetchall()
    return "\n\n".join(sql for (sql,) in rows)


def build_prompt(question: str, schema: str, today: str) -> str:
    return f"{INSTRUCTIONS}\n\nToday is {today}.\n\nTables:\n\n{schema}\n\nQuestion: {question}"


def extract_sql(reply: str) -> str:
    """Models often wrap SQL in a code block or add chatter; keep only the query."""
    match = FENCED.search(reply)
    sql = match.group(1) if match else reply
    return sql.strip().rstrip(";").strip()


def write_sql(question: str, schema: str, llm, today: str | None = None) -> str:
    today = today or date.today().isoformat()
    return extract_sql(llm.invoke(build_prompt(question, schema, today)).content)


if __name__ == "__main__":
    import httpx
    from langchain_ollama import ChatOllama

    from db import connect_read_only
    from guard import rejection_reason

    question = sys.argv[1]
    llm = ChatOllama(model="llama3.2", temperature=0, num_predict=300)
    try:
        sql = write_sql(question, read_schema(connect_read_only()), llm)
    except httpx.ConnectError:
        sys.exit("Ollama is not running. Start it with: ollama serve")
    print(sql)
    print("guard:", rejection_reason(sql) or "allowed")
