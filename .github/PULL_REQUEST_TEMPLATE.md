<!-- Keep the build narrative readable. Small, single-purpose PRs preferred. -->

## What & why

<!-- One or two sentences. Link the module / issue / ADR if relevant. -->

## Module(s)

<!-- e.g. M2 (actions), docs, ci -->

## Checklist (Definition of Done)

- [ ] Tests added/updated and **passing** (`pytest -q`)
- [ ] `ruff` / `black --check` / `mypy` clean (or `pre-commit run --all-files`)
- [ ] New security surface (endpoint / policy / query / image) covered by a test or scan
- [ ] Docs updated (module README + any affected doc in `docs/`)
- [ ] **Synthetic data only** — no real, production, or customer data added
- [ ] Conventional Commit title (`feat:`, `fix:`, `test:`, `ci:`, `docs:`, `chore:`)
- [ ] If an architectural decision was made, an **ADR** was added under `docs/adr/`

## Notes for reviewers

<!-- Anything non-obvious, trade-offs considered, follow-ups deferred. -->
