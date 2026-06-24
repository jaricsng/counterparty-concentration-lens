# FIBO notes — modules used, and why

This prototype builds its semantic model on **FIBO (Financial Industry Business Ontology)**, the open-source financial ontology developed by the **EDM Council** and standardized by the **Object Management Group (OMG)**. FIBO is expressed in **OWL 2 DL** and ships with **SHACL** shapes for validation, which makes it a natural fit for the ontology layer of this stack.

This note explains which FIBO modules the prototype uses and how they map to the counterparty-exposure problem. It is descriptive and educational — not a specification.

## FIBO structure (brief)

FIBO is organised into **domains**, each containing modules and dozens of OWL ontologies. Ontologies carry a maturity level (Release / Provisional / Informative). For a learning prototype, prefer **Release**-level ontologies where available, and treat anything provisional as illustrative.

## Modules used in this prototype

| Concept needed | FIBO domain / module | Why |
|---|---|---|
| Legal entities; ownership & control relationships | **Business Entities (BE)** | Models the parties and the control/ownership links that create *indirect* exposure (group structures). |
| Loan contracts across categories | **Loan (LOAN)** | Commercial, small-business, auto, education, mortgage loan contracts; obligations of parties in different roles; credit, risk, and security agreements. |
| Debt instruments; interest & debt common terms | **Debt & Equities** module, within **Financial Business & Commerce (FBC)** | Debt-instrument detail lives here, separate from the LOAN domain. |
| Contracts, agreements, parties, and **roles** | **Foundations (FND)** (with OMG Commons) | The machinery that lets one entity play many roles. |
| Guarantees & collateral | **Guaranty** package (under FBC) | Guarantee and letter-of-credit structures that link one party's risk to another's. |
| Securities pledged as collateral; their **issuer** | **Securities (SEC)** + the FIBO issuance relation (`fibo-fnd-rel-rel:isIssuedBy`) | Lets collateral that is a security carry a proper issuer — the basis for **structural wrong-way-risk** detection (collateral issued by the same group as the borrower). Added in the concentration enhancement. |

## The key modelling idea: counterparty is a *role*

There is no standalone "counterparty class" in FIBO, and that's a feature, not a gap. FIBO (via OMG Commons / FND) separates a **party** (a legal entity) from the **roles** it plays. One entity can simultaneously be a **borrower** on one contract, a **counterparty** on a trade, a **guarantor** on a third, and a **beneficial owner** behind a fourth.

This is exactly what enables the prototype's core demonstration — surfacing multi-hop concentration. Because roles are modelled explicitly and entities are shared, a query (or a reasoner) can connect exposures that live in different source systems and would be invisible in a flat, per-system table.

## Complementary standards worth knowing

- **LEI (Legal Entity Identifier)** — a global identifier for counterparty identity resolution; useful for the "is this the same entity across systems?" problem.
- **ISO 20022** — message/transaction semantics; relevant where payments or trade data feed the model.
- **FIB-DM** — the EDM Council's transformation of FIBO into a relational data model, useful where a relational projection of the ontology is wanted.

## How to obtain FIBO

FIBO is open source and published by the EDM Council. The ontology files (RDF/OWL) and the online viewer are linked from the references below. Observe FIBO's own licence terms for the ontology files; **FIBO is a trademark of EDM Council, Inc.**

## References

FIBO / standards:
- EDM Council — FIBO: https://edmcouncil.org/frameworks/industry-models/fibo/
- FIBO specification & viewer: https://spec.edmcouncil.org/fibo/
- FIBO on GitHub (ontology source): https://github.com/edmcouncil/fibo
- OMG (Object Management Group) — standardization body: https://www.omg.org/
- FIB-DM (relational transformation of FIBO): https://fib-dm.com/

Public facts cited in the README (why the pattern matters):
- Basel Committee on Banking Supervision, *Progress in adopting the Principles for effective risk data aggregation and risk reporting*, Nov 2023 (the "2 of 31" figure; data as of June 2022): https://www.bis.org/bcbs/publ/d559.pdf
- Bank of England / PRA, *Record £87m fine on Credit Suisse over Archegos*, July 2023: https://www.bankofengland.co.uk/news/2023/july/the-pra-imposes-record-fine-of-87m-on-credit-suisse
- Credit Suisse Special Committee (Paul Weiss) *Report on Archegos Capital Management*, July 2021 (via SEC): https://www.sec.gov/Archives/edgar/data/1053092/000137036821000064/a210729-ex992.htm

*These public sources are included to explain why the modelling pattern matters. Nothing in this repository is advice to, or about, any specific institution.*
