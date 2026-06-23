# M0 — FIBO model + Fuseki + concentration query

The foundation of the Counterparty Concentration Lens: a FIBO-grounded
application ontology, synthetic instance data with group / guarantee /
shared-collateral structure, and the **money-shot** SPARQL query that surfaces
the *true connected exposure* to a counterparty group — far larger than any
single direct-loan view, and here a credit-limit breach that the naive view
hides.

> Learning prototype on **synthetic data**. Production-shaped, not
> production-hardened. FIBO is a trademark of EDM Council, Inc.
> (see `../vendor/fibo/README.md`).

## What's here

```
m0-ontology/
├── ontology/lens.ttl          # thin application ontology (imports FIBO; adds Exposure/Limit + role shortcuts)
├── data/instances.ttl         # ~17 synthetic legal entities, loans, guaranties, collateral, a limit
├── queries/
│   ├── direct_vs_connected.rq      # headline: single-source vs group vs connected + limit breach
│   ├── concentration_breakdown.rq  # every contributing multi-hop path
│   ├── connected_exposure_by_owner.rq  # risk-owner attributed exposure vector
│   ├── hhi.rq · cr10.rq            # portfolio concentration, direct vs connected (§3.2/3.3)
│   ├── sector_concentration.rq     # sector shares of connected exposure (§3.4)
│   ├── wrong_way_risk.rq           # same-issuer-collateral structural WWR (§3.6)
│   ├── nbfi_cascade.rq             # second-order exposure from a stressed NBFI (§3.5)
│   ├── ubo_aggregation.rq          # resolve to UBO; breach the subs don't (§9.1)
│   └── watchlist.rq                # single-name utilisation bands green/amber/red (§9.2)
├── lens_m0/                   # typed Python package (config, query loaders, rdflib + Fuseki backends)
├── scripts/                   # start_fuseki.sh, load_data.py, run_money_shot.py, show_concentration.py
└── tests/                     # unit (rdflib oracle) + integration (live Fuseki, auto-skips)
```

### FIBO modules used

This module models against six FIBO domains — **BE, LOAN, FBC/Debt, FND,
Guaranty, and SEC** — all supplied by the single vendored Production quickstart
(`../vendor/fibo/`, fetched via `fetch_fibo.sh`). The quickstart is self-resolving,
so there is no import closure to assemble by hand. **SEC (Securities)** was added
for the concentration enhancement so that collateral which is a security has a
proper **issuer** (`fibo-fbc-fi-fi:Security` / `Issuer`, issuance relation
`fibo-fnd-rel-rel:isIssuedBy`) — the basis for structural wrong-way-risk
detection. See `../vendor/fibo/README.md`.

### Application-ontology properties (what the model expects)

If you bring your own data, the thin application layer (`ontology/lens.ttl`,
namespace `https://lens.example/ontology/`) expects these conveniences on top of
FIBO:

| Property | On | Meaning |
|---|---|---|
| `lens:borrower` / `lens:lender` | Loan | role shortcuts over FIBO party/role machinery |
| `lens:guarantor` / `lens:guaranteedLoan` / `lens:guaranteedAmount` | Guaranty | who guarantees which loan, for how much |
| `lens:pledgedBy` / `lens:securesLoan` | Collateral | who pledged it; which loan(s) it secures (shared if >1) |
| `lens:isSubsidiaryOf` | LegalEntity → LegalEntity | ownership/control edge (transitive closure = the group) |
| `lens:principalAmount` / `lens:limitAmount` | Loan / Limit | amounts (single-currency SGD denormalisation) |
| `lens:eligibleCapital` | LegalEntity (institution) | single-name limit basis (% of capital) |
| `lens:annualRevenue` | LegalEntity (corporate) | alternative limit basis (% of revenue) |
| `lens:sector` | LegalEntity | sector tag (sector concentration) |
| `lens:counterpartyType` | LegalEntity | enum: `bank` / `corporate` / `nbfi` / `government` |
| `lens:collateralIssuer` | Collateral → LegalEntity | issuer of security collateral (structural WWR); aligned with `fibo-fnd-rel-rel:isIssuedBy` |

### How the multi-hop concentration is modelled

