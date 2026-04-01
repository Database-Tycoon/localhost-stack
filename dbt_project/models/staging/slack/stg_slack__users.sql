-- Staging model for Slack workspace users.
-- Flattens dlt nested profile columns (profile__email, profile__title),
-- aliases id and name to unambiguous business names, and derives is_active
-- to identify human accounts that have not been deactivated.

with source as (
    select * from {{ source('slack', 'users') }}
),

renamed as (
    select
        id                                  as user_id,
        name                                as username,
        real_name,
        display_name,
        -- dlt snake-cases nested Slack JSON: profile.email → profile__email
        profile__email                      as email,
        profile__title                      as title,
        profile__image_72                   as profile_image_url,
        tz,
        is_bot,
        is_admin,
        is_owner,
        deleted                             as is_deleted,
        -- Active = not deactivated and not a bot integration
        (not deleted and not is_bot)        as is_active
    from source
)

select * from renamed
