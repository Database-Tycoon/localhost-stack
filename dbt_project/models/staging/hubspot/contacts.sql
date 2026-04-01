-- Passthrough view that exposes raw.raw_hubspot.contacts in the hubspot_staging schema.
-- Required because the dlt-dbt-hubspot package's source('raw_data', 'contacts') resolves
-- to the schema set by source_dataset_name, which must be a writable dbt schema
-- (the raw database is read-only).
select * from {{ source('hubspot', 'contacts') }}