A legal entity plays many **roles** (FIBO/OMG-Commons machinery): borrower on
one loan, guarantor on another, pledgor of collateral on a third. Because the
same entities are shared across contracts, a query can connect exposures that
live in separate source systems:

1. **Group ownership** — `lens:isSubsidiaryOf*` (transitive) rolls subsidiaries
   into the group head.
2. **Guaranties** — a group entity guaranteeing an *outside* party's loan pulls
   that contingent amount in.
3. **Shared collateral** — one collateral item securing both a group loan and an
   outside loan links the two counterparties.

## Prerequisites

- Python 3.11+ and the repo dev tooling: `pip install -r ../requirements-dev.txt`
- Module deps: `pip install -r requirements.txt` (rdflib, requests)
- Java 17+ (for Fuseki) and the Fuseki distribution unpacked under `.fuseki/`:
  ```bash
  mkdir -p .fuseki && curl -fSLo .fuseki/fuseki.tgz \
    https://dlcdn.apache.org/jena/binaries/apache-jena-fuseki-6.1.0.tar.gz
  tar -C .fuseki -xzf .fuseki/fuseki.tgz
  ```
- FIBO fetched once: `../vendor/fibo/fetch_fibo.sh`

## Run the demo (the money shot)

```bash
# 1. Start Fuseki (in-memory dataset /lens on :3030)
./scripts/start_fuseki.sh &

# 2. Load FIBO + application ontology + synthetic instances (idempotent)
python -m scripts.load_data            # or: --no-fibo to skip the ~8 MB FIBO load

# 3. Run the concentration query for the Acme group
python -m scripts.run_money_shot
```

Expected headline (Acme group, `https://lens.example/id/LE-0001`):

| View | Amount (SGD) |
|---|---|
| Single-source (loans to the named entity only) | 2,000,000 |
| Direct loans across the ownership group | 10,000,000 |
| **True connected exposure (multi-hop)** | **15,500,000** |
| Group credit limit | 12,000,000 → **BREACH** |

Contributing paths: Acme Trading / Logistics / Holdings direct loans, a
**guaranty** over Globex's loan (+4,000,000), and an outside Initech loan linked
by **shared collateral** (+1,500,000) — none of which a single loan table shows.

You can also open the Fuseki UI at <http://localhost:3030/#/dataset/lens/query>
and paste either `.rq` file.

## Concentration metrics (§3 / §9)

The `queries/` folder also holds the full concentration-metric suite, run on the
richer **M1** datasets. Load a dataset (calm or stressed) via M1, then print all
metrics:

```bash
(cd ../m1-ingestion && python -m scripts.load_data --dataset stressed)
python -m scripts.show_concentration
```

On **stressed** this shows: HHI 0.044→**0.187** and CR₁₀ 55%→**92%**
(direct vs connected); financial-services sector **52%**; a watchlist of 3 red +
4 amber names; the **Vortex UBO** breaching (24M/20M) while no subsidiary does;
the **Nimbus** NBFI cascade (direct 5M → **47M** connected); and one structural
**wrong-way-risk** flag (Helios bond). On **calm** every metric sits in band.

Each metric has its own `.rq` (runnable in the Fuseki UI) and is validated
against the M1 Python oracle in `tests/test_metrics_queries.py`. The portfolio
metrics use **risk-owner attribution** (each loan counted once); single-name
utilisation / cascade / UBO use the **connected-exposure** overlap model — see
`../m1-ingestion/lens_m1/metrics.py`.

## Test

```bash
pytest m0-ontology -q                 # unit tests (rdflib in-memory oracle)
pytest -m integration -q              # also hits a running Fuseki (auto-skips if down)
```

The unit tests need neither Fuseki nor FIBO loaded — they run the *same* query
files against an in-memory rdflib graph, which is the oracle the integration
test compares Fuseki against.

## Verify (M0 gates)

- **Functional (money shot):** `connected_total (15.5M) > direct_group (10M) >
  direct_head_only (2M)`, and `connected_total > group_limit (12M)` → limit
  breach. Asserted in `tests/test_concentration.py`; reproduced live by
  `scripts/run_money_shot.py`.
- **Engineering gates:** `ruff check .`, `black --check .`, `mypy .`, `pytest`,
  `bandit -r m0-ontology -c ../pyproject.toml` all clean; `pre-commit
  run --all-files` green.
