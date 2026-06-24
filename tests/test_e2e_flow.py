"""End-to-end against a live Fuseki: the whole chain in one test.

load (M1) -> money-shot query (M0) -> guarded write (M2) -> re-query reflects it
-> flag -> audit. This proves the modules wire together over real HTTP, which the
per-module unit tests (in-memory store) cannot.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from lens_m0 import concentration
from lens_m0.config import load_settings as m0_settings
from lens_m2.derived import connected_exposure

pytestmark = pytest.mark.integration

ACME = "https://lens.example/id/LE-0001"
ZENITH = "https://lens.example/id/LE-0041"


def test_load_query_act_reflect_audit(stressed, runner, service, fuseki_store, audit):
    queries_dir = m0_settings().queries_dir

    # 1) the money shot on freshly loaded stressed data (M0 over live Fuseki)
    head = concentration.headline(runner, queries_dir, ACME)
    assert head.connected_total == Decimal("34000000")
    assert head.limit_breached
    assert head.connected_total > head.direct_head_only  # multi-hop reveals more

    # 2) a guarded M2 write that tips Zenith over its 25M limit (live FusekiStore)
    before = connected_exposure(fuseki_store, ZENITH)
    result = service.create_loan(
        loan_id="LN-E2E-1",
        lender_id="LE-0099",
        borrower_id="LE-0041",
        principal=30_000_000,
        actor="e2e",
        role="group_risk",
    )
    assert result.accepted
    assert "limit-breach:LE-0041" in result.flags

    # 3) re-reading the live store reflects the write
    after = connected_exposure(fuseki_store, ZENITH)
    assert after == before + Decimal("30000000")

    # 4) the flag action now sees the new breach
    breaches = {b.entity for b in service.flag_limit_breaches(actor="e2e", role="group_risk")}
    assert "LE-0041" in breaches

    # 5) the audit trail recorded who/what/when across the chain
    actions = [e["action"] for e in audit.entries()]
    assert "create-loan" in actions
    assert "flag-limit-breach" in actions
