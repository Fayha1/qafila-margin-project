with costed as (
  select l.*, h.unit_cost_sar,
         round(l.quantity * h.unit_cost_sar, 2) as line_cost_sar
  from {{ ref('stg_order_lines') }} l
  left join {{ ref('product_cost_history') }} h on l.sku = h.sku
    and l.order_date >= h.valid_from
    and (h.valid_to is null or l.order_date < h.valid_to)
)
select cast(weekofyear(order_date) as integer) as iso_week, city, category,
       cast(count(*) as integer) as lines,
       cast(round(sum(revenue_sar), 2) as double) as revenue_sar,
       cast(round(sum(case when unit_cost_sar is not null then revenue_sar else 0 end), 2) as double) as costed_revenue_sar,
       cast(round(sum(coalesce(line_cost_sar, 0)), 2) as double) as cost_sar,
       cast(round(sum(case when unit_cost_sar is not null then revenue_sar else 0 end) -
                  sum(coalesce(line_cost_sar, 0)), 2) as double) as margin_sar,
       cast(sum(case when unit_cost_sar is null then 1 else 0 end) as integer) as uncosted_lines
from costed
group by 1, 2, 3
