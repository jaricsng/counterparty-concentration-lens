"""A canary for the connected-exposure query (the money shot).

It traverses guarantees + shared collateral + group ownership via SPARQL paths,
which is the one query prone to pathological blow-up in rdflib. A generous wall-
clock bound catches an accidental O(n^2) regression (we hit one during the build)
without being flaky on slow CI. Runs in-memory — no live Fuseki needed.
"""

from __future__ import annotations

import time
from decimal import Decimal

import pytest
from lens_m0 import concentration
from lens_m0.config import load_settings
from lens_m0.graph import GraphRunner
from lens_m1 import datasets, rdfize

ACME = "https://lens.example/id/LE-0001"


@pytest.fixture(scope="module")
def runner() -> GraphRunner:
    return GraphRunner(rdfize.build_graph(datasets.get_dataset("stressed")))


def test_connected_exposure_query_is_not_pathological(runner: GraphRunner) -> None:
    queries_dir = load_settings().queries_dir
    start = time.perf_counter()
    head = concentration.headline(runner, queries_dir, ACME)
    elapsed = time.perf_counter() - start

    assert head.connected_total == Decimal("34000000")  # it ran and is correct
    assert elapsed < 30.0, f"connected-exposure query took {elapsed:.1f}s — likely a regression"
