"""Counterparty Concentration Lens — Module 4 (grounded AI query).

Natural-language questions -> SPARQL over the FIBO model -> execute -> summarise.
Generated SPARQL is ALWAYS safety-validated (read-only, known schema) before it
may run, and results are scoped by the M3 role filter. A deterministic template
generator works offline; a local Ollama model is used when available.

Learning prototype on SYNTHETIC data. Production-shaped, not production-hardened.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
