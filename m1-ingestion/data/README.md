# Synthetic datasets — provenance & what the numbers mean

> **Everything here is SYNTHETIC.** The entity names are fictional ("Acme
> Holdings Pte Ltd", "Vortex Global Holdings Ltd", …) and the IDs are made up
> (`LE-0001` …). No real institutions, no real exposures.
>
> The **stressed** dataset is **deliberately engineered to cross risk
> thresholds** so the Lens can demonstrate that it computes the concentration
> metrics correctly. It does **not** represent realistic portfolio statistics.
> Two variants are provided so the demo can toggle from green to red:
>
> | Variant | Meaning |
> |---|---|
> | **`calm`** (default) | The same names, exposures rebalanced so every metric sits within normal bands. |
> | **`stressed`** | Engineered so single-name, CR₁₀, HHI, sector, WWR, UBO and cascade metrics breach. |

A fresh clone defaults to **`calm`**. Switch with one flag/var — no code edit.

## The five source tables

These are emitted by the generator as "source-style" CSVs, as if exported from
separate systems. Column names follow the canonical import schema in
`docs/data-import.md` §2 (so they double as bring-your-own-*test*-data templates).

| File | Source system (notional) | Key columns |
|---|---|---|
| `entities.csv` | KYC / onboarding | `entity_id`, `entity_name`, `counterparty_type`, `sector`, `parent_entity_id`, `eligible_capital`, `annual_revenue` |
| `loans.csv` | lending / core banking | `loan_id`, `lender_entity_id`, `borrower_entity_id`, `exposure_amount`, `currency`, `status` |
| `guarantees.csv` | collateral management | `guarantee_id`, `guarantor_entity_id`, `beneficiary_loan_id`, `amount`, `currency` |
| `collateral.csv` | collateral management | `collateral_id`, `collateral_type`, `pledged_by_entity_id`, `securing_loan_id`, `issuer_entity_id` |
| `limits.csv` | risk / limits | `limit_id`, `entity_id`, `single_name_limit`, `currency` |

Shared (cross-pledged) collateral is written as **one row per secured loan**
(same `collateral_id`, different `securing_loan_id`). All amounts are SGD.

## Generate · select · load

```bash
cd m1-ingestion
python -m scripts.generate_data                 # writes data/calm/ and data/stressed/
python -m scripts.load_data                      # loads calm (default) into Fuseki
python -m scripts.load_data --dataset stressed   # or load the stressed set
# equivalently: LENS_DATASET=stressed python -m scripts.load_data
```

Loading is **idempotent** — it replaces the Fuseki default graph, so re-running
gives the same triples. Triple counts scale with the row counts.

## What's engineered into the stressed set (and where to see it)

| Case | Entities | What to look for |
|---|---|---|
| Hidden single-name breach | Acme group (`LE-0001`) | direct SGD 20M (under the 25M limit) → **connected SGD 34M** (breach) via a guarantee + shared collateral |
| NBFI cascade | Nimbus (`LE-0030`) | direct SGD 5M → **connected SGD 47M** (it guarantees six other loans) |
| UBO aggregation breach | Vortex group (`LE-0020`) | three subsidiaries, **none** over its own 10M limit, but the UBO total SGD 24M breaches the 20M group limit |
| Structural wrong-way risk | Helios Power (`LE-0011`) | its loan is collateralised by a bond **issued by its own parent** Helios Holdings |
| Sector concentration | financial-services cluster | the NBFI names push financial services > 30% of attributed exposure |
| Skewed HHI / CR₁₀ | whole book | connected HHI > 0.18 and CR₁₀ > 60% while the direct-only views stay acceptable |
| Amber watchlist | Helios + Vortex subs | several names at 75–100% utilisation (early warning, not yet breached) |

Run `python -m scripts.show_metrics` to print the calm-vs-stressed numbers.

> **A note on scale.** This is a ~30-name book. CR₁₀'s published bands assume a
> large, diversified portfolio, so CR₁₀ reads elevated even in `calm`
> (≈62%); the cleaner calm/stressed discriminators at this scale are **HHI**,
> **single-name utilisation**, and **sector share**. The point is the metrics
> move correctly across thresholds — not that the book is realistic.
