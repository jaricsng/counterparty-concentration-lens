"""Integration: the same money-shot query gives the same answer on live Fuseki.

Skipped automatically when no Fuseki server is reachable (e.g. in CI), so the
default test run stays hermetic. Run a server + ``pytest -m integration`` to
exercise it. The in-memory rdflib result is the oracle.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from lens_m0.concentration import breakdown, headline
from lens_m0.config import DEFAULT_GROUP_HEAD, Settings
from lens_m0.fuseki import FusekiRunner

pytestmark = pytest.mark.integration

CONNECTED_TOTAL = Decimal("15500000")


@pytest.fixture(scope="module")
def fuseki(settings: Settings) -> FusekiRunner:
    runner = FusekiRunner(query_url=settings.query_url, gsp_url=settings.gsp_url)
    ping = f"{settings.fuseki_base_url.rstrip('/')}/$/ping"
    if not runner.is_up(ping):
        pytest.skip(f"Fuseki not reachable at {settings.fuseki_base_url}")
    # Self-contained, idempotent load (app ontology + instances; FIBO not needed
    # for the query and is skipped here for speed).
    runner.clear_default_graph()
    runner.upload_turtle(settings.ontology_path)
    runner.upload_turtle(settings.instances_path)
    return runner


def test_fuseki_headline_matches_oracle(fuseki: FusekiRunner, settings: Settings) -> None:
    h = headline(fuseki, settings.queries_dir, DEFAULT_GROUP_HEAD)
    assert h.connected_total == CONNECTED_TOTAL
    assert h.connected_total > h.direct_group > h.direct_head_only
    assert h.limit_breached is True


def test_fuseki_breakdown_has_three_paths(fuseki: FusekiRunner, settings: Settings) -> None:
    contribs = breakdown(fuseki, settings.queries_dir, DEFAULT_GROUP_HEAD)
    types = {c.contribution_type for c in contribs}
    assert any("Direct loan" in t for t in types)
    assert any("Guaranty" in t for t in types)
    assert any("Shared collateral" in t for t in types)
    assert sum((c.amount for c in contribs), Decimal(0)) == CONNECTED_TOTAL
