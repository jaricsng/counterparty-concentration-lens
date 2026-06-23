# Security policy

## TL;DR — what this project is, security-wise

This repository is a **learning prototype on synthetic data**. It is built to **production-shaped** standards — it demonstrates DevSecOps and secure-engineering practices (CI gates, dependency/secret/SAST/container scanning, SBOM, authorization-as-code, validation-as-code) — but it is **not production-hardened** and must not be treated as a secure system for real data or real use.

This file exists to make that boundary explicit and honest.

## What this prototype DOES demonstrate

- **Authorization as code** — role/attribute-based access enforced via OPA/Rego policies (M3), tested with allow/deny cases.
- **Data validation as code** — SHACL shapes rejecting invalid writes before they land (M2).
- **Safe handling of generated queries** — LLM-generated SPARQL (M4) is validated against the known schema and constrained to read-only before execution.
- **A full DevSecOps CI pipeline** — lint, type-check, tests, dependency vulnerability scan (pip-audit), SAST (bandit), secret scanning (gitleaks), container image scan (trivy), and SBOM generation.
- **Secrets discipline** — configuration via environment; `.env` never committed; secret scanning to catch mistakes.
- **Synthetic data only** — no real, personal, or institutional data anywhere.

## What this prototype does NOT provide (the honest boundary)

It is **not** a secure production system. In particular it does **not** include:

- Real authentication / identity management, session handling, or credential storage.
- Hardened network policy, TLS everywhere, secrets-management infrastructure (e.g. Vault), or key rotation.
- Production-grade authorization beyond the illustrative OPA policies.
- Scale, high availability, disaster recovery, backups, or runtime monitoring/alerting/incident response.
- Any security accreditation or compliance certification.
- Protection suitable for real, personal, regulated, or institutional data.

A passing CI pipeline and green scans demonstrate that the *practices* are in place. They do **not** make this prototype safe for production or for real data. Do not deploy it as-is for anything beyond learning and demonstration.

## Data policy

Use **synthetic data only**. Entity names and identifiers must be obviously fictional. Do not load real customer, counterparty, or institutional data into this prototype under any circumstances.

## Third-party content

This project uses FIBO (© EDM Council, Inc.; standardized by OMG; a trademark of EDM Council). FIBO files are used under their own licence terms. Public references in the documentation (e.g. Archegos, BCBS 239) are factual, drawn from regulatory/industry sources, and included only to explain why the modelling pattern matters — they are not advice to or about any institution.

## Reporting an issue

If you spot a security weakness in the code or pipeline (for example, a way the LLM query layer could execute an unsafe query, or a leaked-secret pattern the scan misses), please open an issue describing it. As a learning prototype there is no formal SLA, but well-described issues are genuinely useful for improving the example.
