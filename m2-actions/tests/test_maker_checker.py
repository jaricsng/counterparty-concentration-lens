"""Maker-checker (four-eyes) approval workflow (M2)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from lens_m1 import datasets, rdfize
from lens_m2.actions import ActionService
from lens_m2.audit import AuditLog
from lens_m2.config import load_settings
from lens_m2.derived import connected_exposure
from lens_m2.store import InMemoryStore

NIMBUS = "https://lens.example/id/LE-0030"


def _service() -> ActionService:
    cfg = load_settings()
    store = InMemoryStore(rdfize.build_graph(datasets.get_dataset("stressed")))
    return ActionService(store, AuditLog(Path(tempfile.mkdtemp()) / "a.jsonl"), cfg.shapes_path)


def test_submit_creates_pending_and_applies_nothing() -> None:
    svc = _service()
    before = connected_exposure(svc._store, NIMBUS)
    pc = svc.submit_deactivation(
        subject_id="GTY-2002", kind="guaranty", maker="bob", maker_role="relationship_manager"
    )
    assert pc.status == "pending" and [p.id for p in svc.pending_changes()] == [pc.id]
    assert connected_exposure(svc._store, NIMBUS) == before  # nothing written on submit


def test_four_eyes_and_role_are_enforced() -> None:
    svc = _service()
    pc = svc.submit_deactivation(
        subject_id="GTY-2002", kind="guaranty", maker="bob", maker_role="relationship_manager"
    )
    assert not svc.approve(pc.id, checker="bob", checker_role="group_risk").accepted  # self
    assert not svc.approve(pc.id, checker="carol", checker_role="relationship_manager").accepted
    assert svc.pending_changes()  # still pending after denied approvals


def test_approval_applies_change_and_clears_queue() -> None:
    svc = _service()
    before = connected_exposure(svc._store, NIMBUS)
    pc = svc.submit_deactivation(
        subject_id="GTY-2002", kind="guaranty", maker="bob", maker_role="relationship_manager"
    )
    res = svc.approve(pc.id, checker="dana", checker_role="group_risk")
    assert res.accepted
    assert connected_exposure(svc._store, NIMBUS) < before  # applied on approval
    assert svc.pending_changes() == []


def test_reject_discards_and_writes_nothing() -> None:
    svc = _service()
    before = connected_exposure(svc._store, NIMBUS)
    pc = svc.submit_deactivation(
        subject_id="GTY-2002", kind="guaranty", maker="bob", maker_role="relationship_manager"
    )
    assert svc.reject(pc.id, checker="dana", checker_role="group_risk", reason="no").accepted
    assert connected_exposure(svc._store, NIMBUS) == before
    assert svc.pending_changes() == []


def test_submit_and_decisions_are_audited() -> None:
    svc = _service()
    pc = svc.submit_deactivation(
        subject_id="GTY-2002", kind="guaranty", maker="bob", maker_role="relationship_manager"
    )
    svc.approve(pc.id, checker="dana", checker_role="group_risk")
    actions = {e["action"] for e in svc._audit.entries()}
    assert {"maker-submit", "maker-approve"} <= actions
