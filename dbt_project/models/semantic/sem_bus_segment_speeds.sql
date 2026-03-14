-- MetricFlow semantic model for bus segment speeds.
-- Exposes the core speed metrics for MetricFlow-based querying.
-- This SQL model selects the columns that MetricFlow will use as entities,
-- dimensions, and measures (defined in the YAML configuration below).

select
    segment_speed_key,
    route_id,
    segment_id,
    metric_date,
    hour_of_day,
    avg_speed_mph,
    min_speed_mph,
    max_speed_mph,
    median_speed_mph,
    speed_variability_mph,
    trip_count,
    segment_start,
    segment_end
from {{ ref('fct_bus_segment_speeds') }}
