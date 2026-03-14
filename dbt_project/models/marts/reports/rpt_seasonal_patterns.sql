-- Bus speed patterns by season and borough.
-- NOTE: speed_variability_mph is not available in the source data and is omitted.

with speeds as (
    select * from {{ ref('fct_bus_segment_speeds') }}
),

dates as (
    select date_day, season, year_number
    from {{ ref('dim_date') }}
),

routes as (
    select route_id, borough
    from {{ ref('dim_bus_routes') }}
),

joined as (
    select
        d.season,
        d.year_number,
        r.borough,
        round(avg(s.avg_speed_mph), 2)      as avg_speed_mph,
        sum(s.trip_count)                   as total_trips,
        count(distinct s.route_id)          as route_count,
        count(distinct s.segment_id)        as segment_count
    from speeds s
    inner join dates d on s.metric_date = d.date_day
    left join routes r using (route_id)
    group by d.season, d.year_number, r.borough
)

select * from joined
order by year_number, season, borough
