-- Passthrough view for dlt's _dlt_loads tracking table.
-- The dlt-dbt-stripe package reads source('raw_data', '_dlt_loads') to find
-- completed load IDs. This view exposes it in the stripe_staging schema.
select * from {{ source('stripe', '_dlt_loads') }}
