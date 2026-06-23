# Vendored FIBO (Financial Industry Business Ontology)

This directory holds the **FIBO** ontology used as the semantic foundation of the
Counterparty Concentration Lens prototype.

> **FIBO is a trademark of EDM Council, Inc.** FIBO is developed and published by
> the [EDM Council](https://edmcouncil.org/) and standardized by the
> [Object Management Group (OMG)](https://www.omg.org/). It is expressed in
> OWL 2 DL and ships with SHACL shapes. This project uses FIBO **unmodified**;
> our own application ontology lives separately under `m0-ontology/ontology/`
> and is never mixed into these files.

## What is vendored

| File | What it is |
|---|---|
| `prod.fibo-quickstart.ttl` | The official **FIBO Production "quickstart"** single-file distribution — every Release-maturity FIBO ontology (and its OMG Commons dependencies) merged into one self-contained Turtle file, ready to load into a triplestore. |
| `fetch_fibo.sh` | Deterministic download + checksum verification of the file above. |
| `SHA256SUMS` | Recorded checksum for integrity / reproducibility. |

The `.ttl` file itself is **not committed** (it is ~8 MB, above the repo's
2 MB pre-commit large-file gate, and is regenerable). Run `./fetch_fibo.sh` to
obtain it. It is git-ignored via the root `.gitignore`.

## Why the quickstart bundle (and not per-module files)

CLAUDE.md calls for the **BE, LOAN, FBC/Debt, FND, and Guaranty** modules. FIBO
ontologies cross-import heavily across domains, so loading individual module
files correctly means resolving a large import closure by hand — fragile and
error-prone. The EDM Council publishes the **quickstart** precisely to avoid
this: it is the canonical, self-resolving distribution of all Production-maturity
modules. It contains every module we need (verified below), so we vendor it as
the single source of FIBO truth and model against the specific terms we use.

## Modules / namespaces this prototype models against

Confirmed present in the vendored distribution:

| CLAUDE.md module | FIBO / Commons namespace(s) used | Representative terms |
|---|---|---|
| **Business Entities (BE)** | `BE/LegalEntities/LegalPersons`, `BE/OwnershipAndControl/*`, OMG `Commons/Organizations` | `cmns-org:LegalEntity`, corporate ownership/control |
| **Foundations (FND)** + OMG Commons | `FND/Parties/Parties`, `FND/Relations/Relations`, `FND/Accounting/CurrencyAmount`, `Commons/PartiesAndSituations`, `Commons/RolesAndCompositions` | `cmns-pts:Party` / `cmns-pts:PartyRole`, `cmns-rlcmp:Role` / `playsRole` / `isPlayedBy`, `fibo-fnd-acc-cur:MonetaryAmount` |
| **Loan (LOAN)** | `LOAN/LoansGeneral/Loans`, `LOAN/LoansSpecific/*` | `fibo-loan-ln-ln:Loan` |
| **FBC / Debt & Equities** | `FBC/DebtAndEquities/Debt`, `FBC/FinancialInstruments/FinancialInstruments` | `fibo-fbc-dae-dbt:Borrower` / `Lender` / `Collateral`, `fibo-fbc-fi-fi:DebtInstrument` |
| **Guaranty** (under FBC) | `FBC/DebtAndEquities/Guaranty` | `fibo-fbc-dae-gty:Guaranty`, `fibo-fbc-dae-gty:Guarantor` |

> Note: in current FIBO the **party/role machinery** (what lets one legal entity
> play borrower, guarantor, beneficial-owner roles at once) lives in **OMG
> Commons** (`cmns-pts:`, `cmns-rlcmp:`) which FND builds on. That role machinery
> is exactly what makes multi-hop concentration expressible — see
> `docs/fibo-notes.md`.

## Source & licence

- Source: <https://spec.edmcouncil.org/fibo/ontology/master/latest/prod.fibo-quickstart.ttl>
- Project & spec: <https://spec.edmcouncil.org/fibo/> · <https://github.com/edmcouncil/fibo>
- Observe FIBO's own licence terms (MIT-style, per the EDM Council). This
  prototype's MIT licence covers **our** code and application ontology only,
  **not** the vendored FIBO files, which remain under their upstream terms and
  trademark.
