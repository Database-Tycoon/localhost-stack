-- Staging model for Slack messages.
--
-- Key casting considerations:
--   - ts is a STRING representing a float Unix epoch (e.g. "1609459200.000100").
--     try_cast to DOUBLE before passing to to_timestamp() so that malformed
--     rows produce NULL rather than a query error.
--   - thread_ts follows the same encoding but is nullable.
--
-- Derived flags:
--   - is_thread_reply: message is a reply inside a thread (thread_ts present
--     and differs from ts, meaning this is not the thread root itself).
--   - is_thread_root: message has spawned at least one reply.
--   - has_reactions: the reactions JSON array is non-null and non-empty.
--   - is_user_message: excludes known system subtypes so aggregations count
--     only substantive human-authored posts.

with source as (
    select * from {{ source('slack', 'messages') }}
),

cast_timestamps as (
    select
        -- Cast the string float epoch to TIMESTAMP; nulls propagate on failure
        to_timestamp(try_cast(ts as double))            as message_ts,
        -- Preserve the raw ts string for use as a natural key in joins
        ts                                              as message_ts_raw,
        channel                                         as channel_id,
        -- user is null for some bot-posted messages
        "user"                                          as user_id,
        text,
        type                                            as message_type,
        subtype,
        -- thread_ts is null for standalone messages; cast same way as ts
        to_timestamp(
            try_cast(thread_ts as double)
        )                                               as thread_ts,
        try_cast(reply_count as integer)                as reply_count,
        reactions,
        files,
        attachments,
        blocks
    from source
),

with_flags as (
    select
        message_ts,
        message_ts_raw,
        channel_id,
        user_id,
        text,
        message_type,
        subtype,
        thread_ts,
        reply_count,

        -- A thread reply has a thread_ts that differs from its own ts.
        -- Thread root messages also carry their own ts in thread_ts, so
        -- equality means this IS the root, not a reply.
        (
            thread_ts is not null
            and thread_ts != message_ts
        )                                               as is_thread_reply,

        -- A thread root is any message that has received at least one reply
        coalesce(reply_count, 0) > 0                   as is_thread_root,

        -- reactions is a JSON array; non-null and non-empty means at least one reaction
        (
            reactions is not null
            and try_cast(json_array_length(reactions) as integer) > 0
        )                                               as has_reactions,

        -- Exclude system-generated subtypes from user activity counts.
        -- NULL subtype = normal user message.
        subtype is null
        or subtype not in (
            'bot_message',
            'channel_join',
            'channel_leave',
            'channel_archive',
            'channel_unarchive',
            'channel_name',
            'channel_purpose',
            'channel_topic',
            'file_share',
            'me_message',
            'thread_broadcast'
        )                                               as is_user_message,

        files,
        attachments,
        blocks
    from cast_timestamps
)

select * from with_flags
