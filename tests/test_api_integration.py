"""The M2 FastAPI app against a live Fuseki (the unit tests use an in-memory stub).

Proves the full wiring: HTTP request -> ActionService -> FusekiStore -> Fuseki,
including the SHACL guard and the audit trail.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from lens_m2.app import create_app

pytestmark = pytest.mark.integration


def test_api_writes_and_reads_through_live_fuseki(stressed, service, fuseki_store, audit):
    client = TestClient(create_app(service, audit))

    # a valid loan is accepted AND actually present in Fuseki
    ok = client.post(
        "/actions/loans",
        json={
            "loan_id": "LN-API-1",
            "lender_id": "LE-0099",
            "borrower_id": "LE-0041",
            "principal": 1_000_000,
            "role": "group_risk",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["accepted"]
    assert fuseki_store.select(
        "SELECT ?a WHERE { <https://lens.example/id/LN-API-1> "
        "<https://lens.example/ontology/principalAmount> ?a }"
    )

    # a record-exposure that breaches the limit is written and flagged
    breaching = client.post(
        "/actions/record-exposure",
        json={
            "loan_id": "LN-API-2",
            "lender_id": "LE-0099",
            "borrower_id": "LE-0041",
            "principal": 30_000_000,
            "role": "group_risk",
        },
    )
    assert "limit-breach:LE-0041" in breaching.json()["flags"]

    # the flag endpoint reports the live breaches (Acme + the new Zenith one)
    breaches = {b["entity"] for b in client.post("/actions/flag-limit-breach").json()["breaches"]}
    assert {"LE-0001", "LE-0041"} <= breaches

    # an invalid write (dangling borrower) is rejected pre-write
    bad = client.post(
        "/actions/loans",
        json={
            "loan_id": "LN-API-3",
            "lender_id": "LE-0099",
            "borrower_id": "LE-NOPE",
            "principal": 1000,
            "role": "group_risk",
        },
    )
    assert not bad.json()["accepted"]

    # the audit endpoint exposes the trail
    assert client.get("/audit").json()["entries"]
