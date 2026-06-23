"""Configuration for Module 0, read from the environment (never hardcoded).

All paths are resolved relative to the module root so the package works the
same whether invoked from the repo root or from ``m0-ontology/``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# m0-ontology/ (parent of this package directory)
MODULE_ROOT: Path = Path(__file__).resolve().parent.parent
REPO_ROOT: Path = MODULE_ROOT.parent

# Default IRI of the counterparty-group head used by the demo (the Acme group).
DEFAULT_GROUP_HEAD = "https://lens.example/id/LE-0001"


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings for M0."""

    fuseki_base_url: str
    fuseki_dataset: str
    ontology_path: Path
    instances_path: Path
    fibo_path: Path
    queries_dir: Path

    @property
    def dataset_url(self) -> str:
        """Base URL of the Fuseki dataset (no trailing slash)."""
        return f"{self.fuseki_base_url.rstrip('/')}/{self.fuseki_dataset}"

    @property
    def query_url(self) -> str:
        """SPARQL query endpoint."""
        return f"{self.dataset_url}/query"

    @property
    def update_url(self) -> str:
        """SPARQL update endpoint."""
        return f"{self.dataset_url}/update"

    @property
    def gsp_url(self) -> str:
        """Graph Store Protocol endpoint (for bulk data upload)."""
        return f"{self.dataset_url}/data"


def load_settings() -> Settings:
    """Build :class:`Settings` from environment variables with safe defaults.

    Environment variables:
        FUSEKI_BASE_URL  default ``http://localhost:3030``
        FUSEKI_DATASET   default ``lens``
        LENS_FIBO_PATH   default ``vendor/fibo/prod.fibo-quickstart.ttl``
    """
    fibo_default = REPO_ROOT / "vendor" / "fibo" / "prod.fibo-quickstart.ttl"
    return Settings(
        fuseki_base_url=os.environ.get("FUSEKI_BASE_URL", "http://localhost:3030"),
        fuseki_dataset=os.environ.get("FUSEKI_DATASET", "lens"),
        ontology_path=MODULE_ROOT / "ontology" / "lens.ttl",
        instances_path=MODULE_ROOT / "data" / "instances.ttl",
        fibo_path=Path(os.environ.get("LENS_FIBO_PATH", str(fibo_default))),
        queries_dir=MODULE_ROOT / "queries",
    )
