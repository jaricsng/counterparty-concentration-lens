"""Configuration for Module 2, read from the environment (never hardcoded)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MODULE_ROOT: Path = Path(__file__).resolve().parent.parent
PACKAGE_ROOT: Path = Path(__file__).resolve().parent
SHAPES_PATH: Path = PACKAGE_ROOT / "shapes" / "lens_shapes.ttl"

# Illustrative breach thresholds (fractions of the limit). Configurable.
AMBER_FROM = 0.75
RED_FROM = 1.00


@dataclass(frozen=True)
class Settings:
    fuseki_base_url: str
    fuseki_dataset: str
    audit_log_path: Path
    shapes_path: Path

    @property
    def dataset_url(self) -> str:
        return f"{self.fuseki_base_url.rstrip('/')}/{self.fuseki_dataset}"

    @property
    def query_url(self) -> str:
        return f"{self.dataset_url}/query"

    @property
    def update_url(self) -> str:
        return f"{self.dataset_url}/update"

    @property
    def ping_url(self) -> str:
        return f"{self.fuseki_base_url.rstrip('/')}/$/ping"


def load_settings() -> Settings:
    """Build :class:`Settings` from environment variables with safe defaults.

    Environment variables:
        FUSEKI_BASE_URL  default ``http://localhost:3030``
        FUSEKI_DATASET   default ``lens``
        LENS_AUDIT_LOG   default ``m2-actions/audit/audit.log.jsonl``
    """
    default_audit = MODULE_ROOT / "audit" / "audit.log.jsonl"
    return Settings(
        fuseki_base_url=os.environ.get("FUSEKI_BASE_URL", "http://localhost:3030"),
        fuseki_dataset=os.environ.get("FUSEKI_DATASET", "lens"),
        audit_log_path=Path(os.environ.get("LENS_AUDIT_LOG", str(default_audit))),
        shapes_path=SHAPES_PATH,
    )
