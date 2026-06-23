# Bring-Your-Own Test Data — Import Spec

*How a user can load their own **test** data into the Counterparty Concentration Lens to try the demo on their own scenarios. Part of the build; folds into M1 (loader) and M2 (validation). Authoritative build context remains `CLAUDE.md`.*

> ## ⛔ Scope boundary — read first
> This feature is for **synthetic / sanitised / sample test data only**. It is **not** a route for real, production, customer, or regulated counterparty data.
>
> - The Lens is a **learning prototype, production-shaped but not production-hardened** (see `SECURITY.md`). It has no production security, access control, encryption-at-rest, or accreditation suitable for real exposure data.
> - **Loading real bank/customer data is out of scope and must not be done.** The correct path for real data is a **contained Proof of Concept in the institution's own environment, with their security team** — not this prototype.
> - The UI and docs must label this clearly as **"Bring-Your-Own *Test* Data (synthetic/sample only)."** Never imply production data management.
> - Live integration to source systems (core banking, APIs, databases) is **explicitly out of scope** — see §5 and the Capstone out-of-scope list.

---

## 1. Why flat-file (CSV), not integration

For a prototype, **CSV import is the right transport and live integration is deliberately excluded.** Rationale:

- Live integration (credentials, network access, schema discovery, security review) is exactly the hard, expensive, risky part a prototype should not claim. CSV is honest about what this is: a sandbox you feed sample data into.
- The genuinely hard problem in "bring your own data" is **mapping** (their schema → FIBO) and **entity resolution** (is this the same counterparty across files?), which is identical regardless of transport. So the simplest transport is correct, and the demo can *show* that mapping is the real work.

Two tiers are supported:
- **Tier 1 — Template CSVs:** user fills CSVs in the Lens's documented shape; existing M1 loader maps to FIBO.
- **Tier 2 — Mapping config:** user has differently-shaped CSVs; a small mapping file translates their columns to the Lens schema.

---

## 2. Tier 1 — Template CSVs

Publish the synthetic generator's output as **templates with documented columns** — the canonical import schema. A user replaces the rows with their own test data in the same shape and loads via the existing M1 loader.

**Files & required columns (illustrative — align to the actual M0 ontology):**

| File | Key columns |
|---|---|
| `entities.csv` | `entity_id`, `entity_name`, `counterparty_type` (bank/corporate/nbfi/government), `sector`, `parent_entity_id` (nullable — for ownership/UBO), `eligible_capital` (lender only), `annual_revenue` (corporates) |
| `loans.csv` | `loan_id`, `borrower_entity_id`, `exposure_amount`, `currency`, `status` (active/closed) |
| `guarantees.csv` | `guarantee_id`, `guarantor_entity_id`, `beneficiary_loan_id`, `amount` |
| `collateral.csv` | `collateral_id`, `securing_loan_id`, `value`, `collateral_type`, `issuer_entity_id` (for WWR) |
| `limits.csv` | `entity_id`, `single_name_limit`, `limit_basis` (capital/revenue) |

**Deliverables:**
- A `templates/` folder with each CSV containing the header row + 1–2 illustrative example rows, clearly marked as examples to overwrite.
- A `templates/README.md` documenting every column: meaning, type, required/optional, allowed values, and how IDs relate across files (foreign keys).
- A `--source` flag (or env var) on the loader to point at a user folder of CSVs instead of the bundled synthetic set.

---

## 3. Tier 2 — Mapping config (for differently-shaped data)

When a user's CSVs don't match the template shape, a **mapping file** (YAML) translates their columns/values to the Lens schema. The loader reads the mapping and transforms on the way in.

**Mapping file (example shape):**
```yaml
# maps a user's CSVs to the Lens import schema
entities:
  file: my_counterparties.csv
  columns:
    entity_id: cpty_ref
    entity_name: cpty_name
    counterparty_type: type            # plus value_map below
    sector: gics_sector
    parent_entity_id: parent_ref
  value_map:
    counterparty_type:                  # their value -> our enum
      "Bank": bank
      "Corp": corporate
      "Non-Bank FI": nbfi
      "Govt": government
loans:
  file: my_exposures.csv
  columns:
    loan_id: deal_id
    borrower_entity_id: cpty_ref
    exposure_amount: notional
    currency: ccy
    status: deal_status
# ... guarantees, collateral, limits
```

