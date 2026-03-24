{{
    config(
        materialized='table'
    )
}}

-- Enriched page records joining pages → databases (for database name) and
-- pages → users twice (creator and last editor).
-- Grain: one row per Notion page.
-- Non-database pages (parent_type != 'database_id') are included with null
-- database fields so that standalone workspace pages are not silently dropped.

with pages as (
    select * from {{ ref('stg_notion__pages') }}
),

databases as (
    select
        id              as database_id,
        title           as database_name,
        url             as database_url
    from {{ ref('stg_notion__databases') }}
),

users as (
    select
        id,
        name,
        email
    from {{ ref('stg_notion__users') }}
),

enriched as (
    select
        -- Page identity
        p.id                                        as page_id,
        p.url                                       as page_url,

        -- Parent database context
        p.database_id,
        p.parent_type,
        d.database_name,
        d.database_url,

        -- Authorship
        p.created_by_id,
        creator.name                                as created_by_name,
        creator.email                               as created_by_email,

        -- Last edit
        p.last_edited_by_id,
        editor.name                                 as last_edited_by_name,
        editor.email                                as last_edited_by_email,

        -- Timestamps
        p.created_time,
        p.last_edited_time,

        -- Derived time columns
        date_trunc('day', p.created_time)           as created_date,
        date_trunc('day', p.last_edited_time)       as last_edited_date,
        date_diff(
            'day', p.created_time, p.last_edited_time
        )                                           as days_since_creation,

        -- Status
        p.archived,

        -- Raw JSON for downstream use
        p.properties
    from pages p
    left join databases d
        on p.database_id = d.database_id
    left join users creator
        on p.created_by_id = creator.id
    left join users editor
        on p.last_edited_by_id = editor.id
)

select * from enriched
