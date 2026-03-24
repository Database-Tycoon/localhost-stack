-- Passthrough view for dlt's _dlt_loads tracking table (HubSpot pipeline).
-- The dlt-dbt-hubspot package reads source('raw_data', '_dlt_loads') to find
-- completed load IDs. This view exposes it in the hubspot_staging schema,
-- which is where source_dataset_name: "raw_hubspot" resolves when you pass
-- --vars '{"source_dataset_name": "hubspot_staging"}' at build time.
--
-- NOTE: run hubspot package with:
--   dbt build --select hubspot+ \
--     --vars '{"source_dataset_name": "hubspot_staging", "destination_dataset_name": "hubspot_staging"}'
select * from {{ source('hubspot', '_dlt_loads') }}
