-- Fuzzy match between bus speed segments and bus lane corridor inventory.
-- Matching is performed on segment_start / segment_end vs street names in the
-- bus lanes table using case-insensitive string containment as a proxy for
-- geo-proximity when spatial data is unavailable.

with segments as (
    select distinct
        segment_id,
        route_id,
        segment_start,
        segment_end
    from {{ ref('stg_mta_bus_speeds__segment_speeds') }}
),

bus_lanes as (
    select
        street,
        from_street,
        to_street,
        borough,
        lane_type
    from {{ ref('stg_nyc_dot__bus_lanes') }}
),

matched as (
    select
        s.segment_id,
        s.route_id,
        s.segment_start,
        s.segment_end,
        bl.street       as lane_street,
        bl.from_street  as lane_from_street,
        bl.to_street    as lane_to_street,
        bl.borough      as lane_borough,
        bl.lane_type,
        true            as has_bus_lane
    from segments s
    inner join bus_lanes bl
        on (
            lower(s.segment_start) like '%' || lower(bl.street) || '%'
            or lower(s.segment_end) like '%' || lower(bl.street) || '%'
            or lower(bl.street) like '%' || lower(s.segment_start) || '%'
            or lower(bl.street) like '%' || lower(s.segment_end) || '%'
        )
    qualify row_number() over (
        partition by s.segment_id
        order by bl.street
    ) = 1
),

all_segments as (
    select
        s.segment_id,
        s.route_id,
        s.segment_start,
        s.segment_end,
        m.lane_street,
        m.lane_from_street,
        m.lane_to_street,
        m.lane_borough,
        m.lane_type,
        coalesce(m.has_bus_lane, false) as has_bus_lane
    from segments s
    left join matched m using (segment_id)
)

select * from all_segments
