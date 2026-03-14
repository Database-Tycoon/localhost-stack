-- Bus speed analysis by hour of day across the network.

with speeds as (
    select * from {{ ref('fct_segment_speeds_hourly') }}
),

routes as (
    select route_id, borough
    from {{ ref('dim_bus_routes') }}
),

by_hour as (
    select
        s.hour_of_day,
        s.time_period,
        s.is_peak_hour,
        s.hour_label,
        r.borough,
        round(avg(s.avg_speed_mph), 2)              as avg_speed_mph,
        round(avg(s.median_speed_mph), 2)           as median_speed_mph,
        round(avg(s.speed_variability_mph), 2)      as avg_variability_mph,
        sum(s.trip_count)                           as total_trips,
        count(distinct s.route_id)                  as route_count,
        count(distinct s.segment_id)                as segment_count
    from speeds s
    left join routes r using (route_id)
    group by
        s.hour_of_day,
        s.time_period,
        s.is_peak_hour,
        s.hour_label,
        r.borough
)

select *
order by hour_of_day, borough
