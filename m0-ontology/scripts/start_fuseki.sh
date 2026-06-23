#!/usr/bin/env bash
# Start a local Apache Jena Fuseki server with an in-memory, updatable dataset.
#
# Downloads-and-extracts are handled separately (see m0-ontology/README.md);
# this script just launches the server that was unpacked under .fuseki/.
#
# Env:
#   FUSEKI_DATASET   dataset name (default: lens)
#   FUSEKI_PORT      port (default: 3030)
#
# The dataset is in-memory: stop the server and the data is gone. That is the
# right default for a synthetic-data demo — `load_data.py` repopulates it.
set -euo pipefail

cd "$(dirname "$0")/.."   # m0-ontology/

DATASET="${FUSEKI_DATASET:-lens}"
PORT="${FUSEKI_PORT:-3030}"

FUSEKI_DIR="$(find .fuseki -maxdepth 1 -type d -name 'apache-jena-fuseki-*' | head -1)"
if [[ -z "${FUSEKI_DIR}" ]]; then
  echo "Fuseki not found under m0-ontology/.fuseki/." >&2
  echo "Download it first, e.g.:" >&2
  echo "  curl -fSLo .fuseki/fuseki.tar.gz https://dlcdn.apache.org/jena/binaries/apache-jena-fuseki-6.1.0.tar.gz" >&2
  echo "  tar -C .fuseki -xzf .fuseki/fuseki.tar.gz" >&2
  exit 1
fi

echo "Starting Fuseki (${FUSEKI_DIR}) on :${PORT} with in-memory dataset /${DATASET} ..."
exec "${FUSEKI_DIR}/fuseki-server" --mem --update --port "${PORT}" "/${DATASET}"
