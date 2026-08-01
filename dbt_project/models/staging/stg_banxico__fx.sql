-- Staging: 1:1 with the raw source table. Only casting/renaming here --
-- no joins, no business logic. The non-business-day gap-fill lives in
-- models/intermediate/int_fx_gap_filled.sql, deliberately not here.
select
    series,
    cast(date as date)    as date,
    cast(value as double) as fx_rate,
    extracted_at
from {{ source('raw', 'banxico_fx') }}
where series = 'fx_usd_mxn'
