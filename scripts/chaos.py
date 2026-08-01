"""
make chaos -- intentionally break a real data contract, on purpose, so
you can check whether the agent (or a human) detects it, explains the
mechanism, and fixes it.

Two independent modes:

  business_rule (default)
    Injects a physically impossible row (temp_min_c > temp_max_c) directly
    into the raw weather table for today. Nothing in staging/intermediate
    rejects this -- it's designed to slip through until
    fct_daily_conditions' singular test (assert_temp_max_gte_temp_min)
    fails in `dbt test`.

  schema_drift
    Renames a column in the raw FX table, simulating an upstream API
    silently changing its schema. stg_banxico__fx casts `value`, which no
    longer exists -- fails at `dbt run`, before tests even get a chance to
    run. Different failure mode, different diagnosis than business_rule.

Usage:
    make chaos
    make chaos MODE=schema_drift
    python scripts/chaos.py --mode schema_drift
"""
import argparse
from datetime import date

from extraction.db import get_connection


def business_rule_chaos(con) -> None:
    con.execute(
        """
        INSERT INTO raw.open_meteo_daily
            (location, date, temp_max_c, temp_min_c, precipitation_mm, extracted_at)
        VALUES ('cdmx', ?, 5.0, 25.0, 0.0, current_timestamp)
        ON CONFLICT (location, date) DO UPDATE SET temp_max_c = 5.0, temp_min_c = 25.0
        """,
        [date.today().isoformat()],
    )
    print("[chaos:business_rule] injected temp_max_c=5.0 < temp_min_c=25.0 for cdmx/today")
    print("Expected to be caught by: dbt test -> assert_temp_max_gte_temp_min")


def schema_drift_chaos(con) -> None:
    con.execute("ALTER TABLE raw.banxico_fx RENAME COLUMN value TO valor")
    print("[chaos:schema_drift] renamed raw.banxico_fx.value -> valor")
    print("Expected to be caught by: dbt run -> stg_banxico__fx casts `value`, which no longer exists")


MODES = {"business_rule": business_rule_chaos, "schema_drift": schema_drift_chaos}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=list(MODES), default="business_rule")
    args = parser.parse_args()
    con = get_connection()
    try:
        MODES[args.mode](con)
    finally:
        con.close()


if __name__ == "__main__":
    main()
