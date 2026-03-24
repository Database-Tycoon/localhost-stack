{{
  config(
    materialized='table'
  )
}}

-- Daily commit activity aggregated from staged commits
with daily_commits as (
    select
        date_trunc('day', committed_at)  as activity_date,
        count(*)                          as commit_count,
        sum(additions)                    as lines_added,
        sum(deletions)                    as lines_deleted
    from {{ ref('stg_github__commits') }}
    where committed_at is not null
    group by date_trunc('day', committed_at)
),

-- Separate aggregations by event date to avoid double-counting opens vs merges
merged_by_day as (
    select
        date_trunc('day', merged_at)      as activity_date,
        count(*)                          as prs_merged
    from {{ ref('stg_github__pull_requests') }}
    where merged_at is not null
    group by date_trunc('day', merged_at)
),

opened_by_day as (
    select
        date_trunc('day', created_at)     as activity_date,
        count(*)                          as prs_opened
    from {{ ref('stg_github__pull_requests') }}
    where created_at is not null
    group by date_trunc('day', created_at)
),

-- Union all active dates from every source so no day is dropped
all_dates as (
    select activity_date from daily_commits
    union
    select activity_date from merged_by_day
    union
    select activity_date from opened_by_day
)

select
    d.activity_date,
    coalesce(c.commit_count,  0)          as commit_count,
    coalesce(c.lines_added,   0)          as lines_added,
    coalesce(c.lines_deleted, 0)          as lines_deleted,
    coalesce(c.lines_added,   0)
        - coalesce(c.lines_deleted, 0)    as net_lines,
    coalesce(m.prs_merged,    0)          as prs_merged,
    coalesce(o.prs_opened,    0)          as prs_opened
from all_dates d
left join daily_commits  c on c.activity_date = d.activity_date
left join merged_by_day  m on m.activity_date = d.activity_date
left join opened_by_day  o on o.activity_date = d.activity_date
order by d.activity_date
