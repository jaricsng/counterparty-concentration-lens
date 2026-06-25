# Threat model

A lightweight **STRIDE** pass over the Lens. Scope: a learning prototype on
**synthetic data**, run locally or on a single k3d cluster — so the goal is to show
the *practice* and name the boundaries, not to certify a production system. Real
deployments inherit the gaps in [`SECURITY.md`](../SECURITY.md).

## Assets

Synthetic exposure data; the audit trail; the authorization policy (M3); the
admission policy (M6); the generated SPARQL path (M4). No real or regulated data is
in scope by design.

## Trust boundaries

```
user ─▶ M5 app ─▶ M2 API (guarded writes) ─▶ Fuseki (triplestore)
                     │                          ▲
                     ├─ M3 OPA (authz)           │ reads (role-scoped)
                     └─ M4 agent (NL→SPARQL, read-only)
```

The dashed boundary in [`architecture.md`](architecture.md) — real source systems,
real data, production-only capabilities — is **out of scope** and never crossed.

## STRIDE

| Threat | Vector | Mitigation in this build | Residual / gap |
|---|---|---|---|
| **Spoofing** | Caller asserts a role | Roles are demo principals; OPA scopes reads (M3) | No real authN (no OIDC/mTLS) — named gap |
| **Tampering** (data) | Direct write to Fuseki bypassing rules | UI/agent write **only** via M2; SHACL validates every write | Fuseki itself has no auth in the prototype |
| **Tampering** (audit) | Edit/delete audit records | **Hash-chained** audit + `verify()` / `/audit/verify` (ADR-0003) | Tamper-evident, not tamper-proof — anchor externally in prod |
| **Repudiation** | "I didn't do that" | Every action audited (who/what/when/outcome) + correlation ID | Bound to a demo identity, not a real one |
| **Information disclosure** | A role sees others' exposure | OPA role/portfolio scoping on reads (M3) | Coarse-grained; no field-level redaction |
| **DoS** | Expensive query / flood | Generated SPARQL is read-only + schema-validated (M4); small data | No rate limiting / quotas (out of scope) |
| **Elevation of privilege** | Run a privileged workload | Gatekeeper denies privileged/over-permissioned pods (M6) | Cluster RBAC not hardened |
| **Injection** | Crafted IDs/SPARQL | Strict ID allowlist + predicate allowlist in SPARQL Update; NL→SPARQL safety gate (read-only, known schema) | — |
| **Supply chain** | Compromised dep/action | Pinned deps; pip-audit, bandit, CodeQL, gitleaks, trivy + SBOM; GH Actions pinned by SHA | No signing/provenance (SLSA) yet |

## Conscious non-goals

Real authentication/identity, secrets management at scale, multi-tenant isolation,
rate limiting, network policy, and HA/DR are **out of scope** for a synthetic-data
prototype. They are part of what separates this from production — see `SECURITY.md`
and the Capstone "what this is NOT".
