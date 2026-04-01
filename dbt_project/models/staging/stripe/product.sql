-- Alias view: renames dlt's plural `products` table to the singular `product`
-- name expected by the dlt-dbt-stripe package's source('raw_data', 'product') call.
select * from {{ source('stripe', 'products') }}
