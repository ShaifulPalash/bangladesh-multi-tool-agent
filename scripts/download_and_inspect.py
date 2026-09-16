"""
STEP 2: Download the three Bangladesh datasets from Hugging Face and inspect
them.

WHY THIS SCRIPT EXISTS
-----------------------
We don't actually know the exact column names, data types, or how messy each
CSV is until we look at it. Rather than guessing column names (which would
break the moment the real data doesn't match), this script:

  1. Downloads each dataset using the `datasets` library.
  2. Converts it to a pandas DataFrame.
  3. Prints the columns, dtypes, row count, a data sample, and null counts.
  4. Saves a clean CSV copy into ./data/ so the next script (build_databases.py)
     has a stable local file to work from.

Run this FIRST, read its printed output carefully, and only then move on to
build_databases.py. If a dataset has a messy/unexpected column (e.g. mixed
Bangla/English text, or a numeric column stored as text with commas), the
"MESSY DATA CHECK" section below will flag it so you can decide how to clean
it in build_databases.py.
"""

import os

import pandas as pd
from datasets import load_dataset

# Where we'll save the raw CSVs after downloading them once.
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# The three Hugging Face dataset repo IDs from the project brief.
DATASETS = {
    "institutions": "Mahadih534/Institutional-Information-of-Bangladesh",
    "hospitals": "Mahadih534/all-bangladeshi-hospitals",
    "restaurants": "Mahadih534/Bangladeshi-Restaurant-Data",
}


def download_as_dataframe(hf_repo_id: str) -> pd.DataFrame:
    """
    Downloads a Hugging Face dataset and returns it as a pandas DataFrame.

    We ask for the 'train' split, which is the default/only split for most
    small CSV-based datasets on the Hub. If a dataset has a different split
    name, `load_dataset` will raise a clear error telling us the available
    splits, and we can adjust the split name here.
    """
    ds = load_dataset(hf_repo_id, split="train")
    return ds.to_pandas()


def inspect_dataframe(name: str, df: pd.DataFrame) -> None:
    """Prints a human-readable summary of a DataFrame's structure and quality."""
    print("\n" + "=" * 70)
    print(f"DATASET: {name}  |  rows={len(df)}  cols={len(df.columns)}")
    print("=" * 70)

    print("\n--- Columns & dtypes ---")
    print(df.dtypes)

    print("\n--- First 5 rows ---")
    with pd.option_context("display.max_columns", None, "display.width", 160):
        print(df.head(5))

    print("\n--- MESSY DATA CHECK ---")
    null_counts = df.isnull().sum()
    cols_with_nulls = null_counts[null_counts > 0]
    if len(cols_with_nulls) > 0:
        print("Columns with missing values:")
        print(cols_with_nulls)
    else:
        print("No missing values detected.")

    # Flag object/text columns that look like they should actually be numbers
    # (common issue: "1,234" or "1234 beds" stored as text instead of int).
    for col in df.select_dtypes(include="object").columns:
        sample_vals = df[col].dropna().astype(str).head(20)
        looks_numeric_ish = sample_vals.str.replace(",", "", regex=False).str.match(
            r"^\d+(\.\d+)?$"
        )
        if looks_numeric_ish.any() and not looks_numeric_ish.all():
            print(
                f"NOTE: column '{col}' is text but partially looks numeric — "
                f"inspect manually before casting to INTEGER/REAL."
            )

    duplicate_count = df.duplicated().sum()
    if duplicate_count > 0:
        print(f"NOTE: {duplicate_count} fully duplicated rows found.")


def main():
    for short_name, repo_id in DATASETS.items():
        print(f"\nDownloading '{repo_id}' ...")
        df = download_as_dataframe(repo_id)

        inspect_dataframe(short_name, df)

        out_path = os.path.join(DATA_DIR, f"{short_name}.csv")
        df.to_csv(out_path, index=False)
        print(f"\nSaved raw copy -> {out_path}")

    print("\nAll datasets downloaded and inspected. Review the printed output "
          "above, then run scripts/build_databases.py next.")


if __name__ == "__main__":
    main()
