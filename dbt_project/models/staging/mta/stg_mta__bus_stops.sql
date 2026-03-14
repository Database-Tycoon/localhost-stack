with source as (
    select * from {{ source('mta', 'gtfs_stops') }}
),

cleaned as (
    select
        cast(stop_id as varchar)    as stop_id,
        cast(stop_name as varchar)  as stop_name,
        cast(stop_lat as double)    as stop_lat,
        cast(stop_lon as double)    as stop_lon
    from source
    where stop_id is not null
)

select * from cleaned
