"""Bring-your-own-data reader: canonical + Tier-2 mapping, with loud errors."""

from __future__ import annotations

from pathlib import Path

import pytest
from lens_m1 import byod

TEMPLATES = Path(__file__).resolve().parent.parent.parent / "templates"


def test_reads_canonical_templates() -> None:
    rows = byod.read_source(TEMPLATES)
    assert {r["entity_id"] for r in rows["entities"]} == {
        "LE-EXAMPLE-BANK",
        "LE-EXAMPLE-1",
        "LE-EXAMPLE-2",
    }
    assert rows["loans"][0]["borrower_entity_id"] == "LE-EXAMPLE-2"
    # optional tables present here, but absent ones would be empty lists
    assert isinstance(rows["guarantees"], list)


def test_missing_required_file_raises(tmp_path: Path) -> None:
    (tmp_path / "loans.csv").write_text("loan_id\nLN-1\n")  # no entities.csv
    with pytest.raises(byod.ByodError, match="entities.csv"):
        byod.read_source(tmp_path)


def test_canonical_missing_required_column_raises(tmp_path: Path) -> None:
    (tmp_path / "entities.csv").write_text("entity_id,entity_name\nLE-1,Acme\n")  # no type/sector
    (tmp_path / "loans.csv").write_text("loan_id\nLN-1\n")
    with pytest.raises(byod.ByodError, match="required column"):
        byod.read_source(tmp_path)


def test_tier2_mapping_renames_and_value_maps(tmp_path: Path) -> None:
    (tmp_path / "cpty.csv").write_text(
        "cpty_ref,cpty_name,type,gics_sector\nC1,Acme Corp,Corp,technology\n"
    )
    (tmp_path / "exposures.csv").write_text(
        "deal_id,lender_ref,cpty_ref,notional,ccy,deal_status\nD1,BANK,C1,5000000,SGD,active\n"
    )
    (tmp_path / "map.yaml").write_text(
        "entities:\n"
        "  file: cpty.csv\n"
        "  columns: {entity_id: cpty_ref, entity_name: cpty_name, counterparty_type: type, "
        "sector: gics_sector}\n"
        "  value_map: {counterparty_type: {Corp: corporate}}\n"
        "loans:\n"
        "  file: exposures.csv\n"
        "  columns: {loan_id: deal_id, lender_entity_id: lender_ref, "
        "borrower_entity_id: cpty_ref, exposure_amount: notional, currency: ccy, "
        "status: deal_status}\n"
    )
    mapping = byod.load_mapping(tmp_path / "map.yaml")
    rows = byod.read_source(tmp_path, mapping)
    ent = rows["entities"][0]
    assert ent["entity_id"] == "C1"
    assert ent["counterparty_type"] == "corporate"  # value-mapped Corp -> corporate
    assert rows["loans"][0]["exposure_amount"] == "5000000"


def test_mapping_unknown_source_column_raises(tmp_path: Path) -> None:
    (tmp_path / "cpty.csv").write_text("ref,name\nC1,Acme\n")
    (tmp_path / "loans.csv").write_text("loan_id\nLN-1\n")
    (tmp_path / "map.yaml").write_text(
        "entities:\n  file: cpty.csv\n  columns: {entity_id: NOT_THERE}\n"
    )
    mapping = byod.load_mapping(tmp_path / "map.yaml")
    with pytest.raises(byod.ByodError, match="not found"):
        byod.read_source(tmp_path, mapping)
