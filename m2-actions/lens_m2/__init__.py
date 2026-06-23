"""Counterparty Concentration Lens — Module 2 (validation & guarded actions).

SHACL-validated, audit-logged write actions over the synthetic graph: the only
sanctioned path for mutating the dataset (the M5 sandbox writes ONLY through
here, never directly to Fuseki). Validate -> SPARQL Update -> audit.

Learning prototype on SYNTHETIC data. Production-shaped, not production-hardened.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
