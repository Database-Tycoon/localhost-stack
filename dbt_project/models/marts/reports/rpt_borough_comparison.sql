-- Borough-level speed and reliability aggregation.

with route_perf as (
    select * from {{ ref('fct_route_daily_performance') }}
),

by_borough as (
    select
        borough,
        round(avg(route_avg_speed_mph), 2)          as avg_speed_mph,
        round(min(route_min_speed_mph), 2)           as min_speed_mph,
        round(max(route_max_speed_mph), 2)           as max_speed_mph,
        round(avg(avg_speed_variability_mph), 2)    as avg_variability_mph,
        sum(total_trips)                            as total_trips,
        count(distinct route_id)                    as route_count,
        count(distinct metric_date)                 as observation_days,

        -- Grade distribution
        round(
            count(case when reliability_grade = 'A' then 1 end) * 100.0
            / nullif(count(*), 0), 1
        ) as pct_grade_a,
        round(
            count(case when reliability_grade in ('A', 'B') then 1 end) * 100.0
            / nullif(count(*), 0), 1
        ) as pct_grade_a_or_b
    from route_perf
    where borough != 'Unknown'
    group by borough
)

select
    *,
    row_number() over (order by avg_speed_mph desc) as speed_rank
from by_borough
order by speed_rank
