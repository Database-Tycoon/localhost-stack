-- Maps (year, month, day_of_week) combinations to a representative calendar date.
-- The representative date is the first occurrence of that day_of_week within that
-- year-month, enabling MetricFlow time-series aggregation on bus speed data which
-- is reported at the (year, month, day_of_week) grain rather than a specific date.

with speed_date_combos as (
    select distinct
        year,
        month,
        day_of_week
    from {{ ref('stg_mta_bus_speeds__segment_speeds') }}
),

calendar as (
    select * from {{ ref('dim_date') }}
),

-- For each (year, month, day_of_week) find the first matching calendar date
matched as (
    select
        s.year,
        s.month,
        s.day_of_week,
        min(c.date_day) as metric_date
    from speed_date_combos s
    inner join calendar c
        on c.year_number = s.year
        and c.month_number = s.month
        and c.day_of_week_number = s.day_of_week
    group by s.year, s.month, s.day_of_week
)

select
    year,
    month,
    day_of_week,
    metric_date
from matched
