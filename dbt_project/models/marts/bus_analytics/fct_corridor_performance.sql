-- Corridor-level performance aggregation joining segment speeds with bus lane matches.
-- Grain: lane_street × metric_date × hour_of_day

with speeds as (
    select * from {{ ref('fct_bus_segment_speeds') }}
),

lane_match as (
    select * from {{ ref('int_segment_bus_lane_match') }}
),

joined as (
    select
        s.metric_date,
        s.year,
        s.month,
        s.day_of_week,
        s.hour_of_day,
        lm.lane_street                      as corridor_street,
        lm.lane_borough                     as borough,
        lm.lane_type,
        lm.has_bus_lane,

        avg(s.avg_speed_mph)                as corridor_avg_speed_mph,
        min(s.min_speed_mph)                as corridor_min_speed_mph,
        max(s.max_speed_mph)                as corridor_max_speed_mph,
        avg(s.speed_variability_mph)        as corridor_avg_variability_mph,
        sum(s.trip_count)                   as total_trips,
        count(distinct s.segment_id)        as segment_count,
        count(distinct s.route_id)          as route_count
    from speeds s
    inner join lane_match lm using (segment_id)
    where lm.has_bus_lane = true
    group by
        s.metric_date,
        s.year,
        s.month,
        s.day_of_week,
        s.hour_of_day,
        lm.lane_street,
        lm.lane_borough,
        lm.lane_type,
        lm.has_bus_lane
),

with_key as (
    select
        md5(
            coalesce(cast(metric_date as varchar), '') || '|' ||
            coalesce(corridor_street, '') || '|' ||
            coalesce(cast(hour_of_day as varchar), '')
        ) as corridor_performance_key,
        *
    from joined
)

select * from with_key
