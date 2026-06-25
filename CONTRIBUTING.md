# Contributing

A learning prototype on **synthetic data** — production-shaped, not production-hardened.
Contributions should keep it honest, tested, and reproducible.

## Ground rules

- **Synthetic data only.** Never add real, production, customer, or regulated data.
  Use obviously-fake names/ids (`Acme Holdings Pte Ltd`, `LE-0001`).
- **One concern per PR**, with a Conventional-Commit title.
- **Tests are part of the change**, not a follow-up. A module isn't done until its
  tests pass and the gates are green.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt        # ruff, black, mypy, pytest, hypothesis, ...
pre-commit install                          # run the gates on every commit
```

See [`docs/running-the-lens.md`](docs/running-the-lens.md) to run the app and
[`docs/lab-handbook.md`](docs/lab-handbook.md) to build it module by module.

## The gates (must pass before merge)

| Gate | Local command | CI job |
|---|---|---|
| Lint | `ruff check .` | quality |
| Format | `black --check .` | quality |
| Types | `mypy . --ignore-missing-imports` | quality |
| Tests | `pytest -q` | quality + **integration** (live Fuseki/OPA/gator) |
| Security | `bandit`, `pip-audit`, `gitleaks`, CodeQL | security + codeql |

`pre-commit run --all-files` runs the same lint/format/type/secret gates locally.
The **integration** tests need a live Fuseki (`m0-ontology/scripts/start_fuseki.sh`);
they auto-skip when one isn't reachable.

## Decisions

If you make an architectural or security-relevant decision, add an **ADR** under
[`docs/adr/`](docs/adr/) (copy `0000-template.md`). It keeps the *why* traceable.

## Standards

The full engineering & DevSecOps standards are in
[`docs/engineering-practices.md`](docs/engineering-practices.md); the build spec is
[`CLAUDE.md`](CLAUDE.md). Report security concerns per [`SECURITY.md`](SECURITY.md).
