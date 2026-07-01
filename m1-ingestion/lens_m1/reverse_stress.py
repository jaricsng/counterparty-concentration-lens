"""Reverse stress testing — the mildest shock that reaches an adverse target.

Ordinary stress asks "what happens under scenario X?". **Reverse** stress inverts it:
"what is the *smallest* shock that produces outcome Y?" (e.g. doubles expected loss,
pushes capital past a threshold, or forces N connected-limit breaches). Because the
shock engine is deterministic and monotone in severity, we search a one-parameter
family for the minimal severity that crosses the target.

Two monotone shock families:
  * **downgrade** — cut every rating by N notches (moves PD → EL, capital);
  * **exposure**  — uplift every drawn exposure by N×10% (moves exposure → limit breaches).

DELIBERATELY SIMPLIFIED, like the forward stress engine: a deterministic search over
shock severity, **not** an optimiser over a calibrated risk-factor space. See
docs/ccr-coverage.md.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import Decimal

from . import credit_risk, metrics, scenarios
from .spec import DatasetSpec


def _downgrade_all(spec: DatasetSpec, severity: int) -> DatasetSpec:
    """Broad downgrade: every entity's rating cut by ``severity`` grades."""
    return replace(
        spec,
        entities=[
            replace(e, rating=scenarios.notch_down(e.rating, severity)) for e in spec.entities
        ],
    )


def _uplift_exposure(spec: DatasetSpec, severity: int) -> DatasetSpec:
    """Uniform exposure uplift: every drawn principal up by ``severity`` × 10%."""
    factor = 1 + Decimal(severity) / 10
    return replace(
        spec, loans=[replace(ln, principal=int(ln.principal * factor)) for ln in spec.loans]
    )


def _limit_breaches(spec: DatasetSpec) -> Decimal:
    return Decimal(sum(1 for u in metrics.utilisations(spec) if u.ratio >= metrics.RED_FROM))


# Named outcome metrics a reverse-stress target can be set on.
METRICS: dict[str, Callable[[DatasetSpec], Decimal]] = {
    "expected_loss": lambda s: credit_risk.portfolio_summary(s).total_el,
    "capital": lambda s: credit_risk.portfolio_summary(s).total_capital,
    "capital_pct_eligible": lambda s: credit_risk.portfolio_summary(s).capital_as_pct_of_eligible,
    "limit_breaches": _limit_breaches,
}

# family key -> (transform, label(severity), default_for_metrics)
FAMILIES: dict[str, tuple[Callable[[DatasetSpec, int], DatasetSpec], Callable[[int], str]]] = {
    "downgrade": (
        _downgrade_all,
        lambda n: f"broad downgrade −{n} notch{'es' if n != 1 else ''}",
    ),
    "exposure": (_uplift_exposure, lambda n: f"+{n * 10}% exposure uplift"),
}

METRIC_LABELS = {
    "expected_loss": "expected loss",
    "capital": "regulatory capital",
    "capital_pct_eligible": "capital as % of eligible",
    "limit_breaches": "connected-limit breaches",
}

# which shock family best drives each metric (downgrades don't move exposure/limits)
DEFAULT_FAMILY = {
    "expected_loss": "downgrade",
    "capital": "downgrade",
    "capital_pct_eligible": "downgrade",
    "limit_breaches": "exposure",
}


@dataclass(frozen=True)
class ReverseStress:
    metric: str
    family: str
    target: Decimal
    base_value: Decimal
    severity: int | None  # minimal severity reaching the target (None = not within cap)
    achieved: Decimal
    shock_label: str

    @property
    def feasible(self) -> bool:
        return self.severity is not None


def min_shock(
    spec: DatasetSpec,
    metric: str,
    target: Decimal,
    *,
    family: str | None = None,
    max_severity: int = 6,
) -> ReverseStress:
    """Smallest shock (in the chosen family) for which ``metric`` reaches ``target``."""
    if metric not in METRICS:
        raise KeyError(f"unknown reverse-stress metric '{metric}'")
    family = family or DEFAULT_FAMILY[metric]
    transform, label = FAMILIES[family]
    fn = METRICS[metric]
    base = fn(spec)
    for severity in range(1, max_severity + 1):
        value = fn(transform(spec, severity))
        if value >= target:
            return ReverseStress(metric, family, target, base, severity, value, label(severity))
    worst = fn(transform(spec, max_severity))
    return ReverseStress(
        metric, family, target, base, None, worst, "not reachable within the search cap"
    )


def multiplier_target(
    spec: DatasetSpec, metric: str, multiple: float, **kw: str | int
) -> ReverseStress:
    """Reverse stress to a *multiple* of the base metric (e.g. 2.0 = double it)."""
    base = METRICS[metric](spec)
    return min_shock(spec, metric, base * Decimal(str(multiple)), **kw)  # type: ignore[arg-type]
