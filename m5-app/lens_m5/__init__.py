"""Counterparty Concentration Lens — Module 5 (the demo app).

An interactive Streamlit tool: a concentration dashboard (direct vs connected),
composable filters and drill-down, an embedded grounded NL query box (M4), and a
guarded "Scenario Sandbox" whose writes go ONLY through the M2 action layer and
recompute the metrics live. Reads are role-scoped by the M3 policy.

Learning prototype on SYNTHETIC data. Production-shaped, not production-hardened.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
