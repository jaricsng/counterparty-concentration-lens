# Architecture Decision Records (ADRs)

Short, immutable notes capturing **why** a significant choice was made — the
context, the decision, and its consequences. New decisions get a new file; we
supersede rather than rewrite, so the reasoning stays traceable.

Copy [`0000-template.md`](0000-template.md) for a new one.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-fibo-as-semantic-model.md) | Adopt FIBO as the semantic model | Accepted |
| [0002](0002-opa-rego-for-authorization.md) | OPA/Rego for authorization (policy as code) | Accepted |
| [0003](0003-tamper-evident-audit-log.md) | Hash-chained, tamper-evident audit log | Accepted |
| [0004](0004-csv-import-validate-all-then-load.md) | BYOD import: validate-all-then-load | Accepted |
