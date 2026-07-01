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

import os
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
    # Make the app's session dataset match what we loaded into Fuseki (in normal
    # use the "Reset to <set>" button does both); the stress base follows it.
    os.environ["LENS_DATASET"] = dataset
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    assert not at.exception
    return at


def _one(widgets, needle: str):
    return next(w for w in widgets if needle in (w.label or "").lower())


def test_byod_import_button_does_not_crash(require_fuseki: None) -> None:
    at = _run_app("calm")
    # match the exact BYOD button — a substring match would also hit the palette
    # example "Which counterparty is most systemically IMPORTant?".
    button = next(b for b in at.button if b.label == "Validate & import via M2")
    button.click().run()
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


def test_nl_chat_net_exposure_question_via_app(require_fuseki: None) -> None:
    # type a net-exposure question into the chat box -> agent -> live Fuseki
    at = _run_app("stressed")
    at.chat_input[0].set_value("what is the net exposure after collateral?").run()
    assert len(at.exception) == 0
    answer = " ".join(str(m.value) for m in at.info).lower()
    assert "net" in answer and ("collateral" in answer or "helios" in answer)


def test_nl_chat_is_multiturn_with_history(require_fuseki: None) -> None:
    # two turns persist in the conversation, each answered + grounded
    at = _run_app("stressed")
    at.chat_input[0].set_value("what is our total expected loss?").run()
    at.chat_input[0].set_value("which counterparty is most systemically important?").run()
    assert len(at.exception) == 0
    text = " ".join(str(m.value) for m in at.info).lower()
    assert "expected loss" in text  # first turn still rendered (history)
    assert "systemic" in text  # second turn rendered
    # both turns kept their generated SPARQL / computed query in expanders
    assert sum(1 for e in at.expander if "generated sparql" in (e.label or "").lower()) >= 2


def test_nl_chat_followup_reuses_last_group(require_fuseki: None) -> None:
    # "exposure to Acme?" then a group-less follow-up reuses Acme as context
    at = _run_app("stressed")
    at.chat_input[0].set_value("what is our exposure to the Acme group?").run()
    at.chat_input[0].set_value("show guarantee chains").run()
    assert len(at.exception) == 0
    # the follow-up resolved to a guarantee-chains answer about the remembered group
    answers = [str(m.value).lower() for m in at.info]
    assert any("guarantee" in a for a in answers)


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


def test_dashboard_shows_country_rating_concentration(require_fuseki: None) -> None:
    at = _run_app("stressed")
    ctable = next(df.value for df in at.dataframe if "country" in list(map(str, df.value.columns)))
    assert ctable.iloc[0]["country"] == "SG"  # sorted desc -> home market on top
    rtable = next(df.value for df in at.dataframe if "rating" in list(map(str, df.value.columns)))
    assert rtable.iloc[0]["rating"] == "BB"  # sub-investment-grade dominates


def test_country_filter_narrows(require_fuseki: None) -> None:
    at = _run_app("stressed")
    ms = next(m for m in at.multiselect if (m.label or "").lower() == "filter country")
    ms.set_value(["HK"]).run()
    ctable = next(df.value for df in at.dataframe if "country" in list(map(str, df.value.columns)))
    assert set(ctable["country"]) == {"HK"}


def test_dashboard_expected_loss_and_capital(require_fuseki: None) -> None:
    at = _run_app("stressed")
    labels = {str(m.label) for m in at.metric}
    assert {"Total EAD", "Expected loss", "RWA", "Capital (8%)"} <= labels
    eltable = next(
        df.value for df in at.dataframe if "expected loss" in list(map(str, df.value.columns))
    )
    helios = eltable[eltable["entity"] == "LE-0011"]
    assert not helios.empty and helios.iloc[0]["rating"] == "BB"


def test_expected_loss_rating_filter(require_fuseki: None) -> None:
    at = _run_app("stressed")
    ms = next(m for m in at.multiselect if (m.label or "").lower() == "filter rating (el)")
    ms.set_value(["B"]).run()
    eltable = next(
        df.value for df in at.dataframe if "expected loss" in list(map(str, df.value.columns))
    )
    assert set(eltable["rating"]) == {"B"}


