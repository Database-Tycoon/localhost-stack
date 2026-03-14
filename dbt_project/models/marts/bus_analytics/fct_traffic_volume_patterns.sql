-- Traffic volume patterns by segment, time period, and date.
-- Grain: segment_id × date × time_period

with hourly as (
    select * from {{ ref('int_traffic_volume_hourly') }}
),

time_of_day as (
    select hour_of_day, time_period
    from {{ ref('dim_time_of_day') }}
),

with_period as (
    select
        h.segment_id,
        h.street,
        h.from_street,
        h.to_street,
        h.direction,
        h.date,
        t.time_period,
        sum(h.hourly_volume)    as period_volume,
        avg(h.hourly_volume)    as avg_hourly_volume,
        h.daily_volume
    from hourly h
    inner join time_of_day t using (hour_of_day)
    group by
        h.segment_id,
        h.street,
        h.from_street,
        h.to_street,
        h.direction,
        h.date,
        t.time_period,
        h.daily_volume
),

with_key as (
    select
        md5(
            coalesce(cast(segment_id as varchar), '') || '|' ||
            coalesce(street, '') || '|' ||
            coalesce(cast(date as varchar), '') || '|' ||
            coalesce(time_period, '') || '|' ||
            coalesce(direction, '')
        ) as traffic_volume_key,
        *
    from with_period
)

select * from with_key
