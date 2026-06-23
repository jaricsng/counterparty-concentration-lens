"""Counterparty Concentration Lens — Module 3 (dynamic security).

Role-based authorization as code: a Rego policy (evaluated by OPA) decides which
counterparty groups a user may see, and the read layer scopes every exposure
query to that visible set. Policy lives outside the application code.

Learning prototype on SYNTHETIC data. Production-shaped, not production-hardened.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
