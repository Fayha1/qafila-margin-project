with valid_prices as (
  select s.sku, s.valid_from, round(s.parsed_cost, 2) as unit_cost_sar,
         row_number() over (partition by s.sku, s.valid_from order by s.source_file desc) as rn
  from {{ ref('stg_supplier_prices') }} s
  join (select distinct sku from {{ ref('stg_products') }}) p on s.sku = p.sku
  where s.parsed_cost > 0 and s.valid_from is not null
), weekly as (
  select sku, valid_from, unit_cost_sar from valid_prices where rn = 1
), compared as (
  select *, lag(unit_cost_sar) over (partition by sku order by valid_from) as previous_cost
  from weekly
), changes as (
  select sku, valid_from, unit_cost_sar from compared
  where previous_cost is null or previous_cost <> unit_cost_sar
), history as (
  select *, lead(valid_from) over (partition by sku order by valid_from) as valid_to
  from changes
)
select sku, cast(unit_cost_sar as double) as unit_cost_sar, valid_from, valid_to,
       (valid_to is null) as is_current
from history
