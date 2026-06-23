"""The datasets are well-formed and within the §4 brief."""

from __future__ import annotations

from lens_m1.datasets import get_dataset
from lens_m1.spec import COUNTERPARTY_TYPES, DatasetSpec


def _entity_ids(spec: DatasetSpec) -> set[str]:
    return {e.entity_id for e in spec.entities}


def test_entity_count_in_brief(calm: DatasetSpec, stressed: DatasetSpec) -> None:
    for spec in (calm, stressed):
        assert 20 <= len(spec.entities) <= 30, f"{spec.name}: {len(spec.entities)} entities"


def test_same_roster_across_variants(calm: DatasetSpec, stressed: DatasetSpec) -> None:
    assert _entity_ids(calm) == _entity_ids(stressed)


def test_limits_identical_across_variants(calm: DatasetSpec, stressed: DatasetSpec) -> None:
    # Limits express risk appetite, not the scenario.
    assert {(lim.entity_id, lim.limit_amount) for lim in calm.limits} == {
        (lim.entity_id, lim.limit_amount) for lim in stressed.limits
    }


def test_counterparty_types_valid(stressed: DatasetSpec) -> None:
    for e in stressed.entities:
        assert e.counterparty_type in COUNTERPARTY_TYPES


def test_referential_integrity(calm: DatasetSpec, stressed: DatasetSpec) -> None:
    for spec in (calm, stressed):
        ids = _entity_ids(spec)
        loan_ids = {ln.loan_id for ln in spec.loans}
        for ln in spec.loans:
            assert ln.borrower_id in ids and ln.lender_id in ids
        for g in spec.guarantees:
            assert g.guarantor_id in ids
            assert g.guaranteed_loan_id in loan_ids
        for c in spec.collateral:
            assert c.pledged_by_id in ids
            assert all(lid in loan_ids for lid in c.secures_loan_ids)
            assert c.issuer_id is None or c.issuer_id in ids
        for lim in spec.limits:
            assert lim.entity_id in ids


def test_generation_is_deterministic() -> None:
    a, b = get_dataset("stressed"), get_dataset("stressed")
    assert a.loans == b.loans and a.entities == b.entities and a.guarantees == b.guarantees


def test_ownership_chain_has_three_levels(stressed: DatasetSpec) -> None:
    # LE-0004 -> LE-0002 -> LE-0001 (UBO) for the UBO-aggregation case.
    assert stressed.entity("LE-0004").parent_id == "LE-0002"
    assert stressed.entity("LE-0002").parent_id == "LE-0001"
    assert stressed.entity("LE-0001").parent_id is None
