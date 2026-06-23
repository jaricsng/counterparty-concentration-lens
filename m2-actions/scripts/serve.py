"""Run the M2 actions API (FastAPI + uvicorn).

Usage:
    python -m scripts.serve            # serves on http://localhost:8000
Requires a running Fuseki with a dataset loaded (see M0/M1).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402
from lens_m2.app import build_default_app  # noqa: E402


def main() -> int:
    uvicorn.run(build_default_app(), host="127.0.0.1", port=8000)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
