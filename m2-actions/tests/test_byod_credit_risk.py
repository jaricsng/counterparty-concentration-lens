"""BYOD import carries rating through to Expected Loss / capital."""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

from lens_m1 import byod
from lens_m2 import derived
from lens_m2.audit import AuditLog
from lens_m2.config import SHAPES_PATH
from lens_m2.importer import import_dataset
from lens_m2.store import InMemoryStore


def test_byod_rating_flows_to_expected_loss(tmp_path: Path) -> None:
    (tmp_path / "entities.csv").write_text(
        "entity_id,entity_name,counterparty_type,sector,country,rating\n"
        "LE-BANK,Bank,bank,financials,SG,AAA\nLE-A,Acme,corporate,tech,SG,B\n"
    )
    (tmp_path / "loans.csv").write_text(
        "loan_id,lender_entity_id,borrower_entity_id,exposure_amount,currency,status\n"
        "LN-1,LE-BANK,LE-A,1000,SGD,active\n"
    )
    store = InMemoryStore()
    report = import_dataset(
        byod.read_source(tmp_path),
        store=store,
        audit=AuditLog(Path(tempfile.mkdtemp()) / "a.jsonl"),
        shapes_path=SHAPES_PATH,
        dataset_name="byod-cr",
        actor="t",
        role="group_risk",
    )
    assert report.loaded
    (row,) = derived.expected_losses(store)
    assert row.entity == "LE-A" and row.rating == "B"
    # EAD 1000, B-grade: PD 0.05, LGD 0.45 -> EL 22.5 ; RW 1.5 -> capital 0.08*1.5*1000 = 120
    assert row.el == Decimal("22.500")
    assert row.capital == Decimal("120.000")
