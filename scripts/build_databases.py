"""
STEP 3: Convert the downloaded CSVs into SQLite databases.

WHAT THIS SCRIPT DOES
----------------------
For each of the three datasets, it:
  1. Reads the CSV saved by download_and_inspect.py.
  2. Cleans obviously messy values (trims whitespace, strips thousands-
     separators from number-looking text columns, normalizes empty strings
     to real NULLs).
  3. Lets pandas infer proper dtypes (int64 / float64 / object), which
     SQLAlchemy then maps to SQLite's INTEGER / REAL / TEXT correctly.
  4. Writes the DataFrame into its own SQLite database file using `to_sql`.
  5. Prints the final CREATE TABLE statement pulled straight from SQLite's
     own schema table, so you can see exactly what was created.

OUTPUT
------
  db/institutions.db   -> table "institutions"
  db/hospitals.db      -> table "hospitals"
  db/restaurants.db    -> table "restaurants"
"""

import os
import re
import sqlite3

import pandas as pd
from sqlalchemy import create_engine

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "db")
os.makedirs(DB_DIR, exist_ok=True)

# short_name -> (csv filename, sqlite db filename, table name)
TABLES = {
    "institutions": ("institutions.csv", "institutions.db", "institutions"),
    "hospitals": ("hospitals.csv", "hospitals.db", "hospitals"),
    "restaurants": ("restaurants.csv", "restaurants.db", "restaurants"),
}


def clean_column_name(col: str) -> str:
    """
    Turns messy source column names into safe, consistent SQL column names:
    lowercase, spaces/hyphens -> underscores, strips anything that isn't
    alphanumeric or underscore.
    """
    col = col.strip().lower()
    col = re.sub(r"[\s\-]+", "_", col)
    col = re.sub(r"[^a-z0-9_]", "", col)
    return col or "unnamed_col"


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Applies general-purpose cleaning that's safe for any of the 3 datasets."""
    df = df.copy()

    # 1. Normalize column names.
    df.columns = [clean_column_name(c) for c in df.columns]

    # 2. Strip whitespace from all text cells and convert empty strings to NaN.
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"": None, "nan": None, "None": None})

    # 3. Try to convert text columns that are actually numeric (e.g. "1,200")
    #    into real numeric columns, but only if EVERY non-null value converts
    #    cleanly — this avoids corrupting genuinely mixed text columns.
    for col in df.select_dtypes(include=["object", "string"]).columns:
        stripped = df[col].dropna().astype(str).str.replace(",", "", regex=False)
        if len(stripped) == 0:
            continue
        is_int = stripped.str.match(r"^-?\d+$").all()
        is_float = stripped.str.match(r"^-?\d+\.\d+$").all()
        if is_int:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "", regex=False),
                errors="coerce",
            ).astype("Int64")
        elif is_float:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "", regex=False),
                errors="coerce",
            )

    # 4. Drop exact duplicate rows.
    df = df.drop_duplicates()

    return df


def build_one_database(short_name: str, csv_file: str, db_file: str, table_name: str):
    csv_path = os.path.join(DATA_DIR, csv_file)
    db_path = os.path.join(DB_DIR, db_file)

    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Missing {csv_path}. Run scripts/download_and_inspect.py first."
        )

    df = pd.read_csv(csv_path)
    df = clean_dataframe(df)

    # Overwrite any existing db file so this script is safely re-runnable.
    if os.path.exists(db_path):
        os.remove(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    df.to_sql(table_name, engine, if_exists="replace", index=False)

    print(f"\nBuilt {db_path}  (table: {table_name}, rows: {len(df)})")
    print("Columns:", list(df.columns))

    # Print the real CREATE TABLE statement SQLite generated, so we can see
    # the actual inferred column types (TEXT / INTEGER / REAL).
    conn = sqlite3.connect(db_path)
    schema_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()[0]
    print("Schema:\n", schema_sql)
    conn.close()


def main():
    for short_name, (csv_file, db_file, table_name) in TABLES.items():
        build_one_database(short_name, csv_file, db_file, table_name)

    print("\nAll three SQLite databases built successfully in ./db/")


if __name__ == "__main__":
    main()
