-- Alias view: renames dlt's plural `subscriptions` table to the singular `subscription`
-- name expected by the dlt-dbt-stripe package's source('raw_data', 'subscription') call.
select * from {{ source('stripe', 'subscriptions') }}
