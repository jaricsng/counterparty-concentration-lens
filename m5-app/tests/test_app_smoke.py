"""Headless smoke test of the Streamlit app (skips when Fuseki is unavailable)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import requests

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parent.parent.parent
APP = ROOT / "m5-app" / "streamlit_app.py"


def _fuseki_up() -> bool:
    try:
        return requests.get("http://localhost:3030/$/ping", timeout=2).ok
    except requests.RequestException:
        return False


@pytest.fixture(scope="module")
def _loaded_calm() -> None:
    sys.path.insert(0, str(ROOT / "m1-ingestion"))
    from lens_m1.config import load_settings
    from lens_m1.loader import load, server_up

    settings = load_settings(dataset="calm")
    if not server_up(settings):
        pytest.skip("Fuseki not reachable")
    load(settings)


def test_app_renders_without_exception(_loaded_calm: None) -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    assert not at.exception, at.exception
    # The dataset banner and the five tabs are always present.
    text = " ".join(str(m.value) for m in at.info) + " ".join(str(m.value) for m in at.warning)
    assert "CALM" in text or "STRESSED" in text
    assert any("Scenario Sandbox" in str(c.value) for c in at.caption)


def test_app_switches_to_stressed(_loaded_calm: None) -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    # Click "Reset to stressed" and confirm the stressed banner appears.
    for btn in at.button:
        if btn.label == "Reset to stressed":
            btn.click().run()
            break
    warnings = " ".join(str(m.value) for m in at.warning)
    assert "STRESSED" in warnings
