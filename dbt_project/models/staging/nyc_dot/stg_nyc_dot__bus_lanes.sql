with source as (
    select * from {{ source('nyc_dot', 'bus_lanes') }}
),

cleaned as (
    select
        cast(street as varchar)       as street,
        cast(from_street as varchar)  as from_street,
        cast(to_street as varchar)    as to_street,
        cast(borough as varchar)      as borough,
        cast(lane_type as varchar)    as lane_type
    from source
    where street is not null
)

select * from cleaned
