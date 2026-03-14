-- Transit equity analysis: speed and reliability distribution across boroughs.
-- Highlights disparities in bus service quality by geography.

with route_perf as (
    select * from {{ ref('fct_route_daily_performance') }}
),

borough_stats as (
    select
        borough,
        avg(route_avg_speed_mph)            as mean_speed,
        stddev(route_avg_speed_mph)         as stddev_speed,
        percentile_cont(0.25) within group (order by route_avg_speed_mph) as p25_speed,
        percentile_cont(0.50) within group (order by route_avg_speed_mph) as median_speed,
        percentile_cont(0.75) within group (order by route_avg_speed_mph) as p75_speed,
        percentile_cont(0.90) within group (order by route_avg_speed_mph) as p90_speed,
        avg(avg_speed_variability_mph)      as mean_variability,
        count(distinct route_id)            as route_count,
        sum(total_trips)                    as total_trips
    from route_perf
    where borough != 'Unknown'
    group by borough
),

with_equity_metrics as (
    select
        borough,
        round(mean_speed, 2)        as mean_speed_mph,
        round(stddev_speed, 2)      as stddev_speed_mph,
        round(p25_speed, 2)         as p25_speed_mph,
        round(median_speed, 2)      as median_speed_mph,
        round(p75_speed, 2)         as p75_speed_mph,
        round(p90_speed, 2)         as p90_speed_mph,
        round(p75_speed - p25_speed, 2) as iqr_speed_mph,
        round(mean_variability, 2)  as mean_variability_mph,
        route_count,
        total_trips,
        -- Coefficient of variation: lower = more equitable service
        round(stddev_speed / nullif(mean_speed, 0) * 100, 1) as cv_pct
    from borough_stats
)

select
    *,
    row_number() over (order by median_speed_mph desc)  as service_quality_rank,
    row_number() over (order by cv_pct asc)             as consistency_rank
from with_equity_metrics
order by service_quality_rank
