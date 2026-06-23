"""Load a generated dataset into Fuseki.

Usage:
    python -m scripts.load_data                      # loads LENS_DATASET (default: calm)
    python -m scripts.load_data --dataset stressed   # explicit override
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lens_m1.config import load_settings  # noqa: E402
from lens_m1.loader import load, server_up  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("load_data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        choices=("calm", "stressed"),
        default=None,
        help="dataset variant to load (default: $LENS_DATASET or calm)",
    )
    args = parser.parse_args(argv)

    settings = load_settings(dataset=args.dataset)
    if not server_up(settings):
        logger.error("Fuseki not reachable at %s — start it first.", settings.fuseki_base_url)
        return 2

    result = load(settings)
    logger.info(
        "Loaded dataset '%s': rows=%s, %d instance triples in store (%d total).",
        result.dataset,
        result.row_counts,
        result.instance_triples,
        result.graph_triples_in_store,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
