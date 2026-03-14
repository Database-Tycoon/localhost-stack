with source as (
    select * from {{ source('nyc_dot', 'traffic_volume_counts') }}
),

cleaned as (
    select
        cast(segmentid as varchar)  as segment_id,
        cast(requestid as varchar)  as request_id,
        cast(street as varchar)     as street,
        cast(fromst as varchar)     as from_street,
        cast(tost as varchar)       as to_street,
        cast(direction as varchar)  as direction,
        cast(boro as varchar)       as borough,
        cast(wktgeom as varchar)    as wkt_geom,
        -- Construct a date from the abbreviated year, month, and day columns
        make_date(
            try_cast(yr as integer),
            try_cast(m as integer),
            try_cast(d as integer)
        )                           as date,
        try_cast(hh as integer)     as hour,
        try_cast(mm as integer)     as minute,
        try_cast(vol as bigint)     as volume
    from source
    where segmentid is not null
      and yr is not null
      and m is not null
      and d is not null
)

select * from cleaned
