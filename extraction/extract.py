"""
Extraction CLI.

    python -m extraction.extract --source open_meteo --mode incremental
    python -m extraction.extract --source banxico --mode backfill --start 2025-01-01 --end 2025-03-01

Why running this twice in a row is safe:
1. Idempotent write: db.upsert() deletes-then-inserts by natural key, so
   the same batch loaded twice never produces duplicate rows.
2. Watermark advance: on success, the incremental watermark moves to
   `window_end`. A second immediate run computes window_start > window_end
   and exits with "nothing new" before even calling the source API.

Both protections are independent on purpose -- if state/<source>.json ever
gets reset or corrupted, (1) alone still prevents duplicates.
"""
import argparse
from datetime import date, timedelta

from extraction.db import get_connection, upsert
from extraction.sources import banxico, open_meteo
from extraction.state import load_state, save_state

SOURCES = {
    "open_meteo": {
        "extract": open_meteo.extract,
        "create_sql": open_meteo.CREATE_SQL,
        "table": "open_meteo_daily",
        "key_cols": ["location", "date"],
        # archive API isn't populated for the last few days yet
        "freshness_lag_days": 5,
        "backfill_default_days": 30,
    },
    "banxico": {
        "extract": banxico.extract,
        "create_sql": banxico.CREATE_SQL,
        "table": "banxico_fx",
        "key_cols": ["series", "date"],
        "freshness_lag_days": 1,
        "backfill_default_days": 30,
    },
}


def run(source_name: str, mode: str, start: date | None, end: date | None) -> None:
    cfg = SOURCES[source_name]
    today = date.today()
    safe_end = end or (today - timedelta(days=cfg["freshness_lag_days"]))

    if mode == "backfill":
        if not start:
            raise ValueError("--start is required for --mode backfill")
        window_start, window_end = start, safe_end
    else:
        state = load_state(source_name)
        watermark = state.get("last_watermark")
        if watermark:
            window_start = date.fromisoformat(watermark) + timedelta(days=1)
        else:
            window_start = safe_end - timedelta(days=cfg["backfill_default_days"])
        window_end = safe_end

    if window_start > window_end:
        print(f"[{source_name}] nothing new to extract (watermark already at {window_start - timedelta(days=1)})")
        return

    print(f"[{source_name}] extracting {window_start} -> {window_end} (mode={mode})")
    df = cfg["extract"](window_start, window_end)

    if df.empty:
        print(f"[{source_name}] source returned 0 rows for this window (no-op, watermark unchanged)")
        return

    con = get_connection()
    try:
        upsert(con, "raw", cfg["table"], df, cfg["key_cols"], cfg["create_sql"])
    finally:
        con.close()

    print(f"[{source_name}] loaded {len(df)} rows (idempotent upsert keyed by {cfg['key_cols']})")

    if mode == "incremental":
        save_state(source_name, {"last_watermark": str(window_end)})
        print(f"[{source_name}] watermark advanced to {window_end}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Idempotent, incremental extraction for the pipeline.")
    parser.add_argument("--source", choices=list(SOURCES.keys()), required=True)
    parser.add_argument("--mode", choices=["incremental", "backfill"], default="incremental")
    parser.add_argument("--start", type=date.fromisoformat, help="YYYY-MM-DD (required for backfill)")
    parser.add_argument("--end", type=date.fromisoformat, help="YYYY-MM-DD (defaults to source freshness lag)")
    args = parser.parse_args()
    run(args.source, args.mode, args.start, args.end)


if __name__ == "__main__":
    main()
