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

## 2. What this is NOT — deliberately out of scope

The Lens demonstrates **connected, relationship-aware concentration** — the gap
that fragmented systems miss. It **consciously excludes** time-series,
simulation, and full credit-modelling. These are real counterparty-risk
disciplines a production platform would add; naming them is deliberate scoping,
not inability.

| Excluded area | What it is | Why it's out |
|---|---|---|
| **PFE / dynamic, time-series exposure** | potential future exposure from market simulation over time | needs pricing + time-series data; the Lens uses static, point-in-time exposure |
| **Stress testing / scenario shocks** ("sector −30%") | revaluing the book under shocked risk factors | needs pricing/risk-factor models; the Scenario Sandbox offers honest manual "what-if" by editing data, not a shock engine |
| **Credit migration & expected loss** (PD / LGD / EAD, IFRS 9 staging) | rating-transition and provisioning models | a distinct credit-modelling discipline needing ratings/default data; would dilute the concentration focus |
| **Systemic-contagion metrics** (DebtRank-style) | network propagation of losses across the financial system | research-grade; the NBFI cascade view is a deliberately simpler taste |
| **Market/liquidity-adjusted exposure, netting sets, CSA / collateral haircuts** | real counterparty-credit machinery | out of scope for a synthetic, structural demo |
| **Correlation-based wrong-way risk** | exposure correlated with counterparty credit quality | the Lens flags only *structural* WWR (same-issuer collateral), and says so |
| **Static limits vs dynamic PFE monitoring** | limits/exposures are static in the data | a real production gap, named here rather than hidden |

**Out of scope for data ingestion** (see `docs/data-import.md` §5):

- **Live / API / database integration** to source systems (core banking, trade,
  collateral, KYC) — credentials, network access, schema discovery and security
  review are the production-PoC path, not a prototype feature.
- **Real, production, customer, or regulated data** — must not be loaded; the
  correct path is a contained PoC in the institution's own environment.
- **Automated schema discovery / ML-based mapping** — mapping is user-authored
  config, not auto-discovered.
- **Streaming / incremental / CDC ingestion** — batch only.

> **Framing line:** *the Lens deliberately demonstrates connected,
> relationship-aware concentration — the gap that fragmented systems miss — and
> consciously excludes time-series, simulation, and full credit-modelling, which
> are separate disciplines a production platform would add.*
