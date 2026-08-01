-- Business rule, singular test: a day's max temperature can never be
-- lower than its min. That's a physical impossibility, not a
-- data-quality nicety -- if this ever returns rows, the source data (or
-- our transform) is broken, full stop.
--
-- This is also exactly what `make chaos MODE=business_rule` injects, on
-- purpose, so you can verify this test actually catches it.
select *
from {{ ref('fct_daily_conditions') }}
where temp_max_c < temp_min_c