**Deliverables:**
- A documented mapping schema + an example mapping file.
- Loader support: `--mapping path/to/map.yaml` applied before the FIBO mapping step.
- Clear errors when a required target field is unmapped or a value falls outside the allowed enum (don't silently drop).

**Honest note for the demo:** Tier 2 is where the *real* integration challenge shows up in miniature — column mapping, value normalisation, and entity-ID alignment across files. This is a feature to *highlight*, not hide: it's the same problem a production platform solves at scale.

---

## 4. Validation & audit — imports go through the guarded M2 path

**Hard rule:** imported data is **not** raw-loaded into Fuseki. It is routed through the **M2 validation path** (SHACL) and audited, exactly like sandbox writes.

- **Pre-load validation:** each mapped record is validated against the SHACL shapes before any triples are written. Referential integrity checked (e.g. a loan's `borrower_entity_id` must exist; a guarantee must reference two distinct existing entities; collateral `issuer_entity_id` must resolve).
- **Import report:** produce a clear, per-row report — accepted vs rejected, with reasons (`row 14: guarantee references unknown entity GTR-xx`). A clean rejection with a readable reason is a **better** outcome than a silent bad load.
- **Atomic-ish behaviour:** default to "validate all, load only if no fatal errors" (configurable), so a partly-broken file doesn't half-load. Offer a `--allow-partial` for exploratory use.
- **Audit:** record the import (who/when/source file/row counts/accepted/rejected) in the same audit log as M2 actions.
- **Dataset isolation:** imported data loads as a **named dataset** (like calm/stressed) so it never silently overwrites the bundled sets, and **"reset to calm/stressed"** still works. The app banner shows when a user-imported dataset is active.

This reuses the M2 SHACL shapes and audit machinery — the import is just another guarded write path, which also *demonstrates* the validation layer doing real work on messy input.

---

## 5. Out of scope (record in Capstone §10 list)

- **Live / API / database integration** to source systems (core banking, trade, collateral, KYC systems) — needs credentials, network access, schema discovery, and security review; the production-PoC path, not a prototype feature.
- **Real, production, customer, or regulated data** — must not be loaded; contained PoC in the institution's environment only.
- **Automated schema discovery / ML-based mapping** — the mapping is user-authored config here; auto-discovery is a production concern.
- **Streaming / incremental / CDC ingestion** — batch CSV only.

---

## 6. Per-module enhancement checklist

### M1 (`m1-ingestion/`)
- [ ] `templates/` folder (CSVs with example rows) + `templates/README.md` column docs.
- [ ] Loader `--source <folder>` to load user CSVs instead of synthetic.
- [ ] Loader `--mapping <yaml>` (Tier 2) applied before FIBO mapping; documented mapping schema + example.
- [ ] Named-dataset isolation; doesn't overwrite calm/stressed; reset still works.

### M2 (`m2-actions/`)
- [ ] Import path runs records through SHACL validation + referential-integrity checks before write.
- [ ] Per-row import report (accepted/rejected + reasons); validate-all-then-load default; `--allow-partial` option.
- [ ] Import logged in the audit trail.

### M5 (`m5-app/`)
- [ ] Optional: upload/point-to user CSVs + (optional) mapping file from the UI; show the import report; banner indicates user-imported dataset is active.
- [ ] Persistent **"Bring-Your-Own Test Data (synthetic/sample only)"** labelling; reset-to-calm/stressed available.

### Docs / README
- [ ] Link this spec from the README; restate the scope boundary (test data only; real data → contained PoC).

---

## 7. Acceptance test
- A user can copy the templates, fill them with their own **test** data, run the loader with `--source`, and see it validated and loaded (or rejected with a clear per-row report).
- A user with differently-shaped CSVs can supply a `--mapping` YAML and achieve the same, with value normalisation applied.
- An invalid import (dangling reference, bad enum, over-mapped/unmapped required field) is **rejected with a readable reason**, not silently loaded.
- Imported data lands as a named dataset; the concentration metrics + UBO + watchlist compute on it; "reset to calm/stressed" restores the bundled data.
- The scope boundary (test/synthetic only; real data out of scope) is visible in the app and docs; all gates green.
