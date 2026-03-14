-- Route-level daily performance aggregation.
-- Grain: route_id × metric_date
-- NOTE: min_speed_mph, max_speed_mph, median_speed_mph, and speed_variability_mph
-- are not available in the source data. Reliability grade is based on average
-- speed across the route (higher avg speed = better grade).

with segment_speeds as (
    select * from {{ ref('fct_bus_segment_speeds') }}
),

routes as (
    select route_id, route_short_name, borough
    from {{ ref('dim_bus_routes') }}
),

aggregated as (
    select
        s.route_id,
        s.metric_date,
        s.year,
        s.month,
        s.day_of_week,

        avg(s.avg_speed_mph)            as route_avg_speed_mph,
        sum(s.trip_count)               as total_trips,
        count(distinct s.segment_id)    as segment_count
    from segment_speeds s
    group by
        s.route_id,
        s.metric_date,
        s.year,
        s.month,
        s.day_of_week
),

with_grade as (
    select
        md5(
            coalesce(cast(route_id as varchar), '') || '|' ||
            coalesce(cast(metric_date as varchar), '')
        ) as route_daily_key,

        route_id,
        metric_date,
        year,
        month,
        day_of_week,
        route_avg_speed_mph,
        total_trips,
        segment_count,

        -- Reliability grade based on average speed:
        -- faster average speed indicates more reliable / unimpeded service
        case
            when route_avg_speed_mph >= 12 then 'A'
            when route_avg_speed_mph >= 9  then 'B'
            when route_avg_speed_mph >= 6  then 'C'
            when route_avg_speed_mph >= 4  then 'D'
            else                                'F'
        end as reliability_grade
    from aggregated
)

select
    wg.*,
    r.route_short_name,
    r.borough
from with_grade wg
left join routes r using (route_id)
