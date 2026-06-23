# M3 — Dynamic security (OPA/Rego)

Authorization **as code**: a Rego policy, evaluated by OPA, decides which
counterparty groups a user may see. The read layer scopes every exposure query
to that visible set, so the *same* request returns different results per role.
The policy lives **outside** the application code and is unit-tested.

> Learning prototype on synthetic data. Production-shaped, not production-hardened.

## What's here

```
m3-security/
├── policies/authz.rego        # the policy: group_risk (all) vs relationship_manager (own portfolio)
├── policies/authz_test.rego   # Rego unit tests (opa test)
├── lens_m3/policy.py          # PolicyEngine — shells out to `opa eval` (does not reimplement rules)
├── lens_m3/portfolios.py      # demo principals + portfolio assignments
└── tests/                     # python tests (skip if no opa binary)
```

## Roles

| Role | Sees |
|---|---|
| `group_risk` | every counterparty group |
| `relationship_manager` | only the groups in their portfolio |

Demo principals (`lens_m3/portfolios.py`): *Dana* (group risk, all), *Bob* (RM —
Acme + Helios), *Carol* (RM — Vortex + Nimbus). In the M5 app the role selector
switches between them and the dashboard/watchlist/NL results re-scope live.

## Prerequisites

- The **OPA** binary on PATH (`brew install opa`), or set `OPA_BIN`.

## Run / test

```bash
opa check m3-security/policies          # validate the policy
opa test  m3-security/policies -v       # Rego unit tests (5)
pytest m3-security -q                    # python tests via `opa eval` (skip if no opa)
```

## Verify

- `opa test` passes (group_risk sees all; RM sees only its portfolio; allow/deny).
- `visible_groups("group_risk", …)` ⊋ `visible_groups("relationship_manager", …)`
  for the same candidate set — the M3 demo point (same request, different results).
- Policy is external to app code (Rego files); the Python wrapper only invokes
  `opa eval`. Gates green (ruff/black/mypy/bandit).
