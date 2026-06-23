"""Shared pytest fixtures for Module 0."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the m0-ontology package importable when pytest runs from the repo root.
MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from lens_m0.config import Settings, load_settings  # noqa: E402
from lens_m0.graph import GraphRunner, load_graph  # noqa: E402


@pytest.fixture(scope="session")
def settings() -> Settings:
    return load_settings()


@pytest.fixture(scope="session")
def graph_runner(settings: Settings) -> GraphRunner:
    """In-memory runner over the app ontology + instances (no FIBO, for speed)."""
    graph = load_graph(settings.ontology_path, settings.instances_path)
    return GraphRunner(graph)
