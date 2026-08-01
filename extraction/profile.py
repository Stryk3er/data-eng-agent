"""Table profiler backing the `profile_table` OpenCode tool.

    python -m extraction.profile --schema raw --table open_meteo_daily
"""
import argparse

from extraction.db import get_connection

NUMERIC_OR_DATE_TYPES = {"DOUBLE", "BIGINT", "INTEGER", "DATE", "TIMESTAMP", "FLOAT"}


def profile(schema: str, table: str) -> None:
    con = get_connection()
    full = f"{schema}.{table}"
    try:
        cols = con.execute(f"describe {full}").fetchall()
        row_count = con.execute(f"select count(*) from {full}").fetchone()[0]
        print(f"table: {full}")
        print(f"row_count: {row_count}")
        if row_count == 0:
            print("(empty table -- nothing further to profile)")
            return
        for col_name, col_type, *_ in cols:
            null_pct = con.execute(
                f'select round(100.0 * sum(case when "{col_name}" is null then 1 else 0 end) / count(*), 2) '
                f"from {full}"
            ).fetchone()[0]
            line = f'  {col_name} ({col_type}): null_pct={null_pct}%'
            base_type = col_type.upper().split("(")[0]
            if base_type in NUMERIC_OR_DATE_TYPES:
                min_v, max_v, distinct_v = con.execute(
                    f'select min("{col_name}"), max("{col_name}"), count(distinct "{col_name}") from {full}'
                ).fetchone()
                line += f" min={min_v} max={max_v} distinct={distinct_v}"
            print(line)
    finally:
        con.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True)
    parser.add_argument("--table", required=True)
    args = parser.parse_args()
    profile(args.schema, args.table)


if __name__ == "__main__":
    main()
