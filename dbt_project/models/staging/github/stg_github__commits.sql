-- Staging model for GitHub commits.
-- Flattens dlt double-underscore nested fields into clean names, casts the
-- author date to TIMESTAMP as committed_at, and deduplicates on SHA keeping
-- the single canonical row per commit.

with source as (
    select
        sha,
        -- Rename dlt-flattened nested fields
        commit__message                                    as message,
        commit__author__name                               as author_name,
        commit__author__email                              as author_email,
        author__login                                      as author_login,
        committer__login                                   as committer_login,
        -- committed_at = when the commit was originally authored
        try_cast(commit__author__date    as timestamp)     as committed_at,
        -- committer_date = when the commit was applied (rebase / merge)
        try_cast(commit__committer__date as timestamp)     as committer_date,
        stats__additions                                   as additions,
        stats__deletions                                   as deletions,
        stats__total                                       as total_changes
    from {{ source('github', 'commits') }}
),

with_surrogate_key as (
    select
        -- Surrogate key from the commit SHA
        md5(coalesce(cast(sha as varchar), ''))            as commit_id,
        sha,
        message,
        author_name,
        author_email,
        author_login,
        committer_login,
        committed_at,
        committer_date,
        additions,
        deletions,
        total_changes
    from source
),

deduplicated as (
    select *
    from with_surrogate_key
    qualify row_number() over (
        partition by sha
        order by committed_at desc nulls last
    ) = 1
)

select * from deduplicated
