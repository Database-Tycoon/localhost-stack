-- Route-level daily performance aggregation.
-- Grain: route_id × metric_date
-- Includes reliability grade derived from speed variability.

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
        min(s.min_speed_mph)            as route_min_speed_mph,
        max(s.max_speed_mph)            as route_max_speed_mph,
        avg(s.median_speed_mph)         as route_median_speed_mph,
        avg(s.speed_variability_mph)    as avg_speed_variability_mph,
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
        route_min_speed_mph,
        route_max_speed_mph,
        route_median_speed_mph,
        avg_speed_variability_mph,
        total_trips,
        segment_count,

        -- Reliability grade: lower variability = better grade
        case
            when avg_speed_variability_mph < 3  then 'A'
            when avg_speed_variability_mph < 6  then 'B'
            when avg_speed_variability_mph < 10 then 'C'
            when avg_speed_variability_mph < 15 then 'D'
            else                                     'F'
        end as reliability_grade
    from aggregated
)

select
    wg.*,
    r.route_short_name,
    r.borough
from with_grade wg
left join routes r using (route_id)
