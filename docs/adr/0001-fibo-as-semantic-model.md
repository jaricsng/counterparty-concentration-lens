# ADR-0001: Adopt FIBO as the semantic model

- **Status:** Accepted
- **Date:** 2026-06-20

## Context

The Lens must connect fragmented exposure data into one governed model where
"counterparty," "loan," and "exposure" mean one thing. We could invent a bespoke
schema or adopt an industry standard.

## Decision

Use **FIBO** (EDM Council / OMG, OWL 2 DL + SHACL) as the semantic model, importing
only the modules we need (BE, LOAN, FBC/Debt, FND, Guaranty, SEC) and adding a thin
application ontology for demo conveniences (an `Exposure` view, a `Limit`). Model a
**counterparty as a role, not a class** — FIBO's role machinery is what surfaces
multi-hop concentration.

## Consequences

- More credible and portable than a bespoke schema; the role model directly enables
  the "money shot" (connected exposure across guarantees, shared collateral, group
  ownership).
- FIBO is large and has a learning curve; we vendor and attribute it, and resolve the
  import closure to only the needed modules.
- We avoid OWL reasoning at runtime (queries over instances + SHACL for validation),
  trading inference completeness for predictable performance.
