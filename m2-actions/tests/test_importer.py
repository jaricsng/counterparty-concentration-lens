"""Guarded BYOD import: validate-all-then-load, per-row report, audit, partial."""

from __future__ import annotations

from pathlib import Path

from lens_m1 import byod
from lens_m2.audit import AuditLog
from lens_m2.config import SHAPES_PATH
from lens_m2.importer import import_dataset
from lens_m2.store import InMemoryStore

TEMPLATES = Path(__file__).resolve().parent.parent.parent / "templates"


def _bad_dataset(d: Path) -> Path:
    (d / "entities.csv").write_text(
        "entity_id,entity_name,counterparty_type,sector,parent_entity_id,"
        "eligible_capital,annual_revenue\n"
        "LE-1,Good Co,corporate,tech,,,10\n"
        "LE-2,Bad Type,alien,tech,,,10\n"
    )
    (d / "loans.csv").write_text(
        "loan_id,lender_entity_id,borrower_entity_id,exposure_amount,currency,status\n"
        "LN-1,LE-1,LE-MISSING,5000000,SGD,active\n"  # dangling borrower
        "LN-2,LE-1,LE-1,-99,SGD,active\n"  # negative amount
    )
    (d / "guarantees.csv").write_text(
        "guarantee_id,guarantor_entity_id,beneficiary_loan_id,amount,currency\n"
        "GTY-1,LE-1,LN-2,1000,SGD\n"  # guarantor == borrower (self-guaranty)
    )
    (d / "collateral.csv").write_text(
        "collateral_id,collateral_type,pledged_by_entity_id,securing_loan_id,issuer_entity_id\n"
    )
    (d / "limits.csv").write_text("limit_id,entity_id,single_name_limit,currency\n")
    return d


def _import(rows, store, name="ds", allow_partial=False):
    import tempfile

    audit = AuditLog(Path(tempfile.mkdtemp()) / "audit.jsonl")
    report = import_dataset(
        rows,
        store=store,
        audit=audit,
        shapes_path=SHAPES_PATH,
        dataset_name=name,
        actor="t",
        role="group_risk",
        allow_partial=allow_partial,
    )
    return report, audit


def test_valid_templates_load_and_audit() -> None:
    store = InMemoryStore()
    report, audit = _import(byod.read_source(TEMPLATES), store, name="tmpl")
    assert report.loaded and report.rejected == 0 and report.accepted == 7
    assert report.triples > 0 and len(list(store.snapshot())) == report.triples
    assert audit.entries()[-1]["action"] == "import"
    assert audit.entries()[-1]["outcome"] == "accepted"


def test_invalid_rejected_with_reasons_nothing_written(tmp_path: Path) -> None:
    store = InMemoryStore()
    rows = byod.read_source(_bad_dataset(tmp_path))
    report, audit = _import(rows, store, name="bad")
    assert not report.loaded
    assert len(list(store.snapshot())) == 0  # atomic: nothing written
    by_id = {(r.table, r.record_id): r.reasons for r in report.rejections()}
    assert any("borrower" in m.lower() for m in by_id[("loans", "LN-1")])
    assert any("positive" in m.lower() for m in by_id[("loans", "LN-2")])
    assert any("distinct" in m.lower() for m in by_id[("guarantees", "GTY-1")])
    assert any("counterpartytype" in m.lower() for m in by_id[("entities", "LE-2")])
    assert audit.entries()[-1]["outcome"] == "rejected"


def test_allow_partial_loads_only_passing_rows(tmp_path: Path) -> None:
    store = InMemoryStore()
    rows = byod.read_source(_bad_dataset(tmp_path))
    report, _ = _import(rows, store, name="partial", allow_partial=True)
    assert report.loaded and report.accepted == 1 and report.rejected == 4
    # only the one good entity's triples are written
    ids = {str(s).rsplit("/", 1)[-1] for s in store.snapshot().subjects()}
    assert "LE-1" in ids and "LE-2" not in ids


def test_blank_id_row_rejected(tmp_path: Path) -> None:
    (tmp_path / "entities.csv").write_text(
        "entity_id,entity_name,counterparty_type,sector,parent_entity_id,"
        "eligible_capital,annual_revenue\n,Nameless,corporate,tech,,,1\n"
    )
    (tmp_path / "loans.csv").write_text(
        "loan_id,lender_entity_id,borrower_entity_id,exposure_amount,currency,status\n"
    )
    report, _ = _import(byod.read_source(tmp_path), InMemoryStore(), name="blank")
    assert any(r.record_id == "(blank)" and "missing id" in r.reasons for r in report.rejections())
