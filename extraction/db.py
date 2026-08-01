"""DuckDB connection + idempotent upsert helper.

The upsert pattern here is delete-by-natural-key then insert. That's the
core of "run it twice, nothing duplicates": whatever keys are present in
the incoming batch get wiped from the target table first, then re-inserted.
Same batch twice = same final state, not double rows.
"""
import duckdb
import pandas as pd
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"


def get_connection() -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def ensure_schema(con: duckdb.DuckDBPyConnection, schema: str) -> None:
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")


def upsert(
    con: duckdb.DuckDBPyConnection,
    schema: str,
    table: str,
    df: pd.DataFrame,
    key_cols: list[str],
    create_sql: str,
) -> None:
    if df.empty:
        return
    ensure_schema(con, schema)
    full_table = f"{schema}.{table}"
    con.execute(create_sql)

    con.register("batch_df", df)
    distinct_keys = df[key_cols].drop_duplicates()
    con.register("keys_df", distinct_keys)

    key_match = " AND ".join([f"t.{c} = k.{c}" for c in key_cols])
    con.execute(
        f"""
        DELETE FROM {full_table} AS t
        WHERE EXISTS (SELECT 1 FROM keys_df AS k WHERE {key_match})
        """
    )
    con.execute(f"INSERT INTO {full_table} SELECT * FROM batch_df")

    con.unregister("batch_df")
    con.unregister("keys_df")
