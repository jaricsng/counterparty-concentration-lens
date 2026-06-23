"""Pydantic request models for the action API.

Input validation at the boundary (types, required fields, enums) happens here;
the deeper data-quality and referential rules are enforced by SHACL in the
action layer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Actor = Field(default="anonymous", description="who is performing the action")
Role = Field(default="group_risk", description="caller role (enforced in M3)")


class EntityIn(BaseModel):
    entity_id: str
    name: str
    counterparty_type: Literal["bank", "corporate", "nbfi", "government"]
    sector: str
    parent_id: str | None = None
    eligible_capital: int | None = None
    annual_revenue: int | None = None
    actor: str = Actor
    role: str = Role


class LoanIn(BaseModel):
    loan_id: str
    lender_id: str
    borrower_id: str
    principal: int = Field(gt=0)
    currency: str = "SGD"
    actor: str = Actor
    role: str = Role


class GuarantyIn(BaseModel):
    guarantee_id: str
    guarantor_id: str
    guaranteed_loan_id: str
    amount: int = Field(gt=0)
    currency: str = "SGD"
    actor: str = Actor
    role: str = Role


class CollateralIn(BaseModel):
    collateral_id: str
    description: str
    pledged_by_id: str
    secures_loan_ids: list[str] = Field(min_length=1)
    issuer_id: str | None = None
    actor: str = Actor
    role: str = Role


class LimitIn(BaseModel):
    limit_id: str
    entity_id: str
    limit_amount: int = Field(gt=0)
    currency: str = "SGD"
    actor: str = Actor
    role: str = Role


class UpdateAmountIn(BaseModel):
    subject_id: str
    predicate: Literal["principalAmount", "limitAmount", "guaranteedAmount"]
    new_amount: int = Field(gt=0)
    actor: str = Actor
    role: str = Role


class DeactivateIn(BaseModel):
    subject_id: str
    kind: Literal["entity", "loan", "guaranty", "collateral", "limit"]
    actor: str = Actor
    role: str = Role


class ActionOut(BaseModel):
    accepted: bool
    action: str
    subject: str
    reason: str
    flags: list[str] = []
