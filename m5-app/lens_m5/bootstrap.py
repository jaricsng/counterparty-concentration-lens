"""Wire the app to every other module (paths + component factories).

Keeps the Streamlit script free of plumbing: it imports build_context() and gets
a runner (reads), an action service (guarded writes via M2), an OPA policy engine
(M3), and the dataset loader (reset), all pointing at the same Fuseki.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
for _mod in ("m0-ontology", "m1-ingestion", "m2-actions", "m3-security", "m4-ai", "capstone"):
    _p = str(REPO_ROOT / _mod)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lens_m0.config import load_settings as load_m0_settings  # noqa: E402
from lens_m0.fuseki import FusekiRunner  # noqa: E402
from lens_m2.actions import ActionService  # noqa: E402
from lens_m2.audit import AuditLog  # noqa: E402
from lens_m2.config import load_settings as load_m2_settings  # noqa: E402
from lens_m2.store import FusekiStore  # noqa: E402
from lens_m3.policy import PolicyEngine, opa_path  # noqa: E402


@dataclass
class Context:
    runner: FusekiRunner
    service: ActionService
    audit: AuditLog
    policy: PolicyEngine
    queries_dir: Path
    ping_url: str
    opa_available: bool


def build_context() -> Context:
    m0 = load_m0_settings()
    m2 = load_m2_settings()
    runner = FusekiRunner(query_url=m0.query_url, gsp_url=m0.gsp_url)
    store = FusekiStore(m2.query_url, m2.update_url)
    audit = AuditLog(m2.audit_log_path)
    service = ActionService(store, audit, m2.shapes_path)
    ping = f"{m0.fuseki_base_url.rstrip('/')}/$/ping"
    return Context(
        runner=runner,
        service=service,
        audit=audit,
        policy=PolicyEngine(),
        queries_dir=m0.queries_dir,
        ping_url=ping,
        opa_available=opa_path() is not None,
    )


def reload_dataset(dataset: str) -> int:
    """Reset the store to a base dataset (calm/stressed); returns triple count."""
    from lens_m1.config import load_settings as load_m1_settings
    from lens_m1.loader import load

    return load(load_m1_settings(dataset=dataset)).graph_triples_in_store
