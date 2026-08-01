-- The "incomoda" logic #2: cross-source join + derived columns. Kept out
-- of staging (which stays 1:1 per source) and out of the mart (which
-- stays a thin, contract-enforced projection).
with weather as (
    select * from {{ ref('stg_open_meteo__daily') }}
),

fx as (
    select * from {{ ref('int_fx_gap_filled') }}
)

select
    weather.location,
    weather.date,
    weather.temp_max_c,
    weather.temp_min_c,
    weather.temp_max_c - weather.temp_min_c as temp_range_c,
    weather.precipitation_mm,
    fx.fx_rate                              as fx_usd_mxn,
    fx.is_published_rate                    as fx_is_published_rate,
    (extract(dow from weather.date) not in (0, 6)) as is_business_day
from weather
left join fx on weather.date = fx.date
