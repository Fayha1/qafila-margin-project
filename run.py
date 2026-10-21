"""Qafila gross margin pipeline: raw files -> DuckDB -> dbt -> Iceberg.

    uv run python run.py --data-dir data --warehouse warehouse

Must work on an empty warehouse folder, and must be safe to run again on the same one.
The grader runs it on a dataset you haven't seen, so never hard-code file names, row counts or SKUs.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import duckdb
from pyiceberg.catalog.sql import SqlCatalog

DBT_DIR = Path(__file__).resolve().parent / "dbt"


def get_catalog(warehouse: Path) -> SqlCatalog:
    """The Iceberg catalog the grader reads. Don't change the name, the URI or the warehouse."""
    warehouse.mkdir(parents=True, exist_ok=True)
    return SqlCatalog("qafila", uri=f"sqlite:///{(warehouse / 'catalog.db').as_posix()}", warehouse=warehouse.resolve().as_posix())


def ingest(data_dir: Path, db: Path) -> None:
    """Step 1: land the sources in DuckDB, schema `raw`, exactly as they arrive.

    - From data_dir/qafila_oltp.sqlite: orders, order_items, products, stores.
    - Every data_dir/suppliers/prices_*.csv, keeping the file name of each row.

    Running this twice must not duplicate anything.
    """
    import csv
    import sqlite3
    with duckdb.connect(str(db)) as con:
        con.execute("CREATE SCHEMA IF NOT EXISTS raw")
        with sqlite3.connect(str(data_dir / "qafila_oltp.sqlite")) as src:
            for table in ("orders", "order_items", "products", "stores"):
                rows = src.execute(f'SELECT * FROM "{table}"').fetchall()
                names = [col[1] for col in src.execute(f'PRAGMA table_info("{table}")')]
                import pandas as pd
                frame = pd.DataFrame(rows, columns=names)
                con.register("incoming", frame)
                con.execute(f'CREATE OR REPLACE TABLE raw.{table} AS SELECT * FROM incoming')
                con.unregister("incoming")
        prices = []
        for file in sorted((data_dir / "suppliers").glob("prices_*.csv")):
            with file.open(encoding="utf-8-sig", newline="") as stream:
                for record in csv.DictReader(stream):
                    prices.append({"source_file": file.name, "sku": record.get("sku"),
                                   "valid_from": record.get("valid_from"),
                                   "raw_cost": record.get("cost_sar", record.get("unit_cost"))})
        import pandas as pd
        frame = pd.DataFrame(prices, columns=["source_file", "sku", "valid_from", "raw_cost"])
        con.register("incoming", frame)
        con.execute('CREATE OR REPLACE TABLE raw.supplier_prices AS SELECT * FROM incoming')
        con.unregister("incoming")


def transform(db: Path) -> None:
    """Steps 2-4: build and test the dbt project in dbt/ against the DuckDB file.

    dbt runs in its own process: in this one it would keep the DuckDB file open and block publish().
    """
    env = {**os.environ, "QAFILA_DUCKDB": str(db.resolve())}
    cmd = [sys.executable, "-c", "from dbt.cli.main import cli; cli()",
           "build", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    if subprocess.run(cmd, env=env).returncode != 0:
        raise SystemExit("dbt build failed")


def publish(db: Path, warehouse: Path) -> None:
    """Step 5: publish three dbt models to Iceberg (see the brief for the exact columns).

        silver.product_cost_history   gold.weekly_margin   quality.price_quarantine

    Update existing tables in place, never drop and recreate them: the table's snapshots are
    how we see what a number was before the supplier's correction arrived.
    """
    import pyarrow as pa
    catalog = get_catalog(warehouse)
    with duckdb.connect(str(db), read_only=True) as con:
        for schema, model in (("silver", "product_cost_history"),
                              ("gold", "weekly_margin"), ("quality", "price_quarantine")):
            catalog.create_namespace_if_not_exists(schema)
            identifier = f"{schema}.{model}"
            incoming = con.execute(f'SELECT * FROM {schema}.{model}').fetch_arrow_table()
            if catalog.table_exists(identifier):
                table = catalog.load_table(identifier)
                previous = table.scan().to_arrow()
                # Avoid an unnecessary Iceberg snapshot on identical re-runs.
                if previous.equals(incoming):
                    continue
                table.overwrite(incoming)
            else:
                catalog.create_table(identifier, schema=incoming.schema).append(incoming)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--warehouse", type=Path, default=Path("warehouse"))
    args = ap.parse_args()

    args.warehouse.mkdir(parents=True, exist_ok=True)
    db = args.warehouse / "qafila.duckdb"
    ingest(args.data_dir, db)
    transform(db)
    publish(db, args.warehouse)
    print(f"done: {args.warehouse.resolve()}")


if __name__ == "__main__":
    main()
