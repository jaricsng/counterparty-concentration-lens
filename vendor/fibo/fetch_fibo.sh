#!/usr/bin/env bash
# Fetch the FIBO Production "quickstart" distribution into this directory.
#
# Why a fetch script instead of committing the ontology?
#   The quickstart file is ~8 MB — larger than the repo's pre-commit
#   large-file gate (2 MB) and not something we want to vendor as a blob.
#   Committing this script + the recorded checksum keeps the build
#   reproducible while linking to the upstream source of truth.
#
# FIBO is published by the EDM Council. FIBO is a trademark of EDM Council, Inc.
# See README.md in this directory for attribution and the modules we use.
#
# Usage:   ./fetch_fibo.sh
# Verifies the download against SHA256SUMS.
set -euo pipefail

cd "$(dirname "$0")"

FILE="prod.fibo-quickstart.ttl"
URL="https://spec.edmcouncil.org/fibo/ontology/master/latest/${FILE}"

echo "Downloading FIBO production quickstart from:"
echo "  ${URL}"
curl -fSL --max-time 300 -o "${FILE}" "${URL}"

echo "Verifying checksum against SHA256SUMS..."
if shasum -a 256 -c SHA256SUMS; then
  echo "OK: ${FILE} downloaded and verified."
else
  echo "WARNING: checksum mismatch. Upstream FIBO may have been re-released." >&2
  echo "Review the change, then update SHA256SUMS with:" >&2
  echo "  shasum -a 256 ${FILE} > SHA256SUMS" >&2
  exit 1
fi
