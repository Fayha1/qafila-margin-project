select a.sku from {{ ref('product_cost_history') }} a
join {{ ref('product_cost_history') }} b on a.sku = b.sku
and a.valid_from < b.valid_from
and (a.valid_to is null or a.valid_to > b.valid_from)
