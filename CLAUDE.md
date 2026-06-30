# CLAUDE.md — Counterparty Concentration Lens (build context)

## What we are building
A working **reference solution** for the **Counterparty Concentration Lens** — a learning prototype that demonstrates a single, real-time, multi-entity view of counterparty exposure, built on the **FIBO** financial ontology. The demo must run on this machine and be presentable end-to-end ("the Lens demo").

**This is a learning prototype on SYNTHETIC data, not production software.** Do not add scale, HA, real auth hardening, or real bank data. Optimise for a clear, runnable, demoable example. Full background: `docs/` (README, lab-handbook, fibo-notes).

## The demo we are driving toward (the "money shot")
A single screen / query that answers: **"What is our true, total exposure to counterparty group X, right now, across every product and relationship?"** — and surfaces **multi-hop concentration** (shared collateral, guarantee chains, group ownership) that no single source system sees. If a stakeholder sees only one thing, it's this.

## Domain & standard
Counterparty / lending exposure, modelled on **FIBO** (EDM Council / OMG, OWL 2 DL + SHACL).
- A **legal entity plays many roles**: borrower, counterparty, guarantor, beneficial owner. Counterparty is a *role*, not a class. This role machinery is what enables multi-hop concentration — preserve it.
- FIBO modules to use: **Business Entities (BE)** (entities, ownership/control), **Loan (LOAN)** (loan contracts), **FBC / Debt & Equities** (debt instruments, interest terms), **Foundations (FND)** (contract/party/role machinery), **Guaranty** package under FBC (guarantees/collateral).
- Obtain FIBO from https://github.com/edmcouncil/fibo (or spec.edmcouncil.org). Keep FIBO files in `vendor/fibo/` with attribution; do not mix into our own model files. FIBO is a trademark of EDM Council, Inc.

## Build rules
1. **One module at a time.** Build, verify it runs, show me the output, then STOP and wait for my confirmation before the next module.
2. **Commit per module** with a clear message (e.g. `m0: FIBO model + Fuseki + concentration SPARQL`).
3. Folder per module: `m0-ontology/` … `m6-infra/`. Docs in `docs/`. FIBO in `vendor/fibo/`.
4. Python venv (`.venv`); `requirements.txt` per Python module. Each module folder gets a `README.md` (what, how to run, how to verify).
5. **Synthetic data only.** Obviously-fake entity names/IDs (e.g. "Acme Holdings Pte Ltd", "LE-0001"). Never realistic real-world entities.
6. Ask before destructive commands; show a plan before large changes.
7. Prefer small, readable code — this is a teaching/portfolio artifact that may be read by others.

## Module plan & verification gates

> **Every module's verification ALSO inc1ludes the engineering gates** from the standards section below: tests pass, `ruff`/`black`/`mypy` clean, CI green, and any new security surface scanned. The functional "verify" below is necessary but not sufficient on its own.

### M0 — FIBO model + store + concentration query  (`m0-ontology/`)
Import the relevant FIBO modules (BE, LOAN, FBC/Debt, FND, Guaranty) into Apache Jena Fuseki. Author a thin **application ontology** that imports FIBO and adds only what's missing for the demo (e.g. an `Exposure` convenience view, a `Limit`). Load synthetic instances: ~15–25 legal entities, some in group/ownership structures; loans; guarantees linking entities; shared collateral; per-counterparty limits.
**Verify (the money shot):** a SPARQL query that, given a counterparty group, returns **total connected exposure including indirect paths** (guarantees + shared collateral + group ownership) — and show that the number is larger than any single direct-loan view. Show the result rows.
**Tier-1 additions (see `docs/concentration-metrics.md` §9):** (a) **UBO aggregation** — resolve the ownership/control chain to the ultimate parent and aggregate connected exposure to the UBO (test against a hand-worked chain; guard against ownership loops/double-counting); (b) **limit early-warning bands** — green/amber/red utilisation watchlist on connected exposure (amber/red flag computed in M2 or on read).

