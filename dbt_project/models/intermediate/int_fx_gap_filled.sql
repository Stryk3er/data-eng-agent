-- The "incomoda" logic #1: Banxico only publishes on business days, so
-- weekends/holidays have no row at all. Downstream needs a value for
-- every calendar day (weather is daily regardless), so we build a full
-- calendar spine and carry the last published rate forward -- standard
-- "last observation carried forward", which is the correct treatment for
-- an FX rate that genuinely doesn't move on days markets are closed
-- (as opposed to, say, silently zero-filling, which would be wrong).
with calendar as (
    select cast(d as date) as date
    from (
        select unnest(generate_series(
            (select min(date) from {{ ref('stg_banxico__fx') }}),
            (select max(date) from {{ ref('stg_banxico__fx') }}),
            interval 1 day
        )) as d
    )
),

fx as (
    select * from {{ ref('stg_banxico__fx') }}
),

joined as (
    select
        calendar.date,
        fx.fx_rate,
        (fx.fx_rate is not null) as is_published_rate
    from calendar
    left join fx on calendar.date = fx.date
)

select
    date,
    last_value(fx_rate ignore nulls) over (
        order by date
        rows between unbounded preceding and current row
    ) as fx_rate,
    is_published_rate
from joined
