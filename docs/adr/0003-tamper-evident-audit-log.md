# ADR-0003: Hash-chained, tamper-evident audit log

- **Status:** Accepted
- **Date:** 2026-06-24

## Context

Every guarded action is recorded (who/what/when/result). A plain append-only
JSON-lines file records events but cannot prove it hasn't been edited, reordered, or
truncated after the fact — the integrity property an audit trail is supposed to give.

## Decision

Make the audit log a **hash chain**. Each record carries a monotonic `seq`, the
`prev_hash` of the previous record, and an `entry_hash` over its own canonical
content. `AuditLog.verify()` recomputes the chain and reports any break (edit,
deletion, reorder, insertion); it's exposed at `GET /audit/verify`. Each record also
carries a `correlation_id` so an action ties back to its request and structured logs.

## Consequences

- Tampering becomes **detectable** with a single verification pass — a meaningful
  integrity guarantee on synthetic data, and an honest demonstration of the pattern.
- It is tamper-**evident**, not tamper-**proof**: an attacker who can rewrite the whole
  file could recompute the chain. Real deployments would anchor the chain externally
  (append-only/WORM storage, periodic notarization, or signing). Named as a gap.
- Records gained fields (`seq`, `prev_hash`, `entry_hash`, `correlation_id`); readers
  are additive-compatible. Chains resume correctly across process restarts.
