import sqlite3
import time
from pathlib import Path

SEED_SQL = Path(__file__).with_name("ops.sql")
DEFAULT_DB = Path(__file__).with_name("ops.db")


def create_db(path: Path = DEFAULT_DB) -> None:
    """Build the ops database from ops.sql, replacing any old file."""
    path = Path(path)
    path.unlink(missing_ok=True)
    conn = sqlite3.connect(path)
    with conn:
        conn.executescript(SEED_SQL.read_text())
    conn.close()


def connect_read_only(path: Path = DEFAULT_DB, timeout_seconds: float = 2.0) -> sqlite3.Connection:
    """Open the database so that nothing run on it can change data, even SQL the guard missed."""
    # mode=ro: the file is opened read-only, so writes to real tables fail.
    conn = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
    # mode=ro still allows TEMP tables; query_only blocks every write.
    conn.execute("PRAGMA query_only = ON")
    # mode=ro still lets ATTACH create a new file; allow zero attached databases.
    conn.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
    # Stop any query that runs too long (e.g. an endless recursive WITH).
    deadline = 0.0

    def start_clock(_sql: str) -> None:  # SQLite calls this as each statement starts
        nonlocal deadline
        deadline = time.monotonic() + timeout_seconds

    def too_slow() -> bool:  # SQLite calls this every 10,000 steps; True aborts the query
        return time.monotonic() > deadline

    conn.set_trace_callback(start_clock)
    conn.set_progress_handler(too_slow, 10_000)
    return conn


if __name__ == "__main__":
    create_db()
    print(f"created {DEFAULT_DB}")
