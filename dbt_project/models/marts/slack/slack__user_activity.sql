-- Weekly user activity mart.
-- Grain: user × ISO week (Monday of the week containing message_ts).
-- Only is_user_message = true rows are counted.
-- Joined to users to carry profile attributes directly into the mart,
-- enabling self-service filtering by is_bot, is_active, username, etc.

with messages as (
    select * from {{ ref('stg_slack__messages') }}
    where is_user_message = true
),

users as (
    select * from {{ ref('stg_slack__users') }}
),

weekly_counts as (
    select
        user_id,
        -- ISO week: truncate to the Monday of each week
        date_trunc('week', message_ts)::date        as activity_week,
        count(*)                                    as messages_sent,
        count(distinct channel_id)                  as channels_active_in,
        count(*) filter (where is_thread_root)      as threads_started,
        count(*) filter (where is_thread_reply)     as thread_replies_sent,
        count(*) filter (where has_reactions)       as messages_with_reactions
    from messages
    group by all
),

joined as (
    select
        -- Surrogate key
        md5(
            coalesce(w.user_id, '') || '|' ||
            coalesce(cast(w.activity_week as varchar), '')
        )                                           as user_activity_key,

        -- User dimension attributes
        w.user_id,
        u.username,
        u.real_name,
        u.is_bot,
        u.is_active,

        -- Grain
        w.activity_week,

        -- Measures
        w.messages_sent,
        w.channels_active_in,
        w.threads_started,
        w.thread_replies_sent,
        w.messages_with_reactions
    from weekly_counts w
    left join users u
        on w.user_id = u.user_id
)

select * from joined
