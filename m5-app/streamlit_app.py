"""Counterparty Concentration Lens — the demo screen (M5).

Run:  streamlit run m5-app/streamlit_app.py
Needs a running Fuseki with a dataset loaded (see M0/M1).
"""

from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
import streamlit as st

# Make the sibling module packages importable when launched via `streamlit run`
# (this must happen BEFORE the lens_* imports below).
_REPO = Path(__file__).resolve().parent.parent
for _mod in (
    "m5-app",
    "m0-ontology",
    "m1-ingestion",
    "m2-actions",
    "m3-security",
    "m4-ai",
    "capstone",
):
    _path = str(_REPO / _mod)
    if _path not in sys.path:
        sys.path.insert(0, _path)

from lens_m3.portfolios import DEFAULT_USER, DEMO_USERS  # noqa: E402
from lens_m4 import agent, ollama  # noqa: E402
from lens_m5 import data  # noqa: E402
from lens_m5.bootstrap import REPO_ROOT, build_context, reload_dataset  # noqa: E402

st.set_page_config(page_title="Counterparty Concentration Lens", layout="wide")


def _m(value: Decimal | float | str) -> str:
    return f"SGD {float(Decimal(str(value))) / 1e6:,.1f}M"


@st.cache_resource
def _ctx():
    return build_context()


