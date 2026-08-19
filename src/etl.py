"""
ETL Script: upworthy_clean.parquet 

Run with: python src/etl.py
"""

import sqlite3
import pandas as pd 
from bs4 import BeautifulSoup
from pathlib import Path

parquet_path = Path("data/processed/upworthy_clean.parquet")
schema_path = Path("database/schema.sql")
db_path = Path("database/upworthy.db")

def extract() -> pd.DataFrame:
    """ Loads the cleaned parquet path """

    df = pd.read_parquet(parquet_path)
    return df

def clean_html(text) -> str | None:
    """ Strips the HTML tags and entities and returns None if nothing meaningful remains """ 

    if pd.isna(text):
        return None
    soup = BeautifulSoup(text, "html.parser")
    clean = soup.get_text(separator = " ", strip = True)
    return clean if clean else None

def normalize_blank(text) -> str | None: 
    """ We want to treat empty/whitespace only string as NULLs """
    if pd.isna(text):
        return None
    stripped = text.strip()
    return stripped if stripped else None

def transform(df : pd.DataFrame) -> pd.DataFrame:

    """
    Applies the cleaning steps: cleans html and normalizes the blanks in lede and excerpt 
    """

    df = df.copy()

    df["lede"] = df["lede"].apply(clean_html)
    df["excerpt"] = df["excerpt"].apply(normalize_blank)
    return df

def load(df : pd.DataFrame, db_path: Path = db_path, schema_path: Path = schema_path) -> None:
    """Apply the schema and insert all the rows (assuming schema has not been applied)"""
    conn = sqlite3.connect(db_path)

    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'variants' "
    )

    if cur.fetchone() is None:
        with open(schema_path) as f:
            conn.executescript(f.read())
    else:
        # table already exists — check it's actually empty before inserting,
        # so re-running the script is safe instead of silently duplicating data
        existing_count = cur.execute("SELECT COUNT(*) FROM variants").fetchone()[0]
        if existing_count > 0:
            conn.close()
            raise RuntimeError(
                f"variants table already contains {existing_count} rows. "
                f"Delete {db_path} first if you want to rebuild from scratch."
            )


    insert_cols = [
        "clickability_test_id", "headline", "lede", "excerpt",
        "eyecatcher_id", "impressions", "clicks", "significance",
        "winner", "first_place", "test_week"
    ]


    df[insert_cols].to_sql(
        "variants", conn, if_exists = "append", index = False
    )

    conn.commit()
    conn.close()

def verify(db_path: Path = db_path) -> None:
   """ Prints a summary to verify a successful run """

   conn = sqlite3.connect(db_path)
   cur = conn.cursor()

   cur.execute("SELECT COUNT(*) FROM variants")
   row_count = cur.fetchone()[0] 

   cur.execute("SELECT COUNT(*) FROM experiment_summary")
   experiment_count = cur.fetchone()[0] 

   cur.execute("SELECT COUNT(*) FROM experiment_summary WHERE winner_count_anomaly")
   anomaly_count = cur.fetchone()[0]

   conn.close()

   print("ETL Summary:")
   print(f"variants inserted:  {row_count}")
   print(f"distinct experiments: {experiment_count}")
   print(f"experiments with anomaly:  {anomaly_count}")


def main():
    raw = extract()
    cleaned = transform(raw)
    load(cleaned)
    verify()

if __name__ == "__main__":
    main() 