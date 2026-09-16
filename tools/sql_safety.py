"""
Shared safety layer used by all three DB tools.

WHY THIS EXISTS
----------------
Our tools let an LLM generate SQL from a natural-language question and then
execute it. That's powerful, but also risky if the generated SQL is a stray
DROP TABLE, DELETE, or UPDATE. This module enforces two hard rules before
ANY query touches the database:

  1. Only a single SELECT statement is allowed (no semicolons chaining a
     second statement, no INSERT/UPDATE/DELETE/DROP/ALTER/ATTACH/etc.).
  2. A LIMIT is added automatically if the query doesn't already have one,
     so a broad question can't dump an enormous table into the LLM's
     context window.

We also open every SQLite connection in read-only mode as a second layer
of defense, using SQLite's URI "mode=ro" so writes fail at the database
engine level even if a bad query somehow got past the regex check.
"""

import re
import sqlite3

FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE",
    "ATTACH", "DETACH", "PRAGMA", "VACUUM", "TRUNCATE", "GRANT", "REVOKE",
]

DEFAULT_ROW_LIMIT = 200


class UnsafeSQLError(Exception):
    """Raised when generated SQL fails the safety check."""


def validate_select_only(sql: str) -> str:
    """
    Validates that `sql` is a single, read-only SELECT statement.
    Returns the (possibly LIMIT-appended) safe SQL string, or raises
    UnsafeSQLError.
    """
    cleaned = sql.strip().rstrip(";")

    if ";" in cleaned:
        raise UnsafeSQLError("Multiple SQL statements are not allowed.")

    if not re.match(r"^\s*SELECT\b", cleaned, flags=re.IGNORECASE):
        raise UnsafeSQLError("Only SELECT statements are allowed.")

    upper = cleaned.upper()
    for word in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{word}\b", upper):
            raise UnsafeSQLError(f"Keyword '{word}' is not allowed in this tool.")

    if not re.search(r"\bLIMIT\b", upper):
        cleaned = f"{cleaned} LIMIT {DEFAULT_ROW_LIMIT}"

    return cleaned


def run_read_only_query(db_path: str, sql: str):
    """
    Opens the SQLite file in read-only URI mode and executes a validated
    SELECT query. Returns (column_names, rows).
    """
    safe_sql = validate_select_only(sql)

    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cursor = conn.execute(safe_sql)
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        return columns, rows
    finally:
        conn.close()


def get_table_schema(db_path: str, table_name: str) -> str:
    """Returns the CREATE TABLE statement for `table_name` from `db_path`."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return row[0] if row else ""
    finally:
        conn.close()
