# Engineering & DevSecOps practices

This repository is a **learning prototype** built to **production-shaped** standards: it demonstrates software-engineering and DevSecOps best practice at each stage of the build, on synthetic data. It is **not production-hardened** — see [`SECURITY.md`](../SECURITY.md) for the boundary.

The point of documenting this is twofold: it makes the prototype a credible portfolio/teaching artifact, and it shows the practices themselves — which, for an operational data platform, are part of the deliverable.

## Principles

- **Practices applied per stage, not bolted on.** Every module is built test-first, linted, type-checked, and CI-gated before it's considered done.
- **Security as code.** Authorization (OPA/Rego) and data validation (SHACL) are first-class, version-controlled, tested artifacts — not configuration afterthoughts.
- **Honest framing.** The pipeline demonstrates the practice; it does not make a synthetic-data prototype production-secure.

## Software-engineering standards

| Area | Standard | Tooling |
|---|---|---|
| Tests | Unit + integration; core logic covered; green before "done" | `pytest` |
| Lint | Clean, no warnings | `ruff` |
| Format | Enforced, checked in CI | `black` |
| Types | Type hints throughout; passes | `mypy` |
| Dependencies | Pinned + lockfile; no unpinned installs | `pip-tools` / `uv` |
| Config | Environment-based; `.env.example` committed, real `.env` never | `python-dotenv` |
| Logging | Structured logs, not `print` | std `logging` |
| Commits | Conventional Commits | — |
| Docs | Docstrings + per-module README (run/test/verify) | — |

## DevSecOps pipeline (GitHub Actions)

Runs on every push and pull request. The build fails on any gate.

| Stage | Purpose | Tool |
|---|---|---|
| Lint / format / type | Code quality gates | ruff, black --check, mypy |
| Unit + integration tests | Correctness | pytest |
| Dependency vulnerability scan | Known CVEs in deps | pip-audit + Dependabot |
| SAST | Static security analysis | bandit |
| Secret scanning | No leaked secrets | gitleaks |
| Container image scan | Vulnerabilities in M6 images | trivy |
| SBOM | Software bill of materials | syft / CycloneDX |

Local equivalents run via **pre-commit hooks** (`.pre-commit-config.yaml`): ruff, black, mypy, gitleaks, whitespace/EOF fixers.

## Security-as-code artifacts

- **SHACL shapes (M2):** validation/data-quality rules expressed as code; tested with valid and invalid fixtures.
- **OPA/Rego policies (M3):** authorization expressed as code; tested with policy unit tests (allow/deny cases).
- **LLM query safety (M4):** generated SPARQL is validated against the known schema and constrained to read-only before execution — never run unverified generated queries.

## Branch & merge guidance

- Protect `main`: require CI to pass before merge.
- Prefer signed commits where feasible.
- Keep the per-module commit history clean and Conventional-Commit formatted (it doubles as a readable build narrative).

## Mapping practices to SDLC / DevSecOps stages

| DevSecOps stage | In this repo |
|---|---|
| Plan | `CLAUDE.md` build plan; per-module objectives & verification gates |
| Code | Type-hinted, linted, documented; security-as-code (SHACL/OPA) |
| Build | Pinned deps; reproducible; Dockerfiles (M6) |
| Test | pytest unit/integration; policy + shape tests |
| Release | Conventional Commits; GitOps via Argo CD (M6) |
| Deploy | k3d + Argo CD reconciliation (M6) |
| Operate | (Out of scope for a prototype — named as a gap in SECURITY.md) |
| Secure (cross-cutting) | pip-audit, bandit, gitleaks, trivy, SBOM, pre-commit |

The "Operate" stage is deliberately out of scope and named as such — a prototype demonstrates build-time and release-time practice; runtime operations (monitoring, alerting, incident response, HA/DR) are part of what separates this from a production system.
