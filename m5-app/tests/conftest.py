"""Fixtures for Module 5 (in-memory runner + paths)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

M5_ROOT = Path(__file__).resolve().parent.parent
ROOT = M5_ROOT.parent
for _p in (M5_ROOT, ROOT / "m0-ontology", ROOT / "m1-ingestion"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lens_m0.config import load_settings  # noqa: E402
from lens_m0.graph import GraphRunner  # noqa: E402
from lens_m1 import datasets, rdfize  # noqa: E402


@pytest.fixture(scope="module")
def runner() -> GraphRunner:
    return GraphRunner(rdfize.build_graph(datasets.get_dataset("stressed")))


@pytest.fixture(scope="module")
def queries_dir() -> Path:
    return load_settings().queries_dir
