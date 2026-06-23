# M4 — Grounded AI query (NL → SPARQL)

Ask the model in natural language; it generates SPARQL over the FIBO schema,
the query is **safety-validated** (read-only, known schema) before it may run,
results are scoped by the M3 role filter, and the generated SPARQL is shown for
transparency.

> Learning prototype on synthetic data. Production-shaped, not production-hardened.

## What's here

```
m4-ai/
├── lens_m4/safety.py     # MANDATORY gate: read-only SELECT/ASK, no update/federation, known schema
├── lens_m4/nl2sparql.py  # deterministic template generator (offline, grounded)
├── lens_m4/ollama.py     # OPTIONAL local Ollama backend (used only when reachable)
├── lens_m4/agent.py      # orchestrate: generate -> safety -> execute -> scope -> summarise
└── tests/                # safety rejection + ≥3 question patterns answered correctly
```

## Safety (never run unverified SPARQL)

`safety.is_safe()` rejects anything that is not a read-only `SELECT`/`ASK`: any
`INSERT`/`DELETE`/`DROP`/`CLEAR`/`LOAD`/`SERVICE`/… keyword, any IRI outside the
project's namespaces, or anything that fails to parse as a query. Both the
template output **and** any Ollama output must pass this gate before execution.

## Engines

- **template** (default, offline, deterministic) — maps a question to one of:
  exposure to a group, top counterparties, names near their limit, guarantee
  chains, sector concentration, wrong-way risk.
- **Ollama** (optional) — if a local server is reachable (`ollama serve` +
  `ollama pull llama3.2`), it is tried first; its SPARQL is held to the same
  safety bar. Disable with `LENS_DISABLE_OLLAMA=1`.

## Example questions

> "What is our total exposure to the Acme group?" · "Which counterparties are
> within 75% of their limit?" · "Show guarantee chains touching Nimbus" · "Any
> wrong-way risk?" · "Top counterparties?"

## Test

```bash
pytest m4-ai -q
```

## Verify

- Every generated query passes `is_safe`; updates/federation/foreign IRIs are rejected.
- ≥3 distinct questions return correct answers on the stressed data (e.g. Acme
  connected = SGD 34M; biggest counterparty = Nimbus; one WWR flag).
- Results respect the M3 visible-group scope (an RM sees a subset).
- Gates green (ruff/black/mypy/bandit/pip-audit).
