-- Bus routes dimension with borough derivation from route_id prefix.

with routes as (
    select * from {{ ref('stg_mta__bus_routes') }}
),

with_borough as (
    select
        md5(route_id) as route_key,
        route_id,
        route_short_name,
        route_long_name,
        route_type,
        route_color,
        route_text_color,
        -- Derive borough from route_id prefix convention
        case
            when left(upper(route_id), 1) = 'Q'  then 'Queens'
            when left(upper(route_id), 2) = 'BX' then 'Bronx'
            when left(upper(route_id), 2) = 'BK' then 'Brooklyn'
            when left(upper(route_id), 1) = 'B'  then 'Brooklyn'
            when left(upper(route_id), 1) = 'M'  then 'Manhattan'
            when left(upper(route_id), 1) = 'S'  then 'Staten Island'
            else 'Unknown'
        end as borough
    from routes
)

select * from with_borough
