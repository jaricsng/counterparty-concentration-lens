# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
the project uses [Conventional Commits](https://www.conventionalcommits.org/).

## [Unreleased]

### Added
- **Observability & traceability**: request-scoped correlation IDs propagated to
  structured JSON logs and the audit trail (`lens_m2/obs.py`); `X-Correlation-ID`
  request/response header on the M2 API.
- **Auditability**: tamper-evident, hash-chained audit log with a `verify()`
  integrity check and an `/audit/verify` endpoint.
- **Governance**: `CODEOWNERS`, PR template, `CONTRIBUTING.md`, this changelog, and
  Architecture Decision Records under `docs/adr/`.
- **Compliance**: data-governance & BCBS 239 mapping (`docs/compliance-and-data-governance.md`)
  and a STRIDE threat model (`docs/threat-model.md`).
- **Supply chain / DevSecOps**: GitHub Actions pinned by commit SHA; CodeQL workflow.
- **Reuse**: a "golden path" to seed new projects with these practices
  (`docs/golden-path.md`).

### Earlier (build history)
M0–M6 + Capstone, the BYOD test-data import, the P1–P3 test suites (e2e/integration,
per-shape SHACL, property-based, contracts, M6 manifest lint), and the CI integration
job (live Fuseki + OPA + gator). See the Conventional-Commit history for detail.
