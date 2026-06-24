"""Bring-your-own import over a live Fuseki: FusekiStore.replace + reset isolation.

The unit importer test uses an in-memory store; this drives the real
replace-the-named-dataset HTTP path and proves a bundled-dataset reset discards
the import (the calm/stressed CSVs are never overwritten).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from lens_m1 import byod
from lens_m1.config import load_settings as m1_settings
from lens_m1.loader import load as m1_load
from lens_m2.config import load_settings as m2_settings
from lens_m2.importer import import_dataset

pytestmark = pytest.mark.integration

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
_ENTITIES = (
    "PREFIX cmns: <https://www.omg.org/spec/Commons/Organizations/> "
    "SELECT ?e WHERE { ?e a cmns:LegalEntity }"
)


def _entity_ids(store) -> set[str]:
    return {r["e"].rsplit("/", 1)[-1] for r in store.select(_ENTITIES)}


def test_byod_import_and_reset_isolation(require_fuseki, fuseki_store, audit):
    report = import_dataset(
        byod.read_source(TEMPLATES),
        store=fuseki_store,
        audit=audit,
        shapes_path=m2_settings().shapes_path,
        dataset_name="it-byod",
        actor="it",
        role="group_risk",
    )
    assert report.loaded
    assert report.accepted == 7

    ids = _entity_ids(fuseki_store)
    assert {"LE-EXAMPLE-1", "LE-EXAMPLE-2", "LE-EXAMPLE-BANK"} <= ids

    # resetting to a bundled dataset restores it and discards the imported one
    m1_load(m1_settings(dataset="calm"))
    after = _entity_ids(fuseki_store)
    assert "LE-EXAMPLE-1" not in after
    assert "LE-0001" in after

    # the import was audited
    assert audit.entries()[-1]["action"] == "import"
