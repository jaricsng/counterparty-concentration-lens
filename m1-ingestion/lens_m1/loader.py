"""Load a generated dataset (CSV source tables) into Fuseki as FIBO triples.

Pipeline: read the five CSV tables -> map rows to FIBO instances (rdfize) ->
replace the Fuseki default graph. Replacing (clear + upload) makes reloads
idempotent: loading the same dataset twice yields the same graph.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import requests
from rdflib import Graph

from .config import Settings
from .csv_tables import read_dataset
from .rdfize import build_graph

logger = logging.getLogger(__name__)

_TIMEOUT = 120


class FusekiError(RuntimeError):
    """Raised when Fuseki is unreachable or returns an error."""


@dataclass(frozen=True)
class LoadResult:
    dataset: str
    row_counts: dict[str, int]
    instance_triples: int
    graph_triples_in_store: int


def server_up(settings: Settings) -> bool:
    try:
        return requests.get(settings.ping_url, timeout=5).ok
    except requests.RequestException:
        return False


def _clear_default_graph(settings: Settings) -> None:
    try:
        resp = requests.delete(settings.gsp_url, params={"default": ""}, timeout=_TIMEOUT)
    except requests.RequestException as exc:  # pragma: no cover - network failure
        raise FusekiError(f"clear failed: {exc}") from exc
    if resp.status_code not in (200, 204, 404):
        raise FusekiError(f"clear failed: {resp.status_code} {resp.text[:200]}")


def _upload_turtle(settings: Settings, turtle: bytes) -> None:
    try:
        resp = requests.post(
            settings.gsp_url,
            params={"default": ""},
            data=turtle,
            headers={"Content-Type": "text/turtle"},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:  # pragma: no cover - network failure
        raise FusekiError(f"upload failed: {exc}") from exc
    if not resp.ok:
        raise FusekiError(f"upload failed: {resp.status_code} {resp.text[:200]}")


def _count_triples(settings: Settings) -> int:
    resp = requests.post(
        settings.query_url,
        data={"query": "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"},
        headers={"Accept": "application/sparql-results+json"},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return int(resp.json()["results"]["bindings"][0]["n"]["value"])


def _row_counts(dataset_dir: Path) -> dict[str, int]:
    import csv

    counts: dict[str, int] = {}
    for table in ("entities", "loans", "guarantees", "collateral", "limits"):
        with (dataset_dir / f"{table}.csv").open(encoding="utf-8") as fh:
            counts[table] = sum(1 for _ in csv.reader(fh)) - 1  # minus header
    return counts


def build_dataset_graph(settings: Settings) -> Graph:
    """Read the selected dataset's CSVs and map them to an RDF graph."""
    spec = read_dataset(settings.dataset_dir, settings.dataset)
    return build_graph(spec)


def load(settings: Settings) -> LoadResult:
    """Load the selected dataset into Fuseki (idempotent replace)."""
    if not settings.dataset_dir.exists():
        raise FusekiError(
            f"dataset '{settings.dataset}' not found at {settings.dataset_dir}; "
            "run scripts/generate_data.py first"
        )
    graph = build_dataset_graph(settings)
    turtle = graph.serialize(format="turtle").encode("utf-8")

    logger.info("Replacing default graph with dataset '%s' ...", settings.dataset)
    _clear_default_graph(settings)
    _upload_turtle(settings, turtle)

    in_store = _count_triples(settings)
    logger.info("Loaded %d instance triples; store now holds %d.", len(graph), in_store)
    return LoadResult(
        dataset=settings.dataset,
        row_counts=_row_counts(settings.dataset_dir),
        instance_triples=len(graph),
        graph_triples_in_store=in_store,
    )
