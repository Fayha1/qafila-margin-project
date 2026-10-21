select i.order_id, i.line_no, p.sku, p.category, s.city,
       cast(cast(o.created_at as timestamp) + interval '3 hours' as date) as order_date,
       i.quantity, round(i.quantity * i.unit_price - i.discount, 2) as revenue_sar
from {{ source('raw', 'order_items') }} i
join {{ source('raw', 'orders') }} o on o.order_id = i.order_id
join {{ ref('stg_products') }} p on p.product_id = i.product_id
join {{ source('raw', 'stores') }} s on s.store_id = o.store_id
where o.status = 'delivered' and i.quantity > 0
  and cast(cast(o.created_at as timestamp) + interval '3 hours' as date) >= date '2026-08-31'