### M1 — Synthetic data + ingestion  (`m1-ingestion/`)
A generator that emits synthetic source-style tables (loans.csv, entities.csv, guarantees.csv, collateral.csv, limits.csv) as if from separate systems, plus a loader (dbt/DuckDB optional; plain Python fine) that maps rows → FIBO instances → triples in Fuseki, with simple lineage notes.
**Verify:** regenerate + reload is idempotent; triple counts match row counts; the M0 concentration query still works on generated data.
**Bring-your-own test data (see `docs/data-import.md`):** publish `templates/` CSVs + column docs; loader `--source <folder>` to load user CSVs and `--mapping <yaml>` (Tier 2) to translate differently-shaped CSVs; load as a named dataset (don't overwrite calm/stressed). **Test/synthetic data only — real data is out of scope** (contained PoC instead).

### M2 — Validation & actions  (`m2-actions/`)
SHACL shapes for business rules (e.g. exposure must not exceed limit; a guarantee must reference two distinct existing entities). FastAPI endpoints for guarded actions: `record-exposure`, `flag-limit-breach` — validate (SHACL) → write (SPARQL Update) → audit log.
**Scenario-sandbox actions (support M5 §8, see `docs/concentration-metrics.md`):** guarded create/update/deactivate endpoints for entity, loan, guarantee, collateral, limit — each validated by SHACL and audit-logged; soft-delete = status change (no hard delete); referential-integrity checks on deactivate. These back the interactive app; the UI must write ONLY through these, never direct to Fuseki.
**Imported test data also goes through this guarded path (see `docs/data-import.md`):** validate each record via SHACL + referential integrity before write; produce a per-row accepted/rejected import report; audit the import. No raw load that bypasses validation.
**Verify:** valid action writes + logs; invalid (over-limit, dangling guarantee) is rejected pre-write; audit trail shows who/what/when; deactivate excludes from metrics but preserves history; writes respect the M3 role.

### M3 — Dynamic security  (`m3-security/`)
OPA/Rego policy: roles like `relationship_manager` (own portfolio only) vs `group_risk` (all). API consults OPA and filters the exposure query by portfolio/desk.
**Verify:** same "show exposures" request returns correctly different result sets per role; policy external to app code.

### M4 — Grounded AI query  (`m4-ai/`)  [needs local Docker/Ollama]
Ollama (e.g. llama3.2) + LangChain: NL question → generated SPARQL over the FIBO model → execute → summarise. Route through M3 security filter. Provide the model the ontology schema as context.
**Verify:** ≥3 distinct questions (e.g. "total exposure to the Acme group?", "which counterparties are within 10% of their limit?", "show guarantee chains touching entity X") produce valid SPARQL and correct answers; security respected.

### M5 — Exposure app (the demo UI)  (`m5-app/`)
Streamlit, interactive (not a static dashboard) — see `docs/concentration-metrics.md` §8 for the full spec.
- **Dashboard:** single-counterparty exposure view (direct vs connected), contributing paths, and the concentration metrics (single-name, CR₁₀, HHI direct-vs-connected, sector, WWR, NBFI cascade), role-scoped (M3), calm/stressed banner.
- **Read/explore:** composable **filters** (sector, counterpartyType, exposure band, group, utilisation band, WWR-only); drill-down; sortable top-10; clickable cascade chain; embedded **M4 NL query box** (shows generated SPARQL, read-only, role-filtered).
- **Scenario Sandbox (guarded CRUD):** add/edit/soft-delete entity, loan, guarantee, collateral, limit — **only via M2 actions** (validate+audit); metrics **recompute live** after each change; audit panel; "reset to calm/stressed". Persistent "Scenario Sandbox — synthetic data" labelling. Writes respect M3 role.
**Verify:** filters update metrics for the subset; NL question returns correct role-filtered answer; a sandbox-added loan can push connected exposure over a single-name limit with the breach + HHI/CR₁₀ moving live (validated, audited); soft-deleting a guarantee drops connected exposure with audit; reset restores base data; **all writes go through M2 (no direct-to-Fuseki writes in the app)**; role scoping visible. **This is the demo screen.**

### M6 — Infra & delivery  (`m6-infra/`)  [needs local Docker/k3d]
Dockerfiles (API, agent, app; Fuseki official image), k8s manifests, k3d cluster, Argo CD Application pointing at the repo.
**Policy as code (admission control):** install **OPA Gatekeeper** (consistent with the OPA/Rego used in M3) and add ConstraintTemplates + Constraints enforcing baseline guardrails — e.g. disallow privileged containers, require resource limits, require images from an approved source / scanned images, require key labels. Store policies in Git; test with `gator test` (pass/fail fixtures) in CI; deploy via Argo CD. Roll out in **audit** mode, then **enforce**. (Kyverno is the YAML-native alternative; Gatekeeper chosen for engine consistency with M3 — see `docs/engineering-practices.md` § Policy as Code.)
**Verify:** components run as pods; Argo CD Synced/Healthy; a Git commit triggers reconcile; Gatekeeper constraints reject a deliberately non-compliant manifest (e.g. a privileged pod) and `gator test` passes in CI; trivy scan + SBOM produced.

### Capstone — scale & reflect
Swap M1's loader for an equivalent Spark job (same output, scaled); write the required **"what this is NOT"** statement.

> **Scope update (v0.4.0–v0.9.0):** the counterparty-risk areas originally listed here as out-of-scope — PFE/time-series, stress/macro shocks, credit-migration/PD-LGD-EAD/IFRS-9, systemic contagion, netting/CSA/haircuts — have since been **built as deliberately-simplified, clearly-labelled** models. The canonical map is `docs/ccr-coverage.md`. So the "what this is NOT" statement now frames the boundary as **simulation realism** (Monte-Carlo paths, calibrated curves, live market data), **not** the capabilities. The **data-import** out-of-scope items in `docs/data-import.md` §5 (live/API integration; real/production data; auto schema discovery; streaming/CDC) **do remain genuinely out of scope.** Core framing: the Lens demonstrates **connected, relationship-aware concentration** end-to-end into the full CCR stack, each layer simplified-but-honest, and consciously excludes simulation realism and live data integration.

### Repo skeleton files (do early, in M0 or a `chore:` commit)
- `LICENSE` (MIT), `.gitignore` (`.venv/`, `__pycache__/`, `*.db`, `.env`, dbt `target/`, `vendor/fibo/` large files if desired).
- `docs/architecture.md` and `docs/oss-stack-mapping.md` referenced by the README (content can be ported from existing materials).

## Engineering & DevSecOps standards (apply to EVERY module)

This prototype is **production-shaped, not production-hardened**: it demonstrates engineering and DevSecOps best practice on synthetic data, without claiming production readiness. Apply the following at each module, not as a final pass. See `docs/engineering-practices.md` and `SECURITY.md`.

**Software-engineering baseline (every module):**
- **Tests first-class:** unit tests for logic, integration tests for the API/SPARQL/SHACL paths. Use `pytest`. Aim for meaningful coverage of core logic (not a vanity %). A module is not "done" until its tests pass.
- **Lint + format:** `ruff` (lint) and `black` (format). Code must pass clean.
- **Type checking:** type hints throughout; `mypy` passes.
- **Dependencies pinned:** pin versions; commit a lockfile (`requirements.txt` with hashes, or `uv`/`pip-tools`). No unpinned installs.
- **Config via environment, not hardcoded:** endpoints, ports, paths from env/`.env.example` (never commit real `.env`). No secrets in code or git.
- **Structured logging,** not `print`. Clear error handling and input validation at boundaries (API inputs, generated SPARQL).
- **Docstrings** on public functions/modules; each module README documents run + test + verify.
- **Conventional Commits** (`feat:`, `fix:`, `test:`, `ci:`, `chore:`, `docs:`).

**DevSecOps pipeline (GitHub Actions, wire up early — in M0 or a `ci:` commit):**
- **CI workflow** runs on every push/PR: install → lint (ruff) → format check (black --check) → type check (mypy) → tests (pytest). Fail the build on any gate.
- **Dependency vulnerability scan:** `pip-audit` in CI; enable Dependabot (`.github/dependabot.yml`).
- **SAST:** `bandit` for Python static security analysis in CI.
- **Secret scanning:** `gitleaks` in CI (and ideally a pre-commit hook).
- **Container image scan:** `trivy` against the M6 Docker images in CI.
- **SBOM:** generate an SBOM (e.g. `syft`/CycloneDX) for the built images/artifacts as a CI artifact.
- **Pre-commit hooks** (`.pre-commit-config.yaml`): ruff, black, mypy, gitleaks, end-of-file/trailing-whitespace.
- **Branch protection guidance** documented in the practices doc (CI must pass before merge). Prefer signed commits where feasible.

**Security-as-code is a feature, not overhead here:**
- M2 SHACL = data-quality/validation as code. M3 OPA/Rego = authorization as code. Treat both as first-class security artifacts and test them (policy tests for OPA, shape tests for SHACL).
- Validate and sanitise any LLM-generated SPARQL (M4) before execution — never execute unverified generated queries; constrain to read-only and to the known schema.

**Honesty guardrail:** the CI badges, scans, and tests demonstrate the *practice*. The repo must still clearly state (README + SECURITY.md) that it is a learning prototype on synthetic data — production-shaped, not production-hardened. Never imply the scans make it production-secure.

**Per-module "done" now also requires:** tests pass, lint/format/type-check clean, CI green, and any new security surface (endpoints, policies, images) covered by the relevant scan/test.

## Definition of done
Every module runs from its README and is **tested, linted, type-checked, and green in CI**; the M0→M5 chain demos end-to-end on this machine (the Lens demo screen works on synthetic data and shows multi-hop concentration); M6 deploys to k3d via Argo CD with image scanning + SBOM and **OPA Gatekeeper admission policies (policy-as-code, gator-tested) enforcing baseline guardrails**; the full DevSecOps pipeline (CI, pip-audit, bandit, gitleaks, trivy, SBOM, pre-commit) is wired and passing; clean per-module Conventional-Commit history; FIBO properly vendored and attributed; `SECURITY.md` and `docs/engineering-practices.md` present; README's "what this is / is not" and the "production-shaped, not production-hardened" framing honoured throughout.

## Tone for any prose in the repo
Learning-led but reusable. Archegos / BCBS 239 may appear as **public facts explaining why the pattern matters** — never as advice to or a pitch at any institution. No bank named. Nothing claims production-readiness.
