# Running the Lens — Operations & User Guide

How to **stand up** the Counterparty Concentration Lens on a laptop, **operate**
it day to day, and **use** the running app to drive the demo.

> Once it's running, see the **[CCR Demo & User Guide](ccr-demo-guide.md)** for a
> capability-by-capability walkthrough (where in the app · what to click · what to ask
> the NL chat · what to expect) covering the full CCR feature set.

> Learning prototype on **synthetic data**. Production-shaped, not
> production-hardened (see [`../SECURITY.md`](../SECURITY.md)). Nothing here loads
> or is suitable for real, production, or customer data.

- **Part A — Operate** (run the stack): below.
- **Part B — Use** (drive the app): [jump ↓](#part-b--use-the-app-user-guide).

---

# Part A — Operate the stack

## What runs, and where

| Component | Module | Port | Purpose |
|---|---|---|---|
| Apache Jena **Fuseki** | M0 | **3030** | triplestore + SPARQL (UI at `/#/dataset/lens/query`) |
| **Streamlit app** | M5 | **8501** | the interactive UI (the demo screen) |
| **Actions API** (FastAPI) | M2 | **8000** | guarded write REST surface (`/docs`) — *optional* |
| **OPA** | M3 | — | role policy (a local binary the app shells out to) |
| **Ollama** | M4 | 11434 | optional local LLM for the NL box |
| **k3d / Gatekeeper** | M6 | 8501 (NodePort 30085) | optional Kubernetes deployment |

> The app talks to the M2 action layer **in-process** for sandbox writes, so you
> do **not** need the standalone Actions API (:8000) running to use the app — it
> is only for driving the write actions over REST/curl.

## Prerequisites

- **Python 3.11+** (this build runs on 3.14) and a virtualenv.
- **Java 17+** for Fuseki (Java 26 is fine).
- **OPA** binary on `PATH` for role scoping — `brew install opa`. Without it the
  app still runs but role scoping is disabled (it shows "OPA policy: unavailable").
- *Optional:* **Docker + Ollama** for the real-LLM NL path; **Docker + k3d** for M6.

## One-time setup

```bash
# from the repo root
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt           # quality gates
pip install -r m0-ontology/requirements.txt -r m1-ingestion/requirements.txt \
            -r m2-actions/requirements.txt -r m5-app/requirements.txt   # runtime
# streamlit/pyarrow on very new Python? force wheels:  pip install --only-binary :all: streamlit pandas

# fetch FIBO (≈8 MB, into vendor/fibo/ — not committed)
./vendor/fibo/fetch_fibo.sh

# download Fuseki once (Java triplestore)
mkdir -p m0-ontology/.fuseki && curl -fSLo m0-ontology/.fuseki/fuseki.tgz \
  https://dlcdn.apache.org/jena/binaries/apache-jena-fuseki-6.1.0.tar.gz
tar -C m0-ontology/.fuseki -xzf m0-ontology/.fuseki/fuseki.tgz
```

## Bring up the app (every time)

```bash
source .venv/bin/activate                      # from repo root

# 1) start Fuseki on :3030 (in-memory dataset /lens)
m0-ontology/scripts/start_fuseki.sh &

# 2) generate the synthetic CSVs + load the CALM dataset (instance triples)
( cd m1-ingestion && python -m scripts.generate_data && python -m scripts.load_data --dataset calm )

# 3) launch the app on :8501
streamlit run m5-app/streamlit_app.py
```

Open **http://localhost:8501**. A fresh load shows the **calm** dataset and its
banner. (FIBO itself is not required for the app — the queries traverse the
instance triples — but you can load it for the standalone M0 demo; see below.)

**Optional — the guarded write API (M2):**

```bash
( cd m2-actions && python -m scripts.serve )    # http://localhost:8000/docs
curl -s localhost:8000/health
curl -s -X POST localhost:8000/actions/flag-limit-breach | python3 -m json.tool
```

**Optional — the standalone M0 "money shot"** (loads FIBO + the M0 starter data):

```bash
( cd m0-ontology && python -m scripts.load_data && python -m scripts.run_money_shot )
# re-load M1 data afterwards for the app:  cd ../m1-ingestion && python -m scripts.load_data --dataset calm
```

## Switch datasets & reset

| Action | How |
|---|---|
| Load stressed (breaches) | `cd m1-ingestion && python -m scripts.load_data --dataset stressed` |
| Back to calm | `… --dataset calm`, or the **sidebar → Reset to calm** in the app |
| In-app reset | sidebar **Reset to calm / Reset to stressed** |
| Active dataset | always shown in the **banner** at the top of the app |

Fuseki here is **in-memory**: restarting it empties the store — just reload.
Imported datasets and sandbox edits live only until the next load/reset, so the
bundled `calm`/`stressed` CSVs are never overwritten.

## Bring your own TEST data

```bash
cd m1-ingestion
python -m scripts.load_data --source <folder> --name my-scenario
python -m scripts.load_data --source <folder> --mapping <map.yaml> --name my-scenario   # differently-shaped CSVs
#   add --allow-partial to load only the rows that pass
```

Templates and column docs are in [`../templates/`](../templates/). Imported data
is validated (SHACL) with a per-row accepted/rejected report and audited — see
[`data-import.md`](data-import.md). **Synthetic / sample TEST data only.**

## Configuration (environment variables)

| Variable | Default | Effect |
|---|---|---|
| `FUSEKI_BASE_URL` | `http://localhost:3030` | triplestore endpoint |
| `FUSEKI_DATASET` | `lens` | dataset name in Fuseki |
| `LENS_DATASET` | `calm` | dataset the app/loader default to |
| `OPA_BIN` | (PATH) | OPA binary location (M3) |
| `OLLAMA_URL` / `OLLAMA_MODEL` | `http://localhost:11434` / `llama3.2` | M4 LLM |
| `LENS_DISABLE_OLLAMA` | unset | set to force the template NL engine |
| `LENS_AUDIT_LOG` | `m2-actions/audit/audit.log.jsonl` | audit trail path |

## Where things live

- **Audit log:** `m2-actions/audit/audit.log.jsonl` (JSON lines; also the app's *Audit* tab).
- **Fuseki log:** `m0-ontology/.fuseki/server.log`.
- **Fuseki UI:** http://localhost:3030/#/dataset/lens/query (paste any `.rq` from `m0-ontology/queries/`).

## Stop it

```bash
# Ctrl-C the streamlit / uvicorn foregrounds; then stop Fuseki:
pkill -f fuseki-server         # or kill the start_fuseki.sh job
```

## Optional: grounded LLM (M4)

```bash
ollama serve &                 # needs Docker/Ollama installed
ollama pull llama3.2
```

The app's sidebar then shows **"NL engine: Ollama"**; without it the NL box uses
the deterministic **template** engine (works fully offline). Either way the
generated SPARQL is safety-validated (read-only, known schema) before it runs.

## Optional: deploy on Kubernetes (M6)

```bash
./m6-infra/setup.sh             # k3d cluster + build/import images + Gatekeeper + policies + workloads
# app -> http://localhost:8501 ; prove admission control:
kubectl apply -f m6-infra/examples/bad-privileged-pod.yaml   # DENIED by Gatekeeper
```

See [`../m6-infra/README.md`](../m6-infra/README.md).

## Troubleshooting

| Symptom | Fix |
|---|---|
| App: *"Fuseki is not reachable"* | start it (`m0-ontology/scripts/start_fuseki.sh &`); check `curl localhost:3030/$/ping` |
| Dashboard empty / *"No counterparty groups"* | no dataset loaded → run the M1 load; or you're an RM whose portfolio is empty for that dataset |
| Sidebar: *"OPA policy: unavailable"* | install OPA (`brew install opa`) or set `OPA_BIN`; role scoping is off until then |
| Sidebar: *"NL engine: template"* | expected without Ollama — the NL box still works |
| `pip install streamlit` fails building pyarrow | `pip install --only-binary :all: streamlit pandas` |
| Spark capstone won't start | Spark 3.5 needs Java 17 + Python ≤3.12 → use `capstone/run_spark.sh` (its dedicated 3.12 venv + JDK 17) |

---

# Part B — Use the app (user guide)

Open **http://localhost:8501**. The layout: a **sidebar** (identity, reset,
status) and the **main area** (a banner + six tabs).

## Sidebar — who you are, and reset

- **Signed in as (role)** — pick a demo principal. This is the **M3** role scope:
  - **Dana — Group Risk** → sees **every** counterparty group.
  - **Bob — RM, Property desk** → only **Acme + Helios**.
  - **Carol — RM, Funds desk** → only **Vortex + Nimbus**.
  The same screen shows **different result sets** per role (reads are scoped).
- **Reset to calm / Reset to stressed** — reload the bundled base dataset.
- **Status line** — whether OPA policy and the Ollama NL engine are active.

## The banner (always visible)

- **CALM** — illustrative synthetic data, metrics in normal bands (the default).
- **⚠ STRESSED** — same names, deliberately engineered to **breach** thresholds.
- **📥 IMPORTED — '<name>'** — your bring-your-own TEST data is loaded.

It is impossible to read the numbers without seeing which dataset they came from.

## The tabs

1. **Dashboard** — the headline. HHI and CR₁₀ shown **connected vs direct**, the
   top sector, and a **red/amber watchlist** count; a role-scoped **exposures**
   table (with a sector filter) and the **wrong-way-risk** list. *(HHI/CR₁₀/sector
   are book-level; the watchlist, WWR and table are role-scoped.)*
2. **Explore** — pick a counterparty group → **Direct (named entity)** vs
   **Direct (group)** vs **Connected (multi-hop)**, the **limit-breach** verdict,
   and the **contributing paths** (which loans/guarantees/collateral build the
   connected number). Below it, the **NBFI cascade** chain for Nimbus.
3. **Ask (NL)** — type a question; the app generates **read-only, safety-validated
   SPARQL** (shown in an expander for transparency), runs it, and summarises.
   Examples: *"What is our total exposure to the Acme group?"*, *"Which
   counterparties are within 75% of their limit?"*, *"Show guarantee chains
   touching Nimbus"*, *"Any wrong-way risk?"*, *"Top counterparties?"*. Answers
   respect your role scope.
4. **Scenario Sandbox** — craft a what-if on synthetic data. **Add a loan**
   (record exposure) or **soft-delete** an object; every change goes through the
   **M2 guarded path** (SHACL-validated + audited — the UI never writes to Fuseki
   directly), and the metrics recompute. No hard delete.
5. **Bring Your Own** — point at a folder of CSVs (+ optional mapping), validate,
   and load as a named dataset; you get a **per-row rejection report**. *(TEST
   data only.)*
6. **Audit** — the who / what / when of every sandbox and import action.

## The 5-minute demo (the "money shot")

1. **Start on calm** — the dashboard is green; watchlist 0/0.
2. **Sidebar → Reset to stressed** — it lights up: **HHI ≈ 0.19**, **CR₁₀ ≈ 92%**,
   **financial services ≈ 52%**, **3 red + 4 amber** on the watchlist.
3. **Explore → Acme Holdings Pte Ltd** — **Direct (group) SGD 20M** vs
   **Connected SGD 34M → BREACH** of the 25M limit. The hidden multi-hop
   exposure (a guarantee + shared collateral) is what tips it over — exactly the
   gap a per-system view misses.
4. **Explore → NBFI cascade** — **Nimbus** direct **SGD 5M**, but if it fails the
   **cascade-connected exposure is SGD 47M** (the Archegos shape).
5. **Ask (NL)** → *"total exposure to the Acme group?"* → **SGD 34M**; open the
   expander to see the generated SPARQL.
6. **Scenario Sandbox** → add a loan: id `LN-9100`, borrower **Zenith Tech
   (LE-0041)**, principal **30,000,000** → it's written and **flagged
   `limit-breach:LE-0041`** (2M → 32M, over its 25M limit). The **Audit** tab
   records it; the dashboard watchlist updates.
7. **Sidebar → role = Bob (RM)** → the visible groups shrink to his portfolio —
   M3 scoping in action on the *same* screen.
8. **Reset to calm** — back to a known-good baseline.

## What the metrics mean (in one line each)

| Metric | Meaning |
|---|---|
| **Connected exposure** | direct loans + guarantees given + shared-collateral links + group roll-up — the *true* reach to a name |
| **Single-name utilisation** | connected exposure ÷ limit → green < 75% · amber 75–100% · red ≥ 100% |
| **CR₁₀** | share of the top-10 names in total connected exposure |
| **HHI** | concentration index (Σ shareᵢ²); shown **direct vs connected** to expose hidden concentration |
| **Sector concentration** | share of connected exposure by sector (financial-services cluster is the stressed story) |
| **Structural WWR** | collateral issued by the **same group** as the borrower — it evaporates when the name fails |
| **UBO aggregation** | exposure rolled up to the **ultimate parent**: subsidiaries each within limit, the group over |
| **NBFI cascade** | second-order exposure that becomes yours if a non-bank financial fails |

Exact definitions and the calm/stressed design are in
[`concentration-metrics.md`](concentration-metrics.md).
