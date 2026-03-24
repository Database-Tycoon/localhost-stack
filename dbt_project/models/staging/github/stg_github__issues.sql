-- Staging model for GitHub issues.
-- Renames dlt double-underscore fields to clean business names, casts ISO 8601
-- timestamp strings to TIMESTAMP, derives boolean flags, and deduplicates on
-- the GitHub issue id keeping the most recently updated row.

with source as (
    select
        id,
        number,
        title,
        body,
        state,
        -- Rename dlt-flattened nested fields
        user__login                                    as author_login,
        user__id                                       as author_id,
        comments,
        reactions__total_count                         as reactions_total,
        labels,
        assignees,
        -- Cast ISO 8601 strings to TIMESTAMP
        try_cast(created_at as timestamp)              as created_at,
        try_cast(updated_at as timestamp)              as updated_at,
        try_cast(closed_at  as timestamp)              as closed_at,
        -- Retain raw struct so we can derive is_pull_request
        pull_request
    from {{ source('github', 'issues') }}
),

with_derived_columns as (
    select
        -- Surrogate key from the stable GitHub issue id
        md5(coalesce(cast(id as varchar), ''))         as issue_id,
        id,
        number,
        title,
        body,
        state,
        -- Boolean convenience flags
        (state = 'open')                               as is_open,
        (pull_request is not null)                     as is_pull_request,
        author_login,
        author_id,
        comments,
        reactions_total,
        labels,
        assignees,
        created_at,
        updated_at,
        closed_at
    from source
),

deduplicated as (
    select *
    from with_derived_columns
    qualify row_number() over (
        partition by id
        order by updated_at desc nulls last
    ) = 1
)

select * from deduplicated
