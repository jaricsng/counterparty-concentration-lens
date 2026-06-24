"""Fixtures for the Capstone (paths for lens_capstone + lens_m1)."""

from __future__ import annotations

import sys
from pathlib import Path

CAP_ROOT = Path(__file__).resolve().parent.parent
ROOT = CAP_ROOT.parent
for _p in (CAP_ROOT, ROOT / "m1-ingestion"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
