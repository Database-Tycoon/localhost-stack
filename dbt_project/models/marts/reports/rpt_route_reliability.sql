-- Routes ranked by reliability grade and average speed.
-- Aggregates route daily performance across all observation dates.
-- NOTE: speed_variability_mph is not available in the source data;
-- reliability is graded by average speed in fct_route_daily_performance.

with route_perf as (
    select * from {{ ref('fct_route_daily_performance') }}
),

summary as (
    select
        route_id,
        route_short_name,
        borough,
        round(avg(route_avg_speed_mph), 2)  as overall_avg_speed_mph,
        sum(total_trips)                    as total_trips,
        count(distinct metric_date)         as observation_days,

        -- Grade distribution
        count(case when reliability_grade = 'A' then 1 end) as grade_a_days,
        count(case when reliability_grade = 'B' then 1 end) as grade_b_days,
        count(case when reliability_grade = 'C' then 1 end) as grade_c_days,
        count(case when reliability_grade = 'D' then 1 end) as grade_d_days,
        count(case when reliability_grade = 'F' then 1 end) as grade_f_days,

        -- Most common grade
        mode() within group (order by reliability_grade) as most_common_grade
    from route_perf
    group by route_id, route_short_name, borough
)

select
    *,
    row_number() over (order by overall_avg_speed_mph desc) as speed_rank,
    row_number() over (order by overall_avg_speed_mph desc) as reliability_rank
from summary
order by reliability_rank
