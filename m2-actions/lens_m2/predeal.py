"""Pre-deal limit checks — would a proposed deal breach the limits, *before* booking it?

A read-only what-if over the live store that extends the static single-name limit with:
  * **pre-deal**   — checks a *proposed* loan against current connected exposure (no write);
  * **dynamic**    — the effective limit is the base limit scaled by a rating factor (a
    downgraded counterparty gets a tighter limit);
  * **tenor**      — the deal's tenor must not exceed a maximum-tenor policy;
  * **settlement** — the deal size must not exceed a settlement sub-limit (a fraction of
    the credit limit).

Deliberately simplified (illustrative factors/caps), consistent with the rest of the
prototype — see docs/ccr-coverage.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .derived import _connected, _entity_meta, _facts
from .store import Store

# Dynamic limit: effective limit = base × factor(rating). Worse rating → tighter.
RATING_LIMIT_FACTOR: dict[str, Decimal] = {
    "AAA": Decimal("1.20"),
    "AA": Decimal("1.10"),
    "A": Decimal("1.00"),
    "BBB": Decimal("1.00"),
    "BB": Decimal("0.80"),
    "B": Decimal("0.60"),
    "CCC": Decimal("0.40"),
}
DEFAULT_TENOR_CAP = 7  # maximum-tenor policy (years)
SETTLEMENT_FRACTION = Decimal("0.25")  # settlement sub-limit = 25% of the credit limit


@dataclass(frozen=True)
class DealVerdict:
    borrower: str
    ubo: str
    rating: str
    amount: Decimal
    tenor: int
    connected_now: Decimal
    base_limit: Decimal
    effective_limit: Decimal  # dynamic (rating-adjusted)
    connected_post: Decimal
    headroom: Decimal
    limit_ok: bool
    tenor_cap: int
    tenor_ok: bool
    settlement_limit: Decimal
    settlement_ok: bool

    @property
    def ok(self) -> bool:
        return self.limit_ok and self.tenor_ok and self.settlement_ok

    @property
    def reasons(self) -> list[str]:
        out: list[str] = []
        if not self.limit_ok:
            out.append(f"connected limit: post-deal {self.connected_post} > {self.effective_limit}")
        if not self.tenor_ok:
            out.append(f"tenor {self.tenor}y exceeds the {self.tenor_cap}y cap")
        if not self.settlement_ok:
            out.append(
                f"deal {self.amount} exceeds the settlement sub-limit {self.settlement_limit}"
            )
        return out


def _ubo(facts: object, entity: str) -> str:
    parent: dict[str, str] = facts.parent  # type: ignore[attr-defined]
    current, seen = entity, {entity}
    while current in parent and parent[current] not in seen:
        current = parent[current]
        seen.add(current)
    return current


def pre_deal_check(
    store: Store,
    *,
    borrower_id: str,
    amount: int,
    tenor: int,
    tenor_cap: int = DEFAULT_TENOR_CAP,
) -> DealVerdict:
    """Evaluate a *proposed* loan against dynamic / tenor / settlement limits (no write)."""
    facts = _facts(store)
    _, meta = _entity_meta(store)  # id -> (sector, rating)
    ubo = _ubo(facts, borrower_id)
    connected_now = _connected(facts, ubo)
    base_limit = facts.limits.get(ubo) or facts.limits.get(borrower_id) or Decimal(0)
    rating = (meta.get(ubo) or meta.get(borrower_id) or ("", ""))[1] or "unrated"
    effective = base_limit * RATING_LIMIT_FACTOR.get(rating, Decimal(1))
    amt = Decimal(amount)
    post = connected_now + amt
    settlement_limit = effective * SETTLEMENT_FRACTION
    return DealVerdict(
        borrower=borrower_id,
        ubo=ubo,
        rating=rating,
        amount=amt,
        tenor=tenor,
        connected_now=connected_now,
        base_limit=base_limit,
        effective_limit=effective,
        connected_post=post,
        headroom=effective - post,
        limit_ok=post <= effective,
        tenor_cap=tenor_cap,
        tenor_ok=tenor <= tenor_cap,
        settlement_limit=settlement_limit,
        settlement_ok=amt <= settlement_limit,
    )
