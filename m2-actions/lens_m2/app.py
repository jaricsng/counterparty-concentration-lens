"""FastAPI surface for the guarded actions.

The sandbox UI (M5) writes ONLY through these endpoints — never directly to
Fuseki — so every mutation is SHACL-validated and audited. A minimal write-role
check is included as a placeholder for the full OPA authorization in M3.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from .actions import ActionResult, ActionService
from .audit import AuditLog
from .config import load_settings
from .models import (
    ActionOut,
    CollateralIn,
    DeactivateIn,
    EntityIn,
    GuarantyIn,
    LimitIn,
    LoanIn,
    UpdateAmountIn,
)
from .store import FusekiStore

# Roles permitted to mutate limits (full role policy lives in M3 / OPA).
_LIMIT_WRITE_ROLES = {"group_risk"}


def _out(result: ActionResult) -> ActionOut:
    return ActionOut(
        accepted=result.accepted,
        action=result.action,
        subject=result.subject,
        reason=result.reason,
        flags=result.flags,
    )


def create_app(service: ActionService, audit: AuditLog) -> FastAPI:
    """Build the API around an injected service (tests pass an in-memory one)."""
    app = FastAPI(
        title="Counterparty Concentration Lens — Actions (M2)",
        description="SHACL-validated, audited write actions on SYNTHETIC data.",
        version="0.1.0",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "note": "synthetic data; guarded write layer"}

    @app.post("/actions/entities", response_model=ActionOut)
    def create_entity(body: EntityIn) -> ActionOut:
        return _out(service.create_entity(**body.model_dump()))

    @app.post("/actions/loans", response_model=ActionOut)
    def create_loan(body: LoanIn) -> ActionOut:
        return _out(service.create_loan(**body.model_dump()))

    @app.post("/actions/record-exposure", response_model=ActionOut)
    def record_exposure(body: LoanIn) -> ActionOut:
        return _out(service.record_exposure(**body.model_dump()))

    @app.post("/actions/guaranties", response_model=ActionOut)
    def create_guaranty(body: GuarantyIn) -> ActionOut:
        return _out(service.create_guaranty(**body.model_dump()))

    @app.post("/actions/collateral", response_model=ActionOut)
    def create_collateral(body: CollateralIn) -> ActionOut:
        return _out(service.create_collateral(**body.model_dump()))

    @app.post("/actions/limits", response_model=ActionOut)
    def create_limit(body: LimitIn) -> ActionOut:
        if body.role not in _LIMIT_WRITE_ROLES:
            raise HTTPException(403, f"role '{body.role}' may not edit limits")
        return _out(service.create_limit(**body.model_dump()))

    @app.post("/actions/update-amount", response_model=ActionOut)
    def update_amount(body: UpdateAmountIn) -> ActionOut:
        if body.predicate == "limitAmount" and body.role not in _LIMIT_WRITE_ROLES:
            raise HTTPException(403, f"role '{body.role}' may not edit limits")
        return _out(service.update_amount(**body.model_dump()))

    @app.post("/actions/deactivate", response_model=ActionOut)
    def deactivate(body: DeactivateIn) -> ActionOut:
        return _out(service.deactivate(**body.model_dump()))

    @app.post("/actions/flag-limit-breach")
    def flag_limit_breach(actor: str = "anonymous", role: str = "group_risk") -> dict[str, Any]:
        breaches = service.flag_limit_breaches(actor=actor, role=role)
        return {
            "breaches": [
                {"entity": b.entity, "connected": str(b.connected), "limit": str(b.limit)}
                for b in breaches
            ]
        }

    @app.post("/actions/flag-wrong-way-risk")
    def flag_wrong_way_risk(actor: str = "anonymous", role: str = "group_risk") -> dict[str, Any]:
        flags = service.flag_wrong_way_risk(actor=actor, role=role)
        return {
            "flags": [
                {"loan": f.loan, "collateral": f.collateral, "issuer": f.issuer, "group": f.group}
                for f in flags
            ]
        }

    @app.get("/audit")
    def audit_log() -> dict[str, Any]:
        return {"entries": audit.entries()}

    return app


def build_default_app() -> FastAPI:  # pragma: no cover - wiring for uvicorn
    """Build the production-shaped app backed by Fuseki (used by `uvicorn`)."""
    settings = load_settings()
    store = FusekiStore(settings.query_url, settings.update_url)
    audit = AuditLog(settings.audit_log_path)
    service = ActionService(store, audit, settings.shapes_path)
    return create_app(service, audit)
