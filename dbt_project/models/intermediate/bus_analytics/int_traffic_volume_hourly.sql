-- Reshape traffic volume counts into a consistent hourly grain.
-- The source data already contains hourly observations (hour column from hh).
-- This model standardizes column names and computes daily totals.

with hourly_counts as (
    select
        segment_id,
        street,
        from_street,
        to_street,
        direction,
        date,
        hour as hour_of_day,
        volume as hourly_volume
    from {{ ref('stg_nyc_dot__traffic_volume_counts') }}
    where volume is not null
),

with_daily as (
    select
        *,
        sum(hourly_volume) over (
            partition by segment_id, street, direction, date
        ) as daily_volume
    from hourly_counts
)

select
    segment_id,
    street,
    from_street,
    to_street,
    direction,
    date,
    hour_of_day,
    hourly_volume,
    daily_volume
from with_daily
