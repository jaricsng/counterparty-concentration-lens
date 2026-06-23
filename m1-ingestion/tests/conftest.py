"""Shared pytest fixtures for Module 1."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parent.parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from lens_m1.datasets import get_dataset  # noqa: E402
from lens_m1.spec import DatasetSpec  # noqa: E402


@pytest.fixture(scope="session")
def calm() -> DatasetSpec:
    return get_dataset("calm")


@pytest.fixture(scope="session")
def stressed() -> DatasetSpec:
    return get_dataset("stressed")
