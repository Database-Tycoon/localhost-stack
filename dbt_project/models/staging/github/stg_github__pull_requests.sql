-- Staging model for GitHub pull requests.
-- Renames dlt double-underscore fields, casts timestamps, derives boolean flags,
-- computes cycle_time_hours, and deduplicates on the GitHub PR id keeping the
-- most recently updated row.

with source as (
    select
        id,
        number,
        title,
        state,
        -- Rename dlt-flattened nested fields
        user__login                                                as author_login,
        draft                                                      as is_draft,
        head__ref                                                  as head_ref,
        base__ref                                                  as base_ref,
        additions,
        deletions,
        changed_files,
        commits,
        review_comments,
        requested_reviewers,
        -- Cast ISO 8601 strings to TIMESTAMP
        try_cast(created_at as timestamp)                          as created_at,
        try_cast(updated_at as timestamp)                          as updated_at,
        try_cast(merged_at  as timestamp)                          as merged_at,
        try_cast(closed_at  as timestamp)                          as closed_at
    from {{ source('github', 'pull_requests') }}
),

with_derived_columns as (
    select
        -- Surrogate key from the stable GitHub PR id
        md5(coalesce(cast(id as varchar), ''))                     as pull_request_id,
        id,
        number,
        title,
        state,
        -- Boolean flags
        (merged_at is not null)                                    as is_merged,
        coalesce(is_draft, false)                                  as is_draft,
        author_login,
        head_ref,
        base_ref,
        additions,
        deletions,
        changed_files,
        commits,
        review_comments,
        -- Cycle time: hours from open to the first terminal event (merge or close)
        -- Null when the PR is still open
        date_diff(
            'hour',
            created_at,
            coalesce(merged_at, closed_at)
        )                                                          as cycle_time_hours,
        requested_reviewers,
        created_at,
        updated_at,
        merged_at,
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
