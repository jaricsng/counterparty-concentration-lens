"""AppTest interaction: clicking buttons must not crash (regression guards).

These drive real widgets (not just the initial render) against a live Fuseki —
which is how the ``principal`` shadowing bug in the sandbox/BYOD tabs slipped past
the render-only smoke test (the crash only happened on button click).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

pytestmark = pytest.mark.integration

APP = Path(__file__).resolve().parent.parent / "m5-app" / "streamlit_app.py"


def _run_app() -> AppTest:
    # ensure data is loaded so the dashboard renders before we interact
    from lens_m1.config import load_settings
    from lens_m1.loader import load

    load(load_settings(dataset="calm"))
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.run()
    return at


def test_byod_import_button_does_not_crash(require_fuseki: None) -> None:
    at = _run_app()
    buttons = [b for b in at.button if "import" in b.label.lower()]
    assert buttons, "BYOD 'Validate & import' button not found"
    buttons[0].click().run()
    assert len(at.exception) == 0  # the principal-shadowing bug raised here
    assert any("IMPORTED" in str(m.value) for m in at.warning)


def test_sandbox_submit_loan_does_not_crash(require_fuseki: None) -> None:
    at = _run_app()
    submits = [b for b in at.button if "submit via m2" in b.label.lower()]
    assert submits, "Sandbox 'Submit via M2' button not found"
    submits[0].click().run()
    assert len(at.exception) == 0
