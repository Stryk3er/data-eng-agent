{{
    config(
        materialized='incremental',
        unique_key=['location', 'date'],
        incremental_strategy='delete+insert',
        incremental_predicate="dbt_internal_dest.date >= (current_date - interval '10 days')",
        on_schema_change='fail'
    )
}}

-- WHY delete+insert with a 10-day lookback, instead of append or full
-- rebuild every run:
--
-- Both sources can revise recent history. Open-Meteo's archive endpoint
-- occasionally corrects the last few days of a station's readings once
-- better QA'd data comes in, and Banxico can republish a same-day rate
-- later in the day. A plain `append` incremental would duplicate rows
-- every time a correction lands, because the (location, date) key would
-- already exist. A full rebuild every run would be correct, but it
-- reprocesses years of history to account for changes that only ever
-- touch the last few days.
--
-- delete+insert with unique_key + a 10-day lookback predicate gives us
-- correction-safety (recent days get fully replaced, not appended) at the
-- cost of reprocessing 10 days instead of everything -- proportional to
-- how far back either source realistically revises.

select
    location,
    date,
    temp_max_c,
    temp_min_c,
    temp_range_c,
    precipitation_mm,
    fx_usd_mxn,
    fx_is_published_rate,
    is_business_day
from {{ ref('int_daily_conditions') }}

{% if is_incremental() %}
where date >= (select coalesce(max(date), date '1970-01-01') from {{ this }}) - interval '10 days'
{% endif %}
