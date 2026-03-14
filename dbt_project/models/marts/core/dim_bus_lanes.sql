-- Dimension table of NYC DOT bus lane corridors.

with lanes as (
    select
        street,
        from_street,
        to_street,
        borough,
        lane_type
    from {{ ref('stg_nyc_dot__bus_lanes') }}
),

with_key as (
    select
        md5(
            coalesce(street, '') || '|' ||
            coalesce(from_street, '') || '|' ||
            coalesce(to_street, '') || '|' ||
            coalesce(borough, '')
        ) as bus_lane_key,
        street,
        from_street,
        to_street,
        borough,
        lane_type
    from lanes
)

select * from with_key
