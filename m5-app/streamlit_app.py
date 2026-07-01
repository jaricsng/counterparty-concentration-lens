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

from lens_m1 import contagion as lens_contagion  # noqa: E402
from lens_m1 import datasets as lens_datasets  # noqa: E402
from lens_m1 import ifrs9 as lens_ifrs9  # noqa: E402
from lens_m1 import macro as lens_macro  # noqa: E402
from lens_m1 import metrics as lens_metrics  # noqa: E402
from lens_m1 import reverse_stress as lens_reverse  # noqa: E402
from lens_m1 import scenarios as lens_scenarios  # noqa: E402
from lens_m1 import xva as lens_xva  # noqa: E402
from lens_m3.portfolios import DEFAULT_USER, DEMO_USERS  # noqa: E402
from lens_m4 import agent, ollama  # noqa: E402
from lens_m5 import data  # noqa: E402
from lens_m5.bootstrap import REPO_ROOT, build_context, reload_dataset  # noqa: E402

st.set_page_config(page_title="Counterparty Concentration Lens", layout="wide")


def _m(value: Decimal | float | str) -> str:
    return f"SGD {float(Decimal(str(value))) / 1e6:,.1f}M"


def _signed_m(delta: Decimal) -> str:
    return f"{'+' if delta >= 0 else '−'}{_m(abs(delta))}"


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

        st.subheader("Country & rating concentration (connected, risk-owner)")
        top_ctry = max(dash.countries.items(), key=lambda kv: kv[1], default=("-", Decimal(0)))
        top_rtg = max(dash.ratings.items(), key=lambda kv: kv[1], default=("-", Decimal(0)))
        st.caption(
            f"Top country: **{top_ctry[0]}** {float(top_ctry[1]) * 100:.0f}% · "
            f"Top rating: **{top_rtg[0]}** {float(top_rtg[1]) * 100:.0f}% "
            "(attributed to the risk-owner; sub-investment-grade = BB and below)."
        )
        cc, rc = st.columns(2)
        with cc:
            cdf = pd.DataFrame(
                [
                    {"country": k, "share": f"{float(v) * 100:.0f}%"}
                    for k, v in sorted(dash.countries.items(), key=lambda kv: -kv[1])
                ]
            )
            if not cdf.empty:
                pick = st.multiselect("Filter country", cdf["country"].tolist(), key="ctry_f")
                if pick:
                    cdf = cdf[cdf["country"].isin(pick)]
            st.dataframe(cdf, width="stretch", hide_index=True)
        with rc:
            rdf = pd.DataFrame(
                [
                    {"rating": k, "share": f"{float(v) * 100:.0f}%"}
                    for k, v in sorted(dash.ratings.items(), key=lambda kv: -kv[1])
                ]
            )
            if not rdf.empty:
                pick = st.multiselect("Filter rating", rdf["rating"].tolist(), key="rtg_f")
                if pick:
                    rdf = rdf[rdf["rating"].isin(pick)]
            st.dataframe(rdf, width="stretch", hide_index=True)

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

        # General (correlation-proxy) WWR: collateral issuer in a different group but the
        # same sector/country as the borrower — quality deteriorates together.
        _wwr_spec = lens_datasets.get_dataset(ds if ds in ("calm", "stressed") else "stressed")
        gen_wwr = lens_metrics.general_wwr_flags(_wwr_spec)
        if gen_wwr:
            st.subheader("General wrong-way risk (correlation proxy)")
            st.caption(
                "Collateral issued by a **different-group** entity sharing the borrower's "
                "sector/country — a structural proxy for exposure↔credit-quality correlation, "
                "not a statistical one."
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "loan": f["loan"],
                            "borrower": name_of.get(f["borrower"], f["borrower"]),
                            "issuer": name_of.get(f["issuer"], f["issuer"]),
                            "correlated via": f["driver"],
                        }
                        for f in gen_wwr
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

        cap = ctx.service.capital_summary()
        st.subheader("Expected loss & capital (simplified, point-in-time)")
        st.caption(
            "EAD = net (post-collateral) exposure · PD from rating · EL = PD × LGD × EAD · "
            "RWA = standardised risk-weight × EAD · capital = 8% × RWA. "
            "Deterministic point-in-time view — NOT Monte-Carlo PFE/CVA or full IFRS-9."
        )
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total EAD", _m(cap.total_ead))
        k2.metric("Expected loss", _m(cap.total_el))
        k3.metric("RWA", _m(cap.total_rwa))
        k4.metric("Capital (8%)", _m(cap.total_capital))
        eldf = pd.DataFrame(
            [
                {
                    "entity": r.entity,
                    "name": r.name,
                    "sector": r.sector,
                    "rating": r.rating,
                    "EAD": _m(r.ead),
                    "PD": f"{float(r.pd) * 100:.2f}%",
                    "expected loss": f"SGD {float(r.el):,.0f}",
                    "capital": f"SGD {float(r.capital):,.0f}",
                }
                for r in ctx.service.expected_losses()
            ]
        )
        if not eldf.empty:
            f1, f2 = st.columns(2)
            rsel = f1.multiselect(
                "Filter rating (EL)", sorted(eldf["rating"].unique()), key="el_rating"
            )
            ssel = f2.multiselect(
                "Filter sector (EL)", sorted(eldf["sector"].unique()), key="el_sector"
            )
            if rsel:
                eldf = eldf[eldf["rating"].isin(rsel)]
            if ssel:
                eldf = eldf[eldf["sector"].isin(ssel)]
        st.dataframe(eldf, width="stretch", hide_index=True)

        # ----- Stress / scenario (what-if) -----
        st.subheader("Stress / scenario (what-if)")
        base_name = ds if ds in ("calm", "stressed") else "stressed"
        st.caption(
            f"Deterministic named shocks re-derive every metric on the **{base_name}** base. "
            "A what-if overlay — NOT a Monte-Carlo simulation or macro model."
        )
        spec = lens_datasets.get_dataset(base_name)
        scen_keys = [k for k in lens_scenarios.SCENARIOS if k != "base"]
        pick = st.selectbox(
            "Scenario", scen_keys, format_func=lambda k: lens_scenarios.SCENARIOS[k].label
        )
        st.caption(lens_scenarios.SCENARIOS[pick].description)
        base_snap, shock_snap = lens_scenarios.compare(spec, pick)
        s1, s2, s3, s4 = st.columns(4)
        s1.metric(
            "Expected loss",
            _m(shock_snap.total_el),
            _signed_m(shock_snap.total_el - base_snap.total_el),
            delta_color="inverse",
        )
        s2.metric(
            "Capital",
            _m(shock_snap.total_capital),
            _signed_m(shock_snap.total_capital - base_snap.total_capital),
            delta_color="inverse",
        )
        s3.metric(
            "Net EAD",
            _m(shock_snap.total_ead),
            _signed_m(shock_snap.total_ead - base_snap.total_ead),
            delta_color="inverse",
        )
        s4.metric(
            "Watchlist red/amber",
            f"{shock_snap.watchlist_red}/{shock_snap.watchlist_amber}",
            f"base {base_snap.watchlist_red}/{base_snap.watchlist_amber}",
        )
        sdf = pd.DataFrame(
            [
                {
                    "entity": d.entity,
                    "rating": f"{d.rating_base} → {d.rating_shocked}",
                    "EL base": f"SGD {float(d.el_base):,.0f}",
                    "EL shocked": f"SGD {float(d.el_shocked):,.0f}",
                    "Δ EL": f"SGD {float(d.delta):,.0f}",
                    "_grade": d.rating_shocked,
                }
                for d in lens_scenarios.expected_loss_deltas(spec, pick)
                if d.delta > 0
            ]
        )
        if not sdf.empty:
            gsel = st.multiselect(
                "Filter shocked rating", sorted(sdf["_grade"].unique()), key="stress_rating"
            )
            if gsel:
                sdf = sdf[sdf["_grade"].isin(gsel)]
            st.dataframe(sdf.drop(columns=["_grade"]), width="stretch", hide_index=True)

        # ----- Macro / multi-factor (correlated) stress -----
        st.subheader("Macro / multi-factor stress (correlated)")
        st.caption(
            "A named macro scenario moves several factors together (GDP, rates, property, "
            "spreads); each sector's sensitivity turns that into a rating downgrade. "
            "Deterministic factor model — NOT a simulated correlation matrix."
        )
        mkeys = list(lens_macro.MACRO_SCENARIOS)
        mpick = st.selectbox(
            "Macro scenario", mkeys, format_func=lambda k: lens_macro.MACRO_SCENARIOS[k].label
        )
        st.caption(lens_macro.MACRO_SCENARIOS[mpick].description)
        mbase, mshock = lens_macro.compare(spec, mpick)
        m1c, m2c, m3c = st.columns(3)
        m1c.metric(
            "Expected loss",
            _m(mshock.total_el),
            _signed_m(mshock.total_el - mbase.total_el),
            delta_color="inverse",
        )
        m2c.metric(
            "Capital",
            _m(mshock.total_capital),
            _signed_m(mshock.total_capital - mbase.total_capital),
            delta_color="inverse",
        )
        m3c.metric(
            "Names downgraded", f"{mshock.names_downgraded}", f"{mshock.total_notches} notches"
        )
        mdf = pd.DataFrame(
            [
                {
                    "sector": si.sector,
                    "downgrade": f"−{si.notches}",
                    "EL base": f"SGD {float(si.el_base):,.0f}",
                    "EL shocked": f"SGD {float(si.el_shocked):,.0f}",
                    "Δ EL": f"SGD {float(si.delta):,.0f}",
                    "_notches": si.notches,
                }
                for si in lens_macro.sector_impacts(spec, mpick)
            ]
        )
        if not mdf.empty:
            hit_only = st.checkbox("Downgraded sectors only", key="macro_hit")
            shown = mdf[mdf["_notches"] > 0] if hit_only else mdf
            st.dataframe(shown.drop(columns=["_notches"]), width="stretch", hide_index=True)

        # ----- Reverse stress (mildest shock to a target) -----
        st.subheader("Reverse stress (mildest shock to a target)")
        st.caption(
            "Inverts stress testing: the **smallest** shock that reaches an adverse outcome. "
            "Downgrades drive EL/capital; exposure uplift drives limit breaches. "
            "Deterministic search over shock severity — not a calibrated optimiser."
        )
        # target value: a float means "× base" (multiplier), a Decimal means an absolute level
        _rev_presets: dict[str, tuple[str, float | Decimal]] = {
            "Double expected loss": ("expected_loss", 2.0),
            "Push capital to 15% of eligible": ("capital_pct_eligible", Decimal("0.15")),
            "Force ≥ 6 connected-limit breaches": ("limit_breaches", Decimal(6)),
        }
        rpick = st.selectbox("Target", list(_rev_presets), key="rev_target")
        _metric, _tv = _rev_presets[rpick]
        if isinstance(_tv, float):
            rev = lens_reverse.multiplier_target(spec, _metric, _tv)
        else:
            rev = lens_reverse.min_shock(spec, _metric, _tv)

        def _fmt_rev(v: Decimal) -> str:
            if _metric == "capital_pct_eligible":
                return f"{float(v) * 100:.1f}%"
            if _metric == "limit_breaches":
                return f"{int(v)}"
            return _m(v)

        r1, r2 = st.columns(2)
        r1.metric("Mildest shock", rev.shock_label)
        r2.metric(
            lens_reverse.METRIC_LABELS[_metric].title(),
            _fmt_rev(rev.achieved),
            f"base {_fmt_rev(rev.base_value)}",
            delta_color="off",
        )

        # ----- Forward-looking exposure (PFE/EE) & CVA -----
        st.subheader("Forward-looking exposure & CVA (analytical, illustrative)")
        st.caption(
            "Analytical EE/PFE profile (amortising base + √t add-on) and unilateral CVA "
            "= LGD·Σ EE·PD·DF on the **"
            f"{base_name}** base. Illustrative shapes — NOT Monte-Carlo paths or derivative MtM."
        )
        xva_rows = lens_xva.portfolio_xva(spec)
        xdf = pd.DataFrame(
            [
                {
                    "entity": r.entity,
                    "rating": r.rating,
                    "EAD": _m(r.ead),
                    "tenor (y)": r.maturity,
                    "peak PFE": _m(r.peak_pfe),
                    "EPE": _m(r.epe),
                    "CVA": f"SGD {float(r.cva):,.0f}",
                    "_grade": r.rating,
                }
                for r in xva_rows
            ]
        )
        if not xdf.empty:
            xsel = st.multiselect(
                "Filter rating (CVA)", sorted(xdf["_grade"].unique()), key="xva_rating"
            )
            shown = xdf[xdf["_grade"].isin(xsel)] if xsel else xdf
            st.dataframe(shown.drop(columns=["_grade"]), width="stretch", hide_index=True)
            by_id = {r.entity: r for r in xva_rows}
            who = st.selectbox("EE/PFE profile for", list(by_id), key="xva_entity")
            row = by_id[who]
            prof = lens_xva.exposure_profile(float(row.ead), row.maturity)
            st.line_chart(
                pd.DataFrame(
                    {"EE": [p.ee / 1e6 for p in prof], "PFE": [p.pfe / 1e6 for p in prof]},
                    index=[p.t for p in prof],
                )
            )

        # ----- Full xVA breakdown (CVA · DVA · FVA · MVA · KVA) -----
        st.markdown("**Full xVA breakdown** (CVA · DVA · FVA · MVA · KVA)")
        st.caption(
            "Each component is a deterministic integral over the same EE/PFE profile + a flat "
            "parameter (funding spread, hurdle rate, own PD) — illustrative, not simulated. "
            "DVA ≈ 0 for a one-directional loan book. Total = CVA − DVA + FVA + MVA + KVA."
        )
        xva_full = lens_xva.portfolio_xva_breakdown(spec)
        fdf = pd.DataFrame(
            [
                {
                    "entity": r.entity,
                    "rating": r.rating,
                    "CVA": f"SGD {float(r.cva):,.0f}",
                    "DVA": f"SGD {float(r.dva):,.0f}",
                    "FVA": f"SGD {float(r.fva):,.0f}",
                    "MVA": f"SGD {float(r.mva):,.0f}",
                    "KVA": f"SGD {float(r.kva):,.0f}",
                    "total xVA": f"SGD {float(r.total_xva):,.0f}",
                    "_grade": r.rating,
                }
                for r in xva_full
            ]
        )
        if not fdf.empty:
            total_xva = sum((r.total_xva for r in xva_full), Decimal(0))
            st.metric("Portfolio total xVA", _m(total_xva))
            fsel = st.multiselect(
                "Filter rating (xVA)", sorted(fdf["_grade"].unique()), key="fullxva_rating"
            )
            shown = fdf[fdf["_grade"].isin(fsel)] if fsel else fdf
            st.dataframe(shown.drop(columns=["_grade"]), width="stretch", hide_index=True)

        # ----- IFRS-9 ECL & staging -----
        st.subheader("IFRS-9 ECL & staging (simplified)")
        st.caption(
            "Stage by rating (1 = performing → 12-month ECL; 2 = sub-investment-grade → "
            "lifetime ECL; 3 = CCC → LGD·EAD). Simplified staging — no SICR backstops or "
            "macro scenarios. Note the Stage-1→2 cliff (lifetime ECL ≫ 12-month)."
        )
        staging = lens_ifrs9.staging_summary(spec)
        g1, g2, g3, g4 = st.columns(4)
        for col, smry in zip((g1, g2, g3), staging, strict=True):
            col.metric(
                f"Stage {smry.stage} ECL", _m(smry.ecl), f"{smry.count} names · EAD {_m(smry.ead)}"
            )
        g4.metric("Total recognised ECL", _m(lens_ifrs9.total_ecl(spec)))
        ecl_rows = lens_ifrs9.portfolio_ecl(spec)
        edf = pd.DataFrame(
            [
                {
                    "entity": r.entity,
                    "rating": r.rating,
                    "stage": r.stage,
                    "EAD": _m(r.ead),
                    "12-month ECL": f"SGD {float(r.ecl_12m):,.0f}",
                    "lifetime ECL": f"SGD {float(r.ecl_lifetime):,.0f}",
                    "recognised ECL": f"SGD {float(r.ecl_recognised):,.0f}",
                    "coverage": f"{float(r.coverage) * 100:.1f}%",
                }
                for r in ecl_rows
            ]
        )
        if not edf.empty:
            stsel = st.multiselect("Filter stage", sorted(edf["stage"].unique()), key="ifrs9_stage")
            if stsel:
                edf = edf[edf["stage"].isin(stsel)]
            st.dataframe(edf, width="stretch", hide_index=True)

        # ----- Systemic contagion (default cascade) -----
        st.subheader("Systemic contagion (default cascade)")
        st.caption(
            "If a group defaults: direct loss (LGD·EAD) + contagion on outside loans that "
            "lose their guarantor. Deterministic two-hop propagation over the exposure graph "
            "— NOT a calibrated network model. Amplification = total ÷ direct."
        )
        casc = lens_contagion.systemic_ranking(spec)
        cas_names = dict(data.group_heads(ctx.runner))
        cdf2 = pd.DataFrame(
            [
                {
                    "seed group": c.seed,
                    "name": cas_names.get(c.seed, c.seed),
                    "group size": c.group_size,
                    "direct loss": _m(c.direct_loss),
                    "contagion loss": _m(c.contagion_loss),
                    "total loss": _m(c.total_loss),
                    "amplification": f"×{float(c.amplification):.1f}",
                    "_contagion": float(c.contagion_loss),
                }
                for c in casc
            ]
        )
        if not cdf2.empty:
            top = casc[0]
            st.caption(
                f"Most systemic: **{cas_names.get(top.seed, top.seed)}** — "
                f"direct {_m(top.direct_loss)} but total {_m(top.total_loss)} "
                f"(×{float(top.amplification):.1f} via guarantee contagion)."
            )
            amplifying = st.checkbox("Amplifying only (contagion > 0)", key="contagion_amp")
            shown = cdf2[cdf2["_contagion"] > 0] if amplifying else cdf2
            st.dataframe(shown.drop(columns=["_contagion"]), width="stretch", hide_index=True)

        # ----- Multi-round cascade with fire-sale spirals -----
        st.markdown("**Multi-round cascade (with fire-sale spirals)**")
        st.caption(
            "Iterates to a fixed point: a defaulter's guarantee obligations topple solvent "
            "guarantors, and dumping collateral lifts a market haircut that deepens losses. "
            "Deterministic iteration — not a calibrated network model. A name can look safe "
            "single-round (its loan is guaranteed) yet topple its guarantor multi-round."
        )
        runs = lens_contagion.systemic_ranking_multiround(spec)
        mrdf = pd.DataFrame(
            [
                {
                    "seed group": r.seed,
                    "name": cas_names.get(r.seed, r.seed),
                    "rounds": r.rounds,
                    "defaulted": r.defaulted,
                    "2nd-order": r.second_order,
                    "fire-sale": f"{float(r.firesale_haircut) * 100:.0f}%",
                    "total loss": _m(r.total_loss),
                    "_second": r.second_order,
                }
                for r in runs
            ]
        )
        if not mrdf.empty:
            worst = runs[0]
            st.caption(
                f"Worst multi-round cascade: **{cas_names.get(worst.seed, worst.seed)}** — "
                f"{worst.rounds} rounds, {worst.defaulted} defaulted "
                f"({worst.second_order} second-order), loss {_m(worst.total_loss)}."
            )
            second_only = st.checkbox("Second-order cascades only", key="mr_second")
            mshown = mrdf[mrdf["_second"] > 0] if second_only else mrdf
            st.dataframe(mshown.drop(columns=["_second"]), width="stretch", hide_index=True)

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
        st.caption(
            "Chat in plain English. **Exposure & concentration:** group · top names · "
            "near-limit · guarantee chains · sector / country / rating · wrong-way risk. "
            "**CCR layer:** net exposure · expected loss · capital · IFRS-9 ECL · PFE / CVA / "
            "xVA · stress · macro · systemic contagion. Read-only, role-scoped, safety-validated; "
            "the generated SPARQL is shown. Follow-ups reuse the last-named group — e.g. "
            "“exposure to Acme?” then “what about Vortex?” or “show its guarantee chains”."
        )
        ss.setdefault("nl_history", [])
        ss.setdefault("nl_last_group", None)
        ss.setdefault("nl_last_intent", None)
        ss.setdefault("nl_area_results", {})

        def _render_turn(turn: dict) -> None:
            with st.chat_message("user"):
                st.write(turn["q"])
            with st.chat_message("assistant"):
                st.info(turn["summary"])
                if turn.get("sparql"):
                    with st.expander(
                        f"Generated SPARQL (engine: {turn['engine']}; read-only, validated)"
                    ):
                        st.code(turn["sparql"], language="sparql")
                if turn.get("rows"):
                    st.dataframe(pd.DataFrame(turn["rows"]), width="stretch", hide_index=True)

        def _run(question: str, *, record: bool = True) -> dict:
            """Answer a question (with follow-up context); ``record`` adds it to the chat
            thread. Palette clicks use ``record=False`` — inline-only, not logged."""
            idx = data.label_index(ctx.runner)
            effective, group = data.resolve_followup(question, ss["nl_last_group"], idx)
            res = agent.answer(
                effective, ctx.runner, label_index=idx, visible_groups=visible, member_to_head=m2h
            )
            if not res.answered:
                # intent carry: a bare "what about Vortex?" reuses the last group-intent
                retry = data.rephrase_for_intent(ss["nl_last_intent"], group or ss["nl_last_group"])
                if retry:
                    res = agent.answer(
                        retry,
                        ctx.runner,
                        label_index=idx,
                        visible_groups=visible,
                        member_to_head=m2h,
                    )
            if group:
                ss["nl_last_group"] = group
            if res.answered and res.intent not in ("none", "unsupported"):
                ss["nl_last_intent"] = res.intent
            turn = {
                "q": question,
                "summary": res.summary,
                "sparql": res.sparql,
                "engine": res.engine,
                "rows": res.rows,
            }
            if record:
                ss["nl_history"].append(turn)
            return turn

        for past in ss["nl_history"]:
            _render_turn(past)

        # Starter-prompt palette — each area shows its clicked example's answer INLINE
        # (summary + result table), so you can explore CCR area by area without scrolling.
        with st.expander("💡 Example questions (click for an inline answer)", expanded=True):
            for area, examples in data.NL_PALETTE:
                st.caption(area)
                cols = st.columns(len(examples))
                for col, example in zip(cols, examples, strict=True):
                    if col.button(example, key=f"ex::{example}"):
                        # inline-only: shown under the area, not added to the chat thread
                        ss["nl_area_results"][area] = _run(example, record=False)
                shown = ss["nl_area_results"].get(area)
                if shown:
                    st.info(f"**{shown['q']}** — {shown['summary']}")
                    if shown.get("rows"):
                        st.dataframe(pd.DataFrame(shown["rows"]), width="stretch", hide_index=True)
        if ss["nl_history"] and st.button("Clear chat", key="nl_clear"):
            ss["nl_history"] = []
            ss["nl_last_group"] = None
            ss["nl_last_intent"] = None
            ss["nl_area_results"] = {}

        prompt = st.chat_input("Ask about exposure, EL, capital, CVA, IFRS-9, stress, contagion…")
        if prompt:
            _render_turn(_run(prompt))

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

        st.subheader("Pre-deal limit check (what-if — no write)")
        st.caption(
            "Would a **proposed** loan breach the limits? Checks the **dynamic** "
            "(rating-adjusted) connected single-name limit, a **tenor** cap, and a "
            "**settlement** sub-limit — read-only, before you book anything."
        )
        pd1, pd2, pd3 = st.columns(3)
        pd_borrower = pd1.selectbox(
            "Borrower ",
            candidates + [h for h in m2h if h not in candidates],
            format_func=lambda x: name_of.get(x, x),
            key="pd_borrower",
        )
        pd_amount = pd2.number_input(
            "Amount (SGD)", min_value=1, value=5_000_000, step=1_000_000, key="pd_amount"
        )
        pd_tenor = pd3.number_input("Tenor (years)", min_value=1, value=3, step=1, key="pd_tenor")
        if st.button("Run pre-deal check", key="pd_run"):
            v = ctx.service.pre_deal_check(
                borrower_id=pd_borrower, amount=int(pd_amount), tenor=int(pd_tenor)
            )
            if v.ok:
                st.success("Deal OK — within limits.")
            else:
                st.error("Deal would breach: " + "; ".join(v.reasons))
            st.caption(
                f"UBO {v.ubo} ({v.rating}) · connected {_m(v.connected_now)} → post "
                f"{_m(v.connected_post)} vs effective limit {_m(v.effective_limit)} "
                f"(base {_m(v.base_limit)}, dynamic) · headroom {_m(v.headroom)} · "
                f"tenor {v.tenor}y/cap {v.tenor_cap}y"
            )

        with st.form("deactivate"):
            st.subheader("Soft-delete (deactivate)")
            sid = st.text_input("Subject id", "GTY-2002")
            kind = st.selectbox("Kind", ["guaranty", "loan", "collateral", "limit", "entity"])
            if st.form_submit_button("Deactivate via M2"):
                r = ctx.service.deactivate(
                    subject_id=sid, kind=kind, actor=principal.role, role=role
                )
                (st.success if r.accepted else st.error)(r.reason)

        st.subheader("Maker-checker approvals (four-eyes)")
        st.caption(
            "A **maker** submits a deactivation; it takes effect only when a **different** "
            "`group_risk` **checker** approves it. Segregation of duties enforced; every "
            "step (submit / approve / reject) is written to the tamper-evident audit trail."
        )
        mk1, mk2 = st.columns(2)
        mc_sid = mk1.text_input("Subject id to deactivate", "GTY-2002", key="mc_subject")
        mc_kind = mk2.selectbox(
            "Kind ", ["guaranty", "loan", "collateral", "limit", "entity"], key="mc_kind"
        )
        if st.button("Submit for approval", key="mc_submit"):
            pc = ctx.service.submit_deactivation(
                subject_id=mc_sid, kind=mc_kind, maker=principal.name, maker_role=role
            )
            st.success(f"Submitted {pc.id} — pending approval by a different group_risk checker.")
        pend = ctx.service.pending_changes()
        if pend:
            st.caption(f"Pending ({len(pend)}) — approval needs `group_risk` and checker ≠ maker:")
            for p in pend:
                a, b, c = st.columns([4, 1, 1])
                a.write(
                    f"**{p.id}** · deactivate {p.kind} `{p.subject_id}` · "
                    f"maker **{p.maker}** ({p.maker_role})"
                )
                if b.button("Approve", key=f"mc_ok_{p.id}"):
                    res = ctx.service.approve(p.id, checker=principal.name, checker_role=role)
                    (st.success if res.accepted else st.error)(res.reason)
                    st.rerun()
                if c.button("Reject", key=f"mc_no_{p.id}"):
                    ctx.service.reject(
                        p.id, checker=principal.name, checker_role=role, reason="rejected in UI"
                    )
                    st.rerun()
        else:
            st.caption("No pending changes.")

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
