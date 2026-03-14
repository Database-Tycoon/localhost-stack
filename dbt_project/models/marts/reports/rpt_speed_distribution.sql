-- Speed distribution buckets across the network.
-- Enables histogram-style analysis of how speeds are distributed.

with speeds as (
    select * from {{ ref('fct_bus_segment_speeds') }}
),

routes as (
    select route_id, borough
    from {{ ref('dim_bus_routes') }}
),

bucketed as (
    select
        s.route_id,
        r.borough,
        s.avg_speed_mph,
        case
            when s.avg_speed_mph < 3   then '0-3 mph (Very Slow)'
            when s.avg_speed_mph < 6   then '3-6 mph (Slow)'
            when s.avg_speed_mph < 9   then '6-9 mph (Below Average)'
            when s.avg_speed_mph < 12  then '9-12 mph (Average)'
            when s.avg_speed_mph < 15  then '12-15 mph (Above Average)'
            when s.avg_speed_mph < 20  then '15-20 mph (Fast)'
            else                            '20+ mph (Very Fast)'
        end as speed_bucket,
        case
            when s.avg_speed_mph < 3   then 1
            when s.avg_speed_mph < 6   then 2
            when s.avg_speed_mph < 9   then 3
            when s.avg_speed_mph < 12  then 4
            when s.avg_speed_mph < 15  then 5
            when s.avg_speed_mph < 20  then 6
            else                            7
        end as bucket_sort_order
    from speeds s
    left join routes r using (route_id)
),

distribution as (
    select
        borough,
        speed_bucket,
        bucket_sort_order,
        count(*)                as record_count,
        count(*) * 100.0 / sum(count(*)) over (partition by borough) as pct_of_borough
    from bucketed
    group by borough, speed_bucket, bucket_sort_order
)

select
    borough,
    speed_bucket,
    record_count,
    round(pct_of_borough, 1) as pct_of_borough
from distribution
order by borough, bucket_sort_order
