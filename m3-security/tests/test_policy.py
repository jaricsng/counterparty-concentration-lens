"""Python-side policy tests (skipped when the OPA binary is unavailable)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

M3_ROOT = Path(__file__).resolve().parent.parent
if str(M3_ROOT) not in sys.path:
    sys.path.insert(0, str(M3_ROOT))

from lens_m3.policy import PolicyEngine, opa_path  # noqa: E402

pytestmark = pytest.mark.skipif(opa_path() is None, reason="opa binary not available")

CANDIDATES = ["LE-0001", "LE-0010", "LE-0020", "LE-0030"]


@pytest.fixture
def engine() -> PolicyEngine:
    return PolicyEngine()


def test_group_risk_sees_all(engine: PolicyEngine) -> None:
    assert engine.visible_groups("group_risk", [], CANDIDATES) == set(CANDIDATES)


def test_rm_sees_only_portfolio(engine: PolicyEngine) -> None:
    assert engine.visible_groups("relationship_manager", ["LE-0020", "LE-0030"], CANDIDATES) == {
        "LE-0020",
        "LE-0030",
    }


def test_rm_empty_portfolio_sees_nothing(engine: PolicyEngine) -> None:
    assert engine.visible_groups("relationship_manager", [], CANDIDATES) == set()


def test_allow_decisions(engine: PolicyEngine) -> None:
    assert engine.allow("group_risk", [], "LE-9999") is True
    assert engine.allow("relationship_manager", ["LE-0001"], "LE-0001") is True
    assert engine.allow("relationship_manager", ["LE-0001"], "LE-0020") is False


def test_same_request_differs_by_role(engine: PolicyEngine) -> None:
    """The M3 demo point: identical request, different result sets per role."""
    risk = engine.visible_groups("group_risk", [], CANDIDATES)
    rm = engine.visible_groups("relationship_manager", ["LE-0001"], CANDIDATES)
    assert risk != rm
    assert rm < risk  # strict subset
