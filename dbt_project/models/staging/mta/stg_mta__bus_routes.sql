with source as (
    select * from {{ source('mta', 'gtfs_routes') }}
),

cleaned as (
    select
        cast(route_id as varchar)       as route_id,
        cast(route_short_name as varchar) as route_short_name,
        cast(route_long_name as varchar)  as route_long_name,
        cast(route_type as integer)       as route_type,
        cast(route_color as varchar)      as route_color,
        cast(route_text_color as varchar) as route_text_color
    from source
    where route_id is not null
)

select * from cleaned
