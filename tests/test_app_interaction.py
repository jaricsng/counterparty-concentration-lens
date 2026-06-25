"""AppTest behavioral e2e: a UI action flows all the way to the backend.

These drive the *real* app widgets (Streamlit's AppTest harness) against a live
Fuseki and assert the **outcome**, not just that nothing crashed — UI click →
M5 app → M2 ActionService (SHACL) → FusekiStore → Fuseki, then back into the
recomputed metric and the tamper-evident audit trail.

Not a browser test (no Playwright/DOM/websocket) — it exercises the app's logic
and the full backend path deterministically, in the CI integration job.

(The sandbox *Add-a-loan* form's Borrower selectbox uses ``format_func``, which
Streamlit's AppTest can't drive — it returns the display label, not the id — so
the deterministic write here is the soft-delete, whose widgets are plain.)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

pytestmark = pytest.mark.integration

APP = Path(__file__).resolve().parent.parent / "m5-app" / "streamlit_app.py"
NIMBUS = "https://lens.example/id/LE-0030"
_STATUS = (
    "SELECT ?s WHERE {{ <https://lens.example/id/{0}> "
    "<https://lens.example/ontology/status> ?s }}"
)


def _load(dataset: str) -> None:
    from lens_m1.config import load_settings
    from lens_m1.loader import load

    load(load_settings(dataset=dataset))


def _run_app(dataset: str) -> AppTest:
    _load(dataset)
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    assert not at.exception
    return at


def _one(widgets, needle: str):
    return next(w for w in widgets if needle in (w.label or "").lower())


def test_byod_import_button_does_not_crash(require_fuseki: None) -> None:
    at = _run_app("calm")
    buttons = [b for b in at.button if "import" in b.label.lower()]
    assert buttons, "BYOD 'Validate & import' button not found"
    buttons[0].click().run()
    assert len(at.exception) == 0
    assert any("IMPORTED" in str(m.value) for m in at.warning)


def test_sandbox_softdelete_flows_to_ui_backend_audit_and_metric(require_fuseki: None) -> None:
    from lens_m2.config import load_settings as m2cfg
    from lens_m2.derived import connected_exposure
    from lens_m2.store import FusekiStore

    at = _run_app("stressed")
    cfg = m2cfg()
    store = FusekiStore(cfg.query_url, cfg.update_url)

    # before: GTY-2002 is active; Nimbus carries the full NBFI cascade exposure
    assert store.select(_STATUS.format("GTY-2002"))[0]["s"] == "active"
    before = connected_exposure(store, NIMBUS)

    # 1) drive the Soft-delete form — defaults are GTY-2002 / guaranty (plain widgets)
    assert _one(at.text_input, "subject id").value == "GTY-2002"
    _one(at.button, "deactivate via m2").click().run()
    assert not at.exception

    # 2) the UI confirms the soft-delete
    assert any("inactive" in str(s.value) for s in at.success)

    # 3) the backend changed status (history preserved — not a hard delete)
    assert store.select(_STATUS.format("GTY-2002"))[0]["s"] == "inactive"

    # 4) the metric recomputed: Nimbus's connected (cascade) exposure dropped
    after = connected_exposure(store, NIMBUS)
    assert after < before  # 47M -> 40M on stressed

    # 5) the tamper-evident audit trail (Audit tab) recorded the action
    assert any(
        "GTY-2002" in df.value.to_csv() and "deactivate" in df.value.to_csv() for df in at.dataframe
    )


def test_dashboard_shows_net_exposure_post_collateral(require_fuseki: None) -> None:
    # render on stressed -> the dashboard queries the backend for net (post-CRM)
    # exposure and renders the table; assert the computed numbers reach the UI.
    at = _run_app("stressed")
    table = next(
        df.value for df in at.dataframe if "net (post-CRM)" in list(map(str, df.value.columns))
    )
    helios = table[table["entity"] == "LE-0011"]  # 7M gross, 4M bond @ 50% haircut -> 5M net
    assert not helios.empty
    assert helios.iloc[0]["gross"] == "SGD 7.0M"
    assert helios.iloc[0]["net (post-CRM)"] == "SGD 5.0M"


def test_nl_net_exposure_question_via_app(require_fuseki: None) -> None:
    # type a net-exposure question into the app's NL box -> agent -> live Fuseki
    at = _run_app("stressed")
    box = next(t for t in at.text_input if "question" in (t.label or "").lower())
    box.set_value("what is the net exposure after collateral?").run()
    assert len(at.exception) == 0
    answer = " ".join(str(m.value) for m in at.info).lower()
    assert "net" in answer and ("collateral" in answer or "helios" in answer)


def test_net_exposure_sector_filter(require_fuseki: None) -> None:
    # drive the net-exposure sector filter and assert the table narrows
    at = _run_app("stressed")
    ms = next(m for m in at.multiselect if "net exposure" in (m.label or "").lower())
    ms.set_value(["financial services"]).run()
    table = next(
        df.value for df in at.dataframe if "net (post-CRM)" in list(map(str, df.value.columns))
    )
    assert set(table["sector"]) == {"financial services"}
    assert set(table["entity"]) == {"LE-0021", "LE-0030"}
