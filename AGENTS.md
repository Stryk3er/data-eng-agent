# Data Engineering Agent -- project instructions

You operate a small, free-tier data pipeline: Open-Meteo (weather) and
Banxico (USD/MXN FX) -> DuckDB -> dbt (staging/intermediate/marts) -> tests.

Read the `data-engineering-agent` skill before doing anything in this repo.
Read the `diagnose-pipeline-failure` skill before explaining any failure --
not after you've already written an explanation.

Hard rule, not a preference: you have no tool capable of running a
full-refresh, a drop, or any other destructive operation. Don't try to
route around that through the raw `bash` tool -- it requires human
approval ("ask") anyway, and pretending otherwise wastes everyone's time.
Use `propose_full_refresh` and stop there.
