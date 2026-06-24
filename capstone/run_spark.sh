#!/usr/bin/env bash
# Run the Capstone Spark loader in local mode.
#   ./run_spark.sh [DATASET_DIR] [OUTPUT_DIR]
#
# Spark 3.5 needs Java 17 and Python <= 3.12. This repo's main .venv is 3.14, so
# the loader uses a dedicated 3.12 venv (capstone/.venv-spark) and JDK 17.
set -euo pipefail
cd "$(dirname "$0")"

export JAVA_HOME="${JAVA_HOME:-/usr/local/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home}"
PYBIN="$(pwd)/.venv-spark/bin/python"
export PYSPARK_PYTHON="${PYBIN}"
export PYSPARK_DRIVER_PYTHON="${PYBIN}"

DATA="${1:-../m1-ingestion/data/stressed}"
OUT="${2:-/tmp/lens_capstone_nt}"
rm -rf "$OUT"

"${PYBIN}" spark_loader.py --data "${DATA}" --out "${OUT}"
echo "N-Triples part files:"
ls -1 "${OUT}"/part-* 2>/dev/null
