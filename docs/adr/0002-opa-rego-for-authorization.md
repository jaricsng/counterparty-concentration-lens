# ADR-0002: OPA/Rego for authorization (policy as code)

- **Status:** Accepted
- **Date:** 2026-06-21

## Context

Different roles must see different exposures (a relationship manager sees their
portfolio; group risk sees everything). Authorization logic embedded in application
code is hard to review, test, and reuse.

## Decision

Express authorization as **policy as code** with **OPA/Rego**, external to the app.
The API consults OPA (`opa eval`) to scope the visible group set per role/portfolio.
Use the **same engine** for Kubernetes admission control in M6 (OPA Gatekeeper), so
one Rego skill covers both layers.

## Consequences

- Authorization is version-controlled, peer-reviewed, and **unit-tested** (allow/deny
  cases) like any code; it's inspectable and reusable.
- Adds an `opa` binary dependency; if it's absent the engine raises
  `PolicyUnavailable` (fail-closed at the policy layer; the app decides how to degrade).
- Kyverno was considered for M6 (YAML-native) but rejected for engine consistency with
  M3 — see `docs/engineering-practices.md` § Policy as Code.
