{{ config(materialized='table') }}

with s as (
  select
    customer_id,
    session_id,
    min(event_ts) as session_start,
    max(event_ts) as session_end,
    count(*) as events,
    sum(case when event_type='checkout' then 1 else 0 end) as checkouts
  from {{ ref('stg_clicks') }}
  group by 1,2
)

select *,
  datediff('minute', session_start, session_end) as session_minutes,
  case when checkouts > 0 then 1 else 0 end as converted
from s