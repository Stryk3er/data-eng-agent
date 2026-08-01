-- Staging: 1:1 with the raw source table. Only casting/renaming here --
-- no joins, no business logic. That belongs in models/intermediate/.
select
    location,
    cast(date as date)               as date,
    cast(temp_max_c as double)        as temp_max_c,
    cast(temp_min_c as double)        as temp_min_c,
    cast(precipitation_mm as double)  as precipitation_mm,
    extracted_at
from {{ source('raw', 'open_meteo_daily') }}
