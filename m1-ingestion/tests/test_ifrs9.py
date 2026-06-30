"""Simplified IFRS-9 ECL staging (M1)."""

from __future__ import annotations

from decimal import Decimal

from lens_m1 import datasets, ifrs9


def test_stage_for_rating() -> None:
    assert ifrs9.stage_for("AAA") == 1
    assert ifrs9.stage_for("BBB") == 1
    assert ifrs9.stage_for("BB") == 2
    assert ifrs9.stage_for("B") == 2
    assert ifrs9.stage_for(None) == 2  # unrated -> conservative
    assert ifrs9.stage_for("CCC") == 3


def test_lifetime_exceeds_12m_for_sub_ig() -> None:
    s = datasets.get_dataset("stressed")
    bb = ifrs9.counterparty_ecl(s, "LE-0011")  # BB, stage 2
    assert bb.stage == 2
    assert bb.ecl_lifetime > bb.ecl_12m  # the lifetime cliff
    assert bb.ecl_recognised == bb.ecl_lifetime


def test_stage1_recognises_12m() -> None:
    s = datasets.get_dataset("stressed")
    acme = ifrs9.counterparty_ecl(s, "LE-0001")  # A, stage 1
    assert acme.stage == 1
    assert acme.ecl_recognised == acme.ecl_12m


def test_zero_ecl_edge_cases() -> None:
    assert ifrs9.lifetime_ecl(0.0, 5, 0.2) == 0.0
    assert ifrs9.lifetime_ecl(1_000_000, 5, 0.0) == 0.0


def test_staging_summary_and_total() -> None:
    s = datasets.get_dataset("stressed")
    summary = {x.stage: x for x in ifrs9.staging_summary(s)}
    assert summary[2].count > 0  # sub-IG cluster sits in stage 2
    total = sum((x.ecl for x in summary.values()), Decimal(0))
    assert total == ifrs9.total_ecl(s)
    # lifetime staging dwarfs the 12-month EL baseline (~811k)
    assert float(total) > 3_000_000
