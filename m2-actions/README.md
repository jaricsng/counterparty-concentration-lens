# M2 — Validation & guarded actions

The **only sanctioned write path** into the graph. Every mutation is
SHACL-validated and audited; the M5 sandbox writes through this API and never
touches Fuseki directly. Validation rules and the audit trail are first-class,
version-controlled, tested security-as-code artifacts.

> Learning prototype on **synthetic data**. Production-shaped, not
> production-hardened. The write layer demonstrates the *pattern*; it is not a
> real data-management system.

## What's here

```
m2-actions/
├── lens_m2/
│   ├── shapes/lens_shapes.ttl  # SHACL business rules (structural + distinct-entities)
│   ├── validation.py           # pyshacl over the candidate graph
│   ├── store.py                # InMemoryStore (tests) / FusekiStore (runtime)
│   ├── graphbuild.py           # proposed triples (one source -> validate + INSERT)
│   ├── derived.py              # status-aware connected-limit breach + WWR (computed)
│   ├── actions.py              # ActionService: validate -> write -> flag -> audit
│   ├── audit.py                # append-only JSON-lines audit log
│   ├── models.py               # pydantic request models (boundary validation)
│   └── app.py                  # FastAPI surface (create_app factory)
├── scripts/serve.py            # uvicorn runner
└── tests/                      # validation, actions, API (in-memory; no Fuseki needed)
```

## The guard (every write)

1. **Boundary validation** — pydantic checks types / enums / required fields (HTTP 422 on bad input).
2. **SHACL validation** — the candidate graph (current data + proposal) must conform:
   referenced entities must exist (`sh:class`), amounts positive, a guaranty's
   guarantor must differ from the guaranteed loan's borrower (**two distinct
   existing entities**, via SHACL-SPARQL). Violations are **rejected pre-write**.
3. **Write** — on success, a single `INSERT DATA` (SPARQL Update).
4. **Derived flags** — connected **single-name limit breach** (a multi-hop
   aggregation, computed in SPARQL+Python, status-aware) and **structural
   wrong-way risk** are recomputed; new flags are returned and audited. A loan
   that breaches a limit is **written and flagged**, not rejected — so the
   sandbox can push a name over a limit and watch the metrics move.
5. **Audit** — every outcome (accepted *or* rejected) is appended to the audit
   log with who / what / when / reason / flags.

**Soft-delete** is a status change (`active` → `closed` for loans, `inactive`
otherwise): no triples are removed, so history is preserved while metrics
exclude the object. Deactivating an entity still referenced by an active loan or
guaranty is **guarded** (rejected).

## Endpoints

`POST /actions/{entities,loans,guaranties,collateral,limits}` (create) ·
`POST /actions/record-exposure` (book a loan) ·
`POST /actions/update-amount` · `POST /actions/deactivate` ·
`POST /actions/flag-limit-breach` · `POST /actions/flag-wrong-way-risk` ·
`GET /audit` · `GET /health`.

Editing limits requires the `group_risk` role (a placeholder for the full OPA
authorization in M3 — write-authorization, not just reads).

## Run

```bash
pip install -r requirements.txt
# needs a running Fuseki with a dataset loaded (see M0/M1):
(cd ../m1-ingestion && python -m scripts.load_data --dataset stressed)
python -m scripts.serve            # http://localhost:8000  (/docs for the OpenAPI UI)

# example: a loan that breaches Zenith's connected limit (written + flagged)
curl -s localhost:8000/actions/record-exposure -H 'content-type: application/json' \
  -d '{"loan_id":"LN-9100","lender_id":"LE-0099","borrower_id":"LE-0041","principal":30000000,"role":"group_risk"}'
```

## Test

```bash
pytest m2-actions -q     # in-memory store (rdflib) — no Fuseki required
```

## Bring-your-own-data import (`importer.py`)

The same guarded path also ingests user **TEST** datasets: `import_dataset()`
builds a candidate graph from canonical rows (`lens_m1.byod`), SHACL-validates it,
returns a **per-row accepted/rejected report**, and — only if every row passes
(`validate-all-then-load`, or `allow_partial=True` to load just the good rows) —
replaces the active graph as a named dataset and audits the import. Bundled
calm/stressed are never overwritten; "reset" restores them. See
`../docs/data-import.md` and `../templates/`.

## Verify (M2 gates)

- Valid create **writes + audits**; invalid (self-guaranty, dangling borrower,
  negative amount) is **rejected pre-write** and the rejection is audited.
- BYOD import: valid templates load + audit; an invalid import is **rejected with
  per-row reasons and nothing written** (atomic); `--allow-partial` loads only
  passing rows.
- A sandbox loan can push connected exposure **over a single-name limit** — it is
  written and the breach is flagged + audited.
- **Soft-delete** a guaranty → the NBFI cascade connected exposure drops
  (47M → 40M) while the triples remain (status `inactive`); deactivating an
  active borrower entity is guarded.
- Deactivating the same-issuer collateral clears the **wrong-way-risk** flag.
- Engineering gates: `ruff` / `black` / `mypy` / `pytest` / `bandit` /
  `pip-audit` clean; `pre-commit run --all-files` green.
