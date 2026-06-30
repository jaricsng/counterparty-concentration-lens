# Bring-Your-Own *Test* Data — CSV templates

> ## ⛔ Test / synthetic data only
> These templates are for **synthetic, sanitised, or sample test data** — **not**
> real, production, customer, or regulated counterparty data. The Lens is a
> learning prototype (not production-hardened — see `../SECURITY.md`). The correct
> path for real data is a contained proof of concept in your own environment with
> your security team, not this prototype.

Copy this folder, **overwrite the `(REPLACE ME)` example rows** with your own test
data in the same shape, and load it through the guarded import path:

```bash
# from m1-ingestion/ — validate + load your CSVs as a named dataset
# (routed through the M2 SHACL validation + audit path):
python -m scripts.load_data --source <your-folder> --name my-scenario
# differently-shaped CSVs? supply a column/value mapping (Tier 2):
python -m scripts.load_data --source <your-folder> --mapping <map.yaml> --name my-scenario
#   add --allow-partial to load only the rows that pass (exploratory)
```

Every row is validated **before** anything is written; you get a per-row report of
what was accepted or rejected and why. Imported data loads as its own **named
dataset** and never overwrites the bundled `calm`/`stressed` sets — "reset to
calm/stressed" always brings you back. See [`../docs/data-import.md`](../docs/data-import.md).

## Files & columns

IDs are free text but must be **consistent across files** (foreign keys). All
amounts are integers in a single currency.

### `entities.csv`
| column | required | meaning |
|---|---|---|
| `entity_id` | yes | unique id, referenced by the other files |
| `entity_name` | yes | display name |
| `counterparty_type` | yes | one of `bank` · `corporate` · `nbfi` · `government` |
| `sector` | yes | industry sector (free text) |
| `parent_entity_id` | no | the entity's owner (for ownership / UBO chains); blank if top-level |
| `eligible_capital` | lender only | the lending bank's regulatory capital (limit basis) |
| `annual_revenue` | corporates | revenue (alternative limit basis) |
| `country` | no | country of risk (ISO-style code, e.g. `SG`); enables country concentration |
| `rating` | no | credit rating grade (e.g. `AAA`..`CCC`); enables rating-bucket concentration |

### `loans.csv`
| column | required | meaning |
|---|---|---|
| `loan_id` | yes | unique id |
| `lender_entity_id` | yes | the lending institution (must exist in `entities.csv`) |
| `borrower_entity_id` | yes | the borrower (must exist) |
| `exposure_amount` | yes | outstanding principal (positive integer) |
| `currency` | yes | ISO code, e.g. `SGD` |
| `status` | yes | `active` or `closed` (closed is excluded from metrics) |
| `maturity_years` | no | remaining tenor in years; drives forward-looking exposure (PFE/EE) and CVA (default 3) |

### `guarantees.csv`
| column | required | meaning |
|---|---|---|
| `guarantee_id` | yes | unique id |
| `guarantor_entity_id` | yes | the guarantor (must exist; must differ from the loan's borrower) |
| `beneficiary_loan_id` | yes | the loan being guaranteed (must exist) |
| `amount` | yes | guaranteed amount (positive integer) |
| `currency` | yes | ISO code |

### `collateral.csv`
One row per **(collateral, secured loan)** pair — repeat the `collateral_id` to
secure several loans (shared / cross-pledged collateral).
| column | required | meaning |
|---|---|---|
| `collateral_id` | yes | id (repeat across rows for shared collateral) |
| `collateral_type` | yes | description |
| `pledged_by_entity_id` | yes | who pledged it (must exist) |
| `securing_loan_id` | yes | the loan it secures (must exist) |
| `issuer_entity_id` | no | the security's issuer (must exist); same-group-as-borrower = wrong-way risk |
| `collateral_value` | no | market value (before haircut); enables collateralised **net exposure** |
| `haircut_pct` | no | supervisory haircut, 0–100. Eligible mitigant = value × (1 − haircut/100) |

### `limits.csv`
| column | required | meaning |
|---|---|---|
| `limit_id` | yes | unique id |
| `entity_id` | yes | the entity the limit applies to (must exist) |
| `single_name_limit` | yes | the connected-exposure limit (positive integer) |
| `currency` | yes | ISO code |

A record that fails any of these rules (missing field, bad enum, dangling
reference, self-guarantee, non-positive amount) is **rejected with a readable
reason** — never silently loaded.
