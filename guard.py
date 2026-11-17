import sqlglot
from sqlglot import exp

ALLOWED_TABLES = {"services", "deploys", "incidents", "costs"}

# Write or admin statements; refused even when nested inside a SELECT (e.g. in a WITH).
WRITE_NODES = (exp.DML, exp.DDL, exp.Drop, exp.Alter, exp.Command, exp.Pragma, exp.Into)

# shortcut: denylist of SQLite file and extension functions; switch to a function allowlist if more appear.
BLOCKED_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit"}

MAX_ROWS = 100


def rejection_reason(sql: str) -> str | None:
    """Return why the SQL is refused, or None if it is allowed."""
    try:
        statements = sqlglot.parse(sql, read="sqlite")
    except sqlglot.errors.ParseError:
        return "could not parse SQL"
    if len(statements) != 1:
        return "only one statement is allowed"
    query = statements[0]
    if not isinstance(query, exp.Query):
        return "only SELECT is allowed"
    if any(query.find_all(*WRITE_NODES)):
        return "writes are not allowed, even inside a SELECT"

    for func in query.find_all(exp.Func):
        name = func.name if isinstance(func, exp.Anonymous) else func.sql_name()
        if name.lower() in BLOCKED_FUNCTIONS:
            return f"function {name} is not allowed"

    cte_names = {cte.alias.lower() for cte in query.find_all(exp.CTE)}
    for table in query.find_all(exp.Table):
        if table.db.lower() not in ("", "main"):
            return f"database {table.db} is not allowed"
        name = table.name.lower()
        if name not in ALLOWED_TABLES | cte_names:
            return f"table {table.name or table.sql()} is not allowed"
    return None


def add_row_limit(sql: str, max_rows: int = MAX_ROWS) -> str:
    """Cap the rows a query can return. Call only on SQL that passed rejection_reason."""
    query = sqlglot.parse_one(sql, read="sqlite")
    limit = query.args.get("limit")
    keep = limit is not None and limit.expression.is_int and int(limit.expression.name) <= max_rows
    if not keep:
        query = query.limit(max_rows)
    return query.sql(dialect="sqlite")
