# Counterparty Concentration Lens — a learning prototype

*An open exploration of how a standards-based semantic layer (FIBO) can give a single, real-time, multi-entity view of counterparty exposure — built to understand the pattern, and reusable by anyone who wants to learn it.*

> **What this is:** a learning prototype on **synthetic data**, built end-to-end to understand how ontology-driven operational data platforms work, using the financial industry's own open standard. It demonstrates an architecture and a pattern. **It is not production software**, and it is not affiliated with or directed at any specific institution.

---

## Why this exists

Banks and other large institutions run extensive risk and compliance systems — but much of that machinery was built to produce *periodic reports*, not to answer, in the moment, a deceptively simple question:

> *What is the true, total exposure to a single counterparty or borrower group — right now — across every product, entity, and jurisdiction?*

When the data behind that question lives in many disconnected systems, each with its own definition of "counterparty," "exposure," and "limit," the connected answer is slow and manual to assemble. This is a well-documented, public problem:

- **It has a documented cost.** When Archegos Capital Management defaulted in March 2021, Credit Suisse lost roughly **US$5.5 billion** and was later fined a record **£87 million** by the UK regulator. The bank's own investigation found the risk systems were not lacking and the risks were "conspicuous" — the failure was that no single, timely, connected view reached decision-makers in time. Peers with better-connected views saw the same counterparty and exited cleanly.
- **Regulators require fixing it.** Risk-data aggregation under **BCBS 239** has been mandatory for globally systemic banks since 2016, yet only **2 of 31** were fully compliant as of the 2022 assessment (Basel Committee, published Nov 2023). Supervisors continue to escalate.

These are public facts, cited here to explain *why the pattern matters*. This repository is an **educational exploration of that pattern**, not advice to or about any organisation.

---

## The idea in one diagram

A semantic layer sits **over** existing systems — connecting them into one governed, queryable model — rather than replacing them. The model is built on **FIBO**, the financial industry's open ontology, so "counterparty," "loan," and "exposure" have a single, standards-based definition.

```mermaid
flowchart TB
    subgraph SOURCES["Source systems (synthetic, in this prototype)"]
        direction LR
        S1["Loan / lending"]
        S2["Counterparty / KYC"]
        S3["Collateral & guarantees"]
        S4["Limits & ratings"]
    end

    subgraph LENS["Counterparty Concentration Lens"]
        direction TB
        O["FIBO semantic model<br/>BE · LOAN · FBC/Debt · FND · Guaranty"]
        Q["Connected, multi-hop exposure view"]
        A["Grounded query + lineage + audit"]
        O --- Q --- A
    end

    SOURCES -->|"map to FIBO"| LENS
    LENS -->|"answers: true total exposure, now"| OUT["Single counterparty view"]

    classDef src fill:#eef4ff,stroke:#7aa2e3,color:#1c2b45;
    classDef lens fill:#fff4e6,stroke:#f0b67f,color:#5a3a14;
    classDef out fill:#eafaf1,stroke:#74c69d,color:#1b3a2b;
    class S1,S2,S3,S4 src;
    class O,Q,A lens;
    class OUT out;
    style SOURCES fill:#f7faff,stroke:#7aa2e3,color:#1c2b45;
    style LENS fill:#fffaf2,stroke:#f0b67f,color:#5a3a14;
```

---

## Why FIBO

The **Financial Industry Business Ontology (FIBO)** is an open-source, machine-readable model of financial concepts, developed by the **EDM Council** and standardized by the **Object Management Group (OMG)**. It emerged from the data-governance lessons of the 2008 crisis and is expressed in **OWL 2 DL** (so it supports automated reasoning) with **SHACL** shapes for validation.

This prototype uses the FIBO modules relevant to counterparty exposure:

| Concept | FIBO module |
|---|---|
| Legal entities, ownership & control chains | **Business Entities (BE)** |
| Loan contracts (commercial, retail, etc.) | **Loan (LOAN)** domain |
| Debt instruments, interest & debt terms | **Debt & Equities** module in **Financial Business & Commerce (FBC)** |
| Contract / agreement / party-role machinery | **Foundations (FND)** |
| Guarantees & collateral | **Guaranty** package in FBC |

