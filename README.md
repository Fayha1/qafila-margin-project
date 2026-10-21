# Qafila gross margin

Submitted by: Fayha Almutairy 

See [BRIEF.md](BRIEF.md) for the assignment and contract.

```bash
uv sync
uv run python tools/make_data.py
uv run python run.py
uv run python tools/check.py
```

## Design

SQLite/CSV → Python ingestion → DuckDB `raw` → dbt staging → dbt silver/quality → dbt gold → PyIceberg tables.

| Model | Layer | Grain | Materialization |
|---|---|---|---|
| `stg_supplier_prices` | staging | supplier-file row | dbt view |
| `stg_products` | staging | product | dbt view |
| `stg_order_lines` | staging | eligible order line | dbt view |
| `product_cost_history` | silver | SKU × changed cost start | dbt table → Iceberg |
| `weekly_margin` | gold | ISO week × city × category | dbt table → Iceberg |
| `price_quarantine` | quality | rejected supplier-file row | dbt table → Iceberg |

**How the SCD2 history is built:** Only valid supplier costs are considered. Missing weekly quotes carry forward the most recent cost, unchanged costs do not create new versions, and for duplicate SKU/date combinations the lexicographically last filename takes precedence, including correction files. Each version ends at the next changed cost's start date, exclusive.

**How each order line finds its cost:** Join trimmed SKU to the SCD2 version with `valid_from <= order_date` and (`valid_to > order_date` or null), where the order date is UTC converted to Riyadh time. Uncosted lines contribute revenue and counts, but not costed revenue or costs.

## Data problems I found

These rules are implemented; **fill in actual counts after running on your own dataset**.

| Problem | Where | Rows affected | What I did |
|---|---|---|---|
| Unknown SKU | supplier prices | To measure | Quarantine as `unknown_sku` |
| Zero/negative/unparseable cost | supplier prices | To measure | Quarantine as `invalid_cost` |
| Decimal comma/Arabic digits | supplier prices | To measure | Normalize before parsing |
| Column rename `unit_cost` → `cost_sar` | supplier prices | To measure | Normalize in ingestion |

## Tests

| Test | On | What it protects against |
|---|---|---|
| Not-null columns | cost history and margin | Missing essential fields |
| Accepted quarantine reasons | price quarantine | Unexpected rejection reason |
| Unique version key | cost history | Duplicate cost versions |
| One current version | cost history | Ambiguous latest cost |
| No overlapping periods | cost history | Ambiguous point-in-time joins |
| Positive costs | cost history | Invalid costs entering margin |
| Unique weekly key | weekly margin | Duplicate summary rows |
| Margin arithmetic | weekly margin | Inconsistent financial measures |

## Re-runs and the correction

**Evidence pending execution.** Run the pipeline twice, compare the three Iceberg tables and record the snapshot ID; add `uv run python tools/make_data.py --add-correction`, run again, then capture the previous and current `gold.weekly_margin` snapshot IDs and a changed metric. No actual snapshot IDs or amounts are claimed here.

## What I'd do next

At 100× scale, full rebuilds and wide historical joins would be the first bottlenecks. Introduce incremental processing, partition-aware reads, and Iceberg file compaction; for daily supplier files, strengthen late-arrival reconciliation and monitoring.

## AI assistance


