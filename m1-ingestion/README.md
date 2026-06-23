# M1 — Synthetic data + ingestion

A generator that emits two labelled synthetic datasets (**calm** and
**stressed**) as source-style CSV tables, a loader that maps those rows to FIBO
instances and replaces the Fuseki default graph (idempotently), and a
plain-Python **metrics oracle** that proves the engineered data lands in the
intended risk bands.

> Learning prototype on **synthetic data**. The stressed set is deliberately
> engineered to breach thresholds; it is not realistic portfolio data. A fresh
> clone defaults to **calm**. See `data/README.md`.

## What's here

```
m1-ingestion/
├── lens_m1/
│   ├── spec.py        # typed source-table records
│   ├── datasets.py    # the engineered calm + stressed designs (one 30-entity roster)
│   ├── metrics.py     # reference (oracle) concentration metrics — §3 / §9
│   ├── csv_tables.py  # write/read the five CSV source tables
│   ├── rdfize.py      # rows -> FIBO instances (the M0 lens vocabulary)
│   ├── loader.py      # CSV -> RDF -> Fuseki (idempotent replace)
│   └── config.py      # env: LENS_DATASET (default calm), Fuseki settings
├── scripts/           # generate_data.py · load_data.py · show_metrics.py
├── data/              # calm/ and stressed/ CSVs + data/README.md (provenance)
└── tests/             # datasets, metrics oracle, CSV/RDF, Fuseki integration
```

## Prerequisites

```bash
pip install -r ../requirements-dev.txt    # dev tooling
pip install -r requirements.txt           # rdflib, requests
# A running Fuseki (see ../m0-ontology/README.md): ../m0-ontology/scripts/start_fuseki.sh &
```

## Run (generate → select → load)

```bash
python -m scripts.generate_data                 # writes data/calm/ and data/stressed/
python -m scripts.show_metrics                   # print the calm-vs-stressed numbers
python -m scripts.load_data                      # load calm (default) into Fuseki
python -m scripts.load_data --dataset stressed   # or stressed
```

The M0 concentration query runs unchanged on the loaded data
(`cd ../m0-ontology && python -m scripts.run_money_shot`): on **stressed** the
Acme group shows SGD 20M direct → **34M connected**, breaching its 25M limit; on
**calm** it stays within limit.

## Test

```bash
pytest m1-ingestion -q                 # unit: datasets, metrics oracle, CSV/RDF
pytest -m integration -q               # also loads into a running Fuseki (auto-skips if down)
```

## Verify (M1 gates)

- **Functional:** generate is deterministic; reload is **idempotent**
  (same triple count); triple counts scale with row counts; the M0 concentration
  query still works on generated data (asserted in `tests/test_load_integration.py`).
- **Engineered cases** (`tests/test_metrics.py`, the oracle for §6/§9): stressed
  breaches single-name (Acme 20M→34M), CR₁₀/HHI, sector, UBO (Vortex), NBFI
  cascade (Nimbus 5M→47M) and structural WWR; calm sits within all bands.
- **Engineering gates:** `ruff` / `black` / `mypy` / `pytest` / `bandit` clean;
  `pre-commit run --all-files` green.

## Notes on the model

- **Two exposure notions** (see `metrics.py`): *single-name connected exposure*
  (overlap; for utilisation, watchlist, UBO, cascade) and *risk-owner
  attribution* (each loan counted once — the guarantor's group if guaranteed,
  else the borrower's UBO; for HHI / CR₁₀ / sector). The latter avoids
  double-counting and reflects where risk concentrates.
- The loader writes **only instance triples**; FIBO and the application ontology
  are loaded separately (M0). The concentration queries traverse instances, so
  they do not require FIBO to be present.
- `status` (`active`/`closed`) is carried on loans now; closed loans are excluded
  from metrics — the hook M2 uses for soft-delete.
