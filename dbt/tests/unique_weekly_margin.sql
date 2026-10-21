select iso_week, city, category from {{ ref('weekly_margin') }}
group by 1, 2, 3 having count(*) > 1
