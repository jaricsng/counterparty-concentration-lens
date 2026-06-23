"""Configuration for Module 1, read from the environment (never hardcoded)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MODULE_ROOT: Path = Path(__file__).resolve().parent.parent
REPO_ROOT: Path = MODULE_ROOT.parent

# A fresh clone defaults to the CALM dataset (safe, unalarming). Switch to
# stressed explicitly via LENS_DATASET=stressed or the loader's --dataset flag.
DEFAULT_DATASET = "calm"


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings for M1."""

    dataset: str
    data_dir: Path
    fuseki_base_url: str
    fuseki_dataset: str

    @property
    def dataset_dir(self) -> Path:
        return self.data_dir / self.dataset

    @property
    def dataset_url(self) -> str:
        return f"{self.fuseki_base_url.rstrip('/')}/{self.fuseki_dataset}"

    @property
    def query_url(self) -> str:
        return f"{self.dataset_url}/query"

    @property
    def gsp_url(self) -> str:
        return f"{self.dataset_url}/data"

    @property
    def ping_url(self) -> str:
        return f"{self.fuseki_base_url.rstrip('/')}/$/ping"


def load_settings(dataset: str | None = None) -> Settings:
    """Build :class:`Settings` from environment variables with safe defaults.

    Environment variables:
        LENS_DATASET     ``calm`` (default) or ``stressed``
        FUSEKI_BASE_URL  default ``http://localhost:3030``
        FUSEKI_DATASET   default ``lens``
    """
    return Settings(
        dataset=dataset or os.environ.get("LENS_DATASET", DEFAULT_DATASET),
        data_dir=MODULE_ROOT / "data",
        fuseki_base_url=os.environ.get("FUSEKI_BASE_URL", "http://localhost:3030"),
        fuseki_dataset=os.environ.get("FUSEKI_DATASET", "lens"),
    )
