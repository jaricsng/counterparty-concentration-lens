"""The money shot: connected exposure > direct view, and it breaches the limit.

These are the M0 verification gates expressed as tests. The expected figures
are derived by hand in m0-ontology/data/instances.ttl.
"""

from __future__ import annotations

from decimal import Decimal

from lens_m0.concentration import breakdown, headline
from lens_m0.config import DEFAULT_GROUP_HEAD, Settings
from lens_m0.graph import GraphRunner

# Hand-computed expectations for the Acme group (see instances.ttl header).
DIRECT_HEAD_ONLY = Decimal("2000000")
DIRECT_GROUP = Decimal("10000000")
CONNECTED_TOTAL = Decimal("15500000")
GROUP_LIMIT = Decimal("12000000")


def test_headline_numbers(graph_runner: GraphRunner, settings: Settings) -> None:
    h = headline(graph_runner, settings.queries_dir, DEFAULT_GROUP_HEAD)
    assert h.direct_head_only == DIRECT_HEAD_ONLY
    assert h.direct_group == DIRECT_GROUP
    assert h.connected_total == CONNECTED_TOTAL
    assert h.group_limit == GROUP_LIMIT


def test_connected_exceeds_direct(graph_runner: GraphRunner, settings: Settings) -> None:
    """The whole point: the connected view is strictly larger than any direct view."""
    h = headline(graph_runner, settings.queries_dir, DEFAULT_GROUP_HEAD)
    assert h.connected_total > h.direct_group > h.direct_head_only
    # The hidden (multi-hop) exposure is material, not a rounding artefact.
    assert h.hidden_exposure == CONNECTED_TOTAL - DIRECT_HEAD_ONLY


def test_limit_breached_only_on_connected_view(
    graph_runner: GraphRunner, settings: Settings
) -> None:
    h = headline(graph_runner, settings.queries_dir, DEFAULT_GROUP_HEAD)
    assert h.limit_breached is True
    # The naive single-entity view would have looked comfortably within limit.
    assert h.direct_head_only < h.group_limit
    assert h.direct_group < h.group_limit
    assert h.connected_total > h.group_limit


def test_breakdown_surfaces_multihop_paths(graph_runner: GraphRunner, settings: Settings) -> None:
    contribs = breakdown(graph_runner, settings.queries_dir, DEFAULT_GROUP_HEAD)
    types = {c.contribution_type for c in contribs}
    assert any("Direct loan" in t for t in types)
    assert any("Guaranty" in t for t in types)
    assert any("Shared collateral" in t for t in types)

    # The guaranty path must surface Globex (exposure no loan table shows).
    guaranty = [c for c in contribs if "Guaranty" in c.contribution_type]
    assert any(c.counterparty_name == "Globex Industries Ltd" for c in guaranty)
    assert sum((c.amount for c in guaranty), Decimal(0)) == Decimal("4000000")

    # The shared-collateral path must surface Initech.
    collateral = [c for c in contribs if "Shared collateral" in c.contribution_type]
    assert any(c.counterparty_name == "Initech Systems Pte Ltd" for c in collateral)
    assert sum((c.amount for c in collateral), Decimal(0)) == Decimal("1500000")


def test_breakdown_sums_to_connected_total(graph_runner: GraphRunner, settings: Settings) -> None:
    contribs = breakdown(graph_runner, settings.queries_dir, DEFAULT_GROUP_HEAD)
    total = sum((c.amount for c in contribs), Decimal(0))
    assert total == CONNECTED_TOTAL
