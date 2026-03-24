-- Staging model for Notion workspace users.
-- Renames dlt double-underscore fields to clean column names.
-- Adds is_person boolean to distinguish human members from integration bots.

with source as (
    select * from {{ source('notion', 'users') }}
),

renamed as (
    select
        id,
        type,
        name,
        avatar_url,
        -- dlt flattens person.email → person__email
        person__email                    as email,
        -- convenience flag: true for workspace members, false for bots
        (type = 'person')                as is_person
    from source
)

select * from renamed
