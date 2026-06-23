"""Integration: generate -> load into Fuseki -> the M0 query still works.

Skipped automatically when no Fuseki server is reachable.
"""

from __future__ import annotations

import pytest
import requests
from lens_m1.config import load_settings
from lens_m1.csv_tables import write_dataset
from lens_m1.datasets import get_dataset
from lens_m1.loader import load, server_up

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def _ensure_data() -> None:
    settings = load_settings()
    for name in ("calm", "stressed"):
        write_dataset(get_dataset(name), settings.data_dir / name)


def _connected_acme(query_url: str) -> int:
    """Connected exposure to the Acme group via the M0-style traversal."""
    query = """
    PREFIX lens: <https://lens.example/ontology/>
    PREFIX lensid: <https://lens.example/id/>
    SELECT (COALESCE(SUM(?amt), 0) AS ?connected) WHERE {
      SELECT DISTINCT ?src ?amt WHERE {
        VALUES ?head { lensid:LE-0001 }
        { ?src lens:borrower ?m ; lens:principalAmount ?amt . ?m lens:isSubsidiaryOf* ?head . }
        UNION
        { ?src lens:guarantor ?m ; lens:guaranteedAmount ?amt . ?m lens:isSubsidiaryOf* ?head . }
        UNION
        { ?col lens:securesLoan ?ml , ?src . ?ml lens:borrower ?gm .
          ?gm lens:isSubsidiaryOf* ?head . FILTER(?ml != ?src) ?src lens:borrower ?eb .
          FILTER NOT EXISTS { ?eb lens:isSubsidiaryOf* ?head } ?src lens:principalAmount ?amt . }
      }
    }"""
    resp = requests.post(
        query_url,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=60,
    )
    resp.raise_for_status()
    return int(float(resp.json()["results"]["bindings"][0]["connected"]["value"]))


def test_idempotent_load_and_m0_query(_ensure_data: None) -> None:
    stressed = load_settings(dataset="stressed")
    if not server_up(stressed):
        pytest.skip("Fuseki not reachable")

    r1 = load(stressed)
    r2 = load(stressed)
    assert r1.graph_triples_in_store == r2.graph_triples_in_store  # idempotent

    # Triple count is consistent with the row counts (each row -> several triples).
    assert r1.instance_triples > sum(r1.row_counts.values())

    # The M0 concentration query works on generated data: Acme breaches on stressed.
    assert _connected_acme(stressed.query_url) == 34_000_000

    # ... and not on calm.
    calm = load_settings(dataset="calm")
    load(calm)
    assert _connected_acme(calm.query_url) == 9_000_000
