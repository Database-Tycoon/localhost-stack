-- Weekend vs weekday speed comparison by route and borough.
-- NOTE: speed_variability_mph is not available in the source data and is omitted.

with speeds as (
    select * from {{ ref('fct_bus_segment_speeds') }}
),

dates as (
    select date_day, is_weekend, is_weekday
    from {{ ref('dim_date') }}
),

routes as (
    select route_id, route_short_name, borough
    from {{ ref('dim_bus_routes') }}
),

joined as (
    select
        s.route_id,
        r.route_short_name,
        r.borough,
        case when d.is_weekend then 'Weekend' else 'Weekday' end as day_type,
        s.avg_speed_mph,
        s.trip_count
    from speeds s
    left join dates d on s.metric_date = d.date_day
    left join routes r using (route_id)
),

aggregated as (
    select
        route_id,
        route_short_name,
        borough,
        day_type,
        round(avg(avg_speed_mph), 2)    as avg_speed_mph,
        sum(trip_count)                 as total_trips
    from joined
    where day_type is not null
    group by route_id, route_short_name, borough, day_type
),

pivoted as (
    select
        route_id,
        route_short_name,
        borough,
        max(case when day_type = 'Weekday' then avg_speed_mph end)  as weekday_avg_speed_mph,
        max(case when day_type = 'Weekend' then avg_speed_mph end)  as weekend_avg_speed_mph,
        max(case when day_type = 'Weekday' then total_trips end)    as weekday_total_trips,
        max(case when day_type = 'Weekend' then total_trips end)    as weekend_total_trips
    from aggregated
    group by route_id, route_short_name, borough
)

select
    *,
    round(weekend_avg_speed_mph - weekday_avg_speed_mph, 2) as weekend_speed_delta_mph
from pivoted
order by borough, route_short_name
