"""Read/write the synthetic source tables as CSV.

The CSV column names follow the canonical import schema in
docs/data-import.md §2, so the generated files double as bring-your-own-test-data
templates later. A shared collateral item that secures several loans is written
as one row per (collateral, loan) pair.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .spec import Collateral, DatasetSpec, Entity, Guarantee, Limit, Loan

TABLES = ("entities", "loans", "guarantees", "collateral", "limits")


def _w(value: object) -> str:
    return "" if value is None else str(value)


def write_dataset(spec: DatasetSpec, out_dir: Path) -> dict[str, int]:
    """Write the five source tables to ``out_dir``; return per-table row counts."""
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}

    with (out_dir / "entities.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(
            [
                "entity_id",
                "entity_name",
                "counterparty_type",
                "sector",
                "parent_entity_id",
                "eligible_capital",
                "annual_revenue",
                "country",
                "rating",
            ]
        )
        for e in spec.entities:
            wr.writerow(
                [
                    e.entity_id,
                    e.name,
                    e.counterparty_type,
                    e.sector,
                    _w(e.parent_id),
                    _w(e.eligible_capital),
                    _w(e.annual_revenue),
                    _w(e.country),
                    _w(e.rating),
                ]
            )
        counts["entities"] = len(spec.entities)

    with (out_dir / "loans.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(
            [
                "loan_id",
                "lender_entity_id",
                "borrower_entity_id",
                "exposure_amount",
                "currency",
                "status",
                "maturity_years",
            ]
        )
        for ln in spec.loans:
            wr.writerow(
                [
                    ln.loan_id,
                    ln.lender_id,
                    ln.borrower_id,
                    ln.principal,
                    ln.currency,
                    ln.status,
                    ln.maturity_years,
                ]
            )
        counts["loans"] = len(spec.loans)

    with (out_dir / "guarantees.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(
            ["guarantee_id", "guarantor_entity_id", "beneficiary_loan_id", "amount", "currency"]
        )
        for g in spec.guarantees:
            wr.writerow(
                [g.guarantee_id, g.guarantor_id, g.guaranteed_loan_id, g.amount, g.currency]
            )
        counts["guarantees"] = len(spec.guarantees)

    with (out_dir / "collateral.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(
            [
                "collateral_id",
                "collateral_type",
                "pledged_by_entity_id",
                "securing_loan_id",
                "issuer_entity_id",
                "collateral_value",
                "haircut_pct",
            ]
        )
        rows = 0
        for c in spec.collateral:
            for loan_id in c.secures_loan_ids:  # one row per secured loan
                wr.writerow(
                    [
                        c.collateral_id,
                        c.description,
                        c.pledged_by_id,
                        loan_id,
                        _w(c.issuer_id),
                        _w(c.collateral_value),
                        c.haircut_pct,
                    ]
                )
                rows += 1
        counts["collateral"] = rows

    with (out_dir / "limits.csv").open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["limit_id", "entity_id", "single_name_limit", "currency"])
        for lim in spec.limits:
            wr.writerow([lim.limit_id, lim.entity_id, lim.limit_amount, lim.currency])
        counts["limits"] = len(spec.limits)

    return counts


def _opt(value: str) -> str | None:
    return value if value else None


def read_dataset(in_dir: Path, name: str) -> DatasetSpec:
    """Read the five source tables from ``in_dir`` back into a DatasetSpec."""
    with (in_dir / "entities.csv").open(encoding="utf-8") as fh:
        entities = [
            Entity(
                entity_id=r["entity_id"],
                name=r["entity_name"],
                counterparty_type=r["counterparty_type"],
                sector=r["sector"],
                parent_id=_opt(r["parent_entity_id"]),
                eligible_capital=int(r["eligible_capital"]) if r["eligible_capital"] else None,
                annual_revenue=int(r["annual_revenue"]) if r["annual_revenue"] else None,
                country=_opt(r.get("country", "")),
                rating=_opt(r.get("rating", "")),
            )
            for r in csv.DictReader(fh)
        ]

    with (in_dir / "loans.csv").open(encoding="utf-8") as fh:
        loans = [
            Loan(
                loan_id=r["loan_id"],
                lender_id=r["lender_entity_id"],
                borrower_id=r["borrower_entity_id"],
                principal=int(r["exposure_amount"]),
                currency=r["currency"],
                status=r["status"],
                maturity_years=int(r["maturity_years"]) if r.get("maturity_years") else 3,
            )
            for r in csv.DictReader(fh)
        ]

    with (in_dir / "guarantees.csv").open(encoding="utf-8") as fh:
        guarantees = [
            Guarantee(
                guarantee_id=r["guarantee_id"],
                guarantor_id=r["guarantor_entity_id"],
                guaranteed_loan_id=r["beneficiary_loan_id"],
                amount=int(r["amount"]),
                currency=r["currency"],
            )
            for r in csv.DictReader(fh)
        ]

    # Re-group collateral rows (one per secured loan) back into items, keeping
    # first-seen order.
    attrs: dict[str, tuple[str, str, str | None, int | None, int]] = {}
    secured: dict[str, list[str]] = {}
    with (in_dir / "collateral.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            cid = r["collateral_id"]
            if cid not in attrs:
                attrs[cid] = (
                    r["collateral_type"],
                    r["pledged_by_entity_id"],
                    _opt(r["issuer_entity_id"]),
                    int(r["collateral_value"]) if r.get("collateral_value") else None,
                    int(r["haircut_pct"]) if r.get("haircut_pct") else 0,
                )
                secured[cid] = []
            secured[cid].append(r["securing_loan_id"])
    collateral = [
        Collateral(
            collateral_id=cid,
            description=attrs[cid][0],
            pledged_by_id=attrs[cid][1],
            secures_loan_ids=tuple(secured[cid]),
            issuer_id=attrs[cid][2],
            collateral_value=attrs[cid][3],
            haircut_pct=attrs[cid][4],
        )
        for cid in attrs
    ]

    with (in_dir / "limits.csv").open(encoding="utf-8") as fh:
        limits = [
            Limit(
                limit_id=r["limit_id"],
                entity_id=r["entity_id"],
                limit_amount=int(r["single_name_limit"]),
                currency=r["currency"],
            )
            for r in csv.DictReader(fh)
        ]

    return DatasetSpec(name, entities, loans, guarantees, collateral, limits)
