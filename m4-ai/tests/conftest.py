"""Fixtures for Module 4 (graph runner over the stressed dataset)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

M4_ROOT = Path(__file__).resolve().parent.parent
ROOT = M4_ROOT.parent
for _p in (M4_ROOT, ROOT / "m0-ontology", ROOT / "m1-ingestion"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lens_m0.graph import GraphRunner  # noqa: E402
from lens_m1 import datasets, rdfize  # noqa: E402

LABEL_INDEX = {
    "acme": "LE-0001",
    "helios": "LE-0010",
    "vortex": "LE-0020",
    "nimbus": "LE-0030",
}


@pytest.fixture(scope="module")
def runner() -> GraphRunner:
    return GraphRunner(rdfize.build_graph(datasets.get_dataset("stressed")))
