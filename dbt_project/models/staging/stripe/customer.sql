-- Alias view: renames dlt's plural `customers` table to the singular `customer`
-- name expected by the dlt-dbt-stripe package's source('raw_data', 'customer') call.
select * from {{ source('stripe', 'customers') }}
