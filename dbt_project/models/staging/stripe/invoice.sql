-- Alias view: renames dlt's plural `invoices` table to the singular `invoice`
-- name expected by the dlt-dbt-stripe package's source('raw_data', 'invoice') call.
select * from {{ source('stripe', 'invoices') }}
