{{ config(materialized='view') }}
select
  event_id,
  customer_id,
  session_id,
  event_type,
  page,
  utm_campaign,
  device,
  geo_city,
  event_ts,
  dt
from {{ source('staging_raw','raw_clicks') }}