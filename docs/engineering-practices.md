# Engineering & DevSecOps practices

This repository is a **learning prototype** built to **production-shaped** standards: it demonstrates software-engineering and DevSecOps best practice at each stage of the build, on synthetic data. It is **not production-hardened** — see [`SECURITY.md`](../SECURITY.md) for the boundary.

The point of documenting this is twofold: it makes the prototype a credible portfolio/teaching artifact, and it shows the practices themselves — which, for an operational data platform, are part of the deliverable.

## Principles

- **Practices applied per stage, not bolted on.** Every module is built test-first, linted, type-checked, and CI-gated before it's considered done.
- **Security as code.** Authorization (OPA/Rego) and data validation (SHACL) are first-class, version-controlled, tested artifacts — not configuration afterthoughts.
- **Honest framing.** The pipeline demonstrates the practice; it does not make a synthetic-data prototype production-secure.

## Practice maturity by domain

| Domain | Status | Where |
|---|---|---|
| Observability | 🟡 partial — structured JSON logs + access logging; no metrics/tracing backend | `lens_m2/obs.py`, M2 API middleware |
| Traceability | 🟢 request correlation IDs → logs + audit; ADRs for decisions; Conventional Commits | `obs.py`, [`adr/`](adr/) |
| Auditability | 🟢 tamper-evident, hash-chained audit + `verify()` | `audit.py`, [ADR-0003](adr/0003-tamper-evident-audit-log.md) |
| Security | 🟢 SHACL + OPA + injection guards + NL-query safety; bandit/CodeQL/gitleaks/trivy | M2/M3/M4, CI, [threat model](threat-model.md) |
| Governance | 🟢 CODEOWNERS, PR template, CONTRIBUTING, ADRs, CHANGELOG, branch protection | `.github/`, [`CONTRIBUTING.md`](../CONTRIBUTING.md) |
| Compliance | 🟡 data-governance + BCBS 239 *illustration* on synthetic data (not conformance) | [compliance doc](compliance-and-data-governance.md) |
| Supply chain | 🟢 pinned deps + SHA-pinned actions + Dependabot + SBOM | `requirements*`, `.github/` |
| Documentation | 🟢 per-module READMEs, ops/user guide, lab handbook, ADRs | `docs/`, module READMEs |

🟢 implemented (prototype-grade) · 🟡 partial / named gap. The boundary to production
is in [`SECURITY.md`](../SECURITY.md); to reuse this baseline elsewhere see the
[golden path](golden-path.md).

## Software-engineering standards

| Area | Standard | Tooling |
|---|---|---|
| Tests | Unit + integration; **≥85% coverage gate**; **mutation-tested** core logic | `pytest`, `pytest-cov`, `cosmic-ray` |
| Lint | Clean, no warnings | `ruff` |
| Format | Enforced, checked in CI | `black` |
| Types | Type hints throughout; passes | `mypy` |
| Dependencies | Pinned + lockfile; no unpinned installs | `pip-tools` / `uv` |
| Config | Environment-based; `.env.example` committed, real `.env` never | `python-dotenv` |
| Logging | Structured **JSON** logs + request **correlation IDs** | std `logging` + `lens_m2/obs.py` |
| Commits | Conventional Commits | — |
| Docs | Docstrings + per-module README (run/test/verify) | — |

## DevSecOps pipeline (GitHub Actions)

Runs on every push and pull request. The build fails on any gate.

| Stage | Purpose | Tool |
|---|---|---|
| Lint / format / type | Code quality gates | ruff, black --check, mypy |
| Unit, property-based & integration tests | Correctness | pytest + Hypothesis |
| Coverage gate | Regression floor (**≥85%**, measured on the full suite) | pytest-cov |
| Mutation testing | Test *effectiveness*, not just line coverage (weekly/manual) | cosmic-ray |
| Dependency vulnerability scan | Known CVEs in deps | pip-audit + Dependabot |
| SAST | Static security analysis | bandit + **CodeQL** |
| Secret scanning | No leaked secrets | gitleaks |
| Container image scan | Vulnerabilities in M6 images | trivy |
| SBOM | Software bill of materials | syft / CycloneDX |

