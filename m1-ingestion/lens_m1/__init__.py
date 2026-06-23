"""Counterparty Concentration Lens — Module 1 (synthetic data + ingestion).

Generates two labelled synthetic datasets (``calm`` and ``stressed``) as
source-style CSV tables, loads them into Fuseki as FIBO instances, and provides
a reference (oracle) computation of the connected-exposure concentration metrics.

Learning prototype on SYNTHETIC data. Production-shaped, not production-hardened.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
