"""The M2 API exposes a stable contract (guarded paths + request schema).

A snapshot of the OpenAPI document so an accidental route rename or a dropped
field on a write model is caught — the app and any client depend on this shape.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

_EXPECTED_PATHS = {
    "/health",
    "/actions/entities",
    "/actions/loans",
    "/actions/record-exposure",
    "/actions/guaranties",
    "/actions/collateral",
    "/actions/limits",
    "/actions/deactivate",
    "/actions/flag-limit-breach",
    "/audit",
}


def test_openapi_documents_the_guarded_actions(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert _EXPECTED_PATHS <= set(schema["paths"])


def test_loan_write_model_keeps_its_required_fields(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    loan = schema["components"]["schemas"]["LoanIn"]["properties"]
    assert {"loan_id", "lender_id", "borrower_id", "principal"} <= set(loan)
