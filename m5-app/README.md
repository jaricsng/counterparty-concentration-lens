# M5 — Exposure app (the demo screen)

The interactive Streamlit tool that ties the whole Lens together: a
concentration **dashboard** (direct vs connected), **filters** and drill-down, an
embedded grounded **NL query box** (M4), and a guarded **Scenario Sandbox** whose
writes go ONLY through the M2 action layer and recompute the metrics live. Reads
are **role-scoped** by the M3 policy. A persistent banner shows the loaded
dataset (calm/stressed) and the synthetic-data framing.

> Learning prototype on synthetic data. Production-shaped, not production-hardened.

## What's here

```
m5-app/
├── streamlit_app.py       # the UI (run with streamlit)
├── lens_m5/bootstrap.py   # wires M0 reads, M2 writes, M3 policy, M4 agent, M1 reset
├── lens_m5/data.py        # testable read-side view-model (metrics + scope + drill-down)
└── tests/                 # view-model unit tests + headless AppTest smoke
```

## Screens

- **Dashboard** — HHI & CR₁₀ (connected vs direct), top sector, watchlist
  (red/amber), scoped exposures table with a sector filter, wrong-way-risk list,
  and the **CCR layer** (each a clearly-labelled simplified model, with its own
  filter): **country & rating concentration**, **net (post-collateral) exposure**,
  **expected loss & capital**, **stress / scenario** and **macro multi-factor**
  what-ifs, **forward-looking exposure (PFE/EE) & full xVA**, **IFRS-9 ECL & staging**,
  and **systemic contagion** (single + multi-round fire-sale cascade). See
  [`../docs/ccr-coverage.md`](../docs/ccr-coverage.md).
- **Explore** — pick a counterparty group → direct (named entity) vs direct
  (group) vs connected, the limit-breach verdict, and the contributing paths;
  plus the NBFI cascade chain.
- **Ask (NL)** — free-text question → M4 answer; shows the generated, validated,
  read-only SPARQL and the result rows.
- **Scenario Sandbox** — add a loan / soft-delete an object **via M2** (validated
  + audited); flags (e.g. limit breach) surface; metrics recompute on rerun.
  Limits require the `group_risk` role.
- **Audit** — the M2 audit trail of sandbox actions.

The sidebar switches **role** (M3 — re-scopes everything) and **resets** to the
calm or stressed base dataset.

## Run

```bash
pip install -r requirements.txt
# 1) Fuseki up + a dataset loaded (see M0/M1):
(cd ../m0-ontology && ./scripts/start_fuseki.sh &) && (cd ../m1-ingestion && python -m scripts.load_data --dataset stressed)
# 2) OPA on PATH for role scoping (brew install opa); optional: ollama serve + ollama pull llama3.2
streamlit run streamlit_app.py
```

## Test

```bash
pytest m5-app/tests/test_views.py -q       # view-model (in-memory; no Fuseki)
pytest -m integration m5-app -q             # headless AppTest (needs Fuseki)
```

## Verify (the demo screen)

- Selecting a counterparty group shows direct vs connected and the multi-hop
  contribution; the limit breach is visible.
- Filters update the metrics/table for the subset; a sandbox-added loan pushes a
  name over its limit with the breach + flags surfacing live (validated,
  audited); soft-deleting a guaranty drops connected exposure with an audit row;
  reset restores the base data.
- **All writes go through M2** (no direct-to-Fuseki writes in the app); role
  scoping is visible (RM sees fewer groups); the dataset banner is always shown.
- Gates green (ruff/black/mypy/pytest/bandit/pip-audit/pre-commit).
