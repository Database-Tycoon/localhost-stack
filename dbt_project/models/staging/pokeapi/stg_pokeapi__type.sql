-- Auto-generated staging model for type
-- Source: raw_pokeapi.type

with source as (
    select * from {{ source('pokeapi', 'type') }}
),

cleaned as (
    select
        name,
        url
    from source
)

select * from cleaned
