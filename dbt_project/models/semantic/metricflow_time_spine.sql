-- MetricFlow required time spine table.
-- Must be named metricflow_time_spine and contain a date_day column.

select date_day
from {{ ref('dim_date') }}