def test_dashboard_stress_scenario(require_fuseki: None) -> None:
    # default scenario (nbfi_downgrade): a B->CCC name is the biggest EL mover
    at = _run_app("stressed")
    stable = next(
        df.value for df in at.dataframe if any("Δ EL" in str(c) for c in df.value.columns)
    )
    assert "CCC" in str(stable.iloc[0]["rating"])
    assert stable.iloc[0]["entity"] in {"LE-0022", "LE-0023", "LE-0047"}


def test_stress_rating_filter(require_fuseki: None) -> None:
    at = _run_app("stressed")
    ms = next(m for m in at.multiselect if (m.label or "").lower() == "filter shocked rating")
    ms.set_value(["CCC"]).run()
    stable = next(
        df.value for df in at.dataframe if any("Δ EL" in str(c) for c in df.value.columns)
    )
    assert all("CCC" in str(r) for r in stable["rating"])


def test_dashboard_xva_cva(require_fuseki: None) -> None:
    at = _run_app("stressed")
    xtable = next(df.value for df in at.dataframe if "peak PFE" in list(map(str, df.value.columns)))
    assert xtable.iloc[0]["rating"] in ("B", "CCC", "BB")  # CVA-sorted; worst grade on top


def test_xva_rating_filter(require_fuseki: None) -> None:
    at = _run_app("stressed")
    ms = next(m for m in at.multiselect if (m.label or "").lower() == "filter rating (cva)")
    ms.set_value(["B"]).run()
    xtable = next(df.value for df in at.dataframe if "peak PFE" in list(map(str, df.value.columns)))
    assert set(xtable["rating"]) == {"B"}


def test_dashboard_ifrs9_staging(require_fuseki: None) -> None:
    at = _run_app("stressed")
    labels = {str(m.label) for m in at.metric}
    assert "Total recognised ECL" in labels and "Stage 2 ECL" in labels
    etable = next(
        df.value for df in at.dataframe if "lifetime ECL" in list(map(str, df.value.columns))
    )
    assert 2 in set(etable["stage"])  # sub-IG cluster in stage 2


def test_ifrs9_stage_filter(require_fuseki: None) -> None:
    at = _run_app("stressed")
    ms = next(m for m in at.multiselect if (m.label or "").lower() == "filter stage")
    ms.set_value([2]).run()
    etable = next(
        df.value for df in at.dataframe if "lifetime ECL" in list(map(str, df.value.columns))
    )
    assert set(etable["stage"]) == {2}


def test_dashboard_systemic_contagion(require_fuseki: None) -> None:
    at = _run_app("stressed")
    ctable = next(
        df.value for df in at.dataframe if "amplification" in list(map(str, df.value.columns))
    )
    assert ctable.iloc[0]["seed group"] == "LE-0030"  # Nimbus: small direct, top systemic


def test_contagion_amplifying_filter(require_fuseki: None) -> None:
    at = _run_app("stressed")
    cb = next(c for c in at.checkbox if "amplifying" in (c.label or "").lower())
    cb.set_value(True).run()
    ctable = next(
        df.value for df in at.dataframe if "amplification" in list(map(str, df.value.columns))
    )
    assert all(float(str(a).replace("×", "")) > 1 for a in ctable["amplification"])


def test_dashboard_full_xva_breakdown(require_fuseki: None) -> None:
    at = _run_app("stressed")
    assert "Portfolio total xVA" in {str(m.label) for m in at.metric}
    ftable = next(
        df.value for df in at.dataframe if "total xVA" in list(map(str, df.value.columns))
    )
    assert {"CVA", "DVA", "FVA", "MVA", "KVA"} <= set(map(str, ftable.columns))


def test_full_xva_rating_filter(require_fuseki: None) -> None:
    at = _run_app("stressed")
    ms = next(m for m in at.multiselect if (m.label or "").lower() == "filter rating (xva)")
    ms.set_value(["B"]).run()
    ftable = next(
        df.value for df in at.dataframe if "total xVA" in list(map(str, df.value.columns))
    )
    assert set(ftable["rating"]) == {"B"}


