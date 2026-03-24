-- Passthrough view that exposes raw.raw_hubspot.companies in the hubspot_staging schema.
-- Required because the dlt-dbt-hubspot package's source('raw_data', 'companies') resolves
-- to the schema set by source_dataset_name, which must be a writable dbt schema.
select * from {{ source('hubspot', 'companies') }}
