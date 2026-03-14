with source_2023_2024 as (
    select
        route_id,
        segment_id,
        year,
        month,
        day_of_week,
        hour_of_day,
        avg_speed_mph,
        min_speed_mph,
        max_speed_mph,
        median_speed_mph,
        number_of_trips,
        segment_start,
        segment_end,
        '2023_2024' as data_source
    from {{ source('mta_bus_speeds', 'bus_segment_speeds_2023_2024') }}
),

source_2025 as (
    select
        route_id,
        segment_id,
        year,
        month,
        day_of_week,
        hour_of_day,
        avg_speed_mph,
        min_speed_mph,
        max_speed_mph,
        median_speed_mph,
        number_of_trips,
        segment_start,
        segment_end,
        '2025' as data_source
    from {{ source('mta_bus_speeds', 'bus_segment_speeds_2025') }}
),

unioned as (
    select * from source_2023_2024
    union all
    select * from source_2025
),

with_surrogate_key as (
    select
        md5(
            coalesce(cast(route_id as varchar), '') || '|' ||
            coalesce(cast(segment_id as varchar), '') || '|' ||
            coalesce(cast(year as varchar), '') || '|' ||
            coalesce(cast(month as varchar), '') || '|' ||
            coalesce(cast(day_of_week as varchar), '') || '|' ||
            coalesce(cast(hour_of_day as varchar), '') || '|' ||
            coalesce(cast(data_source as varchar), '')
        ) as segment_speed_id,
        route_id,
        segment_id,
        year,
        month,
        day_of_week,
        hour_of_day,
        avg_speed_mph,
        min_speed_mph,
        max_speed_mph,
        median_speed_mph,
        number_of_trips,
        segment_start,
        segment_end,
        data_source
    from unioned
),

deduplicated as (
    select *
    from with_surrogate_key
    qualify row_number() over (
        partition by segment_speed_id
        order by data_source desc
    ) = 1
)

select * from deduplicated
