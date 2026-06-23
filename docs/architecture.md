# Architecture — Counterparty Concentration Lens

*A learning prototype. Synthetic data. Not production software.*

The Lens is a **semantic layer that sits over source systems** and connects them into one governed, queryable model built on FIBO. It does not replace source systems; in this prototype the "source systems" are synthetic CSVs standing in for separate real systems.

## Layered view

```mermaid
flowchart TB
    subgraph APP["App / Presentation"]
        A1["Streamlit exposure view<br/>single counterparty, direct + indirect"]
    end
    subgraph AI["Grounded AI"]
        I1["Ollama + LangChain<br/>NL → SPARQL over the model"]
    end
    subgraph ONT["Semantic model (FIBO)"]
        O1["FIBO: BE · LOAN · FBC/Debt · FND · Guaranty"]
        O2["Fuseki triplestore + SPARQL"]
        O3["SHACL validation · guarded actions"]
        O4["OPA dynamic security"]
        O1 --- O2 --- O3 --- O4
    end
    subgraph COMPUTE["Ingestion / compute"]
        C1["Synthetic source data → FIBO instances → triples"]
    end
    subgraph INFRA["Substrate + delivery"]
        R1["k3d (Kubernetes) + Argo CD (GitOps)"]
    end

    APP --> AI --> ONT --> COMPUTE --> INFRA

    classDef app fill:#eef4ff,stroke:#7aa2e3,color:#1c2b45;
    classDef ai fill:#eafaf1,stroke:#74c69d,color:#1b3a2b;
    classDef ont fill:#fff4e6,stroke:#f0b67f,color:#5a3a14;
    classDef compute fill:#f3eefb,stroke:#b39ddb,color:#3a2a52;
    classDef infra fill:#eef9fb,stroke:#7ec8d6,color:#13404a;
    class A1 app;
    class I1 ai;
    class O1,O2,O3,O4 ont;
    class C1 compute;
    class R1 infra;
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

## Component choices (all free / open-source)

| Layer | Component |
|---|---|
| Semantic model | OWL / FIBO, authored in Protégé |
| Triplestore + query | Apache Jena Fuseki + SPARQL |
| Validation / rules | SHACL (pySHACL) |
| Action services | FastAPI |
| Access control | Open Policy Agent (OPA) |
| Grounded AI | Ollama (local LLM) + LangChain |
| App | Streamlit |
| Infra / delivery | k3d (Kubernetes) + Argo CD |

See `oss-stack-mapping.md` for how these map to the layers of a commercial platform, and `fibo-notes.md` for the FIBO modules.
