-- Reshape traffic volume counts into a consistent hourly grain.
-- The source data may contain total daily counts; this model distributes
-- volume across hours using a typical urban traffic distribution profile
-- when hourly breakdown is not available in the source.

with daily_volumes as (
    select
        segment_id,
        street,
        from_street,
        to_street,
        direction,
        date,
        volume as daily_volume
    from {{ ref('stg_nyc_dot__traffic_volume_counts') }}
),

hours as (
    select hour_of_day
    from {{ ref('dim_time_of_day') }}
),

-- Distribute daily volume across 24 hours using a typical urban profile weight.
-- Weights peak during AM (7-9) and PM (16-19) periods.
hour_weights as (
    select
        hour_of_day,
        case
            when hour_of_day between 7 and 9   then 0.075  -- AM peak ~22.5% over 3 hrs
            when hour_of_day between 10 and 15  then 0.050  -- Midday  ~30% over 6 hrs
            when hour_of_day between 16 and 19  then 0.065  -- PM peak ~26% over 4 hrs
            when hour_of_day between 20 and 22  then 0.040  -- Evening ~12% over 3 hrs
            else                                     0.010  -- Overnight ~10% over 8 hrs
        end as weight
    from hours
),

hourly as (
    select
        dv.segment_id,
        dv.street,
        dv.from_street,
        dv.to_street,
        dv.direction,
        dv.date,
        hw.hour_of_day,
        round(dv.daily_volume * hw.weight) as hourly_volume,
        dv.daily_volume
    from daily_volumes dv
    cross join hour_weights hw
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
from hourly
