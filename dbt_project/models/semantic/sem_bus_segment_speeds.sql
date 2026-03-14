-- MetricFlow semantic model for bus segment speeds.
-- Exposes the core speed metrics for MetricFlow-based querying.
-- NOTE: min_speed_mph, max_speed_mph, median_speed_mph, and speed_variability_mph
-- are not available in the source data and are omitted.

select
    segment_speed_key,
    route_id,
    segment_id,
    metric_date,
    hour_of_day,
    avg_speed_mph,
    trip_count,
    road_distance_miles,
    avg_travel_time_min,
    segment_start,
    segment_end
from {{ ref('fct_bus_segment_speeds') }}
