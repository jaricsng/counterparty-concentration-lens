"""BYOD import carries collateral value/haircut through to net exposure.

Proves the cross-cutting bring-your-own-data path works for the netting feature:
CSV (with the new columns) -> read -> SHACL-validated import -> net exposure.
"""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

from lens_m1 import byod
from lens_m2.audit import AuditLog
from lens_m2.config import SHAPES_PATH
from lens_m2.derived import net_exposure
from lens_m2.importer import import_dataset
from lens_m2.store import InMemoryStore


def _write(d: Path) -> None:
    (d / "entities.csv").write_text(
        "entity_id,entity_name,counterparty_type,sector\n"
        "LE-BANK,Bank,bank,financials\nLE-A,Acme,corporate,tech\n"
    )
    (d / "loans.csv").write_text(
        "loan_id,lender_entity_id,borrower_entity_id,exposure_amount,currency,status\n"
        "LN-1,LE-BANK,LE-A,1000,SGD,active\n"
    )
    (d / "collateral.csv").write_text(
        "collateral_id,collateral_type,pledged_by_entity_id,securing_loan_id,"
        "issuer_entity_id,collateral_value,haircut_pct\n"
        "C-1,warehouse,LE-A,LN-1,,800,25\n"
    )


def test_byod_collateral_flows_to_net_exposure(tmp_path: Path) -> None:
    _write(tmp_path)
    store = InMemoryStore()
    report = import_dataset(
        byod.read_source(tmp_path),
        store=store,
        audit=AuditLog(Path(tempfile.mkdtemp()) / "a.jsonl"),
        shapes_path=SHAPES_PATH,
        dataset_name="byod-netting",
        actor="t",
        role="group_risk",
    )
    assert report.loaded  # SHACL-valid (haircut 0.25 in [0,1], value > 0)
    # mitigant = 800 * (1 - 0.25) = 600 ; net = 1000 - 600 = 400
    assert net_exposure(store, "https://lens.example/id/LE-A") == Decimal(400)
