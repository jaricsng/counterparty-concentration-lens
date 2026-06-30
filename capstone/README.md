# Capstone — scale & reflect

Two deliverables: (1) swap M1's loader for an **equivalent Spark job** that
produces the *same* FIBO triples at scale, and (2) the explicit **"what this is
NOT"** statement that names the counterparty-risk areas this prototype
deliberately leaves out.

> Learning prototype on SYNTHETIC data. Production-shaped, not production-hardened.

## 1. Spark-equivalent ingestion (scale)

The M1 loader maps CSV source tables to RDF in-process. The Capstone reproduces
that as a **PySpark** job: each table is read as a DataFrame and its rows are
`flatMap`-ped to N-Triples across partitions — the path you would take to scale
ingestion to a real loan book.

The per-row transform is the pure, Spark-free `lens_capstone.triples_map`, the
single source of truth shared by the Spark job and the test. So the output is
identical to M1's **by construction**, not by luck.

```
capstone/
├── lens_capstone/triples_map.py  # pure row -> N-Triples transform (== lens_m1.rdfize)
├── spark_loader.py               # the PySpark job (DataFrame -> flatMap -> N-Triples)
├── run_spark.sh                  # run in local mode (JDK 17 + the 3.12 spark venv)
├── requirements.txt              # pyspark 3.5.3 (Java 17, Python <= 3.12)
└── tests/test_triples_map.py     # proves the transform == M1, no Spark needed
```

**Runtime note (honest):** Spark 3.5 needs **Java 17** and **Python ≤ 3.12**; the
repo's main `.venv` is 3.14, so the job runs in a dedicated `capstone/.venv-spark`
(python3.12) with JDK 17. The equivalence test runs in the main 3.14 venv (rdflib
only) and is part of CI.

**Verified:** the Spark job, run on the `stressed` dataset, emits **698 triples —
identical (set-equal, zero differences) to the M1 loader's output**:

```bash
./capstone/run_spark.sh ../m1-ingestion/data/stressed /tmp/lens_capstone_nt   # -> wrote 698 triples
pytest capstone -q                                                            # transform == M1 (calm + stressed)
```

## 2. What this is NOT — the boundary is *realism*, not capability

The Lens started as a sharp demonstration of **connected, relationship-aware
concentration** — the gap that fragmented systems miss. It has since been extended
(v0.1.0 → v0.9.0) to cover the **full counterparty-credit-risk landscape** — netting/
collateral, EAD/Expected-Loss/capital, PFE/EE and full xVA, IFRS-9 staging, stress &
macro scenarios, and systemic contagion — **each built as a deliberately simplified,
clearly-labelled model**. So the honest boundary moved: it is no longer *which
capabilities exist*, but **how much simulation realism** sits behind them.

The always-current, capability-by-capability map (✅ implemented · ⚠️ simplified ·
❌ out) is [`../docs/ccr-coverage.md`](../docs/ccr-coverage.md). Each module's docstring
states exactly what it is **not**. In summary:

| CCR area | How the Lens does it (⚠️ simplified) | The realism that stays out (❌) |
|---|---|---|
| **PFE / EE exposure profile** (v0.4.0) | analytical amortising-base + √t add-on profile | Monte-Carlo exposure paths, derivative MtM |
| **xVA — CVA·DVA·FVA·MVA·KVA** (v0.4/0.7) | deterministic integrals over the EE profile + flat params | simulated paths, calibrated funding/own-credit |
| **Stress / scenario shocks** (v0.3.0) | named deterministic shocks re-derive every metric | a real pricing/risk-factor revaluation engine |
| **Macro / multi-factor stress** (v0.8.0) | factor-vector × per-sector sensitivities (correlated) | an *estimated* factor-correlation matrix, simulated paths |
| **EAD / PD / LGD / Expected Loss** (v0.2.0) | rating-driven PD table, flat LGD, SA risk-weights | IRB estimation, PD/LGD calibration from data |
| **IFRS-9 staging & lifetime ECL** (v0.5.0) | Stage 1/2/3 by rating rule; constant-hazard lifetime ECL | quantitative SICR backstops, macro overlays |
| **Systemic contagion** (v0.6/0.9) | two-hop + iterative multi-round cascade with fire-sale | a calibrated network / price-impact model |
| **Netting / collateral / CSA haircuts** (v0.1.0) | net post-collateral exposure, dedicated-collateral rule | full CSA mechanics, variation/initial-margin modelling |
| **Wrong-way risk** | *structural* WWR (same-issuer collateral) | correlation-based WWR (exposure ↔ credit quality) |

**Still genuinely out of scope for data ingestion** (see `docs/data-import.md` §5):

- **Live / API / database integration** to source systems (core banking, trade,
  collateral, KYC) — credentials, network access, schema discovery and security
  review are the production-PoC path, not a prototype feature.
- **Real, production, customer, or regulated data** — must not be loaded; the
  correct path is a contained PoC in the institution's own environment.
- **Automated schema discovery / ML-based mapping** — mapping is user-authored
  config, not auto-discovered.
- **Streaming / incremental / CDC ingestion** — batch only.

> **Framing line:** *the Lens demonstrates **connected, relationship-aware
> concentration** end-to-end — into loss, capital, forward exposure, provisioning
> and systemic contagion — with every counterparty-credit-risk area built as a
> **clearly-labelled simplified** model. What it consciously omits is **simulation
> realism** (Monte-Carlo paths, calibrated curves, live data), not the capabilities.*
