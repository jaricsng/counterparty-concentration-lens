# Concentration Metrics & Hidden-Exposure Spec

*An enhancement to the Counterparty Concentration Lens. Folds into existing modules M0, M1, M2, M5 — this is **not** a redo of M0. Authoritative build context remains `CLAUDE.md`; this spec adds detail for the concentration analytics.*

> **Honesty label (must appear in the app and docs):** the synthetic data is **deliberately engineered to exercise these metrics** (including crossing risk thresholds). It demonstrates that the Lens *computes the metrics correctly*; it does **not** represent realistic portfolio statistics. Two datasets are provided — a **calm** set (metrics within normal ranges) and a **stressed** set (thresholds breached) — so the demo can show metrics moving from green to red. Synthetic data only.

---

## 1. What we are adding, and where it lives

| Capability | Tier | Primary modules |
|---|---|---|
| Single-name limit (% capital / revenue) on **connected** exposure | 1 — computed | M0 (query), M2 (SHACL breach rule), M5 (display) |
| Top-10 concentration (CR₁₀) | 1 — computed | M0/M1 (derived), M5 |
| Herfindahl–Hirschman Index (HHI) | 1 — computed | M0/M1 (derived), M5 |
| Sector & government concentration | 1 — computed | M1 (tags), M0 (query), M5 |
| Indirect interconnectedness (NBFI cascade) | 2 — graph-structural | M0 (traversal), M5 (chain view) |
| Structural Wrong-Way Risk (same-issuer collateral) | 3 — structural flag | M0 (query), M2 (flag), M5 |
| Net exposure · EAD/EL/capital · IFRS-9 · PFE/xVA · stress/macro · contagion | ⚠️ simplified (v0.1–v0.9) | M1/M2 (compute), M5, M4 — see [`ccr-coverage.md`](ccr-coverage.md) |

The guiding principle (unchanged): every metric is computed on **connected exposure** (direct + guarantees + shared collateral + group ownership), not per-system direct exposure. The demo's punch is that a name can look fine on direct exposure and breach once the hidden hops are counted.

---

## 2. Ontology additions (application layer + FIBO SEC)

**Add FIBO SEC (Securities) to `vendor/fibo/`** alongside BE/LOAN/FBC/FND/Guaranty, so collateral that is a security has a proper **issuer**. Resolve the import closure to just what's needed.

**Application-ontology properties** (in *your* layer that imports FIBO — do NOT edit vendor FIBO files):
- On the lending institution: `eligibleCapital` (monetary).
- On corporate counterparties: `annualRevenue` (monetary).
- On every counterparty/legal entity: `sector` (string/enum) and `counterpartyType` (enum: `bank`, `corporate`, `nbfi`, `government`).
- On collateral: link to its **issuer** (a LegalEntity) — prefer FIBO SEC's issuance relationship where the collateral is a security; otherwise a `collateralIssuer` object property on the app layer.
- On counterparty: `singleNameLimit` (already have `Limit` from M0 — reuse/relate).

Keep additions minimal and clearly namespaced as application-layer conveniences.

---

## 3. Metric definitions (exact)

Implement these precisely. All exposures are **connected exposure** unless stated.

### 3.1 Single-name limit utilisation
```
utilisation(name) = connectedExposure(name) / limitBasis(name)
limitBasis = eligibleCapital (for bank book)  OR  annualRevenue (for a corporate counterparty)
```
- Breach thresholds (illustrative, configurable): **> 25%** of eligible capital (single name), or **> 10%** of revenue (corporate).
- **The demo point:** at least one name is **under** threshold on *direct* exposure but **over** on *connected* exposure.

### 3.2 Top-10 concentration (CR₁₀)
```
CR10 = sum(top 10 connected exposures) / sum(all connected exposures)
```
- Bands (illustrative): 30–50% normal · 50–60% elevated · **> 60–70% high risk**.

### 3.3 Herfindahl–Hirschman Index (HHI)
```
share_i = connectedExposure_i / totalConnectedExposure
HHI = sum( share_i^2 )      # fractional form, range 0..1
```
- Threshold (illustrative): **HHI > 0.18 = high concentration**.
- Show **direct-only HHI vs connected HHI** — connected should breach where direct does not.

### 3.4 Sector & government concentration
```
sectorShare(s) = sum(connectedExposure where sector = s) / totalConnectedExposure
```
- Flag any single sector over an illustrative threshold (e.g. **> 30%**); show government/public-sector aggregate separately.

