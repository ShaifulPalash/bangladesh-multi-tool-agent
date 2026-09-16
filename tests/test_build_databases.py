"""
Unit tests for the data-cleaning helpers in scripts/build_databases.py.

Uses small synthetic DataFrames that mimic real-world messiness (numbers
stored as text with commas, stray whitespace, empty strings) rather than
depending on the actual downloaded datasets — this keeps CI fast and
network-free.
"""

import os
import sys

import pandas as pd

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))

from build_databases import clean_column_name, clean_dataframe


def test_clean_column_name_normalizes_spacing_and_case():
    assert clean_column_name("Hospital Name") == "hospital_name"
    assert clean_column_name(" Location ") == "location"
    assert clean_column_name("Beds-Available") == "beds_available"


def test_clean_column_name_strips_invalid_characters():
    assert clean_column_name("Rating (out of 5)") == "rating_out_of_5"


def test_clean_dataframe_normalizes_column_names():
    df = pd.DataFrame({"Hospital Name": ["A"], "Beds ": [10]})
    cleaned = clean_dataframe(df)
    assert list(cleaned.columns) == ["hospital_name", "beds"]


def test_clean_dataframe_converts_comma_numbers_to_int():
    df = pd.DataFrame({"Name": ["A", "B"], "Beds": ["1,000", "500"]})
    cleaned = clean_dataframe(df)
    assert cleaned["beds"].tolist() == [1000, 500]
    assert str(cleaned["beds"].dtype) == "Int64"


def test_clean_dataframe_leaves_mixed_text_column_alone():
    df = pd.DataFrame({"Name": ["A", "B"], "Notes": ["123", "some text"]})
    cleaned = clean_dataframe(df)
    # "Notes" is NOT all-numeric, so it must stay as text, unchanged in value.
    assert cleaned["notes"].tolist() == ["123", "some text"]


def test_clean_dataframe_converts_empty_strings_to_null():
    df = pd.DataFrame({"Name": ["A", ""], "City": ["Dhaka", "Sylhet"]})
    cleaned = clean_dataframe(df)
    assert pd.isna(cleaned["name"].iloc[1])


def test_clean_dataframe_strips_whitespace():
    df = pd.DataFrame({"Name": ["  Dhaka Medical  ", "Sylhet MAG"]})
    cleaned = clean_dataframe(df)
    assert cleaned["name"].iloc[0] == "Dhaka Medical"


def test_clean_dataframe_drops_exact_duplicates():
    df = pd.DataFrame({"Name": ["A", "A"], "City": ["Dhaka", "Dhaka"]})
    cleaned = clean_dataframe(df)
    assert len(cleaned) == 1
