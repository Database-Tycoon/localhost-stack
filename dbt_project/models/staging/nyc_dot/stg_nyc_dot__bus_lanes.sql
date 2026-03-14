with source as (
    select * from {{ source('nyc_dot', 'bus_lanes') }}
),

cleaned as (
    select
        cast(street as varchar)     as street,
        cast(segmentid as varchar)  as segment_id,
        cast(boro as varchar)       as borough,
        cast(facility as varchar)   as facility,
        cast(direction as varchar)  as direction,
        cast(hours as varchar)      as hours,
        cast(days as varchar)       as days,
        cast(lane_type as varchar)  as lane_type,
        cast(lane_type1 as varchar) as lane_type1,
        cast(lane_type2 as varchar) as lane_type2,
        cast(open_dates as varchar) as open_dates,
        cast(lane_width as varchar) as lane_width,
        cast(lane_color as varchar) as lane_color,
        cast(sbs_route1 as varchar) as sbs_route1,
        cast(sbs_route2 as varchar) as sbs_route2,
        cast(bltrafdir as varchar)  as bltrafdir,
        cast(rw_type as varchar)    as rw_type,
        cast(streetwidt as varchar) as street_width,
        try_cast(shape_leng as double) as shape_length
    from source
    where street is not null
)

select * from cleaned
