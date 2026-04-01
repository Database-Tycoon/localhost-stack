-- Staging model for Notion pages.
-- Casts ISO 8601 timestamp strings to TIMESTAMP.
-- Renames dlt double-underscore parent and user fields to clean column names.
-- properties JSON is deliberately kept raw — the structure varies per database
-- and should be flattened in purpose-built intermediate or mart models.

with source as (
    select * from {{ source('notion', 'pages') }}
),

renamed as (
    select
        id,
        url,
        -- Cast ISO 8601 strings to TIMESTAMP
        try_cast(created_time as timestamp)      as created_time,
        try_cast(last_edited_time as timestamp)  as last_edited_time,
        -- Rename dlt double-underscore foreign keys
        created_by__id                           as created_by_id,
        last_edited_by__id                       as last_edited_by_id,
        -- Rename dlt double-underscore parent fields
        parent__database_id                      as database_id,
        parent__type                             as parent_type,
        -- archived is already a boolean in the source
        archived,
        -- Keep full property values as JSON for downstream models
        properties
    from source
)

select * from renamed
