"""Question in, rows out: generate SQL, check it, then run it or refuse with the reason."""
import sqlite3
import sys
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from guard import add_row_limit, rejection_reason
from sql_writer import read_schema, write_sql


class State(TypedDict, total=False):
    question: str
    sql: str
    reason: str | None  # None = allowed; otherwise why it was refused or failed
    columns: list[str]
    rows: list[tuple]


def build_graph(llm, conn: sqlite3.Connection):
    """conn must come from db.connect_read_only, the second wall if the guard misses something."""
    schema = read_schema(conn)

    def generate(state: State) -> State:
        return {"sql": write_sql(state["question"], schema, llm)}

    def check(state: State) -> State:
        return {"reason": rejection_reason(state["sql"])}

    def run(state: State) -> State:
        sql = add_row_limit(state["sql"])
        try:
            cursor = conn.execute(sql)
            rows = cursor.fetchall()
        except sqlite3.Error as error:  # bad column, timeout, or a write the guard missed
            return {"sql": sql, "reason": f"database error: {error}"}
        return {"sql": sql, "columns": [c[0] for c in cursor.description], "rows": rows}

    graph = StateGraph(State)
    graph.add_node("generate", generate)
    graph.add_node("check", check)
    graph.add_node("run", run)
    graph.add_edge(START, "generate")
    graph.add_edge("generate", "check")
    graph.add_conditional_edges("check", lambda s: END if s["reason"] else "run", ["run", END])
    graph.add_edge("run", END)
    return graph.compile()


if __name__ == "__main__":
    import httpx
    from langchain_ollama import ChatOllama

    from db import connect_read_only

    app = build_graph(ChatOllama(model="llama3.2", temperature=0, num_predict=300), connect_read_only())
    try:
        result = app.invoke({"question": sys.argv[1]})
    except httpx.ConnectError:
        sys.exit("Ollama is not running. Start it with: ollama serve")
    print(f"SQL: {result['sql']}\n")
    if result["reason"]:
        sys.exit(f"Refused: {result['reason']}")
    print(" | ".join(result["columns"]))
    for row in result["rows"]:
        print(" | ".join(str(value) for value in row))
