# Open-source stack mapping

How the layers of a commercial ontology-driven operational platform map to the open-source components this prototype uses. This is educational context — it shows the *pattern* is reproducible with open tools, and where the genuinely hard part lies.

| Platform layer | Function | Open-source equivalent (used here) | Swap difficulty |
|---|---|---|---|
| App / Presentation | Operational apps, dashboards | Streamlit (or React/Next.js) | 🟢 Easy |
| AI layer | LLM connectors, grounded agents | Ollama + LangChain; pgvector/Qdrant if RAG | 🟡 Moderate |
| **Ontology** | Semantic model + store + actions + security | **FIBO/OWL + Fuseki + SHACL + OPA** (assembled) | 🔴 Hard — no 1:1 |
| Compute / data plane | Batch/stream transforms | DuckDB + dbt (Spark/Flink at scale) | 🔵 1:1 (same engines) |
| Delivery | Continuous delivery | Argo CD / Flux | 🟢 Easy |
| Substrate | Hardened, autoscaling K8s | Kubernetes / k3d (+ Cilium, OPA, Falco for hardening) | 🟢 Easy (DIY ops) |

## The honest takeaway

Most layers have clean open-source equivalents, and the compute layer is literally the same engines commercial platforms use. The **ontology layer is the irreducible hard part** — not because any single component is missing (FIBO, Fuseki, SHACL, OPA all exist), but because **integrating** semantic model + store + actions + security + a usable operational view into one governed layer is real engineering. That integration is what a commercial platform sells, and what this prototype assembles by hand to demonstrate the pattern.

Using **FIBO** specifically upgrades the semantic-model dimension: instead of inventing a counterparty/loan model, you adopt the financial industry's standards-based one (OWL 2 DL, with SHACL shapes), which is more portable and more credible than a bespoke schema — while the store/actions/security/app scaffolding around it is the same effort either way.
