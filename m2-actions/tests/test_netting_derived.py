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
    assert net_exposure(store, ID + "LE-0044") == Decimal(2_000_000)  # no collateral
    assert net_exposure(store, ID + "LE-0001") == Decimal(5_000_000)  # shared collat excluded


def test_net_exposures_aggregate_has_sector_and_covers_names() -> None:
    from lens_m2.derived import net_exposures

    rows = {n.entity: n for n in net_exposures(_store("stressed"))}
    assert {"LE-0011", "LE-0021", "LE-0030", "LE-0040", "LE-0042", "LE-0043"} <= set(rows)
    assert rows["LE-0042"].sector == "government"
    assert rows["LE-0043"].net == Decimal(4_600_000)
    # two financial-services names (for the sector filter)
    assert {e for e, n in rows.items() if n.sector == "financial services"} == {
        "LE-0021",
        "LE-0030",
    }
