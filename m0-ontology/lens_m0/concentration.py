"""High-level concentration calculations over any SPARQL backend.

A :class:`QueryRunner` is anything that can run a SELECT and return rows as
stringified bindings — both :class:`lens_m0.graph.GraphRunner` (rdflib) and
:class:`lens_m0.fuseki.FusekiRunner` (HTTP) satisfy it, so the demo and the
tests share one code path.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from .queries import load_query, set_group_head


class QueryRunner(Protocol):
    """Minimal SPARQL SELECT interface shared by the rdflib and Fuseki backends."""

    def select(self, query: str) -> list[dict[str, str | None]]: ...


def _to_decimal(value: str | None) -> Decimal:
    if value is None or value == "":
        return Decimal(0)
    return Decimal(value)


def _to_bool(value: str | None) -> bool:
    return str(value).strip().lower() in {"true", "1"}


@dataclass(frozen=True)
class Headline:
    """The money-shot headline numbers for one counterparty group."""

    group_head: str
    direct_head_only: Decimal
    direct_group: Decimal
    connected_total: Decimal
    group_limit: Decimal
    limit_breached: bool

    @property
    def hidden_exposure(self) -> Decimal:
        """Exposure the connected view reveals beyond the single-entity view."""
        return self.connected_total - self.direct_head_only


@dataclass(frozen=True)
class Contribution:
    """One contributing path to a group's connected exposure."""

    contribution_type: str
    counterparty: str
    counterparty_name: str | None
    amount: Decimal
    via: str
    via_detail: str | None


def headline(runner: QueryRunner, queries_dir: Path, group_head: str) -> Headline:
    """Compute the direct-vs-connected headline for ``group_head``."""
    query = set_group_head(load_query(queries_dir, "direct_vs_connected"), group_head)
    rows = runner.select(query)
    if not rows:
        raise RuntimeError("direct_vs_connected query returned no rows")
    row = rows[0]
    return Headline(
        group_head=group_head,
        direct_head_only=_to_decimal(row.get("directHeadOnly")),
        direct_group=_to_decimal(row.get("directGroup")),
        connected_total=_to_decimal(row.get("connectedTotal")),
        group_limit=_to_decimal(row.get("groupLimit")),
        limit_breached=_to_bool(row.get("limitBreached")),
    )


def breakdown(runner: QueryRunner, queries_dir: Path, group_head: str) -> list[Contribution]:
    """Return the contributing paths to ``group_head``'s connected exposure."""
    query = set_group_head(load_query(queries_dir, "concentration_breakdown"), group_head)
    rows = runner.select(query)
    return [
        Contribution(
            contribution_type=row.get("contributionType") or "",
            counterparty=row.get("counterparty") or "",
            counterparty_name=row.get("counterpartyName"),
            amount=_to_decimal(row.get("amount")),
            via=row.get("via") or "",
            via_detail=row.get("viaDetail"),
        )
        for row in rows
    ]
