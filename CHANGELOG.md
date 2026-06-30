# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project uses [Conventional Commits](https://www.conventionalcommits.org/).

## [Unreleased]

## [0.5.0] - 2026-06-30

### Added
- **IFRS-9 ECL staging** (`lens_m1/ifrs9.py`) — simplified, deterministic, clearly
  labelled; **not** a full IFRS-9 model:
  - Stage 1 (performing) -> 12-month ECL; Stage 2 (sub-investment-grade, SICR proxy)
    -> lifetime ECL; Stage 3 (CCC, impaired) -> LGD·EAD. Lifetime ECL uses a
    constant-hazard PD term structure over the loan tenor.
  - Dashboard "IFRS-9 ECL & staging" section: per-stage metrics + a per-counterparty
    table (12m / lifetime / recognised ECL, coverage) with a stage filter.
  - NL `ifrs9` intent ("IFRS-9 ECL?", "lifetime expected credit loss", "stage 2");
    "ecl"/"provision" now route here, while "expected loss" stays the Basel EL intent.
  - The Stage-1->2 cliff is the story: recognised ECL ~3.9M vs the 12-month 0.8M.

## [0.4.0] - 2026-06-30

### Added
- **Forward-looking exposure (PFE / EE) + CVA** (`lens_m1/xva.py`) — analytical and
  deterministic; an honest what-if shape, **NOT** Monte-Carlo paths or derivative MtM:
  - EE/PFE profile = amortising base exposure + a √t diffusion add-on (the classic PFE
    hump); peak PFE and EPE per counterparty.
  - Unilateral CVA = `LGD·Σ EE(t)·marginalPD(t)·DF(t)`, hazard from the rating's 1y PD.
  - Loans gain an optional `maturity_years` tenor (ontology `lens:maturityYears`,
    CSV/BYOD/template; default 3) driving the profile.
  - Dashboard "Forward-looking exposure & CVA" section: per-counterparty PFE/EPE/CVA
    table with a rating filter and an **EE/PFE profile line chart** per counterparty.
  - NL `xva` intent ("total CVA?", "potential future exposure") on the stressed base.
  - Sub-investment-grade long-tenor names dominate CVA (≈595k each; portfolio ≈2.5M).

## [0.3.0] - 2026-06-30

### Added
- **Stress / scenario engine** (`lens_m1/scenarios.py`) — deterministic named shocks
  that re-derive **every** metric (concentration, net exposure, expected loss, capital)
  and compare base vs shocked. Pure dataset transforms; an honest what-if overlay,
  **not** a Monte-Carlo simulation or macro model.
  - Scenarios: NBFI downgrade (−2 notches), broad downgrade (−1), collateral haircuts
    +20pp, CRE downturn (−1 notch + 25% draw). All shocks raise expected loss vs base.
  - Dashboard "Stress / scenario (what-if)" section: scenario picker, base-vs-shocked
    metric deltas, and a per-counterparty EL-delta table with a shocked-rating filter.
  - NL `stress` intent (computed): "what happens to expected loss if NBFIs downgrade?"
    → EL 0.8M → 2.7M on the stressed base, biggest mover surfaced.
- **CCR coverage comparison** (`docs/ccr-coverage.md`) — full CCR stack vs the Lens
  (implemented / simplified / out of scope); maintained as the last step of each loop.

## [0.2.0] - 2026-06-25

### Added
- **Counterparty credit risk — EAD, Expected Loss & capital** (simplified, deterministic,
  point-in-time; clearly labelled, not a production model):
  - `lens_m1/credit_risk.py`: EAD = net (post-collateral) exposure; PD from the credit
    rating; LGD 45%; **EL = PD × LGD × EAD**; RWA = standardised risk-weight × EAD;
    capital = 8% × RWA. Per-counterparty and book-level summary.
  - M2 `derived.expected_losses` / `capital_summary` over the live store, exposed via
    `ActionService` (parity-tested against the M1 oracle).
  - Dashboard "Expected loss & capital" section: portfolio metrics (EAD/EL/RWA/capital)
    + per-counterparty table with rating + sector filters.
  - NL **computed** intents `expected_loss` and `capital` (PD/risk-weight are parametric;
    the agent nets collateral and applies the `credit_risk` parameters — consistent with
    the dashboard; "capital" no longer hijacks entity names like "Nimbus Capital Partners").
  - Reuses the merged netting (→ EAD) and rating (→ PD/risk-weight) features. Still
    out of scope: Monte-Carlo PFE/CVA, full IFRS-9 staging, IRB.

## [0.1.0] - 2026-06-25

First versioned release of the learning prototype (synthetic data; production-shaped,
not production-hardened).

### Added
- **Core Lens (M0–M6 + Capstone)**: FIBO model + Fuseki, synthetic data + ingestion,
  SHACL validation + guarded actions, OPA/Rego dynamic security, grounded NL query
  (M4), the Streamlit demo app, and k3d/Argo CD infra with OPA Gatekeeper.
- **Netting & collateral**: collateralised **net exposure** (gross − Σ value×(1−haircut)
  over dedicated collateral), surfaced on the dashboard with a sector filter, an NL
  intent, BYOD columns, and a behavioral UI→backend test.
- **Country & rating concentration**: geographic and credit-rating-bucket concentration
  attributed to the risk-owner; dashboard tables + filters, NL intents, BYOD columns.
- **Observability & traceability**: request-scoped correlation IDs in structured JSON
  logs and the audit trail; `X-Correlation-ID` header on the M2 API.
- **Auditability**: tamper-evident, hash-chained audit log with `verify()` and an
  `/audit/verify` endpoint.
- **Governance**: `CODEOWNERS`, PR template, `CONTRIBUTING.md`, this changelog, ADRs.
- **Compliance**: data-governance & BCBS 239 mapping and a STRIDE threat model.
- **Supply chain / DevSecOps**: GitHub Actions pinned by commit SHA; CodeQL; the CI
  integration job (live Fuseki + OPA + gator); the P1–P3 test suites.
- **Reuse**: a "golden path" to seed new projects with these practices.

[Unreleased]: https://github.com/jaricsng/counterparty-concentration-lens/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/jaricsng/counterparty-concentration-lens/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/jaricsng/counterparty-concentration-lens/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jaricsng/counterparty-concentration-lens/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/jaricsng/counterparty-concentration-lens/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jaricsng/counterparty-concentration-lens/releases/tag/v0.1.0
