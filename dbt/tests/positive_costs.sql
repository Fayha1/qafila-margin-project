select * from {{ ref('product_cost_history') }} where unit_cost_sar <= 0
