# ADR-0004: BYOD import — validate-all-then-load

- **Status:** Accepted
- **Date:** 2026-06-23

## Context

Bring-your-own test data (`docs/data-import.md`) must go through the same guard as
every other write. A partial load that accepts some rows and silently drops others
can leave the graph in a confusing, half-valid state.

## Decision

Default to **validate-all-then-load**: build the candidate graph, SHACL-validate it,
and write **nothing** unless every record passes — returning a per-row accepted/rejected
report either way. `--allow-partial` is an explicit opt-in that loads only the passing
rows. Imports load as a **named dataset** (never overwriting the bundled calm/stressed),
and are audited like any action.

## Consequences

- Atomicity by default: the store is never left half-updated; rejections are explicit
  and explained per row.
- Slightly less convenient for "just load what's valid" — hence the explicit
  `--allow-partial` escape hatch.
- Reuses the tested row→triples transform shared with the Spark capstone, so import and
  bulk load can't diverge.
