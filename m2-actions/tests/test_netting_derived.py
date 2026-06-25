"""Store-based net exposure (post-CRM) matches the M1 oracle on the stressed set."""

from __future__ import annotations

from decimal import Decimal

from lens_m1 import datasets, rdfize
from lens_m2.derived import net_exposure
from lens_m2.store import InMemoryStore

ID = "https://lens.example/id/"


def _store(name: str) -> InMemoryStore:
    return InMemoryStore(rdfize.build_graph(datasets.get_dataset(name)))


def test_net_exposure_matches_oracle_stressed() -> None:
    store = _store("stressed")
    assert net_exposure(store, ID + "LE-0011") == Decimal(5_000_000)  # 7M - 4M*(1-0.5)
    assert net_exposure(store, ID + "LE-0021") == Decimal(4_000_000)  # 8M - 5M*(1-0.2)
    assert net_exposure(store, ID + "LE-0040") == Decimal(3_000_000)  # no collateral
    assert net_exposure(store, ID + "LE-0001") == Decimal(5_000_000)  # shared collat excluded
