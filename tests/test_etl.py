import sqlite3
from pathlib import Path
import pandas as pd
import pytest

from src.etl import clean_html, normalize_blank, transform, load

schema_path = Path("database/schema.sql")
real_parquet_path = Path("data/processed/upworthy_clean.parquet")

@pytest.fixture

def temp_db(tmp_path):
    """ 
    A fresh, empty SQLite db made from schema.sql
    Stored in a temporary pytest directory
    Does not touch the real upworthy.db
    
    """

    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    with open(schema_path) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    return db_path

@pytest.fixture()
def sample_df():
    """
    Temporary database path 
    """
    return pd.DataFrame([
        {
            "clickability_test_id": "test_a",
            "headline": "Headline One",
            "lede" : "<p>Hello <b>world</b></p>",
            "excerpt": "Excerpt one",
            "eyecatcher_id": "eye_1",
            "impressions": 1000,
            "clicks" : 50,
            "significance" : 100.0,
            "winner" : 1,
            "first_place" : 1,
            "test_week" : 201501,
        },
        {
            "clickability_test_id" : "test_a",
            "headline" : "Headline One",
            "lede" : "<p>Hello <b>world</b></p>",
            "excerpt" : "Excerpt two",
            "eyecatcher_id" : "eye_2",
            "impressions" : 900,
            "clicks" : 30,
            "significance" : 20.0,
            "winner" : 0,
            "first_place" : 0,
            "test_week" : 201501,            
        },
        {
            "clickability_test_id": "test_a",
            "headline": "Headline One",
            "lede" : "<p>Hello <b>world</b></p>",
            "excerpt": "", # blank string -> should become NULL after it transforms
            "eyecatcher_id" : "eye_3",
            "impressions" : 800,
            "clicks" : 120,
            "significance" : 10.0,
            "winner" : 0,
            "first_place" : 0,
            "test_week" : 201501,
        },
        {
            "clickability_test_id" : "test_b",
            "headline" : "Headline Two",
            "lede" : "No HTML lede",
            "excerpt" : "Excerpt four",
            "eyecatcher_id" : "eye_4",
            "impressions" : 800,
            "clicks": 12,
            "significance" : 0,
            "winner": 1,
            "first_place": 1,
            "test_week": 201502,
        },
        {
            "clickability_test_id": "test_aaa",
            "headline": "Headline Two",
            "lede" : "No HTML lede",
            "excerpt": "Excerpt five",
            "eyecatcher_id": "eye_5",
            "impressions": 820,
            "clicks": 13,
            "significance" : 0,
            "winner": 0,
            "first_place": 0,
            "test_week": 201502,

        },
    ])

"""
---------------------
Unit Tests - pure functions
---------------------
"""

def test_clean_html_strips_tags():
    assert clean_html("<p>Hello <b>world</b></p>") == "Hello world"

def test_clean_html_missing_values():
    assert clean_html(None) is None
    assert clean_html(float("nan")) is None

def test_normalize_blank_converts():
    assert normalize_blank("") is None
    assert normalize_blank("  ") is None
    assert normalize_blank("real text") == "real text"
    assert normalize_blank(None) is None

"""
---------------------
Integration Tests - run transforms() + load() against a disposable SQLite database built from schema.sql
---------------------
"""

def test_row_count_matches_input(temp_db, sample_df):
    cleaned = transform(sample_df)
    load(cleaned, db_path = temp_db)

    conn = sqlite3.connect(temp_db)
    count = conn.execute("SELECT COUNT(*) FROM variants").fetchone()[0]
    conn.close()

    assert count == len(sample_df) #5

def test_excerpt_empty_string_becomes_null(temp_db, sample_df):
    cleaned = transform(sample_df)
    load(cleaned, db_path = temp_db)

    conn = sqlite3.connect(temp_db)
    blank_count = conn.execute(
        "SELECT COUNT(*) FROM variants WHERE excerpt = ''"
    ).fetchone()[0]
    
    null_count = conn.execute(
        "SELECT COUNT(*) FROM variants where excerpt is NULL"
    ).fetchone()[0]
    conn.close()

    assert blank_count == 0
    assert null_count == 1

def test_variant_count_grouping(temp_db, sample_df):
    cleaned = transform(sample_df)
    load(cleaned, db_path = temp_db)

    conn = sqlite3.connect(temp_db)
    row = conn.execute(
        "SELECT variant_count FROM experiment_summary "
        "WHERE clickability_test_id = 'test_a'"

    ).fetchone()
    conn.close()

    assert row[0] == 3

def test_winner_count_anomaly_view(temp_db, sample_df):
    cleaned = transform(sample_df)
    load(cleaned, db_path = temp_db)

    conn = sqlite3.connect(temp_db)
    anomalies = dict(conn.execute(
        "SELECT clickability_test_id, winner_count_anomaly "
        "FROM experiment_summary"

    ).fetchall())
    conn.close()

    assert anomalies['test_a'] == 0
    assert anomalies['test_b'] == 0

