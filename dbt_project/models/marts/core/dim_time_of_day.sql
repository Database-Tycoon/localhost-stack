-- Dimension table with one row per hour of day (0-23).
-- Defines named time periods used consistently across all models.

with hours as (
    select unnest(generate_series(0, 23)) as hour_of_day
),

with_periods as (
    select
        hour_of_day,
        case
            when hour_of_day between 7 and 9   then 'AM Peak'
            when hour_of_day between 10 and 15  then 'Midday'
            when hour_of_day between 16 and 19  then 'PM Peak'
            when hour_of_day between 20 and 22  then 'Evening'
            else                                     'Overnight'
        end as time_period,
        case
            when hour_of_day between 7 and 9   then 1
            when hour_of_day between 10 and 15  then 2
            when hour_of_day between 16 and 19  then 3
            when hour_of_day between 20 and 22  then 4
            else                                     5
        end as time_period_sort_order,
        case
            when hour_of_day between 7 and 19  then true
            else                                     false
        end as is_peak_hour,
        lpad(cast(hour_of_day as varchar), 2, '0') || ':00' as hour_label,
        case
            when hour_of_day = 0  then '12:00 AM'
            when hour_of_day < 12 then cast(hour_of_day as varchar) || ':00 AM'
            when hour_of_day = 12 then '12:00 PM'
            else cast(hour_of_day - 12 as varchar) || ':00 PM'
        end as hour_label_ampm
    from hours
)

select * from with_periods
