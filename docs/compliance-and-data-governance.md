# Compliance & data governance

How this prototype demonstrates governance practice — and where it deliberately
stops. It is a **learning artifact on synthetic data**, so "compliance" here means
*modelling the controls and the discipline*, not certifying against a regime.

## Data classification & handling

| Aspect | Position |
|---|---|
| Data class | **Synthetic / test only.** Obviously-fake entities (`Acme Holdings Pte Ltd`, `LE-0001`). |
| Real/regulated data | **Out of scope** and never loaded — enforced as a documented boundary, not a code feature. The BYOD import path (`docs/data-import.md`) repeats this and is for sample/test data only. |
| Secrets | None in code or git; config via environment; `gitleaks` in CI + pre-commit. |
| Retention | The audit trail is append-only and hash-chained; bundled datasets are reproducible from the generator. No real-data retention policy is needed (none exists). |
| Lineage | Ingestion records which synthetic source produced which triples (M1). |

## BCBS 239 — why the pattern matters (illustrative mapping)

BCBS 239 (risk-data aggregation & reporting) is the public backdrop for *why* a
connected counterparty view matters. The Lens **illustrates** several of its
principles on synthetic data — it does not claim conformance:

| BCBS 239 principle | How the Lens illustrates it |
|---|---|
| **P1 Governance** | Practices-as-code: SHACL (validation), OPA (authz), Gatekeeper (admission), all version-controlled, reviewed, tested. |
| **P2 Data architecture** | One governed FIBO model over fragmented sources; lineage on ingestion. |
| **P3 Accuracy & integrity** | SHACL business-rule validation on every write; **tamper-evident audit** of changes. |
| **P4 Completeness** | The "money shot": connected exposure across guarantees, shared collateral, group ownership — not just direct loans. |
| **P5 Timeliness** | Real-time recompute after a sandbox change (the demo screen). |
| **P6 Adaptability** | Composable filters, scenario sandbox, bring-your-own datasets. |
| **P7 Accuracy of reporting** | Metrics defined once (`docs/concentration-metrics.md`), oracle-pinned in tests, NL answers grounded in the model. |

> Reference: BCBS 239, *Principles for effective risk data aggregation and risk
> reporting* (2013). Cited as a public fact explaining the pattern — not as advice to
> or about any institution.

## Auditability & traceability controls

- **Audit trail** — every guarded action (accepted *or* rejected) recorded with
  who/what/when/outcome; **hash-chained** and verifiable (ADR-0003, `/audit/verify`).
- **Correlation IDs** — one id per request flows into logs and audit records, so an
  action is traceable end to end (`lens_m2/obs.py`).
- **Decision traceability** — significant choices recorded as [ADRs](adr/).
- **Change traceability** — Conventional Commits + CODEOWNERS review + green CI.

## License & attribution compliance

MIT (`LICENSE`); FIBO is © EDM Council, vendored with attribution under its own terms;
SBOM (CycloneDX) generated in CI for the built image. Public figures (Archegos, BCBS
239) are cited from regulatory/industry sources.

## Conscious out-of-scope

Regulatory conformance/attestation, real PII/regulated-data handling, records
retention schedules, data residency, and privacy (DPIA/GDPR) controls are **not**
addressed — there is no real data to govern. See the Capstone "what this is NOT".
