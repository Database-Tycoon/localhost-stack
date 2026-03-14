-- Staging model for MTA bus segment speeds (2025 data only).
-- Source columns are all VARCHAR; numeric fields are cast here.
-- segment_id is constructed from timepoint_stop_id || '-' || next_timepoint_stop_id
-- since no pre-built segment_id exists in the source.
--
-- NOTE: When the bus_segment_speeds_2023_2024 table becomes available, add a
-- second CTE identical to source_2025 selecting from that table and UNION ALL
-- it into the `unioned` CTE below.

with source_2025 as (
    select
        route_id,
        direction,
        borough,
        route_type,
        -- Construct a stable segment identifier from the timepoint stop pair
        timepoint_stop_id || '-' || next_timepoint_stop_id  as segment_id,
        timepoint_stop_id,
        timepoint_stop_name                                  as segment_start,
        timepoint_stop_latitude,
        timepoint_stop_longitude,
        next_timepoint_stop_id,
        next_timepoint_stop_name                             as segment_end,
        next_timepoint_stop_latitude,
        next_timepoint_stop_longitude,
        year,
        month,
        day_of_week,
        hour_of_day,
        -- Cast numeric VARCHARs to appropriate types
        try_cast(road_distance as double)       as road_distance_miles,
        try_cast(average_travel_time as double) as avg_travel_time_min,
        try_cast(average_road_speed as double)  as avg_speed_mph,
        try_cast(bus_trip_count as integer)     as trip_count,
        stop_order,
        timestamp,
        '2025'                                               as data_source
    from {{ source('mta_bus_speeds', 'bus_segment_speeds_2025') }}
),

with_surrogate_key as (
    select
        md5(
            coalesce(cast(route_id as varchar), '')    || '|' ||
            coalesce(cast(segment_id as varchar), '')  || '|' ||
            coalesce(cast(year as varchar), '')        || '|' ||
            coalesce(cast(month as varchar), '')       || '|' ||
            coalesce(cast(day_of_week as varchar), '') || '|' ||
            coalesce(cast(hour_of_day as varchar), '')
        ) as segment_speed_id,
        route_id,
        segment_id,
        timepoint_stop_id,
        segment_start,
        timepoint_stop_latitude,
        timepoint_stop_longitude,
        next_timepoint_stop_id,
        segment_end,
        next_timepoint_stop_latitude,
        next_timepoint_stop_longitude,
        direction,
        borough,
        route_type,
        stop_order,
        year,
        month,
        day_of_week,
        hour_of_day,
        road_distance_miles,
        avg_travel_time_min,
        avg_speed_mph,
        trip_count,
        timestamp,
        data_source
    from source_2025
),

deduplicated as (
    select *
    from with_surrogate_key
    qualify row_number() over (
        partition by segment_speed_id
        order by timestamp desc nulls last
    ) = 1
)

select * from deduplicated
