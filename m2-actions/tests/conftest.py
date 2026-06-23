"""Shared fixtures for Module 2 (in-memory store + API client)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

M2_ROOT = Path(__file__).resolve().parent.parent
M1_ROOT = M2_ROOT.parent / "m1-ingestion"
for _p in (str(M2_ROOT), str(M1_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi.testclient import TestClient  # noqa: E402
from lens_m1 import datasets, rdfize  # noqa: E402
from lens_m2.actions import ActionService  # noqa: E402
from lens_m2.app import create_app  # noqa: E402
from lens_m2.audit import AuditLog  # noqa: E402
from lens_m2.config import SHAPES_PATH  # noqa: E402
from lens_m2.store import InMemoryStore  # noqa: E402


@pytest.fixture
def store() -> InMemoryStore:
    """A fresh in-memory store seeded with the stressed dataset."""
    return InMemoryStore(rdfize.build_graph(datasets.get_dataset("stressed")))


@pytest.fixture
def audit(tmp_path: Path) -> AuditLog:
    return AuditLog(tmp_path / "audit.jsonl")


@pytest.fixture
def service(store: InMemoryStore, audit: AuditLog) -> ActionService:
    return ActionService(store, audit, SHAPES_PATH)


@pytest.fixture
def client(service: ActionService, audit: AuditLog) -> TestClient:
    return TestClient(create_app(service, audit))
