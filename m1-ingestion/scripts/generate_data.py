"""Generate the synthetic source tables (CSV) for both dataset variants.

Usage:
    python -m scripts.generate_data            # writes data/calm/ and data/stressed/
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lens_m1.config import load_settings  # noqa: E402
from lens_m1.csv_tables import write_dataset  # noqa: E402
from lens_m1.datasets import DATASETS, get_dataset  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("generate_data")


def main() -> int:
    settings = load_settings()
    for name in DATASETS:
        spec = get_dataset(name)
        counts = write_dataset(spec, settings.data_dir / name)
        logger.info("Wrote %s: %s", name, counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
