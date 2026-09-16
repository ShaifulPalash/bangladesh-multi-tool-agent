"""
Unit tests for tools/sql_safety.py.

These tests need NO API keys and NO network access — they only exercise the
pure SQL-validation logic and a real (throwaway) SQLite file. This is what
runs in CI on every push (see .github/workflows/ci.yml), catching safety
regressions before they ever reach a deployed agent.
"""

import os
import sqlite3
import sys

import pytest

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from tools.sql_safety import (
    DEFAULT_ROW_LIMIT,
    UnsafeSQLError,
    get_table_schema,
    run_read_only_query,
    validate_select_only,
)


@pytest.fixture()
def sample_db(tmp_path):
    """Creates a small throwaway SQLite DB for the tests to query against."""
    db_path = tmp_path / "sample.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE hospitals (name TEXT, location TEXT, beds INTEGER)")
    conn.executemany(
        "INSERT INTO hospitals VALUES (?, ?, ?)",
        [
            ("Dhaka Medical College Hospital", "Dhaka", 1000),
            ("Chittagong General Hospital", "Chittagong", 500),
            ("Sylhet MAG Osmani Medical College Hospital", "Sylhet", 750),
        ],
    )
    conn.commit()
    conn.close()
    return str(db_path)


# --- validate_select_only: things that SHOULD pass ---

def test_plain_select_is_allowed():
    sql = validate_select_only("SELECT * FROM hospitals WHERE location = 'Dhaka'")
    assert sql.upper().startswith("SELECT")


def test_limit_is_auto_appended_when_missing():
    sql = validate_select_only("SELECT * FROM hospitals")
    assert f"LIMIT {DEFAULT_ROW_LIMIT}" in sql


def test_existing_limit_is_preserved_not_duplicated():
    sql = validate_select_only("SELECT * FROM hospitals LIMIT 5")
    assert sql.count("LIMIT") == 1
    assert "LIMIT 5" in sql


# --- validate_select_only: things that SHOULD be rejected ---

@pytest.mark.parametrize(
    "bad_sql",
    [
        "DROP TABLE hospitals",
        "DELETE FROM hospitals",
        "UPDATE hospitals SET beds = 0",
        "INSERT INTO hospitals VALUES ('x', 'y', 1)",
        "SELECT * FROM hospitals; DROP TABLE hospitals",
        "ATTACH DATABASE 'evil.db' AS evil",
        "PRAGMA table_info(hospitals)",
    ],
)
def test_unsafe_sql_is_rejected(bad_sql):
    with pytest.raises(UnsafeSQLError):
        validate_select_only(bad_sql)


# --- run_read_only_query: end-to-end against a real SQLite file ---

def test_run_read_only_query_returns_expected_rows(sample_db):
    columns, rows = run_read_only_query(
        sample_db, "SELECT name, beds FROM hospitals WHERE location = 'Dhaka'"
    )
    assert columns == ["name", "beds"]
    assert rows == [("Dhaka Medical College Hospital", 1000)]


def test_run_read_only_query_blocks_write_attempt(sample_db):
    with pytest.raises(UnsafeSQLError):
        run_read_only_query(sample_db, "DELETE FROM hospitals")

    # Double-check the data really is untouched.
    conn = sqlite3.connect(sample_db)
    count = conn.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0]
    conn.close()
    assert count == 3


def test_db_level_readonly_blocks_writes_even_bypassing_validator(sample_db):
    """
    Defense-in-depth check: even if a write statement somehow bypassed
    validate_select_only, SQLite's own read-only file mode must still
    refuse it.
    """
    uri = f"file:{sample_db}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM hospitals")
    conn.close()


def test_get_table_schema_returns_create_statement(sample_db):
    schema = get_table_schema(sample_db, "hospitals")
    assert "CREATE TABLE hospitals" in schema
    assert "beds" in schema


def test_get_table_schema_returns_empty_for_missing_table(sample_db):
    schema = get_table_schema(sample_db, "does_not_exist")
    assert schema == ""
