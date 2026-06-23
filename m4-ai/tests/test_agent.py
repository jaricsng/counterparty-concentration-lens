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
