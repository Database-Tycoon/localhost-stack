-- Hourly grain fact table for bus segment speeds.
-- Identical grain to fct_bus_segment_speeds but enriched with time-of-day attributes
-- for easier hourly analysis without additional joins.
-- NOTE: min_speed_mph, max_speed_mph, median_speed_mph, and speed_variability_mph
-- are not available in the source data and are omitted.

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
        s.trip_count,
        s.road_distance_miles,
        s.avg_travel_time_min,
        s.segment_start,
        s.segment_end,
        s.direction,
        s.borough,
        s.route_type,
        s.data_source
    from speeds s
    left join time_of_day t using (hour_of_day)
)

select * from enriched
