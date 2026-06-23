"""The FastAPI surface: guarded writes, flags, audit, and a write-role check."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    assert client.get("/health").json()["status"] == "ok"


def test_create_loan_endpoint(client: TestClient) -> None:
    resp = client.post(
        "/actions/loans",
        json={
            "loan_id": "LN-9001",
            "lender_id": "LE-0099",
            "borrower_id": "LE-0041",
            "principal": 1_000_000,
            "actor": "rm1",
            "role": "group_risk",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["accepted"] is True


def test_dangling_guaranty_rejected_endpoint(client: TestClient) -> None:
    resp = client.post(
        "/actions/guaranties",
        json={
            "guarantee_id": "GTY-9001",
            "guarantor_id": "LE-0001",
            "guaranteed_loan_id": "LN-NONE",
            "amount": 1000,
        },
    )
    assert resp.status_code == 200  # business rejection, not a transport error
    assert resp.json()["accepted"] is False
    assert "loan" in resp.json()["reason"].lower()


def test_pydantic_rejects_bad_enum(client: TestClient) -> None:
    resp = client.post(
        "/actions/entities",
        json={
            "entity_id": "LE-7000",
            "name": "Bad Co",
            "counterparty_type": "alien",
            "sector": "x",
        },
    )
    assert resp.status_code == 422  # input validation at the boundary


def test_record_exposure_breach_flag(client: TestClient) -> None:
    resp = client.post(
        "/actions/record-exposure",
        json={
            "loan_id": "LN-9100",
            "lender_id": "LE-0099",
            "borrower_id": "LE-0041",
            "principal": 30_000_000,
            "actor": "rm1",
            "role": "group_risk",
        },
    )
    body = resp.json()
    assert body["accepted"] is True
    assert "limit-breach:LE-0041" in body["flags"]


def test_limit_edit_requires_group_risk_role(client: TestClient) -> None:
    forbidden = client.post(
        "/actions/limits",
        json={
            "limit_id": "LIM-NEW",
            "entity_id": "LE-0041",
            "limit_amount": 5_000_000,
            "actor": "rm1",
            "role": "relationship_manager",
        },
    )
    assert forbidden.status_code == 403
    allowed = client.post(
        "/actions/limits",
        json={
            "limit_id": "LIM-NEW",
            "entity_id": "LE-0041",
            "limit_amount": 5_000_000,
            "actor": "risk",
            "role": "group_risk",
        },
    )
    assert allowed.status_code == 200 and allowed.json()["accepted"] is True


def test_flag_limit_breach_endpoint(client: TestClient) -> None:
    resp = client.post("/actions/flag-limit-breach")
    entities = {b["entity"] for b in resp.json()["breaches"]}
    assert {"LE-0030", "LE-0001", "LE-0020"} <= entities


def test_audit_endpoint_records_actions(client: TestClient) -> None:
    client.post(
        "/actions/loans",
        json={
            "loan_id": "LN-9001",
            "lender_id": "LE-0099",
            "borrower_id": "LE-0041",
            "principal": 1_000_000,
        },
    )
    entries = client.get("/audit").json()["entries"]
    assert entries and entries[-1]["action"] == "create-loan"
