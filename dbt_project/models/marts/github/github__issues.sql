{{
  config(
    materialized='table'
  )
}}

select
    issue_id,
    id,
    number,
    title,
    body,
    state,
    is_open,
    is_pull_request,
    author_login,
    author_id,
    comments,
    reactions_total,
    labels,
    assignees,
    created_at,
    updated_at,
    closed_at
from {{ ref('stg_github__issues') }}