A dedicated **integration** job stands up a live Apache Jena Fuseki plus the **OPA** and **gator** binaries, so the tests that exercise real HTTP/SPARQL/SHACL, the M3 authorization policy, and the M6 admission policy actually run in CI (they auto-skip locally when those tools are absent). The fast lint/type job runs the unit tests on every push regardless.

**Test quality, not just quantity.** Two gates guard against false confidence:
a **coverage floor** (`fail_under=85`, enforced in the integration job where the
full suite runs so the HTTP/SPARQL paths count — CI aggregate ~89%), and
**mutation testing** (`cosmic-ray`, weekly/manual via `mutation.yml` and
`scripts/run_mutation.sh`) which mutates the core risk logic and checks the tests
actually *kill* the mutants — coverage proves lines ran, mutation proves the
assertions catch bugs. Current mutation scores: `lens_m2/derived.py` 100%,
`lens_m4/safety.py` ~83%, `lens_m1/metrics.py` ~80% killed. Mutation is
report-only (slow + equivalent-mutant noise), so it informs rather than blocks.

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

## Observability & traceability

- **Structured JSON logs** (`lens_m2/obs.py`) — one machine-parseable event per line.
- **Correlation IDs** — one id per request (honouring an inbound `X-Correlation-ID`),
  propagated via a context variable into both the logs and the audit trail, and echoed
  back in the response header — so a single action is traceable end to end.
- **Access logging** — the M2 API middleware logs method / path / status / latency per request.
- *Named gaps:* no metrics/tracing backend (Prometheus/OpenTelemetry) or dashboards —
  runtime **operations** are consciously out of scope (see the SDLC table and `SECURITY.md`).

## Auditability

Every guarded action — accepted or rejected — is recorded with who/what/when/outcome.
The trail is **tamper-evident**: a hash chain (`seq` + `prev_hash` + `entry_hash`) that
`AuditLog.verify()` (and `GET /audit/verify`) recomputes to detect any edit, deletion,
reorder, or insertion — see [ADR-0003](adr/0003-tamper-evident-audit-log.md). It is
tamper-*evident*, not tamper-*proof*; production would anchor the chain externally.

## Supply-chain security

- **Pinned dependencies** — including `black` pinned exactly to the pre-commit hook so
  local and CI never diverge; `pip-audit` + Dependabot for CVEs.
- **GitHub Actions pinned by commit SHA** (not moving tags); Dependabot bumps them safely.
- **CodeQL** semantic analysis alongside `bandit` (Python SAST) and `gitleaks` (secrets).
- **SBOM** (CycloneDX) for the built image; `trivy` image scan.

## Governance, decisions & compliance

- **Ownership & review:** `CODEOWNERS`, a PR template carrying the Definition of Done,
  and [`CONTRIBUTING.md`](../CONTRIBUTING.md).
- **Decisions:** significant choices captured as immutable [ADRs](adr/).
- **Change log:** user-visible changes in [`CHANGELOG.md`](../CHANGELOG.md).
- **Risk & compliance:** a [STRIDE threat model](threat-model.md) and a
  [data-governance + BCBS 239 mapping](compliance-and-data-governance.md).
- **Reuse:** to carry all of this into the next project, see the
  [golden path](golden-path.md).

## Branch & merge guidance

- Protect `main`: require the `quality`, `integration`, `security`, and `codeql` checks
  plus a CODEOWNERS review before merge (see [golden path §2](golden-path.md) for how to
  make the gates unskippable). Without branch protection, green CI is advisory.
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
| Operate | Structured logs + correlation IDs + **tamper-evident audit** (`/audit/verify`); monitoring/alerting/HA-DR remain out of scope |
| Secure (cross-cutting) | pip-audit, bandit, **CodeQL**, gitleaks, trivy, SBOM, pre-commit, **SHA-pinned actions** |

The build demonstrates build-time and release-time practice, and adds operational
**traceability** (structured logs, correlation IDs, a verifiable audit trail). Runtime
**operations** proper — monitoring, alerting, incident response, HA/DR — remain out of
scope and are part of what separates this from a production system.
