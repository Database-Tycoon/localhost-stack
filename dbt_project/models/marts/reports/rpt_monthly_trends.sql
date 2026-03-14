-- Month-over-month speed trends by borough.

with speeds as (
    select * from {{ ref('fct_bus_segment_speeds') }}
),

dates as (
    select date_day, year_number, month_number, month_name, year_month_key
    from {{ ref('dim_date') }}
),

routes as (
    select route_id, borough
    from {{ ref('dim_bus_routes') }}
),

joined as (
    select
        d.year_number,
        d.month_number,
        d.month_name,
        d.year_month_key,
        r.borough,
        round(avg(s.avg_speed_mph), 2)              as avg_speed_mph,
        round(avg(s.speed_variability_mph), 2)      as avg_variability_mph,
        sum(s.trip_count)                           as total_trips,
        count(distinct s.route_id)                  as route_count
    from speeds s
    inner join dates d on s.metric_date = d.date_day
    left join routes r using (route_id)
    group by
        d.year_number,
        d.month_number,
        d.month_name,
        d.year_month_key,
        r.borough
),

with_mom as (
    select
        *,
        lag(avg_speed_mph) over (
            partition by borough
            order by year_month_key
        ) as prior_month_avg_speed,

        round(
            avg_speed_mph - lag(avg_speed_mph) over (
                partition by borough
                order by year_month_key
            ), 2
        ) as mom_speed_change_mph,

        round(
            (avg_speed_mph - lag(avg_speed_mph) over (
                partition by borough
                order by year_month_key
            )) / nullif(lag(avg_speed_mph) over (
                partition by borough
                order by year_month_key
            ), 0) * 100, 1
        ) as mom_speed_change_pct
    from joined
)

select *
order by borough, year_month_key