### 3.5 Indirect interconnectedness (NBFI cascade)
- Graph traversal: starting from a stressed entity, follow guarantee + shared-collateral + group-ownership edges to compute **second-order exposure** (exposure that becomes yours if the entity fails and its guarantees/links cascade).
- **Demo point:** direct exposure to the NBFI is small, but the cascade-connected exposure is large — the Archegos-shaped lesson.

### 3.6 Structural Wrong-Way Risk (WWR)
- Flag any loan/exposure where the **collateral issuer is the same legal entity or group as the counterparty** (collateral that evaporates exactly when the name fails).
- This is a *structural* WWR proxy, not correlation-based WWR. **State this explicitly** in the app and docs.

### 3.7 Forward-looking exposure (PFE / EE) — IMPLEMENTED, simplified (v0.4.0+)
- The prototype now derives an **analytical** EE/PFE profile (amortising base + √t add-on) and integrates **CVA** (and the full xVA stack — FVA/MVA/KVA/DVA, v0.7.0) over it. See `lens_m1/xva.py` and [`ccr-coverage.md`](ccr-coverage.md).
- It remains **deliberately simplified**: an illustrative analytical *shape*, **not** Monte-Carlo exposure paths or derivative MtM. Limits/exposures are still static point-in-time. That realism gap — analytical profile vs simulated paths — is the honest boundary, recorded in the Capstone "what this is NOT".

---

## 4. Synthetic data design (regenerate: 20–30 entities)

