-- Corridor-level summary aggregating performance across all time periods.
-- NOTE: corridor_min_speed_mph, corridor_max_speed_mph, and corridor_avg_variability_mph
-- are not available in the source data and are omitted from this report.

with corridor as (
    select * from {{ ref('fct_corridor_performance') }}
),

summary as (
    select
        corridor_street,
        borough,
        lane_type,
        round(avg(corridor_avg_speed_mph), 2)   as overall_avg_speed_mph,
        sum(total_trips)                        as total_trips,
        max(segment_count)                      as segment_count,
        max(route_count)                        as route_count,
        count(distinct metric_date)             as observation_days,

        -- Peak vs off-peak
        round(avg(case when cast(hour_of_day as integer) between 7 and 9
                  then corridor_avg_speed_mph end), 2)  as am_peak_avg_speed_mph,
        round(avg(case when cast(hour_of_day as integer) between 16 and 19
                  then corridor_avg_speed_mph end), 2)  as pm_peak_avg_speed_mph,
        round(avg(case when cast(hour_of_day as integer) not between 7 and 19
                  then corridor_avg_speed_mph end), 2)  as offpeak_avg_speed_mph
    from corridor
    group by corridor_street, borough, lane_type
)

select
    *,
    round(overall_avg_speed_mph - am_peak_avg_speed_mph, 2)     as am_peak_penalty_mph,
    round(overall_avg_speed_mph - pm_peak_avg_speed_mph, 2)     as pm_peak_penalty_mph,
    row_number() over (order by overall_avg_speed_mph desc)      as speed_rank
from summary
order by speed_rank
