-- Dimension table of NYC DOT bus lane corridors.
-- NOTE: The source data has no from_street or to_street columns;
-- the surrogate key is derived from street + segment_id + borough.

with lanes as (
    select
        street,
        segment_id,
        borough,
        lane_type,
        facility,
        direction,
        hours,
        days,
        lane_type1,
        lane_type2,
        open_dates,
        sbs_route1,
        sbs_route2
    from {{ ref('stg_nyc_dot__bus_lanes') }}
    qualify row_number() over (
        partition by street, segment_id, borough
        order by lane_type nulls last
    ) = 1
),

with_key as (
    select
        md5(
            coalesce(street, '')      || '|' ||
            coalesce(segment_id, '')  || '|' ||
            coalesce(borough, '')
        ) as bus_lane_key,
        street,
        segment_id,
        borough,
        lane_type,
        facility,
        direction,
        hours,
        days,
        lane_type1,
        lane_type2,
        open_dates,
        sbs_route1,
        sbs_route2
    from lanes
)

select * from with_key