def test_dashboard_macro_stress(require_fuseki: None) -> None:
    # default macro scenario (property_crash): CRE is the hardest-hit sector
    at = _run_app("stressed")
    mtable = next(
        df.value
        for df in at.dataframe
        if "downgrade" in list(map(str, df.value.columns))
        and "Δ EL" in list(map(str, df.value.columns))
    )
    assert mtable.iloc[0]["sector"] == "commercial real estate"


def test_macro_downgraded_only_filter(require_fuseki: None) -> None:
    at = _run_app("stressed")
    cb = next(c for c in at.checkbox if "downgraded sectors only" in (c.label or "").lower())
    cb.set_value(True).run()
    mtable = next(
        df.value
        for df in at.dataframe
        if "downgrade" in list(map(str, df.value.columns))
        and "Δ EL" in list(map(str, df.value.columns))
    )
    assert all(str(d) != "−0" for d in mtable["downgrade"])


def test_dashboard_multiround_cascade(require_fuseki: None) -> None:
    at = _run_app("stressed")
    mtable = next(
        df.value for df in at.dataframe if "2nd-order" in list(map(str, df.value.columns))
    )
    assert mtable.iloc[0]["2nd-order"] >= 1  # worst cascade has second-order defaults


def test_multiround_second_order_filter(require_fuseki: None) -> None:
    at = _run_app("stressed")
    cb = next(c for c in at.checkbox if "second-order cascades only" in (c.label or "").lower())
    cb.set_value(True).run()
    mtable = next(
        df.value for df in at.dataframe if "2nd-order" in list(map(str, df.value.columns))
    )
    assert all(int(v) > 0 for v in mtable["2nd-order"])


def test_nl_chat_palette_button_asks(require_fuseki: None) -> None:
    # clicking a starter-prompt button submits it as a chat turn
    at = _run_app("stressed")
    btn = next(b for b in at.button if b.label == "What is our total expected loss?")
    btn.click().run()
    assert len(at.exception) == 0
    answer = " ".join(str(m.value) for m in at.info).lower()
    assert "expected loss" in answer


def test_nl_chat_followup_what_about_reuses_intent(require_fuseki: None) -> None:
    # "exposure to Acme?" then a bare "what about Vortex?" reuses the exposure intent
    at = _run_app("stressed")
    at.chat_input[0].set_value("what is our exposure to the Acme group?").run()
    at.chat_input[0].set_value("what about Vortex?").run()
    assert len(at.exception) == 0
    # the follow-up produced a connected-exposure answer (not the unsupported help text)
    answers = [str(m.value).lower() for m in at.info]
    assert any("connected exposure" in a for a in answers[-2:])


def test_nl_palette_shows_inline_result_table(require_fuseki: None) -> None:
    # clicking a palette example renders its answer + result table INLINE under the area
    at = _run_app("stressed")
    btn = next(b for b in at.button if b.label == "What is our total expected loss?")
    btn.click().run()
    assert len(at.exception) == 0
    infos = " ".join(str(m.value) for m in at.info).lower()
    assert "total expected loss" in infos  # inline summary, prefixed with the question
    # the expected-loss result table (raw agent columns) rendered inline
    assert any({"el", "capital"} <= set(map(str, df.value.columns)) for df in at.dataframe)


def test_nl_palette_areas_hold_independent_results(require_fuseki: None) -> None:
    # two areas each keep their own inline result after successive clicks
    at = _run_app("stressed")
    next(b for b in at.button if b.label == "What is our total CVA?").click().run()
    next(b for b in at.button if b.label == "Which country are we most exposed to?").click().run()
    assert len(at.exception) == 0
    infos = " ".join(str(m.value) for m in at.info).lower()
    assert "cva" in infos and "country" in infos  # both areas' inline answers persist


def test_nl_palette_click_is_inline_only_not_in_thread(require_fuseki: None) -> None:
    at = _run_app("stressed")
    next(b for b in at.button if b.label == "What is our total CVA?").click().run()
    # the answer shows inline (info) but the chat thread stays empty
    assert any("cva" in str(m.value).lower() for m in at.info)
    assert at.session_state["nl_history"] == []
    # a typed question, by contrast, IS logged to the thread
    at.chat_input[0].set_value("what is our total expected loss?").run()
    assert len(at.session_state["nl_history"]) == 1
