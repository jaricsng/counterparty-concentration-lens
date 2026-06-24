"""Spark-equivalent of the M1 loader: CSV source tables -> FIBO N-Triples, scaled.

A PySpark job that reads the same synthetic CSV tables M1 emits and produces the
*same* RDF triples, but as a distributed flatMap over partitions — the "scale"
path for the ingestion step. The per-row transform is the pure, tested
:mod:`lens_capstone.triples_map`, so the output is identical to M1's by
construction (proven in tests/test_triples_map.py).

Runtime: Spark 3.5 needs Java 17 and Python <= 3.12 (see capstone/run_spark.sh).

Usage:
    spark-submit spark_loader.py --data <dataset_dir> --out <output_dir>
    python spark_loader.py --data ../m1-ingestion/data/stressed --out /tmp/lens_nt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lens_capstone.triples_map import TABLE_MAP  # noqa: E402
from pyspark.sql import SparkSession  # noqa: E402


def build_triples(spark: SparkSession, data_dir: str):
    """Union of N-Triples from every source table (deduplicated)."""
    sc = spark.sparkContext
    rdd = sc.emptyRDD()
    for _table, (filename, fn) in TABLE_MAP.items():
        df = spark.read.option("header", True).csv(f"{data_dir}/{filename}")
        table_nt = df.rdd.map(lambda row: row.asDict()).flatMap(fn)
        rdd = rdd.union(table_nt)
    # RDF is a set: collateral rows repeat collateral-level triples -> distinct.
    return rdd.distinct()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="dataset dir of CSV source tables")
    parser.add_argument("--out", required=True, help="output dir for N-Triples")
    args = parser.parse_args(argv)

    spark = SparkSession.builder.appName("lens-capstone-loader").getOrCreate()
    try:
        triples = build_triples(spark, args.data)
        count = triples.count()
        # coalesce(1) so the demo writes a single part file (drop for real scale).
        triples.coalesce(1).saveAsTextFile(args.out)
        print(f"wrote {count} triples to {args.out}")
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
