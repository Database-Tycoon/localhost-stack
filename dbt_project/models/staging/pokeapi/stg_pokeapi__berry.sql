-- Auto-generated staging model for berry
-- Source: raw_pokeapi.berry

with source as (
    select * from {{ source('pokeapi', 'berry') }}
),

cleaned as (
    select
        name,
        url
    from source
)

select * from cleaned
