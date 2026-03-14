-- Dimension table of distinct bus segments from the MTA speed data.

with segments as (
    select distinct
        segment_id,
        segment_start,
        segment_end,
        route_id
    from {{ ref('stg_mta_bus_speeds__segment_speeds') }}
),

with_key as (
    select
        md5(coalesce(cast(segment_id as varchar), '') || '|' ||
            coalesce(cast(route_id as varchar), ''))    as segment_key,
        segment_id,
        route_id,
        segment_start,
        segment_end
    from segments
    qualify row_number() over (partition by segment_id order by route_id) = 1
)

select * from with_key
