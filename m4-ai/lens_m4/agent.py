"""Grounded NL query agent: generate -> safety-check -> execute -> scope -> summarise.

The single entry point the app calls. It never executes SPARQL that fails the
safety check, and applies the M3 visible-group scope to row results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from . import nl2sparql, ollama
from .safety import is_safe


class Runner(Protocol):
    def select(self, query: str) -> list[dict[str, str | None]]: ...


@dataclass(frozen=True)
class AnswerResult:
    question: str
    answered: bool
    engine: str  # template | ollama | none
    intent: str
    sparql: str
    summary: str
    rows: list[dict[str, str | None]] = field(default_factory=list)
    safe: bool = True


def _local(iri: str | None) -> str:
    return iri.rsplit("/", 1)[-1] if iri else ""


def _scope_rows(
    rows: list[dict[str, str | None]],
    visible_groups: set[str] | None,
    member_to_head: dict[str, str] | None,
) -> list[dict[str, str | None]]:
    """Drop rows whose entity/owner is not in the caller's visible group set."""
    if visible_groups is None:
        return rows
    member_to_head = member_to_head or {}
    kept = []
    for row in rows:
        ids = [_local(row.get(k)) for k in ("owner", "entity", "head") if row.get(k)]
        heads = {member_to_head.get(i, i) for i in ids}
        if not ids or heads & visible_groups:
            kept.append(row)
    return kept


def _money(value: str | None) -> str:
    return f"SGD {Decimal(value or 0) / 1_000_000:.1f}M"


def _summarise(intent: str, rows: list[dict[str, str | None]], params: dict[str, str]) -> str:
    if intent == "exposure_to_group":
        connected = rows[0].get("connected") if rows else "0"
        return f"Connected exposure to {params.get('group', 'the group')}: {_money(connected)}."
    if intent == "top_counterparties":
        names_amounts = ", ".join(
            f"{r.get('ownerName') or _local(r.get('owner'))} ({_money(r.get('exposure'))})"
            for r in rows[:3]
        )
        if not rows:
            return "No exposures."
        return f"Top counterparties by connected exposure: {names_amounts}."
    if intent == "near_limit":
        if not rows:
            return "None near limit."
        near = ", ".join(r.get("entityName") or _local(r.get("entity")) for r in rows)
        return f"{len(rows)} name(s) at/above the threshold: {near}."
    if intent == "guarantee_chains":
        return f"{len(rows)} guarantee(s) touch this group." if rows else "No guarantees found."
    if intent == "sector_concentration":
        sector_total = sum((Decimal(r.get("exposure") or 0) for r in rows), Decimal(0))
        top_sector = max(rows, key=lambda r: Decimal(r.get("exposure") or 0)) if rows else None
        if top_sector is not None and sector_total:
            share = float(Decimal(top_sector.get("exposure") or 0) / sector_total) * 100
            name = top_sector.get("sector")
            return f"Largest sector: {name} at {share:.0f}% of connected exposure."
        return "No sector data."
    if intent in ("country_concentration", "rating_concentration"):
        dim = "country" if intent == "country_concentration" else "rating"
        total = sum((Decimal(r.get("exposure") or 0) for r in rows), Decimal(0))
        top = max(rows, key=lambda r: Decimal(r.get("exposure") or 0)) if rows else None
        if top is not None and total:
            share = float(Decimal(top.get("exposure") or 0) / total) * 100
            return f"Largest {dim}: {top.get(dim)} at {share:.0f}% of connected exposure."
        return f"No {dim} data."
    if intent == "wrong_way_risk":
        return (
            f"{len(rows)} structural wrong-way-risk flag(s)."
            if rows
            else "No wrong-way-risk flags."
        )
    if intent == "net_exposure":
        if not rows:
            return "No counterparties have eligible collateral."
        top = rows[0]
        name = top.get("entityName") or "a counterparty"
        return (
            f"{len(rows)} name(s) collateralised. Largest net (post-collateral): "
            f"{name} {_money(top.get('gross'))} gross -> {_money(top.get('net'))} net."
        )
    return f"{len(rows)} row(s)."


def answer(
    question: str,
    runner: Runner,
    *,
    label_index: dict[str, str] | None = None,
    visible_groups: set[str] | None = None,
    member_to_head: dict[str, str] | None = None,
    allow_ollama: bool = True,
) -> AnswerResult:
    """Answer a natural-language question, read-only and role-scoped."""
    nlq = None
    if allow_ollama and ollama.is_available():
        sparql = ollama.generate(question)
        if sparql and is_safe(sparql).safe:
            nlq = nl2sparql.NLQuery(question, "ollama", "ollama", sparql)
    if nlq is None:
        nlq = nl2sparql.generate(question, label_index)
    if nlq is None:
        return AnswerResult(
            question,
            False,
            "none",
            "unsupported",
            "",
            "I can answer questions about exposure to a group, top counterparties, names "
            "near their limit, guarantee chains, sector concentration, or wrong-way risk.",
        )

    safety = is_safe(nlq.sparql)
    if not safety.safe:
        return AnswerResult(
            question,
            False,
            nlq.engine,
            nlq.intent,
            nlq.sparql,
            f"Generated query rejected by the safety check: {safety.reason}.",
            safe=False,
        )

    rows = _scope_rows(runner.select(nlq.sparql), visible_groups, member_to_head)
    return AnswerResult(
        question,
        True,
        nlq.engine,
        nlq.intent,
        nlq.sparql,
        _summarise(nlq.intent, rows, nlq.params),
        rows=rows,
    )
