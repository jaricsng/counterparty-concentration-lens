"""Load FIBO + the application ontology + synthetic instances into Fuseki.

Idempotent: clears the default graph first, so re-running gives the same state.

Usage:
    python -m scripts.load_data            # load FIBO + app ontology + data
    python -m scripts.load_data --no-fibo  # skip the ~8 MB FIBO load (faster)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lens_m0.config import load_settings  # noqa: E402
from lens_m0.fuseki import FusekiRunner  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("load_data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-fibo",
        action="store_true",
        help="skip loading the FIBO quickstart (instances still reference FIBO IRIs)",
    )
    args = parser.parse_args(argv)

    settings = load_settings()
    runner = FusekiRunner(query_url=settings.query_url, gsp_url=settings.gsp_url)

    ping = f"{settings.fuseki_base_url.rstrip('/')}/$/ping"
    if not runner.is_up(ping):
        logger.error("Fuseki is not reachable at %s — start it first.", settings.fuseki_base_url)
        return 2

    logger.info("Clearing default graph for an idempotent reload ...")
    runner.clear_default_graph()

    if not args.no_fibo:
        if not settings.fibo_path.exists():
            logger.error(
                "FIBO file not found: %s (run vendor/fibo/fetch_fibo.sh)", settings.fibo_path
            )
            return 3
        logger.info("Loading FIBO (%s) — ~8 MB, give it a moment ...", settings.fibo_path.name)
        runner.upload_turtle(settings.fibo_path)

    runner.upload_turtle(settings.ontology_path)
    runner.upload_turtle(settings.instances_path)

    triples = runner.select("SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }")
    logger.info("Done. Default graph now holds %s triples.", triples[0]["n"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
