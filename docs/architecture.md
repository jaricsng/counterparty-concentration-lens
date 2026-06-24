# Architecture — Counterparty Concentration Lens

*A learning prototype. Synthetic data. Not production software.*

The Lens is a **semantic layer that sits over source systems** and connects them into one governed, queryable model built on FIBO. It does not replace source systems; in this prototype the "source systems" are synthetic CSVs standing in for separate real systems.

## System context

Who and what sits around the Lens — and, importantly, where the boundary is. Solid arrows are in scope (synthetic / test data only); dashed arrows mark the deliberate boundary to real systems, real data, and production-only capabilities.

```mermaid
flowchart TB
    subgraph ACTORS["People"]
        direction LR
        RM["Relationship Manager<br/>(own portfolio)"]
        GR["Group Risk Officer<br/>(whole book)"]
        AN["Analyst / Explorer"]
        AD["Platform Admin"]
    end

    LENS["<b>Counterparty Concentration Lens</b><br/>FIBO-based prototype · connected exposure,<br/>concentration metrics, grounded query, sandbox<br/><i>learning prototype · synthetic data</i>"]

    subgraph INSCOPE["In scope (synthetic / test data only)"]
        direction LR
        DS["Bundled datasets<br/>calm · stressed"]
        BYO["Bring-your-own<br/>test CSVs (+ mapping)"]
        LLM["Local LLM<br/>(Ollama, on-device)"]
    end

    subgraph OUTSCOPE["Out of scope (production / real-data boundary)"]
        direction LR
        SRC["Real source systems<br/>core banking · trade · KYC · collateral"]
        REAL["Real / regulated<br/>counterparty data"]
        PFE["Time-series · PFE ·<br/>stress simulation · credit models"]
    end

    RM --> LENS
    GR --> LENS
    AN --> LENS
    AD --> LENS

    DS -->|"validated load"| LENS
    BYO -->|"validated load (via guarded actions)"| LENS
    LENS <-->|"on-device, grounded"| LLM

    SRC -.->|"contained PoC in bank's own<br/>environment — NOT this prototype"| LENS
    REAL -.->|"never loaded here"| LENS
    PFE -.->|"named gaps (Capstone)"| LENS

    classDef actor fill:#eef4ff,stroke:#7aa2e3,color:#1c2b45;
    classDef sys fill:#fff4e6,stroke:#f0b67f,color:#5a3a14;
    classDef inscope fill:#eafaf1,stroke:#74c69d,color:#1b3a2b;
    classDef outscope fill:#fdeef2,stroke:#e89ab0,color:#5a1f33;

    class RM,GR,AN,AD actor;
    class LENS sys;
    class DS,BYO,LLM inscope;
    class SRC,REAL,PFE outscope;

    style ACTORS fill:#f7faff,stroke:#7aa2e3,color:#1c2b45;
    style INSCOPE fill:#f4fcf7,stroke:#74c69d,color:#1b3a2b;
    style OUTSCOPE fill:#fdf4f8,stroke:#e89ab0,color:#5a1f33;
```

The dashed boundary is the point: real source systems, real data, and production-only risk capabilities sit *outside* the prototype by design. The Lens reads roles (relationship manager vs group risk) to scope what each person sees, runs an on-device LLM so nothing leaves the machine, and accepts only synthetic/test inputs through a validated load path.

## Layered view

```mermaid
flowchart TB
    subgraph APP["App / Presentation"]
        A1["Streamlit interactive app<br/>dashboard · filters · drill-down"]
        A2["Scenario sandbox<br/>add / edit / soft-delete (guarded)"]
    end
    subgraph AI["Grounded AI"]
        I1["NL → SPARQL (safety-validated, read-only)<br/>templates + local LLM (Ollama) when available"]
    end
    subgraph ONT["Semantic model (FIBO) + analytics"]
        O1["FIBO: BE · LOAN · FBC/Debt · FND · Guaranty · SEC"]
        O2["Fuseki triplestore + SPARQL"]
        O5["Concentration analytics<br/>single-name · CR₁₀ · HHI · sector · WWR · UBO · watchlist"]
        O3["SHACL validation · guarded actions · audit"]
        O4["OPA dynamic security (authz as code)"]
        O1 --- O2 --- O5 --- O3 --- O4
    end
    subgraph COMPUTE["Ingestion / compute"]
        C1["Synthetic datasets (calm / stressed)"]
        C2["Bring-your-own test CSVs<br/>+ mapping → validated import"]
        C1 --- C2
    end
    subgraph INFRA["Substrate + delivery"]
        R1["k3d (Kubernetes) + Argo CD (GitOps)"]
        R2["OPA Gatekeeper (policy as code)<br/>+ trivy scan + SBOM"]
        R1 --- R2
    end

    APP --> AI --> ONT
    COMPUTE -->|"validated load (via M2)"| ONT
    ONT --> INFRA

    classDef app fill:#eef4ff,stroke:#7aa2e3,color:#1c2b45;
    classDef ai fill:#eafaf1,stroke:#74c69d,color:#1b3a2b;
    classDef ont fill:#fff4e6,stroke:#f0b67f,color:#5a3a14;
    classDef compute fill:#f3eefb,stroke:#b39ddb,color:#3a2a52;
    classDef infra fill:#eef9fb,stroke:#7ec8d6,color:#13404a;
    class A1,A2 app;
    class I1 ai;
    class O1,O2,O3,O4,O5 ont;
    class C1,C2 compute;
    class R1,R2 infra;
    style APP fill:#f7faff,stroke:#7aa2e3,color:#1c2b45;
    style AI fill:#f4fcf7,stroke:#74c69d,color:#1b3a2b;
    style ONT fill:#fffaf2,stroke:#f0b67f,color:#5a3a14;
    style COMPUTE fill:#faf7fe,stroke:#b39ddb,color:#3a2a52;
    style INFRA fill:#f5fcfd,stroke:#7ec8d6,color:#13404a;
```