def main() -> None:
    ctx = _ctx()
    ss = st.session_state
    ss.setdefault("dataset", os.environ.get("LENS_DATASET", "calm"))

    # --- sidebar: identity, dataset, reset ---------------------------------- #
    with st.sidebar:
        st.header("Lens controls")
        user_key = st.selectbox(
            "Signed in as (role)", list(DEMO_USERS), index=list(DEMO_USERS).index(DEFAULT_USER)
        )
        principal = DEMO_USERS[user_key]
        st.caption(
            f"role: **{principal.role}**"
            + (f" · portfolio: {principal.portfolios}" if principal.portfolios else "")
        )
        st.divider()
        st.subheader("Scenario reset")
        col_a, col_b = st.columns(2)
        if col_a.button("Reset to calm"):
            ss["dataset"] = "calm"
            reload_dataset("calm")
            st.rerun()
        if col_b.button("Reset to stressed"):
            ss["dataset"] = "stressed"
            reload_dataset("stressed")
            st.rerun()
        st.caption(
            f"OPA policy: {'on' if ctx.opa_available else 'unavailable'} · "
            f"NL engine: {'Ollama' if ollama.is_available() else 'template'}"
        )

    if not ctx.runner.is_up(ctx.ping_url):
        st.error("Fuseki is not reachable. Start it and load a dataset (M0/M1).")
        st.stop()

    # --- M3: scope the visible group set ------------------------------------ #
    heads = data.group_heads(ctx.runner)
    candidates = [h for h, _ in heads]
    visible = ctx.policy.visible_groups(principal.role, principal.portfolios, candidates)
    m2h = data.member_to_head(ctx.runner)
    name_of = dict(heads)

    # --- banner ------------------------------------------------------------- #
    ds = ss["dataset"]
    if ds.startswith("imported:"):
        st.warning(
            f"📥 Dataset: IMPORTED — '{ds.split(':', 1)[1]}'. Bring-Your-Own **TEST** "
            "data (synthetic/sample only). Reset to calm/stressed to restore the bundled set."
        )
    elif ds == "stressed":
        st.warning(
            "⚠ Dataset: STRESSED — illustrative synthetic data, deliberately engineered "
            "to breach risk thresholds. Not real portfolio statistics."
        )
    else:
        st.info("Dataset: CALM — illustrative synthetic data (metrics within normal bands).")
    st.caption(
        f"Scenario Sandbox — synthetic data · viewing as **{principal.role}** "
        f"({len(visible)}/{len(candidates)} counterparty groups visible)"
    )

    tabs = st.tabs(
        ["Dashboard", "Explore", "Ask (NL)", "Scenario Sandbox", "Bring Your Own", "Audit"]
    )

    # ---------------------------------------------------------------- Dashboard
    with tabs[0]:
        dash = data.dashboard(ctx.runner, ctx.queries_dir, visible, m2h)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "HHI (connected)",
            f"{float(dash.hhi.connected):.3f}",
            f"direct {float(dash.hhi.direct):.3f}",
        )
        c2.metric(
            "CR10 (connected)",
            f"{float(dash.cr10.connected) * 100:.0f}%",
            f"direct {float(dash.cr10.direct) * 100:.0f}%",
        )
        top_sector = max(dash.sectors.items(), key=lambda kv: kv[1], default=("-", Decimal(0)))
        c3.metric("Top sector", top_sector[0], f"{float(top_sector[1]) * 100:.0f}%")
        c4.metric(
            "Watchlist (red/amber)",
            f"{sum(w.band == 'red' for w in dash.watchlist)}/"
            f"{sum(w.band == 'amber' for w in dash.watchlist)}",
        )
        st.caption(
            "HHI/CR10/sector are book-level; watchlist, WWR and the table below are role-scoped."
        )

        st.subheader("Exposures (connected, risk-owner)")
        df = pd.DataFrame(
            [
                {
                    "group": e.head,
                    "name": e.name,
                    "sector": e.sector,
                    "connected (SGD m)": float(e.connected) / 1e6,
                }
                for e in dash.exposures
            ]
        )
        if not df.empty:
            sectors = st.multiselect("Filter sector", sorted(df["sector"].unique()))
            if sectors:
                df = df[df["sector"].isin(sectors)]
        st.dataframe(df, width="stretch", hide_index=True)

        st.subheader("Watchlist (connected utilisation)")
        wl = pd.DataFrame(
            [
                {
                    "entity": w.entity,
                    "name": w.entity_name,
                    "band": w.band,
                    "utilisation": f"{float(w.utilisation) * 100:.0f}%",
                    "connected": _m(w.connected),
                    "limit": _m(w.limit),
                }
                for w in dash.watchlist
            ]
        )
        if not wl.empty:
            wband = st.multiselect("Filter band", sorted(wl["band"].unique()), key="wl_band")
            if wband:
                wl = wl[wl["band"].isin(wband)]
        st.dataframe(wl, width="stretch", hide_index=True)

        if dash.wwr:
            st.subheader("Structural wrong-way risk")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "loan": f.loan,
                            "borrower": f.borrower_name or f.borrower,
                            "issuer": f.issuer_name or f.issuer,
                        }
                        for f in dash.wwr
                    ]
                ),
                width="stretch",
                hide_index=True,
            )

        nets = ctx.service.net_exposures()
        if nets:
            st.subheader("Net exposure (post-collateral / netting)")
            st.caption(
                "Gross single-name exposure reduced by eligible collateral = value × (1 − haircut)."
            )
            ndf = pd.DataFrame(
                [
                    {
                        "entity": n.entity,
                        "name": n.name,
                        "sector": n.sector,
                        "gross": _m(n.gross),
                        "collateral mitigant": _m(n.mitigant),
                        "net (post-CRM)": _m(n.net),
                    }
                    for n in nets
                ]
            )
            nsec = st.multiselect(
                "Filter sector (net exposure)", sorted(ndf["sector"].unique()), key="net_sector"
            )
            if nsec:
                ndf = ndf[ndf["sector"].isin(nsec)]
            st.dataframe(ndf, width="stretch", hide_index=True)

    # ------------------------------------------------------------------- Explore
    with tabs[1]:
        visible_heads = [(h, name_of.get(h, h)) for h in candidates if h in visible]
        if not visible_heads:
            st.info("No counterparty groups in your portfolio.")
        else:
            choice = st.selectbox("Counterparty group", visible_heads, format_func=lambda x: x[1])
            gv = data.group_view(ctx.runner, ctx.queries_dir, choice[0])
            d1, d2, d3 = st.columns(3)
            d1.metric("Direct (named entity)", _m(gv.direct_head_only))
            d2.metric("Direct (group)", _m(gv.direct_group))
            d3.metric(
                "Connected (multi-hop)",
                _m(gv.connected),
                "BREACH" if gv.limit_breached else "within limit",
            )
            st.caption(
                f"Group limit {_m(gv.group_limit)} — "
                + ("**breached** on connected exposure" if gv.limit_breached else "within limit")
            )
            st.dataframe(
                pd.DataFrame([{**c, "amount": _m(c["amount"])} for c in gv.contributions]),
                width="stretch",
                hide_index=True,
            )

        st.subheader("NBFI cascade")
        cascade = data.cascade_view(ctx.runner, ctx.queries_dir, "LE-0030")
        total = sum((Decimal(c["amount"]) for c in cascade), Decimal(0))
        st.caption(f"If Nimbus (LE-0030) fails, second-order connected exposure = {_m(total)}")
        st.dataframe(
            pd.DataFrame([{**c, "amount": _m(c["amount"])} for c in cascade]),
            width="stretch",
            hide_index=True,
        )

    # ------------------------------------------------------------------- Ask NL
    with tabs[2]:
        st.write(
            "Ask about exposure to a group, top counterparties, names near their limit, "
            "guarantee chains, sector concentration, or wrong-way risk."
        )
        q = st.text_input("Question", "What is our total exposure to the Acme group?")
        if q:
            res = agent.answer(
                q,
                ctx.runner,
                label_index=data.label_index(ctx.runner),
                visible_groups=visible,
                member_to_head=m2h,
            )
            st.info(res.summary)
            if res.sparql:
                with st.expander(f"Generated SPARQL (engine: {res.engine}; read-only, validated)"):
                    st.code(res.sparql, language="sparql")
            if res.rows:
                st.dataframe(pd.DataFrame(res.rows), width="stretch", hide_index=True)

    # --------------------------------------------------------------- Sandbox
    with tabs[3]:
        st.warning(
            "Scenario Sandbox — synthetic data. Every change is validated (SHACL) and "
            "audited via the M2 action layer; the UI never writes to Fuseki directly."
        )
        role = principal.role
        with st.form("add_loan"):
            st.subheader("Add a loan (record exposure)")
            lid = st.text_input("Loan id", "LN-9100")
            borrower = st.selectbox(
                "Borrower",
                candidates + [h for h in m2h if h not in candidates],
                format_func=lambda x: name_of.get(x, x),
            )
            principal_amt = st.number_input(
                "Principal (SGD)", min_value=1, value=30_000_000, step=1_000_000
            )
            if st.form_submit_button("Submit via M2"):
                r = ctx.service.create_loan(
                    loan_id=lid,
                    lender_id="LE-0099",
                    borrower_id=borrower,
                    principal=int(principal_amt),
                    actor=principal.role,
                    role=role,
                )
                (st.success if r.accepted else st.error)(f"{r.reason}")
                if r.flags:
                    st.warning("Flags: " + ", ".join(r.flags))

        with st.form("deactivate"):
            st.subheader("Soft-delete (deactivate)")
            sid = st.text_input("Subject id", "GTY-2002")
            kind = st.selectbox("Kind", ["guaranty", "loan", "collateral", "limit", "entity"])
            if st.form_submit_button("Deactivate via M2"):
                r = ctx.service.deactivate(
                    subject_id=sid, kind=kind, actor=principal.role, role=role
                )
                (st.success if r.accepted else st.error)(r.reason)

    # --------------------------------------------------------- Bring Your Own
    with tabs[4]:
        from lens_m1 import byod

        st.warning(
            "Bring-Your-Own **TEST** Data — synthetic / sample only. Not for real, "
            "production, or customer data. Imported rows are validated (SHACL) and "
            "audited through the M2 path; on success they load as a named dataset that "
            "never overwrites calm/stressed (use 'Reset' in the sidebar to restore)."
        )
        st.caption("Folder of CSVs in the documented template shape (see templates/README.md).")
        source = st.text_input("Source folder path", str(REPO_ROOT / "templates"))
        mapping_path = st.text_input("Mapping YAML (optional, for differently-shaped CSVs)", "")
        name = st.text_input("Dataset name", "my-scenario")
        allow_partial = st.checkbox("Allow partial load (skip rejected rows)", value=False)
        if st.button("Validate & import via M2"):
            try:
                mapping = byod.load_mapping(Path(mapping_path)) if mapping_path else None
                rows = byod.read_source(Path(source), mapping)
                report = ctx.service.import_dataset(
                    rows,
                    dataset_name=name,
                    actor=principal.role,
                    role=principal.role,
                    allow_partial=allow_partial,
                )
            except byod.ByodError as exc:
                st.error(f"Import aborted: {exc}")
            else:
                summary = (
                    f"{report.accepted} accepted · {report.rejected} rejected · "
                    f"loaded={report.loaded} ({report.triples} triples)"
                )
                (st.success if report.loaded else st.error)(summary)
                if report.rejections():
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "table": r.table,
                                    "id": r.record_id,
                                    "reason": "; ".join(r.reasons),
                                }
                                for r in report.rejections()
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                if report.loaded:
                    ss["dataset"] = f"imported:{name}"
                    st.rerun()

    # ----------------------------------------------------------------- Audit
    with tabs[5]:
        st.subheader("Audit log (who / what / when)")
        entries = ctx.audit.entries()
        if entries:
            st.dataframe(pd.DataFrame(entries[-50:]), width="stretch", hide_index=True)
        else:
            st.caption("No sandbox actions yet.")


main()
