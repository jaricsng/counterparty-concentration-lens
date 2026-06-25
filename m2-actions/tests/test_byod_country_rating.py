"""BYOD import carries country/rating through to concentration shares.

CSV (with the new entity columns) -> SHACL-validated import -> the M0 country /
rating concentration queries see the imported attribution.
"""

from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

from lens_m0 import metrics_queries as Q
from lens_m0.config import load_settings
from lens_m1 import byod
from lens_m2.audit import AuditLog
from lens_m2.config import SHAPES_PATH
from lens_m2.importer import import_dataset
from lens_m2.store import InMemoryStore

QUERIES = load_settings().queries_dir


def test_byod_country_rating_flows_to_concentration(tmp_path: Path) -> None:
    (tmp_path / "entities.csv").write_text(
        "entity_id,entity_name,counterparty_type,sector,country,rating\n"
        "LE-BANK,Bank,bank,financials,SG,AAA\nLE-A,Acme,corporate,tech,MY,BBB\n"
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
    # all exposure attributed to the borrower (LE-A): country MY, rating BBB
    assert Q.country_shares(store, QUERIES) == {"MY": Decimal(1)}
    assert Q.rating_shares(store, QUERIES) == {"BBB": Decimal(1)}
