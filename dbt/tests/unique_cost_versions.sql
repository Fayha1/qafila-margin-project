select sku, valid_from from {{ ref('product_cost_history') }}
group by 1, 2 having count(*) > 1
