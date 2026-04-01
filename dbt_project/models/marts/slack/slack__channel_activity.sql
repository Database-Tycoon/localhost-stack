-- Daily channel activity mart.
-- Grain: channel × calendar day (date_trunc('day', message_ts)).
-- Only is_user_message = true rows are counted so system events (joins, leaves,
-- archive notices) are excluded from every metric.
-- Joined to channels to carry channel metadata directly into the mart.

with messages as (
    select * from {{ ref('stg_slack__messages') }}
    where is_user_message = true
),

channels as (
    select * from {{ ref('stg_slack__channels') }}
),

daily_counts as (
    select
        channel_id,
        date_trunc('day', message_ts)::date     as activity_date,
        count(*)                                as message_count,
        count(distinct user_id)                 as unique_users,
        count(*) filter (where is_thread_reply) as thread_replies,
        count(*) filter (where is_thread_root)  as threads_started,
        count(*) filter (where has_reactions)   as messages_with_reactions
    from messages
    group by all
),

joined as (
    select
        -- Surrogate key
        md5(
            coalesce(d.channel_id, '') || '|' ||
            coalesce(cast(d.activity_date as varchar), '')
        )                                       as channel_activity_key,

        -- Channel dimension attributes
        d.channel_id,
        c.channel_name,
        c.is_private,
        c.is_active,

        -- Grain
        d.activity_date,

        -- Measures
        d.message_count,
        d.unique_users,
        d.thread_replies,
        d.threads_started,
        d.messages_with_reactions
    from daily_counts d
    left join channels c
        on d.channel_id = c.channel_id
)

select * from joined
