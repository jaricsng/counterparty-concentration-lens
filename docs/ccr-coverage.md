# CCR coverage — full counterparty-credit-risk system vs the Lens

A feature-by-feature comparison of a full **counterparty credit risk (CCR)** stack
against what this learning prototype implements. Kept current as each feature ships
(it is the last step of the per-feature loop).

**Legend:** ✅ implemented · ⚠️ implemented but **deliberately simplified** (structurally
honest, not production-accurate) · ❌ consciously out of scope (see
[`concentration-metrics.md` §10](concentration-metrics.md)).

> This is a prototype on **synthetic data** — *production-shaped, not production-hardened*.
> "Simplified" means the shape is real but the calibration is illustrative; it is never
> a substitute for a validated model.

## A. Quantify exposure

| CCR capability | Lens | Notes |
|---|---|---|
| Current / drawn exposure | ✅ | Loan principal, status-aware (active only). |
| Netting sets | ⚠️ | Implicit one set per counterparty (M0 `lens:NettingSet`). |
| Collateral / CRM (haircuts) | ✅ | `value × (1 − haircut)`; "dedicated collateral" rule avoids double-counting shared collateral. |
| **Net (post-collateral) exposure** | ✅ | `net = max(0, gross − Σ eligible)` — M1 `metrics`, M2 `derived`, dashboard, NL, BYOD. **v0.1.0** |
| EAD (exposure at default) | ⚠️ | EAD = net exposure; **no PFE add-on** (point-in-time). **v0.2.0** |
| **PFE / EE / expected exposure profile** | ⚠️ | **Analytical** profile (amortising base + √t add-on) — illustrative shape, not Monte-Carlo paths. **v0.4.0** |
| **CVA** (unilateral) | ⚠️ | `LGD·Σ EE·marginalPD·DF`, hazard from the rating's 1y PD, on the analytical EE profile. **v0.4.0** |
| **Full xVA (FVA / MVA / KVA), bilateral CVA/DVA** | ⚠️ | Each a deterministic integral over the analytical EE/PFE profile + a flat parameter. DVA ≈ 0 for the one-directional loan book. Not simulated. **v0.7.0** |
| Wrong-way risk | ⚠️ | **Structural** WWR (collateral issued by the borrower's group); not correlation-based. |
| PD (probability of default) | ⚠️ | Mapped from credit rating via an illustrative table. **v0.2.0** |
| LGD / EAD/PD calibration (IRB) | ⚠️ | Flat 45% LGD; standardised-style risk weights. No IRB estimation. **v0.2.0** |
| **Expected Loss (≈ 12-mo ECL)** | ⚠️ | `EL = PD × LGD × EAD`; not full IFRS-9 staging/lifetime/macro. **v0.2.0** |
| RWA / regulatory capital | ⚠️ | Standardised risk-weight × EAD; capital = 8% × RWA. Not SA-CCR/IMM. **v0.2.0** |
| **IFRS-9 staging / lifetime ECL** | ⚠️ | Stage 1/2/3 by a **rating rule**; lifetime ECL via a constant-hazard PD term structure. No SICR backstops or macro scenarios. **v0.5.0** |

## B. Aggregate · connect · concentrate · control  (the Lens's core)

| CCR capability | Lens | Notes |
|---|---|---|
| Single-name exposure | ✅ | Direct per counterparty. |
| Group / UBO aggregation | ✅ | Ownership chain to the ultimate parent; loop-guarded. |
| **Connected exposure** (multi-hop) | ✅ | Direct + guarantees + shared collateral — the "money shot". |
| Limits & utilisation / watchlist | ✅ | Green/amber/red bands on connected exposure. |
| Dynamic / pre-deal / tenor / settlement limits | ⚠️ | Read-only **pre-deal** what-if: dynamic (rating-adjusted) connected limit + tenor cap + settlement sub-limit (`predeal.py`). Illustrative factors/caps. **v1.6.0** |
| HHI / CR₁₀ (direct vs connected) | ✅ | Book-level concentration indices. |
| Sector concentration | ✅ | Risk-owner attribution (NBFI guarantees count to financials). |
| **Country / geographic concentration** | ✅ | Risk-owner country of risk; dashboard, NL, BYOD, filter. **v0.1.0** |
| **Rating-bucket concentration** | ✅ | Sub-investment-grade share; dashboard, NL, BYOD, filter. **v0.1.0** |
| NBFI cascade | ✅ | Small direct, large connected via guarantees (Archegos-shaped). |
| **Stress / scenario engine** | ⚠️ | Deterministic named shocks re-derive **every** metric (incl. EL/capital); a what-if, **not** Monte-Carlo. **v0.3.0** |
| **Reverse stress** | ⚠️ | Mildest shock that reaches an adverse target (double EL, capital %, N limit breaches) via a monotone deterministic search — not a calibrated optimiser. **v1.4.0** |
| **Macro / multi-factor stress** | ⚠️ | Deterministic factor model: a named scenario's factor vector × per-sector sensitivities → correlated downgrades. Not a simulated correlation matrix. **v0.8.0** |
| **Systemic contagion** | ⚠️ | Two-hop cascade (**v0.6.0**) + an iterative **multi-round cascade with fire-sale spirals** (**v0.9.0**) over the guarantee/ownership graph. Not a calibrated network model. |
| Fire-sale / liquidity spirals | ⚠️ | Deterministic fire-sale haircut feedback inside the multi-round cascade — illustrative, not a calibrated price-impact model. **v0.9.0** |

## C. Engineering & delivery (cross-cutting, every feature)

| Capability | Lens |
|---|---|
| Grounded NL query over the model (M4) | ✅ every feature has an intent |
| Bring-your-own test data (M2 guarded import) | ✅ every feature's columns |
| Composable dashboard filters (M5) | ✅ sector / band / country / rating / EL / stress |
| Dynamic authorization (OPA/Rego, M3) | ✅ role-scoped views |
| Maker-checker / four-eyes approval (M2) | ✅ SoD-enforced, audited — **v1.5.0** |
| Validation-as-code (SHACL, M2) | ✅ guarded writes |
| Behavioral UI→backend tests | ✅ AppTest per feature |
| CI/CD, SAST, SBOM, policy-as-code | ✅ see `engineering-practices.md` |

## Release history

| Version | Feature |
|---|---|
| `v0.1.0` | Core Lens (M0–M6 + Capstone) · netting & collateral · country & rating concentration |
| `v0.2.0` | EAD · Expected Loss · capital |
| `v0.3.0` | Stress / scenario engine |
| `v0.4.0` | Forward-looking exposure (PFE / EE profile) · CVA |
| `v0.5.0` | IFRS-9 staging & lifetime ECL |
| `v0.6.0` | Systemic contagion (default cascade) |
| `v0.7.0` | Full xVA (FVA / MVA / KVA) · bilateral CVA/DVA |
| `v0.8.0` | Macro / multi-factor (correlated) stress |
| `v0.9.0` | Multi-round contagion with fire-sale spirals |
| `v1.4.0` | Reverse stress testing |
| `v1.5.0` | Maker-checker (four-eyes) approval workflow |
| `v1.6.0` | Dynamic / pre-deal / tenor / settlement limits |
| `v1.7.0` | General (correlation-proxy) wrong-way risk |
