"""Run the concentration-metric SPARQL queries and parse their results.

A thin typed layer over the ``.rq`` files in ``queries/`` (§3 / §9 of
docs/concentration-metrics.md), reusing the same :class:`QueryRunner` protocol
as :mod:`lens_m0.concentration` so it works against rdflib or Fuseki.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from .concentration import QueryRunner
from .queries import load_query, set_values

DEFAULT_NBFI = "https://lens.example/id/LE-0030"
DEFAULT_UBO_MEMBER = "https://lens.example/id/LE-0021"


def _dec(value: str | None) -> Decimal:
    if value is None or value == "":
        return Decimal(0)
    return Decimal(value)


def _local(iri: str | None) -> str:
    return iri.rsplit("/", 1)[-1] if iri else ""


@dataclass(frozen=True)
class DirectConnected:
    """A metric reported both ways: direct-only vs connected."""

    direct: Decimal
    connected: Decimal


def hhi(runner: QueryRunner, queries_dir: Path) -> DirectConnected:
    row = runner.select(load_query(queries_dir, "hhi"))[0]
    return DirectConnected(_dec(row.get("directHHI")), _dec(row.get("connectedHHI")))


def cr10(runner: QueryRunner, queries_dir: Path) -> DirectConnected:
    row = runner.select(load_query(queries_dir, "cr10"))[0]
    return DirectConnected(_dec(row.get("directCR10")), _dec(row.get("connectedCR10")))


def connected_by_owner(runner: QueryRunner, queries_dir: Path) -> dict[str, Decimal]:
    rows = runner.select(load_query(queries_dir, "connected_exposure_by_owner"))
    return {_local(r.get("owner")): _dec(r.get("exposure")) for r in rows}


def sector_shares(runner: QueryRunner, queries_dir: Path) -> dict[str, Decimal]:
    rows = runner.select(load_query(queries_dir, "sector_concentration"))
    total = sum((_dec(r.get("exposure")) for r in rows), Decimal(0))
    if total == 0:
        return {}
    return {str(r.get("sector")): _dec(r.get("exposure")) / total for r in rows}


def _dimension_shares(runner: QueryRunner, queries_dir: Path, dim: str) -> dict[str, Decimal]:
    """Share of attributed exposure grouped by a risk-owner attribute (country/rating)."""
    rows = runner.select(load_query(queries_dir, f"{dim}_concentration"))
    total = sum((_dec(r.get("exposure")) for r in rows), Decimal(0))
    if total == 0:
        return {}
    return {str(r.get(dim)): _dec(r.get("exposure")) / total for r in rows}


def country_shares(runner: QueryRunner, queries_dir: Path) -> dict[str, Decimal]:
    return _dimension_shares(runner, queries_dir, "country")


def rating_shares(runner: QueryRunner, queries_dir: Path) -> dict[str, Decimal]:
    return _dimension_shares(runner, queries_dir, "rating")


@dataclass(frozen=True)
class WwrFlag:
    loan: str
    borrower: str
    borrower_name: str | None
    collateral: str
    issuer: str
    issuer_name: str | None
    group: str


def wrong_way_risk(runner: QueryRunner, queries_dir: Path) -> list[WwrFlag]:
    rows = runner.select(load_query(queries_dir, "wrong_way_risk"))
    return [
        WwrFlag(
            loan=_local(r.get("loan")),
            borrower=_local(r.get("borrower")),
            borrower_name=r.get("borrowerName"),
            collateral=_local(r.get("collateral")),
            issuer=_local(r.get("issuer")),
            issuer_name=r.get("issuerName"),
            group=_local(r.get("group")),
        )
        for r in rows
    ]


@dataclass(frozen=True)
class WatchlistRow:
    entity: str
    entity_name: str | None
    connected: Decimal
    limit: Decimal
    utilisation: Decimal
    band: str


def watchlist(runner: QueryRunner, queries_dir: Path) -> list[WatchlistRow]:
    rows = runner.select(load_query(queries_dir, "watchlist"))
    return [
        WatchlistRow(
            entity=_local(r.get("entity")),
            entity_name=r.get("entityName"),
            connected=_dec(r.get("connected")),
            limit=_dec(r.get("limit")),
            utilisation=_dec(r.get("utilisation")),
            band=r.get("band") or "",
        )
        for r in rows
    ]


@dataclass(frozen=True)
class UboMember:
    member: str
    member_name: str | None
    is_ubo: bool
    connected: Decimal
    limit: Decimal
    utilisation: Decimal
    band: str


def ubo_aggregation(
    runner: QueryRunner, queries_dir: Path, member_iri: str = DEFAULT_UBO_MEMBER
) -> list[UboMember]:
    query = set_values(load_query(queries_dir, "ubo_aggregation"), "cp", member_iri)
    rows = runner.select(query)
    return [
        UboMember(
            member=_local(r.get("member")),
            member_name=r.get("memberName"),
            is_ubo=str(r.get("isUBO")).lower() in {"true", "1"},
            connected=_dec(r.get("connected")),
            limit=_dec(r.get("limit")),
            utilisation=_dec(r.get("utilisation")),
            band=r.get("band") or "",
        )
        for r in rows
    ]


@dataclass(frozen=True)
class CascadeRow:
    contribution_type: str
    counterparty: str
    counterparty_name: str | None
    amount: Decimal
    via: str


def nbfi_cascade(
    runner: QueryRunner, queries_dir: Path, nbfi_iri: str = DEFAULT_NBFI
) -> list[CascadeRow]:
    query = set_values(load_query(queries_dir, "nbfi_cascade"), "nbfi", nbfi_iri)
    rows = runner.select(query)
    return [
        CascadeRow(
            contribution_type=r.get("contributionType") or "",
            counterparty=_local(r.get("counterparty")),
            counterparty_name=r.get("counterpartyName"),
            amount=_dec(r.get("amount")),
            via=_local(r.get("via")),
        )
        for r in rows
    ]
