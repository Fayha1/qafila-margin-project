# Qafila gross margin

Submitted by: Fayha Almutairy — academy: @SDAIAAcademy

See [BRIEF.md](BRIEF.md) for the assignment and contract.

## Quick start

```bash
uv sync
uv run python tools/make_data.py
uv run python run.py
uv run python tools/check.py
```

To test a late supplier price correction:

```bash
uv run python tools/make_data.py --add-correction
uv run python run.py
uv run python tools/check.py
```

## Design

SQLite/CSV → Python ingestion → DuckDB `raw` → dbt staging → dbt silver/quality → dbt gold → PyIceberg tables.

| Model | Layer | Grain | Materialization |
|---|---|---|---|
| `stg_supplier_prices` | staging | Supplier-file row | dbt view |
| `stg_products` | staging | Product | dbt view |
| `stg_order_lines` | staging | Eligible order line | dbt view |
| `product_cost_history` | silver | SKU × changed cost start | dbt table → Iceberg |
| `weekly_margin` | gold | ISO week × city × category | dbt table → Iceberg |
| `price_quarantine` | quality | Rejected supplier-file row | dbt table → Iceberg |

**How the SCD2 history is built:** Only valid supplier costs are considered. Missing weekly quotes carry forward the most recent cost, unchanged costs do not create new versions, and for duplicate SKU/date combinations the lexicographically last filename takes precedence, including correction files. Each version ends at the next changed cost's start date, exclusive.

**How each order line finds its cost:** Join the trimmed SKU to the SCD2 version with `valid_from <= order_date` and (`valid_to > order_date` or null), where the order date is UTC converted to Riyadh time. Uncosted lines contribute revenue and line counts, but not costed revenue or costs.

## Data problems I found

| Problem | Where | Rows affected | Handling |
|---|---|---:|---|
| Unknown SKU | Supplier prices | 3 | Quarantine as `unknown_sku` |
| Zero, negative, or unparseable cost | Supplier prices | 4 | Quarantine as `invalid_cost` |
| Decimal commas and Arabic digits | Supplier prices | Not separately measured | Normalize before cost parsing |
| Column rename `unit_cost` → `cost_sar` | Supplier prices | Not separately measured | Standardize during ingestion |

On the tested dataset, `quality.price_quarantine` contained **7** rejected supplier price records: **3** unknown SKUs and **4** invalid costs. Counts for normalization cases were not independently measured.

## Tests

| Test | On | What it protects against |
|---|---|---|
| Not-null columns | Cost history and margin | Missing essential fields |
| Accepted quarantine reasons | Price quarantine | Unexpected rejection reason |
| Unique version key | Cost history | Duplicate cost versions |
| One current version | Cost history | Ambiguous latest cost |
| No overlapping periods | Cost history | Ambiguous point-in-time joins |
| Positive costs | Cost history | Invalid costs entering margin |
| Unique weekly key | Weekly margin | Duplicate summary rows |
| Margin arithmetic | Weekly margin | Inconsistent financial measures |

**Observed test results:** dbt completed with **14/14 tests passing**, and `uv run python tools/check.py` reported **22/22 checks passed**, both before and after the correction.

## Re-runs and the correction

The pipeline was run repeatedly against the generated dataset. Before the correction, the three output tables retained the same row counts across runs; the dbt tests and assignment checker continued to pass. Matching row counts alone do not prove full content-level idempotency.

A late supplier price correction was generated using `uv run python tools/make_data.py --add-correction`, which created `data/suppliers/prices_2026-W39_fix.csv`. The pipeline was then rerun and checked successfully.

| Output | Before correction | After correction |
|---|---:|---:|
| `silver.product_cost_history` rows | 633 | 637 |
| `gold.weekly_margin` rows | 165 | 165 |
| `quality.price_quarantine` rows | 7 | 7 |
| Total `margin_sar` (SAR) | 801,016.88 | 803,515.80 |

**Change in total margin:** **+2,498.92 SAR**.

The `gold.weekly_margin` Iceberg table contained **5 snapshots** after the correction. A previous snapshot (ID `2984445167896402947`) remained readable with **165 rows**; the current snapshot (ID `4816905562591656245`) also had **165 rows**. The two Arrow tables were **not identical** (`old.equals(new) == False`), and the total margin comparison above quantified the difference. This demonstrates access to historical table data after a correction.

Snapshot IDs and exact totals above are evidence from the local test run; they may differ when data is regenerated with another seed or the pipeline is run in a different environment.

## What I'd do next

At 100× scale, full rebuilds and wide historical joins would be the first bottlenecks. Introduce incremental processing, partition-aware reads, and Iceberg file compaction; for daily supplier files, strengthen late-arrival reconciliation and monitoring.

## AI assistance

ChatGPT was used to explain the assignment requirements, generate a preliminary implementation draft, assist with documentation, and guide the testing and validation process. The implementation was executed and checked against the provided assignment tests, including reruns, late correction handling, and Iceberg snapshot comparison.