## Why the multi-hop view is the point

```mermaid
flowchart LR
    G["Acme Group (parent)"]:::grp
    A["Acme Holdings"]:::ent
    B["Acme Trading"]:::ent
    C["Acme Property"]:::ent
    L1["Loan 1"]:::loan
    L2["Loan 2"]:::loan
    COL["Shared collateral"]:::col

    G --> A
    G --> B
    A -->|borrower| L1
    B -->|guarantor| L1
    B -->|borrower| L2
    L1 -->|secured by| COL
    L2 -->|secured by| COL

    classDef grp fill:#fff4e6,stroke:#f0b67f,color:#5a3a14;
    classDef ent fill:#eef4ff,stroke:#7aa2e3,color:#1c2b45;
    classDef loan fill:#eafaf1,stroke:#74c69d,color:#1b3a2b;
    classDef col fill:#fdeef2,stroke:#e89ab0,color:#5a1f33;
```

A per-system view sees Loan 1 and Loan 2 as separate, modestly-sized exposures. The connected FIBO model sees that they share collateral, sit under one parent group, and are cross-guaranteed — so the *true* concentrated exposure is far larger than any single system reports. Surfacing that gap is the demo.

## Concentration analytics

Every metric is computed on **connected exposure** (the number above), then expressed in the forms a risk function uses. The recurring punchline: a name or portfolio looks acceptable on *direct* exposure but breaches once the hidden, connected exposure is counted.

```mermaid
flowchart TB
    EXP["Connected exposure per name / group<br/>direct + guarantees + shared collateral + group ownership"]:::core

    subgraph PERNAME["Per-name / per-group measures"]
        direction LR
        SN["Single-name limit<br/>utilisation % (vs capital/revenue)"]:::m
        WL["Early-warning bands<br/>green / amber / red watchlist"]:::m
        UBO["UBO roll-up<br/>aggregate to ultimate parent"]:::m
    end

    subgraph PORTFOLIO["Portfolio measures"]
        direction LR
        CR["CR₁₀<br/>top-10 share"]:::m
        HHI["HHI<br/>(direct vs connected)"]:::m
        SEC["Sector / government<br/>concentration share"]:::m
    end

    subgraph HIDDEN["Hidden-risk flags"]
        direction LR
        WWR["Structural WWR<br/>same-issuer collateral"]:::f
        NBFI["NBFI cascade<br/>second-order exposure"]:::f
    end

    EXP --> PERNAME
    EXP --> PORTFOLIO
    EXP --> HIDDEN

    PERNAME --> OUT["Breach + watchlist surfaced live<br/>(direct looks fine · connected breaches)"]:::out
    PORTFOLIO --> OUT
    HIDDEN --> OUT

    classDef core fill:#fff4e6,stroke:#f0b67f,color:#5a3a14;
    classDef m fill:#eef4ff,stroke:#7aa2e3,color:#1c2b45;
    classDef f fill:#fdeef2,stroke:#e89ab0,color:#5a1f33;
    classDef out fill:#eafaf1,stroke:#74c69d,color:#1b3a2b;
    style PERNAME fill:#f7faff,stroke:#7aa2e3,color:#1c2b45;
    style PORTFOLIO fill:#f7faff,stroke:#7aa2e3,color:#1c2b45;
    style HIDDEN fill:#fdf4f8,stroke:#e89ab0,color:#5a1f33;
```

Thresholds (illustrative): single-name > 25% of capital / > 10% of revenue; CR₁₀ > 60–70%; HHI > 0.18; sector > 30%. See `concentration-metrics.md` for exact definitions. PFE / time-series, stress-shock simulation, and full credit-modelling are deliberately out of scope.

## Component choices (all free / open-source)

| Layer | Component |
|---|---|
| Semantic model | OWL 2 DL / FIBO (vendored) + a thin, hand-authored application ontology |
| Triplestore + query | Apache Jena Fuseki + SPARQL |
| Validation / rules | SHACL (pySHACL) |
| Action services | FastAPI |
| Access control | Open Policy Agent (OPA) |
| Grounded AI | safety-validated NL→SPARQL — deterministic templates, with a local LLM (Ollama) when available |
| App | Streamlit |
| Infra / delivery | k3d (Kubernetes) + Argo CD (GitOps) + OPA Gatekeeper (admission policy-as-code) |
| Scale (capstone) | Apache Spark (PySpark) ingestion equivalent |

See `oss-stack-mapping.md` for how these map to the layers of a commercial platform, and `fibo-notes.md` for the FIBO modules.
