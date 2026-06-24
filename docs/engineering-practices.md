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
| Unit, property-based & integration tests | Correctness | pytest + Hypothesis |
| Dependency vulnerability scan | Known CVEs in deps | pip-audit + Dependabot |
| SAST | Static security analysis | bandit |
| Secret scanning | No leaked secrets | gitleaks |
| Container image scan | Vulnerabilities in M6 images | trivy |
| SBOM | Software bill of materials | syft / CycloneDX |

A dedicated **integration** job stands up a live Apache Jena Fuseki plus the **OPA** and **gator** binaries, so the tests that exercise real HTTP/SPARQL/SHACL, the M3 authorization policy, and the M6 admission policy actually run in CI (they auto-skip locally when those tools are absent). The fast lint/type job runs the unit tests on every push regardless.

Local equivalents run via **pre-commit hooks** (`.pre-commit-config.yaml`): ruff, black, mypy, gitleaks, whitespace/EOF fixers.

## Security-as-code artifacts

- **SHACL shapes (M2):** validation/data-quality rules expressed as code; tested with valid and invalid fixtures.
- **OPA/Rego policies (M3):** authorization expressed as code; tested with policy unit tests (allow/deny cases).
- **LLM query safety (M4):** generated SPARQL is validated against the known schema and constrained to read-only before execution — never run unverified generated queries.

## Policy as Code

This repo treats **policy as code (PaC)** as a first-class engineering practice — policies are written in a declarative language, version-controlled, peer-reviewed, unit-tested, and deployed through the same pipeline as application code. It appears at **two layers**, deliberately using the **same engine (OPA/Rego)** for consistency:

| Layer | Where | What it governs | Tool |
|---|---|---|---|
| Application authorization | **M3** | Who can see which exposures (role/desk/portfolio scoping) | OPA + Rego |
| Kubernetes admission control | **M6** | What workloads may run (no privileged containers, require resource limits, only scanned/approved images) | OPA **Gatekeeper** |

**Why OPA at both layers (honest scoping):** OPA is a general-purpose policy engine — the *same* Rego skill secures application authorization, Kubernetes admission, CI/CD, and infrastructure. Using OPA in M3 and OPA Gatekeeper in M6 makes "policy as code" a single coherent story across the stack rather than a one-off. This prototype demonstrates **two** of those layers; it does not claim org-wide, multi-environment policy governance — that is the broader pattern this points toward.

**Alternative (named for honesty):** Kyverno is the Kubernetes-native alternative for the M6 admission layer — policies are YAML (no Rego to learn) and it adds mutation/generation. The trade-off is Gatekeeper/Rego gives consistency with the OPA already used in M3 and more expressive logic, while Kyverno is simpler for Kubernetes-only teams. This build chooses **Gatekeeper** for engine consistency; Kyverno is a reasonable swap if you prefer YAML.

**Policy lifecycle (applies to both layers):** policies live in Git, are reviewed in PRs, tested in CI (OPA unit tests for M3; `gator test` against pass/fail fixtures for Gatekeeper constraints in M6), and deployed via GitOps (Argo CD). Use **audit mode** when rolling out new admission policies, then switch to **enforce** once existing violations are cleared.

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
