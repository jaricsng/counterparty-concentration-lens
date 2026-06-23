"""M2 verify: validate -> write -> audit; reject pre-write; soft-delete."""

from __future__ import annotations

from decimal import Decimal

from lens_m2.actions import ActionService
from lens_m2.audit import AuditLog
from lens_m2.derived import connected_exposure, wrong_way_risk
from lens_m2.store import InMemoryStore


def _kw(**kw: object) -> dict[str, object]:
    return {"actor": "rm1", "role": "group_risk", **kw}


# --- valid writes are committed + audited ------------------------------------ #


def test_valid_loan_written_and_audited(
    service: ActionService, store: InMemoryStore, audit: AuditLog
) -> None:
    r = service.create_loan(
        **_kw(loan_id="LN-9001", lender_id="LE-0099", borrower_id="LE-0041", principal=1_000_000)
    )
    assert r.accepted
    rows = store.select(
        "PREFIX lens: <https://lens.example/ontology/> "
        "SELECT ?a WHERE { <https://lens.example/id/LN-9001> lens:principalAmount ?a }"
    )
    assert rows and rows[0]["a"] == "1000000"
    entries = audit.entries()
    assert entries[-1]["action"] == "create-loan"
    assert entries[-1]["outcome"] == "accepted"
    assert entries[-1]["actor"] == "rm1"


# --- invalid writes are rejected BEFORE the store changes -------------------- #


def test_self_guaranty_rejected(service: ActionService, store: InMemoryStore) -> None:
    service.create_loan(
        **_kw(loan_id="LN-9001", lender_id="LE-0099", borrower_id="LE-0041", principal=1_000_000)
    )
    r = service.create_guaranty(
        **_kw(
            guarantee_id="GTY-9001",
            guarantor_id="LE-0041",
            guaranteed_loan_id="LN-9001",
            amount=500_000,
        )
    )
    assert not r.accepted
    assert "distinct" in r.reason.lower()
    # Nothing written for the rejected guaranty.
    rows = store.select(
        "PREFIX lens: <https://lens.example/ontology/> "
        "SELECT ?g WHERE { ?g lens:guarantor <https://lens.example/id/LE-0041> }"
    )
    assert rows == []


def test_dangling_borrower_rejected(service: ActionService) -> None:
    r = service.create_loan(
        **_kw(loan_id="LN-9002", lender_id="LE-0099", borrower_id="LE-9999", principal=100)
    )
    assert not r.accepted
    assert "borrower" in r.reason.lower()


def test_negative_amount_rejected(service: ActionService) -> None:
    r = service.create_loan(
        **_kw(loan_id="LN-9003", lender_id="LE-0099", borrower_id="LE-0041", principal=-5)
    )
    assert not r.accepted
    assert "positive" in r.reason.lower()


def test_rejection_is_audited(service: ActionService, audit: AuditLog) -> None:
    service.create_loan(
        **_kw(loan_id="LN-9002", lender_id="LE-0099", borrower_id="LE-9999", principal=100)
    )
    assert audit.entries()[-1]["outcome"] == "rejected"


# --- a loan can breach a connected limit; it is written AND flagged ---------- #


def test_loan_over_limit_written_and_flagged(service: ActionService, store: InMemoryStore) -> None:
    assert connected_exposure(store, "LE-0041") == Decimal("2000000")  # Zenith, within limit
    r = service.create_loan(
        **_kw(loan_id="LN-9100", lender_id="LE-0099", borrower_id="LE-0041", principal=30_000_000)
    )
    assert r.accepted
    assert "limit-breach:LE-0041" in r.flags
    assert connected_exposure(store, "LE-0041") == Decimal("32000000")


# --- soft-delete excludes from metrics but preserves history ----------------- #


def test_deactivate_guaranty_drops_connected(service: ActionService, store: InMemoryStore) -> None:
    assert connected_exposure(store, "LE-0030") == Decimal("47000000")  # Nimbus cascade
    r = service.deactivate(**_kw(subject_id="GTY-2002", kind="guaranty"))
    assert r.accepted
    assert connected_exposure(store, "LE-0030") == Decimal("40000000")  # 7M guaranty removed
    # History preserved: the triples still exist, just marked inactive.
    rows = store.select(
        "PREFIX lens: <https://lens.example/ontology/> "
        "SELECT ?s WHERE { <https://lens.example/id/GTY-2002> lens:status ?s }"
    )
    assert rows[0]["s"] == "inactive"


def test_deactivate_loan_excluded_from_metrics(
    service: ActionService, store: InMemoryStore
) -> None:
    before = connected_exposure(store, "LE-0001")  # Acme
    service.deactivate(**_kw(subject_id="LN-1003", kind="loan"))  # an Acme direct loan
    assert connected_exposure(store, "LE-0001") < before


def test_deactivate_referenced_entity_guarded(service: ActionService) -> None:
    r = service.deactivate(**_kw(subject_id="LE-0001", kind="entity"))
    assert not r.accepted
    assert "referenced" in r.reason.lower()


# --- explicit flag actions --------------------------------------------------- #


def test_flag_limit_breach_reports_reds(service: ActionService, audit: AuditLog) -> None:
    breaches = service.flag_limit_breaches(actor="risk", role="group_risk")
    names = {b.entity for b in breaches}
    assert {"LE-0030", "LE-0001", "LE-0020"} <= names  # Nimbus, Acme, Vortex
    assert any(e["action"] == "flag-limit-breach" for e in audit.entries())


def test_flag_wrong_way_risk(service: ActionService, store: InMemoryStore) -> None:
    flags = service.flag_wrong_way_risk(actor="risk", role="group_risk")
    assert any(f.loan == "LN-1030" and f.issuer == "LE-0010" for f in flags)


def test_deactivating_wwr_collateral_clears_flag(
    service: ActionService, store: InMemoryStore
) -> None:
    assert wrong_way_risk(store)  # present
    service.deactivate(**_kw(subject_id="COL-3002", kind="collateral"))
    assert wrong_way_risk(store) == []