Regenerate a richer dataset (replaces/extends M0's starter instances). Provide a generator that emits **two labelled variants**: `calm` and `stressed`. Same schema; the stressed set is engineered to breach thresholds.

**Entities (~20–30):** mix of `bank`, `corporate`, `nbfi`, `government`; several grouped under parent holding structures (for group aggregation); spread across ~5 sectors with deliberate clustering in one.

**Engineer these specific demonstrable cases (stressed set):**
1. **Hidden single-name breach:** "Acme Group" — direct exposure ~20% of eligible capital (under 25%), but guarantees + shared collateral push **connected** exposure to ~35% (breach).
2. **Skewed CR₁₀ / HHI:** exposure distribution skewed so connected CR₁₀ > 60% and connected HHI > 0.18, while direct-only versions look acceptable.
3. **Sector concentration:** one sector (e.g. "commercial real estate") holds > 30% of connected exposure.
4. **NBFI cascade:** one `nbfi` entity with small direct exposure but guaranteeing/sharing collateral across 3–4 others, so its failure cascades to a large connected number.
5. **Structural WWR:** at least one loan whose collateral is a security **issued by the same group** as the borrower.

**Calm set:** same entities, exposures rebalanced so all metrics sit within normal bands — so the demo can toggle calm → stressed and watch the dashboard light up.

**Data provenance note:** ship a short `data/README.md` documenting that the data is synthetic, the entity names are fictional, and the stressed set is intentionally engineered to exercise thresholds.

---

## 5. Per-module enhancement checklist

### M0 (`m0-ontology/`)
- [ ] Add FIBO SEC to `vendor/fibo/`; update import closure.
- [ ] Extend application ontology: capital/revenue, sector, counterpartyType, collateral issuer.
- [ ] SPARQL: connected-exposure aggregation per name/group; CR₁₀; HHI (direct vs connected); sector shares; WWR (same-issuer-collateral) detection; NBFI cascade traversal.
- [ ] Tests for each query against a known fixture with hand-checked expected values.

### M1 (`m1-ingestion/`)
- [ ] Regenerate `calm` + `stressed` synthetic datasets (20–30 entities) per §4.
- [ ] Tag entities with sector / type; add capital/revenue; add same-issuer-collateral case + NBFI chain.
- [ ] `data/README.md` provenance + "engineered, illustrative" note.
- [ ] Idempotent load; triple counts checked.

### M2 (`m2-actions/`)
- [ ] SHACL/derived rule: **connected** single-name limit breach (not direct).
- [ ] Action/flag: `flag-wrong-way-risk` for same-issuer-collateral cases.
- [ ] Tests: a name passing on direct but breaching on connected is flagged.

### M5 (`m5-app/`)
- [ ] **Concentration dashboard:** single-name utilisation (direct vs connected), CR₁₀, HHI (direct vs connected), sector/government breakdown.
- [ ] **Interconnectedness view:** the NBFI cascade chain, with direct vs cascade-connected numbers.
- [ ] **WWR flags** listed with the same-issuer explanation.
- [ ] **Calm/Stressed toggle** that re-runs the metrics and visibly moves them across thresholds.
- [ ] Prominent "illustrative synthetic data" label; the credit-risk / forward-looking layers labelled as **simplified** (see [`ccr-coverage.md`](ccr-coverage.md)).

### Capstone
- [ ] "What this is NOT" frames the boundary as **simulation realism** (Monte-Carlo paths, calibrated curves, live data), not the capabilities — every CCR area is implemented as a labelled-simplified model. Correlation-based (vs structural) WWR remains a noted simplification.

---

## 6. Acceptance test for the whole enhancement
On the **stressed** dataset, the Lens must show, live, at least:
1. A name **within** its single-name limit on direct exposure but **breaching** on connected exposure.
2. CR₁₀ and HHI **breaching** thresholds on connected exposure while direct-only looks acceptable.
3. A sector over its concentration threshold.
4. An NBFI whose **cascade**-connected exposure dwarfs its direct exposure.
5. At least one **structural WWR** flag (same-issuer collateral).
Toggling to **calm** returns all metrics to normal bands. Every figure traceable (lineage/audit); all gates green (tests, ruff, mypy, CI).

---

## 7. Cloner & onboarding instructions (BUILD THESE — don't just assume)

A fresh clone/fork must not be confused by the two datasets, the engineered numbers, or the new FIBO/ontology requirements. Claude Code must create the following so onboarding is frictionless. **Default behaviour: a fresh clone loads the CALM dataset** (safe, unalarming); the user explicitly switches to STRESSED to see thresholds breach.

### 7.1 Defaults & dataset selection
- Fresh clone defaults to **`calm`**. Selection via a single obvious mechanism — an env var (e.g. `LENS_DATASET=calm|stressed`) or a CLI flag on the loader/app — documented identically everywhere it appears.
- Switching datasets must be one command/flag, not a code edit.

### 7.2 In-app dataset banner (M5) — the most important guardrail
- A **persistent, prominent banner** always shows which dataset is loaded, e.g.:
  - calm: `Dataset: CALM — illustrative synthetic data (metrics within normal bands)`
  - stressed: `⚠ Dataset: STRESSED — illustrative synthetic data, deliberately engineered to breach risk thresholds. Not real portfolio statistics.`
- The banner is visible on the main screen at all times, not hidden in a menu. It must be impossible to read the numbers without seeing the label.

### 7.3 `m1-ingestion/data/README.md`
- Explain: two datasets (calm, stressed); both fully synthetic; entity names fictional; the stressed set is **intentionally engineered** to cross thresholds to demonstrate the metrics, and is **not** realistic portfolio data.
- Give the exact generate + select + load commands for each.

### 7.4 Module READMEs (M0, M1)
- **M0 README:** updated FIBO module list now **includes SEC** (BE, LOAN, FBC/Debt, FND, Guaranty, **SEC**); how to fetch into `vendor/fibo/` and resolve the import closure; the **application-ontology properties** the model expects (`eligibleCapital`, `annualRevenue`, `sector`, `counterpartyType`, collateral issuer) so anyone bringing their own data knows what's required.
- **M1 README:** the new explicit sequence — (1) generate data (calm/stressed), (2) select dataset, (3) load into Fuseki — with copy-pasteable commands; note idempotency.

### 7.5 Top-level README
- Add a short **"Datasets & what the numbers mean"** subsection (calm default, stressed opt-in, engineered-illustrative caveat) and update the **quickstart** to reflect the new steps (FIBO SEC, generate/select dataset). See the repo README for the canonical wording; keep this spec and the README consistent.

### 7.6 Consistency rule
- The dataset-selection command, the env var/flag name, and the "engineered/illustrative" wording must be **identical** across: this spec, `data/README.md`, M0/M1 READMEs, the app banner, and the top-level README. One name, one phrasing, everywhere — divergence is exactly what confuses cloners.

### 7.7 Onboarding acceptance test
- A new user who clones the repo and follows **only** the top-level README quickstart can: install, fetch FIBO (incl. SEC), generate+load the **calm** data, launch the app, and see the banner stating it's calm illustrative data — **without reading any other doc**. Then one documented command switches to stressed and the metrics visibly move.

---

## 8. Interactive app & scenario sandbox (M5, with M2 support)

The app is **not** a static dashboard. It is an interactive tool for exploring the model and for **user-defined scenario testing** on synthetic data. Two sides: read/explore (free, all reads) and a guarded write sandbox (all writes through M2 actions). Everything operates on the loaded dataset (calm/stressed) and respects the M3 role filter.

> **Framing (must appear in the app):** the write features are a **"Scenario Sandbox" for user-defined testing on synthetic data** — craft a scenario, watch the metrics move. Not production data management. All edits are synthetic and routed through the validated action layer.

### 8.1 Read / explore side (build fully — pure reads)
- **Filters:** by `sector`, `counterpartyType` (bank/corporate/nbfi/government), exposure band, group/parent, limit-utilisation band, WWR-flagged only. Filters compose and update the dashboard + metrics live.
- **Structured query / drill-down:** select a counterparty or group → its single exposure view (direct vs connected), contributing paths (guarantees/collateral/group), and the metrics recomputed for the current filter set. Sortable top-10; clickable NBFI cascade chain.
- **Natural-language box (M4):** embed the grounded NL→SPARQL agent so users can ask free-form questions; answers come from the model, schema-validated and read-only, through the M3 filter. Show the generated SPARQL (transparency).
- All metric panels show **direct vs connected** side by side wherever applicable.

### 8.2 Scenario Sandbox — guarded write side
**Hard rule:** every create/update/deactivate goes **through an M2 action** (validate via SHACL → SPARQL Update → audit log). The UI never writes to Fuseki directly. No hard delete.

- **Add:** legal entity, loan, guarantee, collateral, limit — via forms that POST to M2 action endpoints. SHACL validates before write (e.g. a guarantee must reference two distinct existing entities; a loan must not breach a limit, or must be flagged if it does).
- **Edit:** attributes of existing objects (exposure amount, limit, sector, etc.) via the same guarded path; re-validated on write.
- **Soft-delete / status change:** set status to `closed`/`inactive` rather than removing triples — preserves audit history. Inactive objects are excluded from exposure metrics but remain queryable/auditable.
- **Live recompute:** after any successful action, the concentration metrics (single-name, CR₁₀, HHI, sector, WWR, cascade) recompute and the UI updates — so the user sees their edit ripple into the numbers. This is the core demo of the sandbox.
- **Audit panel:** show the audit log of sandbox actions (who/what/when, validation result).
- **Reset:** a "reset to calm" and "reset to stressed" control to reload the base dataset and discard sandbox edits — so users can experiment freely and return to a known state.

### 8.3 M2 additions implied
- Action endpoints for create/update/deactivate of each object type (entity, loan, guarantee, collateral, limit), each with its SHACL shape and audit logging.
- Referential-integrity checks on deactivate (e.g. warn/guard if deactivating an entity that is a guarantor on an active loan).
- Tests: valid create writes+logs; invalid create rejected pre-write; deactivate excludes from metrics but keeps audit/history.

### 8.4 Honesty & safety
- Persistent "Scenario Sandbox — synthetic data" labelling; never imply real data management.
- Writes still respect the M3 role (e.g. only `group_risk` can edit limits) — demonstrates authorization on writes, not just reads.
- Sandbox edits apply to the loaded synthetic dataset only; reset restores the base set.

### 8.5 M5 acceptance test (extends §6)
- User can filter by sector + type and see metrics update for the subset.
- User can ask an NL question and get a correct, schema-valid answer through the role filter.
- User can **add a loan via the sandbox** that pushes a counterparty's connected exposure over its single-name limit, and **see the breach flag and HHI/CR₁₀ move live** — with the action validated and audit-logged.
- User can **soft-delete** (deactivate) a guarantee and watch connected exposure drop accordingly, with the change audited.
- "Reset to calm/stressed" restores the base dataset.
- All writes went through M2 (verify: no direct-to-Fuseki writes in the app); gates green.

---

## 9. Tier-1 additions (sharpen the existing thesis — low data cost)

Two small, high-value additions that reuse data you already have and reinforce the core point (hidden, connected concentration). Fold into M0 (queries), M2 (early-warning flag), and M5 (display).

### 9.1 Ultimate Beneficial Owner (UBO) aggregation
- Traverse the ownership/control chain (BE) to the **ultimate parent** of each counterparty, and aggregate **connected exposure to the UBO**, not just the immediate counterparty.
- **Demo point:** several separately-onboarded counterparties roll up to one UBO; exposure-to-UBO breaches a limit that no individual subsidiary does. This is the Archegos lesson in its purest form.
- M0: a UBO-resolution query (walk control edges to the top; handle multi-level chains). M5: show "exposure to immediate counterparty" vs "exposure to UBO". Data: ensure the synthetic set has at least one 2–3-level ownership chain whose UBO aggregation breaches.
- **Correctness caution:** like the cascade, UBO traversal can loop on circular ownership or double-count cross-holdings — test against a hand-worked chain with a known UBO total.

### 9.2 Limit early-warning bands (watchlist)
- Beyond breached/not-breached, classify each name's single-name utilisation into bands: **green** (< 75% of limit), **amber** (75–100%), **red** (≥ 100%, breached). Thresholds configurable.
- M2: a derived/flag action `set-watchlist-band` (or compute on read) producing an amber/red watchlist.
- M5: a **watchlist panel** — names approaching or over their limits, sortable by utilisation, using **connected** exposure. Makes the dashboard feel operational (you act *before* breach, not after).
- Data: tune the stressed set so several names sit in amber (the early-warning story), not only red.

### 9.3 Acceptance (extends §6)
- A UBO with multiple subsidiaries shows aggregated exposure breaching a limit that no single subsidiary breaches.
- The watchlist lists amber names (approaching) distinctly from red (breached), on connected exposure.
- Both reflect the calm/stressed toggle and the M3 role filter; gates green.

---

## 10. Scope & the realism boundary (record in the Capstone "what this is NOT")

> **Update (v0.4.0–v0.9.0):** the CCR areas once listed here as out-of-scope have since
> been **built as deliberately-simplified, clearly-labelled** versions. The canonical,
> always-current map of *what's implemented · simplified · still out* is
> [`ccr-coverage.md`](ccr-coverage.md). The boundary moved from *capability* to *realism*.

**Now implemented (⚠️ simplified — real shape, illustrative calibration, never faked):**
- **Forward-looking exposure (PFE / EE) + full xVA** (`xva.py`, v0.4.0/v0.7.0) — analytical EE/PFE profile + CVA·DVA·FVA·MVA·KVA, integrated deterministically (no Monte-Carlo paths).
- **Stress / scenario shocks + macro multi-factor stress** (`scenarios.py`, `macro.py`, v0.3.0/v0.8.0) — named deterministic shocks and a correlated factor model that re-derive every metric (no simulated correlation matrix).
- **Credit migration → EAD / PD / LGD / Expected Loss + IFRS-9 staging** (`credit_risk.py`, `ifrs9.py`, v0.2.0/v0.5.0) — rating-driven PD, EL, RWA/capital, and Stage 1/2/3 lifetime ECL (rating-rule staging, not a full SICR/IRB model).
- **Network / systemic contagion** (`contagion.py`, v0.6.0/v0.9.0) — a two-hop cascade and an iterative multi-round cascade with fire-sale spirals over the guarantee/ownership graph (deterministic, not a calibrated network model).
- **Netting sets, collateral / CSA haircuts** (v0.1.0) — net post-collateral exposure with the dedicated-collateral rule.

**Still consciously out of scope — the *realism* boundary, not the capability:**
- **Monte-Carlo exposure simulation** (true PFE/EE paths, derivative MtM) — the analytical profile shows the shape, not simulated paths.
- **Calibrated curves & correlations** — real lifetime-PD term structures, an estimated macro factor-correlation matrix, calibrated price-impact for fire-sales.
- **Full xVA realism / IRB / full IFRS-9** — FVA/MVA/KVA are illustrative integrals; no IRB PD/LGD estimation, no quantitative SICR backstops or forward-looking macro overlays.
- **Live / real-data integration** — synthetic point-in-time data only (see `data-import.md` §5).

Framing line for the capstone: *the Lens demonstrates **connected, relationship-aware concentration** end-to-end into loss, capital, forward exposure, provisioning and systemic contagion — every CCR area built as a **clearly-labelled simplified** model. What it consciously omits is **simulation realism** (Monte-Carlo paths, calibrated curves, live data), not the capabilities.*
