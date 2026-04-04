-- Auto-generated staging model for pokemon
-- Source: raw_pokeapi.pokemon

with source as (
    select * from {{ source('pokeapi', 'pokemon') }}
),

cleaned as (
    select
        name,
        url
    from source
)

select * from cleaned
