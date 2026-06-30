"""Deterministic stress / scenario engine — named shocks re-derive every metric.

DELIBERATELY DETERMINISTIC (parametric shocks), **not** a Monte-Carlo stress engine:
each scenario is a pure transform of the dataset; we then re-derive the full metric
set (concentration, net exposure, expected loss, capital) and compare base vs shocked.
An honest "what-if" overlay, not a simulated loss distribution or a macro model.
See docs/concentration-metrics.md §10 for what stays out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from . import credit_risk, metrics
from .spec import DatasetSpec

# Rating scale, best -> worst. Downgrades move down this list (floored at CCC).
RATING_ORDER: tuple[str, ...] = ("AAA", "AA", "A", "BBB", "BB", "B", "CCC")


def notch_down(rating: str | None, notches: int) -> str | None:
    """Downgrade a rating by ``notches`` grades (unknown/None ratings pass through)."""
    if rating not in RATING_ORDER:
        return rating
    idx = min(len(RATING_ORDER) - 1, RATING_ORDER.index(rating) + notches)
    return RATING_ORDER[idx]


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    description: str


SCENARIOS: dict[str, Scenario] = {
    "base": Scenario("base", "Base (no shock)", "The dataset as-is — the comparison baseline."),
    "nbfi_downgrade": Scenario(
        "nbfi_downgrade",
        "NBFI downgrade (−2 notches)",
        "Downgrade every non-bank financial institution by two rating grades "
        "(an Archegos-style NBFI stress) — PD, expected loss and capital jump.",
    ),
    "broad_downgrade": Scenario(
        "broad_downgrade",
        "Broad downgrade (−1 notch)",
        "Downgrade every counterparty by one grade (a system-wide credit deterioration).",
    ),
    "haircut_plus20": Scenario(
        "haircut_plus20",
        "Collateral haircuts +20pp",
        "Add 20 percentage points to every collateral haircut (a liquidity/quality "
        "shock) — eligible mitigant falls, so net EAD and expected loss rise.",
    ),
    "cre_downturn": Scenario(
        "cre_downturn",
        "CRE downturn (−1 notch, +25% draw)",
        "Commercial-real-estate names downgraded one grade and their drawn exposure "
        "up 25% (a sector downturn) — concentration and loss shift toward CRE.",
    ),
}

_CRE = "commercial real estate"


def apply_scenario(spec: DatasetSpec, key: str) -> DatasetSpec:
    """Return a NEW dataset with the named shock applied (the input is unchanged)."""
    if key not in SCENARIOS:
        raise KeyError(f"unknown scenario '{key}'")
    if key == "base":
        return spec

    entities = spec.entities
    loans = spec.loans
    collateral = spec.collateral

    if key == "nbfi_downgrade":
        entities = [
            replace(e, rating=notch_down(e.rating, 2)) if e.counterparty_type == "nbfi" else e
            for e in entities
        ]
    elif key == "broad_downgrade":
        entities = [replace(e, rating=notch_down(e.rating, 1)) for e in entities]
    elif key == "haircut_plus20":  # gitleaks:allow — scenario key, not a secret
        collateral = [replace(c, haircut_pct=min(100, c.haircut_pct + 20)) for c in collateral]
    elif key == "cre_downturn":
        cre_ids = {e.entity_id for e in entities if e.sector == _CRE}
        entities = [
            replace(e, rating=notch_down(e.rating, 1)) if e.entity_id in cre_ids else e
            for e in entities
        ]
        loans = [
            replace(ln, principal=int(ln.principal * 5 // 4)) if ln.borrower_id in cre_ids else ln
            for ln in loans
        ]

    return replace(spec, entities=entities, loans=loans, collateral=collateral)


@dataclass(frozen=True)
class StressSnapshot:
    scenario: str
    total_ead: Decimal
    total_el: Decimal
    total_capital: Decimal
    capital_pct_eligible: Decimal
    top_rating: str
    top_rating_share: Decimal
    watchlist_red: int
    watchlist_amber: int


def snapshot(spec: DatasetSpec, key: str = "base") -> StressSnapshot:
    """Re-derive the headline metrics for a (possibly shocked) dataset."""
    shocked = apply_scenario(spec, key)
    summary = credit_risk.portfolio_summary(shocked)
    shares = metrics.rating_shares(shocked)
    top_rating, top_share = (
        max(shares.items(), key=lambda kv: kv[1]) if shares else ("-", Decimal(0))
    )
    bands = [u.band for u in metrics.utilisations(shocked)]
    return StressSnapshot(
        scenario=key,
        total_ead=summary.total_ead,
        total_el=summary.total_el,
        total_capital=summary.total_capital,
        capital_pct_eligible=summary.capital_as_pct_of_eligible,
        top_rating=top_rating,
        top_rating_share=top_share,
        watchlist_red=bands.count("red"),
        watchlist_amber=bands.count("amber"),
    )


def compare(spec: DatasetSpec, key: str) -> tuple[StressSnapshot, StressSnapshot]:
    """Return (base, shocked) headline snapshots for a side-by-side delta."""
    return snapshot(spec, "base"), snapshot(spec, key)


@dataclass(frozen=True)
class ExpectedLossDelta:
    entity: str
    rating_base: str
    rating_shocked: str
    el_base: Decimal
    el_shocked: Decimal

    @property
    def delta(self) -> Decimal:
        return self.el_shocked - self.el_base


def expected_loss_deltas(spec: DatasetSpec, key: str) -> list[ExpectedLossDelta]:
    """Per-counterparty expected-loss base vs shocked, sorted by the increase."""
    base = {r.entity: r for r in credit_risk.portfolio_credit_risk(spec)}
    shocked = {r.entity: r for r in credit_risk.portfolio_credit_risk(apply_scenario(spec, key))}
    rows = [
        ExpectedLossDelta(e, base[e].rating, shocked[e].rating, base[e].el, shocked[e].el)
        for e in base
    ]
    return sorted(rows, key=lambda d: d.delta, reverse=True)
