-- Staging model for Notion databases.
-- Casts ISO 8601 timestamp strings to TIMESTAMP.
-- Extracts the plain-text title from Notion's rich-text JSON array format.
-- Renames dlt double-underscore fields to clean foreign key names.
-- The properties column (database schema definition) is kept as raw JSON.

with source as (
    select * from {{ source('notion', 'databases') }}
),

renamed as (
    select
        id,
        url,
        -- Notion stores title as a rich-text JSON array: [{plain_text: "My DB", ...}, ...]
        -- Extract the first element's plain_text; fall back to null if malformed.
        try_cast(
            json_extract_string(title, '$[0].plain_text')
        as varchar)                                                as title,
        -- Keep raw title and description JSON for downstream use if needed
        title                                                      as title_raw,
        description                                                as description_raw,
        -- Cast ISO 8601 strings to TIMESTAMP
        try_cast(created_time as timestamp)                        as created_time,
        try_cast(last_edited_time as timestamp)                    as last_edited_time,
        -- Rename dlt double-underscore foreign keys
        created_by__id                                             as created_by_id,
        last_edited_by__id                                         as last_edited_by_id,
        -- Keep full property schema as JSON for reference
        properties
    from source
)

select * from renamed
