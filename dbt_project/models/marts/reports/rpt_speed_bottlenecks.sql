-- Slowest segments by time of day.
-- Identifies recurring speed bottlenecks across the network.

with speeds as (
    select * from {{ ref('fct_segment_speeds_hourly') }}
),

segment_summary as (
    select
        segment_id,
        segment_start,
        segment_end,
        time_period,
        round(avg(avg_speed_mph), 2)            as avg_speed_mph,
        round(avg(speed_variability_mph), 2)    as avg_variability_mph,
        sum(trip_count)                         as total_trips,
        count(distinct route_id)                as route_count,
        count(distinct metric_date)             as observation_days
    from speeds
    group by
        segment_id,
        segment_start,
        segment_end,
        time_period
),

ranked as (
    select
        *,
        row_number() over (
            partition by time_period
            order by avg_speed_mph asc
        ) as speed_rank
    from segment_summary
)

select *
from ranked
where speed_rank <= 50
order by time_period, speed_rank