A key modelling point worth understanding: in FIBO, **"counterparty" is a role, not a separate class.** One legal entity plays many roles — borrower, counterparty, guarantor, beneficial owner — through FIBO's role machinery. That is exactly what lets the model see that the borrower on one loan is the guarantor on another: the multi-hop connection a flat, relational warehouse loses.

---

## What the prototype demonstrates

- A **single connected exposure view** across entities and products, from a FIBO-based model.
- **Multi-hop concentration** that no single source system sees (shared collateral, guarantee chains, group structures).
- A **grounded query layer** — natural-language questions answered by generated queries over the governed model, not by a black-box guess.
- **Lineage and audit** on every figure — the traceability that BCBS 239 calls for.

All on **synthetic data**, runnable on a laptop.

---

## Architecture & learning path

This prototype is built on the same layered, open-source stack documented in the companion learning lab. Each layer has a clean open-source component:

| Layer | Component |
|---|---|
| Semantic model | OWL / FIBO, authored in Protégé |
| Triplestore + query | Apache Jena Fuseki + SPARQL |
| Validation / rules | SHACL (pySHACL) |
| Action services | FastAPI |
| Access control | Open Policy Agent (OPA) |
| Grounded AI | local LLM (Ollama) + LangChain |
| App | Streamlit |
| Infra / delivery | k3d (Kubernetes) + Argo CD (GitOps) |

See [`docs/`](docs/) for the full lab handbook, the architecture and diagrams, the open-source-stack mapping, the FIBO module notes, and the [engineering & DevSecOps practices](docs/engineering-practices.md) applied throughout.

This prototype is built to **production-shaped** standards — it demonstrates DevSecOps and secure-engineering practice at each stage (CI gates, tests, dependency/secret/SAST/container scanning, SBOM, authorization-as-code, validation-as-code) — but it is **not production-hardened**. See [`SECURITY.md`](SECURITY.md) for the honest boundary.

---

## Repo structure

```
.
├── README.md                  ← you are here
├── LICENSE
├── SECURITY.md                 ← production-shaped vs production-hardened boundary
├── .pre-commit-config.yaml     ← local quality + security hooks
├── .github/
│   ├── workflows/ci.yml        ← lint, type, test, scan, SBOM
│   └── dependabot.yml
├── docs/
│   ├── lab-handbook.md         ← step-by-step build, module by module
│   ├── architecture.md         ← diagrams (light-theme Mermaid)
│   ├── oss-stack-mapping.md    ← platform layers → open-source equivalents
│   ├── engineering-practices.md← DevSecOps & SDLC practices applied
│   └── fibo-notes.md           ← which FIBO modules, and why
├── vendor/
│   └── fibo/                   ← FIBO ontology files (attributed)
├── m0-ontology/                ← FIBO model + Fuseki + concentration SPARQL
├── m1-ingestion/               ← synthetic data + dbt/DuckDB → triples
├── m2-actions/                 ← SHACL + FastAPI guarded actions
├── m3-security/                ← OPA policy scoping (authz as code)
├── m4-ai/                      ← grounded NL→SPARQL agent (query-safe)
├── m5-app/                     ← Streamlit exposure view (the demo)
└── m6-infra/                   ← k3d + Argo CD + image scan + SBOM
```

---

## What this is *not*

Being precise here is part of the point:

- **Not production software.** A learning prototype on synthetic data, single-instance, laptop-scale. Not scalable, hardened, or operated as built.
- **Not financial, legal, or compliance advice.** The Archegos and BCBS 239 references are public facts included to explain why the pattern matters — nothing here is advice to any institution.
- **Not affiliated** with EDM Council, OMG, or any bank. FIBO is used under its open licence; FIBO is a trademark of EDM Council, Inc.
- **Not a real risk system.** A better connected *view* surfaces a concentration or breach; acting on it is a matter of governance and people, which no prototype provides.

---

## Getting started

See [`docs/lab-handbook.md`](docs/lab-handbook.md). Everything is free and open-source; no cloud account or API key is required. Start with `m0-ontology/` and build up one module at a time.

---

## License & attribution

Released under the [MIT License](LICENSE) — you're free to learn from, fork, and reuse it. FIBO content is © EDM Council and used under its open licence; please observe FIBO's own terms for the ontology files. Public figures (Archegos, BCBS 239) are drawn from regulatory and industry sources; see [`docs/fibo-notes.md`](docs/fibo-notes.md) for references.
