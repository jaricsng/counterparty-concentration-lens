"""Macro / multi-factor correlated stress — deterministic factor model.

DELIBERATELY DETERMINISTIC and clearly labelled — **not** a Monte-Carlo macro
simulation and **not** a calibrated factor-correlation matrix. A named macro
scenario is a vector of **adverse factor intensities** (0..1); each sector has a
**sensitivity** (rating notches at full intensity) to each factor. The two combine
into a per-entity downgrade — so factors move together (correlation is baked into
the named scenario) and hit sectors differently. We then re-derive every metric.

    notches(entity) = round( Σ_factor  intensity[factor] · sensitivity[sector][factor] )

Reuses the rating downgrade machinery (scenarios.notch_down) and the credit-risk /
metrics layers. See docs/ccr-coverage.md for what stays out of scope (simulated
factor paths, an estimated correlation matrix, GVAR/agent-based macro models).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from . import credit_risk, scenarios
from .spec import DatasetSpec

# Macro factors (adverse direction). Intensity 0..1 = none..severe.
FACTORS = ("gdp", "rates", "property", "credit_spread")

# Sector sensitivity = rating notches at full (intensity 1) factor stress.
_SENSITIVITY: dict[str, dict[str, float]] = {
    "commercial real estate": {"property": 3, "gdp": 1, "rates": 1},
    "energy": {"gdp": 2, "credit_spread": 1},
    "financial services": {"rates": 2, "credit_spread": 2, "gdp": 1},
    "technology": {"gdp": 1, "rates": 1},
    "industrials": {"gdp": 1.5, "credit_spread": 0.5},
    "transport & logistics": {"gdp": 1.5},
    "consumer": {"gdp": 1},
    "healthcare": {"gdp": 0.5},
    "government": {},  # resilient
}


@dataclass(frozen=True)
class MacroScenario:
    key: str
    label: str
    description: str
    intensities: dict[str, float]


MACRO_SCENARIOS: dict[str, MacroScenario] = {
    "property_crash": MacroScenario(
        "property_crash",
        "Property crash",
        "Property −30%, mild recession, rates up — commercial real estate is hit hardest.",
        {"property": 1.0, "gdp": 0.6, "rates": 0.3},
    ),
    "rates_shock": MacroScenario(
        "rates_shock",
        "Rates + spread shock",
        "Rates +200bp and credit spreads widen — leveraged and non-bank financials suffer.",
        {"rates": 1.0, "credit_spread": 0.7},
    ),
    "recession": MacroScenario(
        "recession",
        "Broad recession",
        "GDP contraction with wider spreads and softer property across the book.",
        {"gdp": 1.0, "credit_spread": 0.6, "property": 0.4},
    ),
    "stagflation": MacroScenario(
        "stagflation",
        "Stagflation (severe)",
        "High rates AND contraction AND wider spreads AND weaker property — severe, broad.",
        {"rates": 0.8, "gdp": 0.7, "property": 0.5, "credit_spread": 0.6},
    ),
}


def entity_notches(sector: str, key: str) -> int:
    """Downgrade notches for a sector under a macro scenario (0..4)."""
    scenario = MACRO_SCENARIOS[key]
    sens = _SENSITIVITY.get(sector, {})
    raw = sum(scenario.intensities.get(f, 0.0) * sens.get(f, 0.0) for f in FACTORS)
    return min(4, round(raw))


def apply_macro(spec: DatasetSpec, key: str) -> DatasetSpec:
    """Return a NEW dataset with each entity downgraded per its sector's macro sensitivity."""
    if key not in MACRO_SCENARIOS:
        raise KeyError(f"unknown macro scenario '{key}'")
    entities = [
        replace(e, rating=scenarios.notch_down(e.rating, entity_notches(e.sector, key)))
        for e in spec.entities
    ]
    return replace(spec, entities=entities)


@dataclass(frozen=True)
class MacroSnapshot:
    scenario: str
    total_el: Decimal
    total_capital: Decimal
    capital_pct_eligible: Decimal
    names_downgraded: int
    total_notches: int


def _snapshot(spec: DatasetSpec, label: str, downgraded: int, notches: int) -> MacroSnapshot:
    summary = credit_risk.portfolio_summary(spec)
    return MacroSnapshot(
        scenario=label,
        total_el=summary.total_el,
        total_capital=summary.total_capital,
        capital_pct_eligible=summary.capital_as_pct_of_eligible,
        names_downgraded=downgraded,
        total_notches=notches,
    )


def compare(spec: DatasetSpec, key: str) -> tuple[MacroSnapshot, MacroSnapshot]:
    """Return (base, shocked) headline snapshots under a macro scenario."""
    notches = {e.entity_id: entity_notches(e.sector, key) for e in spec.entities}
    downgraded = sum(1 for n in notches.values() if n > 0)
    base = _snapshot(spec, "Base", 0, 0)
    shocked = _snapshot(
        apply_macro(spec, key), MACRO_SCENARIOS[key].label, downgraded, sum(notches.values())
    )
    return base, shocked


@dataclass(frozen=True)
class SectorMacroImpact:
    sector: str
    notches: int
    el_base: Decimal
    el_shocked: Decimal

    @property
    def delta(self) -> Decimal:
        return self.el_shocked - self.el_base


def sector_impacts(spec: DatasetSpec, key: str) -> list[SectorMacroImpact]:
    """Per-sector notch + expected-loss base vs shocked, sorted by the increase."""
    shocked = apply_macro(spec, key)
    base_el: dict[str, Decimal] = {}
    shocked_el: dict[str, Decimal] = {}
    for cr in credit_risk.portfolio_credit_risk(spec):
        sector = spec.entity(cr.entity).sector
        base_el[sector] = base_el.get(sector, Decimal(0)) + cr.el
    for cr in credit_risk.portfolio_credit_risk(shocked):
        sector = shocked.entity(cr.entity).sector
        shocked_el[sector] = shocked_el.get(sector, Decimal(0)) + cr.el
    rows = [
        SectorMacroImpact(
            sector=sector,
            notches=entity_notches(sector, key),
            el_base=base_el.get(sector, Decimal(0)),
            el_shocked=shocked_el.get(sector, Decimal(0)),
        )
        for sector in sorted(base_el)
    ]
    return sorted(rows, key=lambda r: r.delta, reverse=True)
