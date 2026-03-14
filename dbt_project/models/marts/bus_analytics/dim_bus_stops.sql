-- Bus stops dimension with surrogate key.

with stops as (
    select * from {{ ref('stg_mta__bus_stops') }}
),

with_key as (
    select
        md5(stop_id)    as stop_key,
        stop_id,
        stop_name,
        stop_lat,
        stop_lon
    from stops
)

select * from with_key
