"""Minimal Apache Jena Fuseki HTTP client.

Just enough to: check the server is up, (re)load Turtle files into the default
graph via the Graph Store Protocol, and run SELECT queries. Read-only by
default; the only write path is the explicit data upload used by the loader.
"""

from __future__ import annotations

import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 120  # seconds; FIBO is ~8 MB so the first load is not instant


class FusekiError(RuntimeError):
    """Raised when Fuseki returns an error or is unreachable."""


class FusekiRunner:
    """A :class:`~lens_m0.concentration.QueryRunner` backed by a Fuseki dataset."""

    def __init__(
        self,
        query_url: str,
        gsp_url: str,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._query_url = query_url
        self._gsp_url = gsp_url
        self._timeout = timeout

    def is_up(self, ping_url: str) -> bool:
        """Return True if the Fuseki server answers its ping endpoint."""
        try:
            resp = requests.get(ping_url, timeout=5)
            return resp.ok
        except requests.RequestException:
            return False

    def clear_default_graph(self) -> None:
        """Drop all triples in the default graph (idempotent reloads)."""
        try:
            resp = requests.delete(self._gsp_url, params={"default": ""}, timeout=self._timeout)
            # 204/404 are both fine (nothing to delete is not an error).
            if resp.status_code not in (200, 204, 404):
                raise FusekiError(f"clear failed: {resp.status_code} {resp.text[:200]}")
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise FusekiError(f"clear request failed: {exc}") from exc

    def upload_turtle(self, path: Path) -> None:
        """POST a Turtle file into the default graph via the Graph Store Protocol."""
        data = path.read_bytes()
        try:
            resp = requests.post(
                self._gsp_url,
                params={"default": ""},
                data=data,
                headers={"Content-Type": "text/turtle"},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise FusekiError(f"upload of {path.name} failed: {exc}") from exc
        if not resp.ok:
            raise FusekiError(f"upload of {path.name} failed: {resp.status_code} {resp.text[:200]}")
        logger.info("Loaded %s into default graph", path.name)

    def select(self, query: str) -> list[dict[str, str | None]]:
        """Run a SELECT query, returning rows as stringified bindings."""
        try:
            resp = requests.post(
                self._query_url,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:  # pragma: no cover - network failure
            raise FusekiError(f"query failed: {exc}") from exc
        if not resp.ok:
            raise FusekiError(f"query failed: {resp.status_code} {resp.text[:300]}")

        payload = resp.json()
        variables: list[str] = payload.get("head", {}).get("vars", [])
        rows: list[dict[str, str | None]] = []
        for binding in payload.get("results", {}).get("bindings", []):
            row: dict[str, str | None] = {}
            for var in variables:
                cell = binding.get(var)
                row[var] = None if cell is None else cell.get("value")
            rows.append(row)
        return rows
