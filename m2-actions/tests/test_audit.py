"""The audit trail is tamper-evident (hash-chained) and trace-correlated."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from lens_m2 import obs
from lens_m2.audit import AuditLog, AuditRecord


def _rec(action: str) -> AuditRecord:
    return AuditRecord(action, "T-1", "alice", "group_risk", "accepted", "ok")


def _log(tmp_path: Path) -> AuditLog:
    return AuditLog(tmp_path / "audit.jsonl")


def test_records_form_a_verifiable_hash_chain(tmp_path: Path) -> None:
    log = _log(tmp_path)
    for a in ("create-loan", "flag-limit-breach", "deactivate"):
        log.record(_rec(a))
    rows = log.entries()
    assert [r["seq"] for r in rows] == [0, 1, 2]
    assert rows[0]["prev_hash"] == "0" * 64
    assert rows[1]["prev_hash"] == rows[0]["entry_hash"]  # chained
    status = log.verify()
    assert status.ok and status.length == 3 and status.problems == []


def test_verify_detects_content_tampering(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.record(_rec("create-loan"))
    log.record(_rec("deactivate"))
    # an attacker edits a recorded outcome in place
    rows = [json.loads(line) for line in log.path.read_text().splitlines()]
    rows[0]["outcome"] = "rejected"
    log.path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n")
    status = log.verify()
    assert not status.ok
    assert any("content altered" in p for p in status.problems)


def test_verify_detects_deletion(tmp_path: Path) -> None:
    log = _log(tmp_path)
    for a in ("a", "b", "c"):
        log.record(_rec(a))
    lines = log.path.read_text().splitlines()
    log.path.write_text("\n".join([lines[0], lines[2]]) + "\n")  # drop the middle
    assert not log.verify().ok


def test_chain_resumes_across_reopen(tmp_path: Path) -> None:
    AuditLog(tmp_path / "audit.jsonl").record(_rec("first"))
    reopened = AuditLog(tmp_path / "audit.jsonl")  # new instance, same file
    reopened.record(_rec("second"))
    status = reopened.verify()
    assert status.ok and status.length == 2


def test_correlation_id_is_propagated(tmp_path: Path) -> None:
    obs.set_correlation_id("trace-abc")
    rec = AuditLog(tmp_path / "audit.jsonl").record(_rec("create-loan"))
    assert rec.correlation_id == "trace-abc"


def test_api_returns_correlation_header_and_verify(client: TestClient) -> None:
    r = client.post("/actions/flag-limit-breach")
    assert "X-Correlation-ID" in r.headers
    assert client.get("/audit/verify").json()["ok"] is True
