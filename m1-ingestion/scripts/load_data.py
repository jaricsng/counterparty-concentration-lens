"""Load a dataset into Fuseki — a bundled set, or your own TEST data.

Usage:
    python -m scripts.load_data                          # LENS_DATASET (default: calm)
    python -m scripts.load_data --dataset stressed       # bundled variant

    # Bring your own TEST data (validated + audited via the M2 import path):
    python -m scripts.load_data --source <folder> --name my-scenario
    python -m scripts.load_data --source <folder> --mapping <map.yaml> --name my-scenario
    #   add --allow-partial to load only the rows that pass (exploratory)

Synthetic / sample TEST data only — never real, production, or customer data.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = MODULE_ROOT.parent
sys.path.insert(0, str(MODULE_ROOT))

from lens_m1.config import load_settings  # noqa: E402
from lens_m1.loader import load, server_up  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("load_data")


def _import_byod(args: argparse.Namespace) -> int:
    """Validate + load a user folder of TEST CSVs through the guarded M2 path."""
    for mod in ("m2-actions", "capstone"):
        sys.path.insert(0, str(REPO_ROOT / mod))
    from lens_m1 import byod
    from lens_m2.audit import AuditLog
    from lens_m2.config import load_settings as load_m2_settings
    from lens_m2.importer import import_dataset
    from lens_m2.store import FusekiStore

    m1 = load_settings()
    if not server_up(m1):
        logger.error("Fuseki not reachable at %s — start it first.", m1.fuseki_base_url)
        return 2

    mapping = byod.load_mapping(Path(args.mapping)) if args.mapping else None
    try:
        rows = byod.read_source(Path(args.source), mapping)
    except byod.ByodError as exc:
        logger.error("import aborted: %s", exc)
        return 3

    m2 = load_m2_settings()
    store = FusekiStore(m2.query_url, m2.update_url)
    report = import_dataset(
        rows,
        store=store,
        audit=AuditLog(m2.audit_log_path),
        shapes_path=m2.shapes_path,
        dataset_name=args.name,
        actor="cli",
        allow_partial=args.allow_partial,
    )
    print(
        f"Import '{report.dataset_name}': {report.accepted} accepted, "
        f"{report.rejected} rejected, loaded={report.loaded} ({report.triples} triples)"
    )
    for rec in report.rejections():
        print(f"  REJECTED {rec.table}/{rec.record_id}: {'; '.join(rec.reasons)}")
    if not report.loaded:
        print(
            "Nothing written (validate-all-then-load). Fix the rows above or use --allow-partial."
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        choices=("calm", "stressed"),
        default=None,
        help="bundled variant to load (default: $LENS_DATASET or calm)",
    )
    parser.add_argument("--source", help="folder of your own TEST CSVs to import")
    parser.add_argument("--mapping", help="YAML column/value mapping for differently-shaped CSVs")
    parser.add_argument("--name", default="imported", help="name for the imported dataset")
    parser.add_argument(
        "--allow-partial", action="store_true", help="load rows that pass even if some are rejected"
    )
    args = parser.parse_args(argv)

    if args.source:
        return _import_byod(args)

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
