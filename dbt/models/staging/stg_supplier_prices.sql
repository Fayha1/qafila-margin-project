select source_file, trim(sku) as sku, try_cast(valid_from as date) as valid_from,
       raw_cost,
       try_cast(replace(translate(trim(raw_cost), '٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬',
          '01234567890123456789.,'), ',', '.') as double) as parsed_cost
from {{ source('raw', 'supplier_prices') }}
