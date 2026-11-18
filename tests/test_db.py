import sqlite3

import pytest

from db import connect_read_only, create_db


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "ops.db"
    create_db(path)
    return path


@pytest.fixture
def conn(db_path):
    conn = connect_read_only(db_path)
    yield conn
    conn.close()


def test_seed_data_is_loaded(conn):
    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("services", "deploys", "incidents", "costs")
    }
    assert all(count > 0 for count in counts.values()), counts


def test_create_db_replaces_an_old_file(db_path):
    create_db(db_path)  # second run must not fail or double the rows
    conn = connect_read_only(db_path)
    assert conn.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 6
    conn.close()


def test_reads_work(conn):
    rows = conn.execute("SELECT name FROM services ORDER BY name LIMIT 2").fetchall()
    assert len(rows) == 2


# Second wall: these must fail at the database even if the guard missed them.
@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM incidents",
        "UPDATE incidents SET severity = 'low'",
        "INSERT INTO services (name, team, tier) VALUES ('x', 'y', 1)",
        "DROP TABLE incidents",
        "CREATE TABLE evil (id INTEGER)",
        "CREATE TEMP TABLE scratch (id INTEGER)",
        "SELECT load_extension('/tmp/evil.so')",
    ],
)
def test_writes_fail_at_the_database(conn, sql):
    with pytest.raises(sqlite3.OperationalError):
        conn.execute(sql)


def test_attach_cannot_create_a_file(conn, tmp_path):
    target = tmp_path / "evil.db"
    with pytest.raises(sqlite3.OperationalError):
        conn.execute(f"ATTACH DATABASE '{target}' AS evil")
    assert not target.exists()


def test_runaway_query_is_stopped(db_path):
    conn = connect_read_only(db_path, timeout_seconds=0.5)
    endless = "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) SELECT COUNT(*) FROM n"
    with pytest.raises(sqlite3.OperationalError, match="interrupted"):
        conn.execute(endless).fetchone()
    conn.close()
