-- Staging model for Slack channels.
-- Casts epoch integer timestamps to TIMESTAMP, aliases dlt nested-column names
-- (topic__value, purpose__value) to clean business names, and derives is_active.

with source as (
    select * from {{ source('slack', 'channels') }}
),

renamed as (
    select
        id                                  as channel_id,
        name                                as channel_name,
        is_private,
        is_archived,
        -- Derived flag: a channel is active when it has not been archived
        not is_archived                     as is_active,
        -- dlt snake-cases nested Slack JSON: topic.value → topic__value
        topic__value                        as topic,
        purpose__value                      as purpose,
        num_members,
        -- Slack stores channel creation/update times as Unix epoch integers
        to_timestamp(created)               as created_at,
        to_timestamp(updated)               as updated_at
    from source
)

select * from renamed
