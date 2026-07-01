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


def test_stress_nbfi_downgrade(runner: GraphRunner) -> None:
    a = _ans(runner, "what happens to expected loss if NBFIs are downgraded?")
    assert a.intent == "stress"
    assert "expected loss" in a.summary.lower() and "->" in a.summary


def test_stress_keyword_routing(runner: GraphRunner) -> None:
    assert _ans(runner, "stress the book with a haircut shock").intent == "stress"
    assert _ans(runner, "what if there is a broad downgrade?").intent == "stress"


def test_xva_cva(runner: GraphRunner) -> None:
    a = _ans(runner, "what is our total CVA?")
    assert a.intent == "xva"
    assert "cva" in a.summary.lower() and "pfe" in a.summary.lower()


def test_pfe_intent_routes_to_xva(runner: GraphRunner) -> None:
    assert _ans(runner, "show potential future exposure").intent == "xva"


def test_ifrs9_ecl(runner: GraphRunner) -> None:
    a = _ans(runner, "what is our IFRS-9 ECL?")
    assert a.intent == "ifrs9"
    assert "ecl" in a.summary.lower() and "stage 2" in a.summary.lower()


def test_expected_credit_loss_routes_to_ifrs9(runner: GraphRunner) -> None:
    assert _ans(runner, "show lifetime expected credit loss").intent == "ifrs9"


def test_expected_loss_still_routes_to_el(runner: GraphRunner) -> None:
    assert _ans(runner, "what is our total expected loss?").intent == "expected_loss"


def test_systemic_contagion(runner: GraphRunner) -> None:
    a = _ans(runner, "which counterparty is most systemically important?")
    assert a.intent == "contagion"
    assert "LE-0030" in a.summary and "systemic" in a.summary.lower()


def test_macro_property_crash(runner: GraphRunner) -> None:
    a = _ans(runner, "what happens in a property crash?")
    assert a.intent == "macro"
    assert "commercial real estate" in a.summary.lower()


def test_macro_recession_routes(runner: GraphRunner) -> None:
    assert _ans(runner, "show the recession macro scenario").intent == "macro"


def test_single_factor_stress_still_routes(runner: GraphRunner) -> None:
    assert _ans(runner, "what if NBFIs are downgraded?").intent == "stress"


def test_reverse_stress_double_el(runner: GraphRunner) -> None:
    a = _ans(runner, "what is the mildest shock to double expected loss?")
    assert a.intent == "reverse_stress"
    assert "downgrade" in a.summary.lower()


def test_reverse_stress_routes_before_forward_stress(runner: GraphRunner) -> None:
    assert _ans(runner, "reverse stress our capital").intent == "reverse_stress"
    assert _ans(runner, "what happens in a property crash?").intent == "macro"


def test_general_wwr(runner: GraphRunner) -> None:
    a = _ans(runner, "show general wrong-way risk")
    assert a.intent == "general_wwr" and "wrong-way" in a.summary.lower()


def test_structural_wwr_still_routes(runner: GraphRunner) -> None:
    assert _ans(runner, "any wrong-way risk?").intent == "wrong_way_risk"
