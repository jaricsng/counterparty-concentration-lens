"""Cross-module end-to-end / live-Fuseki integration fixtures.

These tests exercise the real HTTP paths (FusekiStore, the M2 API against a live
triplestore, the full load→query→act→audit chain) that the per-module unit tests
deliberately stub with an in-memory store. They are marked ``integration`` and
**skip** when no Fuseki is reachable.

> They MUTATE the configured Fuseki (``FUSEKI_BASE_URL``, default
> ``http://localhost:3030``). A session finalizer reloads the bundled ``calm``
> dataset afterwards so a shared store returns to a known baseline. Point
> ``FUSEKI_BASE_URL`` at a throwaway instance to keep a running app untouched.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _mod in (
    "m0-ontology",
    "m1-ingestion",
    "m2-actions",
    "m3-security",
    "m4-ai",
    "m5-app",
    "capstone",
):
    _p = str(ROOT / _mod)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lens_m0.config import load_settings as m0_settings  # noqa: E402
from lens_m0.fuseki import FusekiRunner  # noqa: E402
from lens_m1.config import load_settings as m1_settings  # noqa: E402
from lens_m1.loader import load as m1_load  # noqa: E402
from lens_m1.loader import server_up  # noqa: E402
from lens_m2.actions import ActionService  # noqa: E402
from lens_m2.audit import AuditLog  # noqa: E402
from lens_m2.config import load_settings as m2_settings  # noqa: E402
from lens_m2.store import FusekiStore  # noqa: E402


def fuseki_up() -> bool:
    return server_up(m1_settings())


def load_dataset(name: str) -> int:
    return m1_load(m1_settings(dataset=name)).graph_triples_in_store


@pytest.fixture(scope="session", autouse=True)
def _restore_calm_after_session():
    yield
    if fuseki_up():  # leave a shared store in a known baseline state
        with contextlib.suppress(Exception):  # best-effort cleanup
            load_dataset("calm")


@pytest.fixture
def require_fuseki() -> None:
    if not fuseki_up():
        pytest.skip(f"Fuseki not reachable at {m1_settings().fuseki_base_url}")


@pytest.fixture
def stressed(require_fuseki: None) -> None:
    load_dataset("stressed")


@pytest.fixture
def runner(require_fuseki: None) -> FusekiRunner:
    s = m0_settings()
    return FusekiRunner(query_url=s.query_url, gsp_url=s.gsp_url)


@pytest.fixture
def fuseki_store(require_fuseki: None) -> FusekiStore:
    s = m2_settings()
    return FusekiStore(s.query_url, s.update_url)


@pytest.fixture
def audit(tmp_path: Path) -> AuditLog:
    return AuditLog(tmp_path / "audit.jsonl")


@pytest.fixture
def service(fuseki_store: FusekiStore, audit: AuditLog) -> ActionService:
    return ActionService(fuseki_store, audit, m2_settings().shapes_path)
