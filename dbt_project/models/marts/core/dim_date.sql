-- Generated calendar dimension covering 2022-2026.
-- Used as the time spine for MetricFlow and for date enrichment across all fact tables.

with date_spine as (
    select
        unnest(
            generate_series(
                date '2022-01-01',
                date '2026-12-31',
                interval '1 day'
            )
        )::date as date_day
),

enriched as (
    select
        date_day,
        -- Keys
        cast(strftime(date_day, '%Y%m%d') as integer) as date_key,

        -- Year / quarter / month
        year(date_day)                                              as year_number,
        quarter(date_day)                                           as quarter_number,
        'Q' || quarter(date_day)                                    as quarter_label,
        month(date_day)                                             as month_number,
        strftime(date_day, '%B')                                    as month_name,
        strftime(date_day, '%b')                                    as month_short_name,
        cast(strftime(date_day, '%Y%m') as integer)                 as year_month_key,

        -- Week
        week(date_day)                                              as week_of_year,
        yearweek(date_day)                                          as year_week_key,
        date_trunc('week', date_day)::date                          as week_start_date,

        -- Day
        dayofmonth(date_day)                                        as day_of_month,
        -- DuckDB dayofweek: 0=Sunday, 1=Monday ... 6=Saturday
        dayofweek(date_day)                                         as day_of_week_number,
        strftime(date_day, '%A')                                    as day_of_week_name,
        strftime(date_day, '%a')                                    as day_of_week_short,
        dayofyear(date_day)                                         as day_of_year,

        -- Flags
        dayofweek(date_day) in (0, 6)                              as is_weekend,
        dayofweek(date_day) not in (0, 6)                          as is_weekday,

        -- Season (meteorological)
        case month(date_day)
            when 12 then 'Winter'
            when 1  then 'Winter'
            when 2  then 'Winter'
            when 3  then 'Spring'
            when 4  then 'Spring'
            when 5  then 'Spring'
            when 6  then 'Summer'
            when 7  then 'Summer'
            when 8  then 'Summer'
            when 9  then 'Fall'
            when 10 then 'Fall'
            when 11 then 'Fall'
        end as season,

        -- Fiscal year (NYC fiscal year starts July 1)
        case
            when month(date_day) >= 7 then year(date_day) + 1
            else year(date_day)
        end as fiscal_year,

        case
            when month(date_day) >= 7 then (month(date_day) - 6)
            else (month(date_day) + 6)
        end as fiscal_month_number
    from date_spine
)

select * from enriched
