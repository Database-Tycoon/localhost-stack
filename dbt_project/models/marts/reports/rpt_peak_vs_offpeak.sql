-- Peak vs off-peak speed comparison by route and borough.

with speeds as (
    select * from {{ ref('fct_segment_speeds_hourly') }}
),

routes as (
    select route_id, route_short_name, borough
    from {{ ref('dim_bus_routes') }}
),

classified as (
    select
        s.route_id,
        r.route_short_name,
        r.borough,
        case when s.is_peak_hour then 'Peak' else 'Off-Peak' end as period_class,
        s.avg_speed_mph,
        s.speed_variability_mph,
        s.trip_count
    from speeds s
    left join routes r using (route_id)
),

aggregated as (
    select
        route_id,
        route_short_name,
        borough,
        period_class,
        round(avg(avg_speed_mph), 2)            as avg_speed_mph,
        round(avg(speed_variability_mph), 2)    as avg_variability_mph,
        sum(trip_count)                         as total_trips
    from classified
    group by route_id, route_short_name, borough, period_class
),

pivoted as (
    select
        route_id,
        route_short_name,
        borough,
        max(case when period_class = 'Peak' then avg_speed_mph end)         as peak_avg_speed_mph,
        max(case when period_class = 'Off-Peak' then avg_speed_mph end)     as offpeak_avg_speed_mph,
        max(case when period_class = 'Peak' then avg_variability_mph end)   as peak_avg_variability_mph,
        max(case when period_class = 'Off-Peak' then avg_variability_mph end) as offpeak_avg_variability_mph,
        max(case when period_class = 'Peak' then total_trips end)           as peak_total_trips,
        max(case when period_class = 'Off-Peak' then total_trips end)       as offpeak_total_trips
    from aggregated
    group by route_id, route_short_name, borough
)

select
    *,
    round(peak_avg_speed_mph - offpeak_avg_speed_mph, 2)    as speed_delta_mph
from pivoted
order by borough, route_short_name
