"""Bring-your-own *test* data: read user CSVs into the canonical Lens schema.

Tier 1 — the user fills the documented templates (``templates/``); we read them
directly. Tier 2 — the user's CSVs have different column names, so a small YAML
mapping renames columns and normalises values before we read them.

This module only *reads and maps* rows into the canonical shape. Validation,
the per-row report, the load, and the audit happen on the guarded M2 import path
(``lens_m2.importer``) — bring-your-own data is just another guarded write.

> Synthetic / sample TEST data only — never real, production, or customer data.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

# Canonical columns per source table (the templates' shape).
COLUMNS: dict[str, list[str]] = {
    "entities": [
        "entity_id",
        "entity_name",
        "counterparty_type",
        "sector",
        "parent_entity_id",
        "eligible_capital",
        "annual_revenue",
        "country",
        "rating",
    ],
    "loans": [
        "loan_id",
        "lender_entity_id",
        "borrower_entity_id",
        "exposure_amount",
        "currency",
        "status",
        "maturity_years",
    ],
    "guarantees": [
        "guarantee_id",
        "guarantor_entity_id",
        "beneficiary_loan_id",
        "amount",
        "currency",
    ],
    "collateral": [
        "collateral_id",
        "collateral_type",
        "pledged_by_entity_id",
        "securing_loan_id",
        "issuer_entity_id",
        "collateral_value",
        "haircut_pct",
    ],
    "limits": ["limit_id", "entity_id", "single_name_limit", "currency"],
}

# Required (non-nullable) canonical columns per table.
REQUIRED: dict[str, list[str]] = {
    "entities": ["entity_id", "entity_name", "counterparty_type", "sector"],
    "loans": [
        "loan_id",
        "lender_entity_id",
        "borrower_entity_id",
        "exposure_amount",
        "currency",
        "status",
    ],
    "guarantees": [
        "guarantee_id",
        "guarantor_entity_id",
        "beneficiary_loan_id",
        "amount",
        "currency",
    ],
    "collateral": ["collateral_id", "collateral_type", "pledged_by_entity_id", "securing_loan_id"],
    "limits": ["limit_id", "entity_id", "single_name_limit", "currency"],
}

_FILES = {t: f"{t}.csv" for t in COLUMNS}


class ByodError(ValueError):
    """Raised for a malformed source folder or mapping (fail loud, never silent)."""


@dataclass(frozen=True)
class TableMapping:
    file: str
    columns: dict[str, str] = field(default_factory=dict)  # canonical_target -> their_column
    value_map: dict[str, dict[str, str]] = field(default_factory=dict)


def load_mapping(path: Path) -> dict[str, TableMapping]:
    """Parse a Tier-2 mapping YAML into per-table mappings."""
    import yaml

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, TableMapping] = {}
    for table, spec in raw.items():
        if table not in COLUMNS:
            raise ByodError(f"mapping refers to unknown table '{table}'")
        out[table] = TableMapping(
            file=spec.get("file", _FILES[table]),
            columns=spec.get("columns", {}),
            value_map=spec.get("value_map", {}),
        )
    return out


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def _map_table(
    table: str, rows: list[dict[str, str]], mapping: TableMapping
) -> list[dict[str, str]]:
    headers = set(rows[0].keys()) if rows else set()
    for target, source in mapping.columns.items():
        if rows and source not in headers:
            raise ByodError(
                f"{table}: mapped column '{target}' -> '{source}' not found in {mapping.file}"
            )
    for required in REQUIRED[table]:
        mapped = required in mapping.columns
        present = required in headers
        if rows and not mapped and not present:
            raise ByodError(
                f"{table}: required field '{required}' is not mapped and not in {mapping.file}"
            )
    out: list[dict[str, str]] = []
    for row in rows:
        canonical: dict[str, str] = {}
        for target in COLUMNS[table]:
            source = mapping.columns.get(target, target)
            value = row.get(source, "")
            vmap = mapping.value_map.get(target)
            if vmap and value in vmap:
                value = vmap[value]
            canonical[target] = value
        out.append(canonical)
    return out


def read_source(
    source: Path, mapping: dict[str, TableMapping] | None = None
) -> dict[str, list[dict[str, str]]]:
    """Read a source folder into canonical rows per table (entities/loans/…).

    Missing optional tables (e.g. no guarantees) yield an empty list. ``entities``
    and ``loans`` must be present.
    """
    source = Path(source)
    if not source.is_dir():
        raise ByodError(f"source is not a directory: {source}")
    mapping = mapping or {}
    out: dict[str, list[dict[str, str]]] = {}
    for table in COLUMNS:
        tmap = mapping.get(table)
        filename = tmap.file if tmap else _FILES[table]
        path = source / filename
        if not path.exists():
            if table in ("entities", "loans"):
                raise ByodError(f"required source file missing: {filename}")
            out[table] = []
            continue
        rows = _read_csv(path)
        out[table] = (
            _map_table(table, rows, tmap) if tmap else _check_canonical(table, rows, filename)
        )
    return out


def _check_canonical(table: str, rows: list[dict[str, str]], filename: str) -> list[dict[str, str]]:
    if rows:
        headers = set(rows[0].keys())
        missing = [c for c in REQUIRED[table] if c not in headers]
        if missing:
            raise ByodError(f"{filename}: missing required column(s): {missing}")
    # Normalise to the full canonical column set (fill absent optional columns).
    return [{c: row.get(c, "") for c in COLUMNS[table]} for row in rows]
