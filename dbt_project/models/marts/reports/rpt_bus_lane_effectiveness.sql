-- Compare average bus speeds on segments with bus lanes vs without.
-- Quantifies the speed benefit of bus lane infrastructure.

with speeds as (
    select * from {{ ref('fct_segment_speeds_hourly') }}
),

lane_match as (
    select segment_id, has_bus_lane, lane_type
    from {{ ref('int_segment_bus_lane_match') }}
),

joined as (
    select
        s.time_period,
        s.hour_of_day,
        lm.has_bus_lane,
        lm.lane_type,
        round(avg(s.avg_speed_mph), 2)              as avg_speed_mph,
        round(avg(s.speed_variability_mph), 2)      as avg_variability_mph,
        count(distinct s.segment_id)                as segment_count,
        sum(s.trip_count)                           as total_trips
    from speeds s
    inner join lane_match lm using (segment_id)
    group by
        s.time_period,
        s.hour_of_day,
        lm.has_bus_lane,
        lm.lane_type
),

pivoted as (
    select
        time_period,
        hour_of_day,
        max(case when has_bus_lane then avg_speed_mph end)      as bus_lane_avg_speed,
        max(case when not has_bus_lane then avg_speed_mph end)  as no_bus_lane_avg_speed,
        max(case when has_bus_lane then segment_count end)      as bus_lane_segments,
        max(case when not has_bus_lane then segment_count end)  as no_bus_lane_segments
    from joined
    group by time_period, hour_of_day
)

select
    time_period,
    hour_of_day,
    bus_lane_avg_speed,
    no_bus_lane_avg_speed,
    round(bus_lane_avg_speed - no_bus_lane_avg_speed, 2)    as speed_benefit_mph,
    round(
        (bus_lane_avg_speed - no_bus_lane_avg_speed)
        / nullif(no_bus_lane_avg_speed, 0) * 100, 1
    )                                                       as speed_benefit_pct,
    bus_lane_segments,
    no_bus_lane_segments
from pivoted
order by hour_of_day
