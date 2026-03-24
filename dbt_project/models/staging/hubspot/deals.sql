-- Passthrough view that exposes raw.raw_hubspot.deals in the hubspot_staging schema.
-- Required because the dlt-dbt-hubspot package's source('raw_data', 'deals') resolves
-- to the schema set by source_dataset_name, which must be a writable dbt schema.
select * from {{ source('hubspot', 'deals') }}
