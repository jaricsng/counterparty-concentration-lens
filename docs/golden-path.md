# The golden path — reusing these practices in every project

The practices in this repo aren't bespoke; they're a **portable baseline**. This
page is how you carry them into the next project so quality, security, and
governance are the default — not a heroic per-project effort.

## 1. What's reusable here (copy as a starter)

| Concern | Reusable artifact |
|---|---|
| Lint / format / type / security gates | `.pre-commit-config.yaml` (ruff, black, mypy, gitleaks, file hygiene) |
| Tool config | `pyproject.toml` (`[tool.ruff]`, `[tool.mypy]`, `[tool.bandit]`, pytest) |
| CI pipeline | `.github/workflows/ci.yml` (quality + integration + security + scan/SBOM), `codeql.yml` |
| Supply chain | Actions pinned by SHA; `dependabot.yml`; SBOM step |
| Governance | `CODEOWNERS`, `PULL_REQUEST_TEMPLATE.md`, `CONTRIBUTING.md`, `CHANGELOG.md` |
| Decisions | `docs/adr/` + `0000-template.md` |
| Security & compliance | `SECURITY.md`, `docs/threat-model.md`, `docs/compliance-and-data-governance.md` |
| Observability/audit pattern | `lens_m2/obs.py` (correlation IDs + JSON logs), hash-chained `audit.py` |

The cleanest way to make this repeatable: extract the above into a **template
repository** (GitHub "Template") or a **cookiecutter/`copier`** so `New repo →
from template` starts every project compliant on day one.

## 2. Make the gates unskippable (enforcement, not hope)

Practices only stick when they're enforced automatically:

1. **Pre-commit installed** (`pre-commit install`) — local gates run on every commit.
2. **CI required on `main`** — turn on **branch protection**:
   - Require status checks: `quality`, `integration`, `security`, `codeql`.
   - Require a PR + at least one **CODEOWNERS** review; no direct pushes to `main`.
   - Require branches up to date; require conversation resolution.
   - (Optional) require **signed commits**.
3. **Dependabot** open by default; pinned-by-SHA actions so it can bump them safely.
4. **Definition of Done** in the PR template — the checklist *is* the gate reviewers see.

> Set branch protection via **Settings → Branches → Add rule** (or `gh api`/Terraform
> in an org). Without it, green CI is advisory; with it, red CI blocks merge.

## 3. Definition of Done (per change / per module)

- [ ] Tests added and green (`pytest -q`); meaningful coverage of the logic.
- [ ] `ruff` / `black` / `mypy` clean; `pre-commit run --all-files` green.
- [ ] New security surface (endpoint / policy / query / image) has a test or scan.
- [ ] Docs updated (README + affected `docs/`); an **ADR** if a decision was made.
- [ ] Config via env, secrets out of git; deps pinned.
- [ ] Observability: structured logs + correlation id on new request paths; audit any
      state change.
- [ ] Conventional Commit; CHANGELOG updated for user-visible changes.

## 4. Scale it across an organisation

- **Org-level defaults**: a `.github` org repo for shared workflow templates,
  CODEOWNERS, and issue/PR templates; **org rulesets** to require checks on every repo.
- **Reusable workflows**: factor `ci.yml` into a callable workflow (`workflow_call`)
  so every repo references one maintained pipeline.
- **Policy as code for the platform**: the same OPA/Gatekeeper pattern (M3/M6) governs
  clusters fleet-wide; `gator test` keeps policies honest in CI.
- **Golden images / SBOM everywhere**: scan + SBOM in every pipeline; require provenance
  (SLSA) as maturity grows.
- **Make the easy path the compliant path**: scaffolding + templates so doing the right
  thing is less work than not.

## 5. Honest boundary

This is the *practice* baseline. Production adds what a prototype consciously omits —
real authN/Z, secrets management, runtime monitoring/alerting, HA/DR, and regulatory
conformance. Carry the **discipline** forward; add the **hardening** when the system is
real. See [`SECURITY.md`](../SECURITY.md) and the Capstone "what this is NOT".
