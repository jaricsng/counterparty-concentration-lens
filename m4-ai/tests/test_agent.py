"""The grounded agent answers known questions correctly (template engine)."""

from __future__ import annotations

from lens_m0.graph import GraphRunner
from lens_m4.agent import answer
from lens_m4.safety import is_safe

LABEL_INDEX = {"acme": "LE-0001", "helios": "LE-0010", "vortex": "LE-0020", "nimbus": "LE-0030"}


def _ans(runner: GraphRunner, q: str, **kw: object):
    # Force the deterministic template engine for reproducible tests.
    return answer(q, runner, label_index=LABEL_INDEX, allow_ollama=False, **kw)


def test_every_generated_query_is_safe(runner: GraphRunner) -> None:
    for q in (
        "total exposure to Acme",
        "which counterparties are within 75% of their limit",
        "show guarantee chains touching Nimbus",
        "sector concentration",
        "any wrong-way risk?",
        "top counterparties",
    ):
        a = _ans(runner, q)
        assert a.answered, q
        assert is_safe(a.sparql).safe, q


def test_exposure_to_acme(runner: GraphRunner) -> None:
    a = _ans(runner, "what is our total exposure to the Acme group?")
    assert a.intent == "exposure_to_group"
    assert a.rows[0]["connected"] == "34000000"  # matches the M0/M1 number


def test_near_limit_threshold(runner: GraphRunner) -> None:
    a = _ans(runner, "which counterparties are within 75% of their limit?")
    assert a.intent == "near_limit"
    names = {r.get("entityName") for r in a.rows}
    # Nimbus, Acme, Vortex (red) + Helios (amber) at least.
    assert any("Nimbus" in (n or "") for n in names)


def test_wrong_way_risk(runner: GraphRunner) -> None:
    a = _ans(runner, "show me any wrong-way risk")
    assert a.intent == "wrong_way_risk"
    assert len(a.rows) == 1


def test_top_counterparties(runner: GraphRunner) -> None:
    a = _ans(runner, "who are the top counterparties?")
    assert a.intent == "top_counterparties"
    assert a.rows[0]["ownerName"] == "Nimbus Capital Partners Ltd"  # biggest connected


def test_unsupported_question(runner: GraphRunner) -> None:
    a = _ans(runner, "what's the weather today?")
    assert not a.answered and a.engine == "none"


def test_role_scoping_filters_rows(runner: GraphRunner) -> None:
    # group_risk sees all; an RM who manages only Acme sees a strict subset.
    full = _ans(runner, "top counterparties")
    scoped = _ans(runner, "top counterparties", visible_groups={"LE-0001"})
    assert len(scoped.rows) < len(full.rows)
    assert all(r.get("owner", "").endswith("LE-0001") for r in scoped.rows)


def test_net_exposure_after_collateral(runner: GraphRunner) -> None:
    from decimal import Decimal

    a = _ans(runner, "what is the net exposure after collateral?")
    assert a.intent == "net_exposure"
    assert a.answered
    helios = next(r for r in a.rows if r["entityName"] == "Helios Power Pte Ltd")
    assert Decimal(helios["gross"]) == 7_000_000
    assert Decimal(helios["net"]) == 5_000_000  # 4M bond @ 50% haircut -> 2M mitigant
    # every generated query is still safe (read-only, known schema)
    assert is_safe(a.sparql).safe


def test_country_concentration(runner: GraphRunner) -> None:
    a = _ans(runner, "which country are we most exposed to?")
    assert a.intent == "country_concentration"
    assert "SG" in a.summary
    assert is_safe(a.sparql).safe


def test_rating_concentration(runner: GraphRunner) -> None:
    a = _ans(runner, "what is our credit rating concentration?")
    assert a.intent == "rating_concentration"
    assert "BB" in a.summary
    assert is_safe(a.sparql).safe


def test_expected_loss(runner: GraphRunner) -> None:
    from decimal import Decimal

    a = _ans(runner, "what is our total expected loss?")
    assert a.intent == "expected_loss"
    assert is_safe(a.sparql).safe
    assert round(sum(Decimal(r["el"] or 0) for r in a.rows)) == 811_287  # == derived


def test_capital(runner: GraphRunner) -> None:
    a = _ans(runner, "how much regulatory capital do we need?")
    assert a.intent == "capital"
    assert "capital" in a.summary.lower()


def test_capital_keyword_does_not_hijack_entity_name(runner: GraphRunner) -> None:
    # "Nimbus Capital Partners" contains "capital" but this is an exposure question
    a = _ans(runner, "what is our exposure to Nimbus Capital Partners?")
    assert a.intent == "exposure_to_group"
