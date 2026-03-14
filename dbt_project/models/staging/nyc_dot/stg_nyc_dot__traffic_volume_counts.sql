with source as (
    select * from {{ source('nyc_dot', 'traffic_volume_counts') }}
),

cleaned as (
    select
        cast(segment_id as varchar)    as segment_id,
        cast(street as varchar)        as street,
        cast(from_street as varchar)   as from_street,
        cast(to_street as varchar)     as to_street,
        cast(direction as varchar)     as direction,
        cast(date as date)             as date,
        cast(volume as bigint)         as volume
    from source
    where segment_id is not null
      and date is not null
)

select * from cleaned
