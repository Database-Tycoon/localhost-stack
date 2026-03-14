-- Hourly grain fact table for bus segment speeds.
-- Identical grain to fct_bus_segment_speeds but enriched with time-of-day attributes
-- for easier hourly analysis without additional joins.

with speeds as (
    select * from {{ ref('fct_bus_segment_speeds') }}
),

time_of_day as (
    select * from {{ ref('dim_time_of_day') }}
),

enriched as (
    select
        s.segment_speed_key,
        s.route_id,
        s.segment_id,
        s.metric_date,
        s.year,
        s.month,
        s.day_of_week,
        s.hour_of_day,
        t.time_period,
        t.time_period_sort_order,
        t.is_peak_hour,
        t.hour_label,
        s.avg_speed_mph,
        s.min_speed_mph,
        s.max_speed_mph,
        s.median_speed_mph,
        s.speed_variability_mph,
        s.trip_count,
        s.segment_start,
        s.segment_end,
        s.data_source
    from speeds s
    left join time_of_day t using (hour_of_day)
)

select * from enriched
