-- Central fact table for bus segment speeds.
-- Grain: route_id × segment_id × metric_date × hour_of_day
-- Joins staging speeds with representative dates to produce a date-based fact.
-- NOTE: min_speed_mph, max_speed_mph, median_speed_mph, and speed_variability_mph
-- are not available in the source data and are therefore absent from this model.

with speeds as (
    select * from {{ ref('stg_mta_bus_speeds__segment_speeds') }}
),

rep_dates as (
    select * from {{ ref('int_representative_dates') }}
),

joined as (
    select
        -- Surrogate key
        md5(
            coalesce(cast(s.route_id as varchar), '') || '|' ||
            coalesce(cast(s.segment_id as varchar), '') || '|' ||
            coalesce(cast(rd.metric_date as varchar), '') || '|' ||
            coalesce(cast(s.hour_of_day as varchar), '')
        ) as segment_speed_key,

        -- Foreign keys / natural keys
        s.route_id,
        s.segment_id,
        rd.metric_date,
        s.year,
        s.month,
        s.day_of_week,
        s.hour_of_day,
        s.data_source,

        -- Measures
        s.avg_speed_mph,
        s.trip_count,
        s.road_distance_miles,
        s.avg_travel_time_min,

        -- Descriptive
        s.segment_start,
        s.segment_end,
        s.direction,
        s.borough,
        s.route_type
    from speeds s
    left join rep_dates rd
        on  s.year        = rd.year
        and s.month       = rd.month
        and s.day_of_week = rd.day_of_week
)

select * from joined
