{{
    config(
        materialized='table'
    )
}}

-- Daily workspace editing activity derived from page-level timestamps.
-- Grain: one row per calendar day where at least one page was created or edited.
--
-- pages_edited:   count of pages whose last_edited_time falls on this day
-- pages_created:  count of pages whose created_time falls on this day
-- unique_editors: count of distinct users who last-edited a page on this day
--
-- NOTE: A page that was both created and edited on the same day contributes
-- to both pages_created and pages_edited. This is intentional — the two
-- metrics answer different questions about workspace activity.

with pages as (
    select * from {{ ref('stg_notion__pages') }}
),

-- Aggregate edits by day
edits_by_day as (
    select
        date_trunc('day', last_edited_time)    as activity_date,
        count(*)                               as pages_edited,
        count(distinct last_edited_by_id)      as unique_editors
    from pages
    where last_edited_time is not null
    group by all
),

-- Aggregate creations by day
creations_by_day as (
    select
        date_trunc('day', created_time)        as activity_date,
        count(*)                               as pages_created
    from pages
    where created_time is not null
    group by all
),

-- Full outer join so days with only creations or only edits are not lost
combined as (
    select
        coalesce(e.activity_date, c.activity_date)  as activity_date,
        coalesce(e.pages_edited, 0)                 as pages_edited,
        coalesce(c.pages_created, 0)                as pages_created,
        coalesce(e.unique_editors, 0)               as unique_editors
    from edits_by_day e
    full outer join creations_by_day c
        on e.activity_date = c.activity_date
)

select
    activity_date,
    pages_edited,
    pages_created,
    unique_editors,
    -- Running totals useful for growth charts
    sum(pages_created) over (
        order by activity_date
        rows between unbounded preceding and current row
    )                                               as cumulative_pages_created
from combined
order by activity_date
