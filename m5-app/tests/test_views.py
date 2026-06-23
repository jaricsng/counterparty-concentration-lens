"""The read-side view-model: metrics, scoping, drill-down."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from lens_m0.graph import GraphRunner
from lens_m5 import data


def test_group_heads_excludes_bank_and_subs(runner: GraphRunner) -> None:
    heads = dict(data.group_heads(runner))
    assert "LE-0001" in heads and "LE-0099" not in heads  # bank excluded
    assert "LE-0021" not in heads  # a Vortex subsidiary, not a head


def test_member_to_head_resolves_ubo(runner: GraphRunner) -> None:
    assert data.member_to_head(runner)["LE-0021"] == "LE-0020"


def test_dashboard_metrics(runner: GraphRunner, queries_dir: Path) -> None:
    d = data.dashboard(runner, queries_dir)
    assert d.hhi.connected > Decimal("0.18") > d.hhi.direct
    assert d.cr10.connected > Decimal("0.60")
    assert len(d.wwr) == 1
    assert d.exposures[0].name == "Nimbus Capital Partners Ltd"  # biggest connected


def test_dashboard_scoped_to_portfolio(runner: GraphRunner, queries_dir: Path) -> None:
    m2h = data.member_to_head(runner)
    full = data.dashboard(runner, queries_dir, m2h=m2h)
    scoped = data.dashboard(runner, queries_dir, visible={"LE-0001"}, m2h=m2h)
    assert len(scoped.exposures) == 1
    assert len(scoped.exposures) < len(full.exposures)
    assert all(m2h.get(w.entity, w.entity) == "LE-0001" for w in scoped.watchlist)


def test_group_drilldown_rolls_up_subsidiaries(runner: GraphRunner, queries_dir: Path) -> None:
    gv = data.group_view(runner, queries_dir, "LE-0001")  # Acme has subsidiaries
    assert gv.direct_head_only == Decimal("5000000")  # loan booked to the named entity
    assert gv.direct_group == Decimal("20000000")  # rolled up across the group
    assert gv.connected == Decimal("34000000")
    assert gv.limit_breached is True
    assert len(gv.contributions) >= 4


def test_label_index_for_nl(runner: GraphRunner) -> None:
    idx = data.label_index(runner)
    assert idx.get("acme") == "LE-0001"
    assert idx.get("nimbus") == "LE-0030"
